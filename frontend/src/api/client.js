const API_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`)
  return payload
}

const send = (method, body) => ({ method, body: JSON.stringify(body) })

export const api = {
  overview: () => request('/dashboards/overview'),
  templates: () => request('/templates'),
  experiment: (id) => request(`/experiments/${id}`),
  createExperiment: (body) => request('/experiments', send('POST', body)),
  generateSpec: (id) => request(`/experiments/${id}/spec/generate`, send('POST', {})),
  saveSpec: (id, spec) => request(`/experiments/${id}/spec`, send('PUT', { spec })),
  approveSpec: (id) => request(`/experiments/${id}/spec/approve`, send('POST', {})),
  approvePlan: (id) => request(`/experiments/${id}/plan/approve`, send('POST', {})),
  updateTask: (id, status) => request(`/tasks/${id}`, send('PATCH', { status })),
  addMetric: (id, body) => request(`/experiments/${id}/metrics`, send('POST', body)),
  assignVariant: (id, subjectKey) => request(`/experiments/${id}/assignments`, send('POST', { subject_key: subjectKey })),
  decide: (id, body) => request(`/experiments/${id}/decisions`, send('POST', body)),
  blocker: (id, blocker) => request(`/experiments/${id}/blocker`, send('PATCH', { blocker })),
  quality: (id) => request(`/experiments/${id}/quality`),
  qualityTrends: () => request('/quality/trends'),
  generateQuality: (id, kind, evidence = {}) => request(`/experiments/${id}/quality/${kind}`, send('POST', evidence)),
}
