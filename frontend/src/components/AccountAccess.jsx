import { useEffect, useId, useState } from 'react'
import { api } from '../api/client'
import './gaps.css'

export default function AccountAccess({ onAuthenticated }) {
  const id = useId()
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [mode, setMode] = useState('login')
  const [fields, setFields] = useState({ email: '', name: '', password: '', token: '' })

  useEffect(() => {
    let active = true
    api.authStatus().then((result) => {
      if (active) {
        setStatus(result)
        setMode(result.setup_required ? 'bootstrap' : 'login')
      }
    }).catch((err) => {
      if (active) setError(err.message || 'Could not check account access.')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const changeMode = (next) => {
    setMode(next)
    setFields({ email: '', name: '', password: '', token: '' })
    setError('')
  }
  const update = (field) => (event) => setFields((current) => ({ ...current, [field]: event.target.value }))
  const submit = async (event) => {
    event.preventDefault()
    if (busy || !status) return
    setBusy(true)
    setError('')
    try {
      const account = { email: fields.email.trim(), name: fields.name.trim(), password: fields.password }
      const result = mode === 'bootstrap'
        ? await api.bootstrap(account, fields.token)
        : mode === 'invite'
          ? await api.acceptInvite({ ...account, token: fields.token })
          : await api.login({ email: account.email, password: account.password })
      if (!result?.user) throw new Error('The server did not return an authenticated account.')
      setFields({ email: '', name: '', password: '', token: '' })
      onAuthenticated(result)
    } catch (err) {
      setError(err.message || 'Account access failed.')
    } finally {
      setBusy(false)
    }
  }

  return <section className="gap-access gap-scope" aria-labelledby={`${id}-heading`} aria-busy={loading || busy}>
    <div className="gap-panel">
      <div className="gap-kicker">PROPLOOP · INVITE-ONLY TEAM</div>
      <h1 id={`${id}-heading`}>{mode === 'bootstrap' ? 'Set up your team' : mode === 'invite' ? 'Accept your invitation' : 'Welcome back'}</h1>
      <p className="gap-muted">Secure account access for your team’s experiment workspace.</p>
      {loading && <p role="status">Checking account access…</p>}
      {error && <p className="gap-error" role="alert">{error}</p>}
      {!loading && !status && <button className="secondary-button" type="button" onClick={() => window.location.reload()}>Retry access check</button>}
      {!loading && status && <>
        <div className="gap-actions" aria-label="Account access mode">
          <button type="button" className="secondary-button" aria-pressed={mode === 'login'} disabled={busy} onClick={() => changeMode('login')}>Sign in</button>
          <button type="button" className="secondary-button" aria-pressed={mode === 'invite'} disabled={busy} onClick={() => changeMode('invite')}>Accept invite</button>
          {status.setup_required && <button type="button" className="secondary-button" aria-pressed={mode === 'bootstrap'} disabled={busy} onClick={() => changeMode('bootstrap')}>Initial admin</button>}
        </div>
        {mode === 'bootstrap' && <p className="gap-muted">Create the initial administrator using the protected setup token supplied by your operator.</p>}
        <form className="gap-form" onSubmit={submit}>
          <fieldset disabled={busy}>
            <label htmlFor={`${id}-email`}>Email<input id={`${id}-email`} type="email" autoComplete="username" required value={fields.email} onChange={update('email')} /></label>
            {mode !== 'login' && <label htmlFor={`${id}-name`}>Name<input id={`${id}-name`} autoComplete="name" required value={fields.name} onChange={update('name')} /></label>}
            <label htmlFor={`${id}-password`}>Password<input id={`${id}-password`} type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required value={fields.password} onChange={update('password')} /></label>
            {mode !== 'login' && <label htmlFor={`${id}-token`}>{mode === 'bootstrap' ? 'Protected setup token' : 'Invitation token'}<input id={`${id}-token`} type="password" autoComplete="off" required value={fields.token} onChange={update('token')} /></label>}
            <button className="primary-button" type="submit">{busy ? 'Connecting…' : mode === 'bootstrap' ? 'Create administrator' : mode === 'invite' ? 'Join team' : 'Sign in'}</button>
          </fieldset>
        </form>
      </>}
    </div>
  </section>
}
