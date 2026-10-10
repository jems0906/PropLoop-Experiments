import { useEffect, useId, useState } from 'react'
import { api } from '../api/client'
import './gaps.css'

const roles = ['admin', 'reviewer', 'member']

export default function TeamSettings({ user }) {
  return <TeamSettingsContent key={`${user?.id}-${user?.role}`} user={user} />
}

function TeamSettingsContent({ user }) {
  const id = useId()
  const isAdmin = user?.role === 'admin'
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(isAdmin)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('member')
  const [invitation, setInvitation] = useState(null)

  useEffect(() => {
    if (!isAdmin) return undefined
    let active = true
    api.users().then((result) => {
      if (active) setUsers(Array.isArray(result) ? result : result.users || [])
    }).catch((err) => {
      if (active) setError(err.message || 'Could not load team members.')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [isAdmin])

  const createInvite = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    setNotice('')
    setInvitation(null)
    try {
      const result = await api.createInvite({ email: email.trim(), role })
      if (!result?.token) throw new Error('The server did not return a new invitation token.')
      setInvitation(result)
      setEmail('')
    } catch (err) {
      setError(err.message || 'Could not create invitation.')
    } finally { setBusy(false) }
  }

  const updateUser = async (member, patch) => {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await api.updateUser(member.id, { role: member.role, active: member.active, ...patch })
      const result = await api.users()
      setUsers(Array.isArray(result) ? result : result.users || [])
      setNotice('Team member updated.')
    } catch (err) {
      setError(err.message || 'Could not update team member.')
    } finally { setBusy(false) }
  }

  const copyToken = async () => {
    setError('')
    setNotice('')
    try {
      await navigator.clipboard.writeText(invitation.token)
      setNotice('Invitation token copied. Share it only with the invited person.')
    } catch {
      setError('Clipboard access is unavailable. Select and copy the token manually.')
    }
  }

  return <section className="gap-scope gap-panel" aria-labelledby={`${id}-heading`} aria-busy={loading || busy}>
    <div className="gap-kicker">WORKSPACE ACCESS</div>
    <h2 id={`${id}-heading`}>Team settings</h2>
    <p className="gap-muted">One team. Access is granted by invitation.</p>
    <dl className="gap-facts"><div><dt>Name</dt><dd>{user?.name || 'Not provided'}</dd></div><div><dt>Email</dt><dd>{user?.email || 'Not provided'}</dd></div><div><dt>Role</dt><dd>{user?.role || 'Unknown'}</dd></div></dl>
    {!isAdmin && <p className="gap-muted">Contact an administrator to change your role or invite team members.</p>}
    {error && <p role="alert" className="gap-error">{error}</p>}
    {notice && <p role="status" className="gap-notice">{notice}</p>}
    {isAdmin && <>
      <h3>Invite a team member</h3>
      <form className="gap-form" onSubmit={createInvite}>
        <fieldset disabled={busy}>
          <div className="gap-form-grid">
            <label htmlFor={`${id}-email`}>Email<input id={`${id}-email`} type="email" required autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
            <label htmlFor={`${id}-role`}>Role<select id={`${id}-role`} value={role} onChange={(event) => setRole(event.target.value)}>{roles.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
          </div>
          <button type="submit" className="primary-button">{busy ? 'Working…' : 'Create invitation'}</button>
        </fieldset>
      </form>
      {invitation && <div className="gap-token-box">
        <strong>New invitation token</strong>
        <p className="gap-muted">Only this freshly created token is shown. Treat it as a secret; it is not saved in browser storage.</p>
        <label htmlFor={`${id}-token`}>Token<input id={`${id}-token`} readOnly value={invitation.token} onFocus={(event) => event.target.select()} /></label>
        <p className="gap-muted">Expires: {invitation.expires_at ? new Date(invitation.expires_at).toLocaleString() : 'Not supplied by server'}</p>
        <div className="gap-actions"><button type="button" className="secondary-button" onClick={copyToken}>Copy token</button><button type="button" className="quiet-button" onClick={() => setInvitation(null)}>Hide token</button></div>
      </div>}
      <h3>Team members</h3>
      {loading ? <p role="status">Loading team members…</p> : !users.length ? <p className="gap-muted">No team members returned.</p> : <ul className="gap-members">
        {users.map((member) => <li key={member.id}>
          <div><strong>{member.name || member.email}</strong><p className="gap-muted">{member.email}</p><span className="gap-tag">{member.active ? 'Active' : 'Inactive'}</span></div>
          <div className="gap-actions">
            <label>Role for {member.name || member.email}<select aria-label={`Role for ${member.email}`} value={member.role} disabled={busy} onChange={(event) => updateUser(member, { role: event.target.value })}>{roles.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
            <button className="secondary-button" type="button" disabled={busy} onClick={() => updateUser(member, { active: !member.active })}>{member.active ? 'Deactivate' : 'Activate'}</button>
          </div>
        </li>)}
      </ul>}
    </>}
  </section>
}
