#!/bin/bash
# Reuse the existing EC2/systemd/SQLite deployment. No infrastructure changes.
set -euo pipefail
bucket="$1"
release="$2"
[[ "$release" =~ ^[a-f0-9]{40}$ ]]
stage="/opt/j-erp/releases/$release"
test ! -e "$stage"
install -d -m 700 "$stage"
aws s3 cp "s3://$bucket/artifacts/$release.tar.gz" "$stage/release.tar.gz" --only-show-errors
tar -xzf "$stage/release.tar.gz" -C "$stage"
test -f "$stage/backend/app/main.py"
test -f "$stage/frontend/dist/index.html"
/opt/j-erp/venv/bin/pip install --quiet -r "$stage/backend/requirements.lock.txt"
systemctl start jerp-backup.service
cp -a /opt/j-erp/backend "$stage/previous-backend"
cp -a /opt/j-erp/frontend/dist "$stage/previous-dist"
stopped=0
recover() {
  code=$?
  if [ "$code" -ne 0 ] && [ "$stopped" = 1 ]; then
    if [ -d "$stage/old-backend" ]; then
      if [ -d /opt/j-erp/backend ]; then mv /opt/j-erp/backend "$stage/failed-backend"; fi
      mv "$stage/old-backend" /opt/j-erp/backend
    fi
    if [ -d "$stage/old-dist" ]; then
      if [ -d /opt/j-erp/frontend/dist ]; then mv /opt/j-erp/frontend/dist "$stage/failed-dist"; fi
      mv "$stage/old-dist" /opt/j-erp/frontend/dist
    fi
    systemctl start jerp
  fi
  exit "$code"
}
trap recover EXIT
systemctl stop jerp
stopped=1
# Snapshot with writes paused, then perform only additive table creation.
PYTHONPATH="$stage/backend" /opt/j-erp/venv/bin/python - "$stage" <<'PY'
import json, pathlib, sqlite3, sys
from dotenv import load_dotenv
load_dotenv('/opt/j-erp/backend/.env', override=True)
from app.core.database import Base, engine
from app.main import app
from sqlalchemy import inspect, text
stage = pathlib.Path(sys.argv[1])
with sqlite3.connect('file:/var/lib/j-erp/erp.db?mode=ro', uri=True) as src, sqlite3.connect(stage/'before-migration.db') as dst:
    src.backup(dst)
    assert dst.execute('pragma integrity_check').fetchone()[0] == 'ok'
with engine.connect() as connection:
    tables = inspect(engine).get_table_names()
    before = {t: connection.execute(text('select count(*) from "' + t.replace('"', '""') + '"')).scalar() for t in tables}
Base.metadata.create_all(engine)
with engine.connect() as connection:
    after = {t: connection.execute(text('select count(*) from "' + t.replace('"', '""') + '"')).scalar() for t in tables}
    assert before == after, 'Existing table counts changed'
    assert connection.execute(text('pragma integrity_check')).scalar() == 'ok'
    assert not connection.execute(text('pragma foreign_key_check')).fetchall()
added = sorted(set(inspect(engine).get_table_names()) - set(tables))
(stage/'migration-report.json').write_text(json.dumps({'existing_counts_preserved': True, 'added_tables': added}))
print(json.dumps({'existing_counts_preserved': True, 'added_tables': added}))
engine.dispose()
PY
cp -p /opt/j-erp/backend/.env "$stage/backend/.env"
chown -R jerp:jerp "$stage/backend"
chmod 600 "$stage/backend/.env"
# Keep previous code intact so a failed health check can restore it.
mv /opt/j-erp/backend "$stage/old-backend"
mv /opt/j-erp/frontend/dist "$stage/old-dist"
mv "$stage/backend" /opt/j-erp/backend
mv "$stage/frontend/dist" /opt/j-erp/frontend/dist
systemctl start jerp
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/api/health >/dev/null; then
    printf '%s\n' "$release" > /opt/j-erp/deployed-commit
    echo 'Deployment health check passed'
    exit 0
  fi
  sleep 2
done
exit 1
