#!/bin/bash
set -euo pipefail
bucket="$1"
site_url="$2"
release_key="$3"
for attempt in $(seq 1 60); do
  test -f /var/lib/jerp-bootstrap-ready && break
  sleep 5
done
test -f /var/lib/jerp-bootstrap-ready
id jerp >/dev/null 2>&1 || useradd --system --home-dir /opt/j-erp --shell /sbin/nologin jerp
install -d -m 755 /opt/j-erp /var/lib/j-erp /var/lib/j-erp/uploads
aws s3 cp "s3://$bucket/$release_key" /opt/j-erp/release.tar.gz --only-show-errors
tar -xzf /opt/j-erp/release.tar.gz -C /opt/j-erp
if [ ! -f /var/lib/j-erp/erp.db ]; then
  aws s3 cp "s3://$bucket/artifacts/initial-data.tar.gz" /var/lib/j-erp/initial-data.tar.gz --only-show-errors
  tar -xzf /var/lib/j-erp/initial-data.tar.gz -C /var/lib/j-erp
fi
python3.12 -m venv /opt/j-erp/venv
/opt/j-erp/venv/bin/pip install --quiet -r /opt/j-erp/backend/requirements.lock.txt
cat > /opt/j-erp/backend/.env <<EOF
APP_ENV=production
SESSION_COOKIE_SECURE=true
DATABASE_URL=sqlite:////var/lib/j-erp/erp.db
UPLOAD_DIR=/var/lib/j-erp/uploads
PUBLIC_ORIGIN=$site_url
CORS_ORIGINS=$site_url
EOF
chown -R jerp:jerp /var/lib/j-erp /opt/j-erp/backend
chmod 700 /var/lib/j-erp
chmod 600 /opt/j-erp/backend/.env
cat > /etc/systemd/system/jerp.service <<'EOF'
[Unit]
Description=J-ERP API
After=network-online.target
Wants=network-online.target
[Service]
User=jerp
Group=jerp
WorkingDirectory=/opt/j-erp/backend
ExecStart=/opt/j-erp/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=on-failure
RestartSec=3
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/j-erp
[Install]
WantedBy=multi-user.target
EOF
site_host="${site_url#https://}"
cat > /etc/nginx/nginx.conf <<EOF
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log;
pid /run/nginx.pid;
include /usr/share/nginx/modules/*.conf;
events { worker_connections 1024; }
http {
  include /etc/nginx/mime.types;
  default_type application/octet-stream;
  server_tokens off;
  sendfile on;
  server { listen 80 default_server; server_name _; return 444; }
  server {
    listen 80;
    server_name $site_host;
    root /opt/j-erp/frontend/dist;
    client_max_body_size 11m;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy same-origin always;
    location /api/ {
      proxy_pass http://127.0.0.1:8000;
      proxy_set_header Host \$host;
      proxy_set_header X-Forwarded-Proto https;
      proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
    location / { try_files \$uri \$uri/ /index.html; }
  }
}
EOF
nginx -t
systemctl daemon-reload
systemctl enable jerp nginx
systemctl restart jerp nginx
cat > /usr/local/sbin/jerp-backup <<EOF
#!/bin/bash
set -euo pipefail
work=\$(mktemp -d /var/lib/j-erp/backup.XXXXXX)
trap 'rm -rf -- "\$work"' EXIT
python3.12 - "\$work/erp.db" <<'PY'
import sqlite3, sys
with sqlite3.connect('file:/var/lib/j-erp/erp.db?mode=ro', uri=True) as src, sqlite3.connect(sys.argv[1]) as dst:
    src.backup(dst)
    assert dst.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
PY
tar -czf "\$work/data.tar.gz" -C "\$work" erp.db -C /var/lib/j-erp uploads
aws s3 cp "\$work/data.tar.gz" "s3://$bucket/backups/data.tar.gz" --only-show-errors
EOF
chmod 700 /usr/local/sbin/jerp-backup
cat > /etc/systemd/system/jerp-backup.service <<'EOF'
[Unit]
Description=J-ERP database and upload backup
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/jerp-backup
UMask=0077
EOF
cat > /etc/systemd/system/jerp-backup.timer <<'EOF'
[Unit]
Description=Daily J-ERP backup
[Timer]
OnCalendar=*-*-* 18:00:00 UTC
Persistent=true
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now jerp-backup.timer
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/openapi.json >/dev/null; then
    echo 'J-ERP API ready'
    exit 0
  fi
  sleep 2
done
exit 1
