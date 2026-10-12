import { useEffect, useState } from 'react'
import { AlertCircle, ExternalLink, GitPullRequest, LoaderCircle, ShieldCheck, Sparkles } from 'lucide-react'
import { api } from '../api/client'
import './CodingAgentPanel.css'

export default function CodingAgentPanel({ experiment, busy, run }) {
  const [status, setStatus] = useState(null)
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [historyError, setHistoryError] = useState('')

  useEffect(() => {
    let active = true
    Promise.all([api.codingAgentStatus(), api.agentRuns(experiment.id)]).then(([configuration, history]) => {
      if (active) {
        setStatus(configuration)
        setRuns(history)
      }
    }).catch(() => {
      if (active) setStatus({ enabled: false, missing: ['Agent status could not be loaded'] })
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [experiment.id])

  const planReady = experiment.stage === 'build'
    && experiment.spec_approved
    && experiment.plan_approved
    && experiment.tasks?.length > 0
    && !experiment.blocker

  const createRun = async () => {
    const created = await run(() => api.createAgentRun(experiment.id), 'Draft pull request created. Review the code and CI before merging.')
    try {
      setRuns(await api.agentRuns(experiment.id))
      setHistoryError('')
    } catch (error) {
      setHistoryError(error.message || 'Could not refresh agent run history.')
    }
    if (created) setRuns((current) => [created, ...current.filter((item) => item.id !== created.id)])
  }

  return <section className="panel coding-agent-panel">
    <div className="section-head panel-head">
      <div><div className="section-kicker">IMPLEMENTATION PROPOSAL</div><h2><GitPullRequest size={17} /> GitHub coding agent</h2></div>
      <span className={`agent-state ${status?.enabled ? 'ready' : ''}`}>{loading ? 'Checking' : status?.enabled ? 'Ready' : 'Not configured'}</span>
    </div>
    <p className="agent-description">Create a branch and draft pull request from the approved plan. The agent cannot merge changes or run your test suite.</p>
    {status?.enabled && <div className="agent-repository"><span>Repository</span><strong>{status.repository}</strong><span>Model</span><strong>{status.model}</strong></div>}
    {!loading && status && !status.enabled && <div className="agent-missing"><AlertCircle size={15} /><span>Configure these backend variables to enable proposals: {status.missing.join(', ')}.</span></div>}
    {historyError && <p className="agent-history-error" role="alert">{historyError}</p>}
    <div className="agent-disclosure"><ShieldCheck size={15} /><span>Approved plan and a small allowlisted set of source files will be sent to OpenAI. Review every change and require CI before merging.</span></div>
    <div className="agent-action-row">
      <span>{planReady ? 'Approved build plan is ready.' : 'Requires an approved spec and plan, build stage, tasks, and no active blocker.'}</span>
      <button className="primary-button" disabled={busy || loading || !status?.enabled || !planReady} onClick={createRun}>
        {busy ? <LoaderCircle size={15} className="agent-spinner" /> : <Sparkles size={15} />} Create draft PR
      </button>
    </div>
    {runs.length > 0 && <div className="agent-history">
      <h3>Recent agent runs</h3>
      {runs.map((item) => <div className="agent-run" key={item.id}>
        <span className={`agent-run-status ${item.status}`}>{item.status === 'pull_request' ? 'Draft PR' : item.status}</span>
        <span className="agent-run-summary">{item.summary || item.error || item.branch || item.repository}</span>
        {item.pull_request_url && <a href={item.pull_request_url} target="_blank" rel="noreferrer">Open PR <ExternalLink size={12} /></a>}
        <time>{new Date(item.created_at).toLocaleString()}</time>
      </div>)}
    </div>}
  </section>
}
