import { defineConfig } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = fileURLToPath(new URL('.', import.meta.url))
const backendRoot = resolve(frontendRoot, '..', 'backend')
const bootstrapToken = 'e2e-bootstrap-token-only'
const databaseUrl = `sqlite:///./proploop-e2e-${randomUUID()}.db`
const python = process.env.PROPLOOP_PYTHON || (process.platform === 'win32'
  ? resolve(frontendRoot, '..', '.venv', 'Scripts', 'python.exe')
  : 'python3')

process.env.PROPLOOP_E2E_BOOTSTRAP_TOKEN = bootstrapToken

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.js',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  outputDir: './test-results/e2e',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command: `"${python}" -m alembic upgrade head && "${python}" -m uvicorn app.main:app --host 127.0.0.1 --port 8000`,
      cwd: backendRoot,
      url: 'http://127.0.0.1:8000/api/health',
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        ...process.env,
        DATABASE_URL: databaseUrl,
        BOOTSTRAP_TOKEN: bootstrapToken,
        FRONTEND_URL: 'http://127.0.0.1:5173',
        COOKIE_SECURE: 'false',
        AI_PROVIDER: 'mock',
        OPENAI_API_KEY: '',
        GITHUB_TOKEN: '',
        GITHUB_REPOSITORY: '',
      },
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173',
      cwd: frontendRoot,
      url: 'http://127.0.0.1:5173',
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
})
