import { defineConfig } from '@playwright/test'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { resolve, join } from 'node:path'

const testRoot = process.env.JERP_E2E_DIR || mkdtempSync(join(tmpdir(), 'jerp-e2e-'))
process.env.JERP_E2E_DIR = testRoot
const projectRoot = resolve(import.meta.dirname, '..')
const python = process.env.JERP_PYTHON || join(projectRoot, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  expect: { timeout: 10000 },
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:5174',
    viewport: { width: 1280, height: 900 },
    timezoneId: 'Asia/Seoul',
    locale: 'ko-KR',
    channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port 8001`,
      cwd: join(projectRoot, 'backend'),
      url: 'http://127.0.0.1:8001/api/health',
      reuseExistingServer: false,
      env: { DATABASE_URL: `sqlite:///${join(testRoot, 'erp.db').replaceAll('\\', '/')}`, UPLOAD_DIR: join(testRoot, 'uploads'), APP_ENV: 'development', SESSION_COOKIE_SECURE: 'false', CORS_ORIGINS: 'http://127.0.0.1:5174' },
    },
    {
      command: 'npm run dev -- --port 5174',
      url: 'http://127.0.0.1:5174',
      reuseExistingServer: false,
      env: { API_PROXY_TARGET: 'http://127.0.0.1:8001' },
    },
  ],
})
