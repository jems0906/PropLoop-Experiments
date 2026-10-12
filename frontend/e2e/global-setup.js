import { request } from '@playwright/test'

export default async function globalSetup() {
  const context = await request.newContext({ baseURL: 'http://127.0.0.1:8000' })
  try {
    const response = await context.post('/api/auth/bootstrap', {
      headers: {
        Origin: 'http://127.0.0.1:5173',
        'X-Bootstrap-Token': process.env.PROPLOOP_E2E_BOOTSTRAP_TOKEN,
      },
      data: {
        email: 'admin@proploop.test',
        name: 'E2E Admin',
        password: 'e2e-admin-password-2026',
      },
    })
    if (response.status() !== 201) {
      throw new Error(`E2E administrator setup failed with HTTP ${response.status()}.`)
    }
  } finally {
    await context.dispose()
  }
}
