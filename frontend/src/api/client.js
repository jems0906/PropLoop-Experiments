const API_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')
let csrfToken = ''

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}), ...options.headers },
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = typeof payload.detail === 'string' ? payload.detail : Array.isArray(payload.detail) ? payload.detail.map((item) => item.msg).join('; ') : `Request failed (${response.status})`
    const error = new Error(detail)
    error.status = response.status
    throw error
  }
  if (payload.csrf_token) csrfToken = payload.csrf_token
  return payload
}

const send = (method, body) => ({ method, body: JSON.stringify(body) })

export const api = {
  authStatus: () => request('/auth/status'),
  me: () => request('/auth/me'),
  login: (body) => request('/auth/login', send('POST', body)),
  logout: async () => { await request('/auth/logout', send('POST', {})); csrfToken = '' },
  bootstrap: (body, token) => request('/auth/bootstrap', { ...send('POST', body), headers: { 'X-Bootstrap-Token': token } }),
  acceptInvite: (body) => request('/auth/accept-invite', send('POST', body)),
  users: () => request('/auth/users'),
  invites: () => request('/auth/invites'),
  createInvite: (body) => request('/auth/invites', send('POST', body)),
  updateUser: (id, body) => request(`/auth/users/${id}`, send('PATCH', body)),
  overview: () => request('/dashboards/overview'),
  templates: () => request('/templates'),
  experiment: (id) => request(`/experiments/${id}`),
  createExperiment: (body) => request('/experiments', send('POST', body)),
  generateSpec: (id) => request(`/experiments/${id}/spec/generate`, send('POST', {})),
  saveSpec: (id, spec) => request(`/experiments/${id}/spec`, send('PUT', { spec })),
  approveSpec: (id) => request(`/experiments/${id}/spec/approve`, send('POST', {})),
  approvePlan: (id) => request(`/experiments/${id}/plan/approve`, send('POST', {})),
  approveStage: (id, stage) => request(`/experiments/${id}/${stage}/approve`, send('POST', {})),
  saveBrief: (id, body) => request(`/experiments/${id}/brief`, send('PUT', body)),
  observe: (id, subjectKey, body) => request(`/experiments/${id}/observations/${encodeURIComponent(subjectKey)}`, send('PUT', body)),
  updateTask: (id, status) => request(`/tasks/${id}`, send('PATCH', { status })),
  addMetric: (id, body) => request(`/experiments/${id}/metrics`, send('POST', body)),
  assignVariant: (id, subjectKey) => request(`/experiments/${id}/assignments`, send('POST', { subject_key: subjectKey })),
  decide: (id, body) => request(`/experiments/${id}/decisions`, send('POST', body)),
  blocker: (id, blocker) => request(`/experiments/${id}/blocker`, send('PATCH', { blocker })),
  quality: (id) => request(`/experiments/${id}/quality`),
  qualityTrends: () => request('/quality/trends'),
  generateQuality: (id, kind, evidence = {}) => request(`/experiments/${id}/quality/${kind}`, send('POST', evidence)),
}
