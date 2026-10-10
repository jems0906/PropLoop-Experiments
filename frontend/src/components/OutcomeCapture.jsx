import { useId, useState } from 'react'
import { api } from '../api/client'
import './gaps.css'

const numeric = (value) => typeof value === 'number' && Number.isFinite(value)
const display = (value) => numeric(value) ? value.toLocaleString(undefined, { maximumFractionDigits: 4 }) : 'Insufficient data'

export default function OutcomeCapture({ experiment, busy, run }) {
  return experiment ? <OutcomeContent key={experiment.id} experiment={experiment} busy={busy} run={run} /> : null
}

function OutcomeContent({ experiment, busy, run }) {
  const id = useId()
  const [subjectKey, setSubjectKey] = useState('')
  const [exposed, setExposed] = useState(false)
  const [completed, setCompleted] = useState(false)
  const [errored, setErrored] = useState(false)
  const [csat, setCsat] = useState('')
  const [duration, setDuration] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const metrics = experiment.computed_metrics || []
  const observations = experiment.observations || []
  const counts = {
    recorded: observations.length,
    exposed: observations.filter((item) => item.exposed === true).length,
    completed: observations.filter((item) => item.completed === true).length,
    errored: observations.filter((item) => item.errored === true).length,
  }

  const save = async (event) => {
    event.preventDefault()
    if (busy || saving || experiment.stage !== 'measure') return
    if (!subjectKey.trim()) { setError('An opaque assigned participant key is required.'); return }
    const body = { exposed, completed, errored, csat: csat === '' ? null : Number(csat), duration_minutes: duration === '' ? null : Number(duration) }
    if ((body.csat !== null && (!Number.isInteger(body.csat) || body.csat < 1 || body.csat > 5)) || (body.duration_minutes !== null && (!numeric(body.duration_minutes) || body.duration_minutes < 0))) {
      setError('Use a CSAT score from 1–5 and a non-negative duration in minutes.')
      return
    }
    setSaving(true)
    setError('')
    setNotice('')
    let saved = false
    const operation = async () => {
      try {
        const result = await api.observe(experiment.id, subjectKey.trim(), body)
        saved = true
        return result
      } catch (err) {
        setError(err.message || 'Could not save this outcome.')
        throw err
      }
    }
    try {
      if (run) await run(operation, 'Participant outcome saved')
      else await operation()
      if (saved) setNotice('Outcome saved. Saving the same assigned key updates its observation.')
    } catch (err) { setError(err.message || 'Could not save this outcome.') }
    finally { setSaving(false) }
  }

  return <section className="gap-scope gap-panel" aria-labelledby={`${id}-heading`} aria-busy={busy || saving}>
    <div className="gap-kicker">MEASUREMENT EVIDENCE</div>
    <h2 id={`${id}-heading`}>Participant outcomes</h2>
    <p className="gap-muted">Record observed outcomes, not enrollment. Use only opaque keys already assigned to a test arm; never enter names or emails.</p>
    <dl className="gap-facts">{Object.entries(counts).map(([label, count]) => <div key={label}><dt>{label}</dt><dd>{count}</dd></div>)}</dl>
    <p className="gap-muted">Counts summarize recorded observations only. Metric sample sizes are supplied by the server for each outcome, not inferred from assignments.</p>
    <div className="gap-metrics">
      {!metrics.length && <p className="gap-muted">No computed metrics available. Record outcomes to collect evidence.</p>}
      {metrics.map((metric, index) => {
        const stats = metric.comparison || metric
        const test = stats.confidence || stats
        const controlN = stats.control_sample_size ?? stats.control_n ?? stats.n?.control
        const treatmentN = stats.treatment_sample_size ?? stats.treatment_n ?? stats.n?.treatment
        const timeMetric = /time|duration/i.test(metric.name || '') && /min/i.test(metric.unit || '')
        const timeSaved = numeric(stats.baseline) && numeric(stats.observed) ? stats.baseline - stats.observed : null
        return <article className="gap-metric" key={metric.id || `${metric.name}-${index}`}>
          <h3>{metric.name || 'Unnamed metric'}</h3>
          <dl className="gap-facts">
            <div><dt>Control baseline</dt><dd>{display(stats.baseline)}</dd></div>
            <div><dt>Treatment observed</dt><dd>{display(stats.observed)}</dd></div>
            <div><dt>Unit</dt><dd>{metric.unit || stats.unit || 'Not supplied'}</dd></div>
            <div><dt>Control outcome n</dt><dd>{numeric(controlN) ? controlN : 'Not supplied'}</dd></div>
            <div><dt>Treatment outcome n</dt><dd>{numeric(treatmentN) ? treatmentN : 'Not supplied'}</dd></div>
            <div><dt>p-value</dt><dd>{display(stats.p_value ?? test.p_value)}</dd></div>
            <div><dt>Method</dt><dd>{stats.method || test.method || metric.method || 'Not supplied'}</dd></div>
          </dl>
          {timeMetric && <p className="gap-muted">Absolute time saved (control − treatment): {numeric(timeSaved) ? `${display(timeSaved)} minutes` : 'Insufficient data'}. Negative values mean treatment took longer.</p>}
          {/csat|satisfaction/i.test(metric.name || '') && <p className="gap-muted">CSAT is simulated/test-user feedback, not a production satisfaction claim.</p>}
        </article>
      })}
    </div>
    {experiment.stage === 'measure' ? <form className="gap-form" onSubmit={save}>
      <h3>Record or update an outcome</h3>
      {error && <p className="gap-error" role="alert">{error}</p>}
      {notice && <p className="gap-notice" role="status">{notice}</p>}
      <fieldset disabled={busy || saving}>
        <label htmlFor={`${id}-key`}>Opaque assigned participant key<input id={`${id}-key`} required autoComplete="off" value={subjectKey} onChange={(event) => { setSubjectKey(event.target.value); setNotice('') }} /></label>
        <div className="gap-checks">
          <label><input type="checkbox" checked={exposed} onChange={(event) => setExposed(event.target.checked)} /> Exposed to assigned experience</label>
          <label><input type="checkbox" checked={completed} onChange={(event) => setCompleted(event.target.checked)} /> Completed outcome</label>
          <label><input type="checkbox" checked={errored} onChange={(event) => setErrored(event.target.checked)} /> Encountered an error</label>
        </div>
        <div className="gap-form-grid">
          <label htmlFor={`${id}-csat`}>CSAT · simulated/test-user (optional, 1–5)<input id={`${id}-csat`} type="number" min="1" max="5" step="1" value={csat} onChange={(event) => setCsat(event.target.value)} /></label>
          <label htmlFor={`${id}-duration`}>Duration in minutes (optional)<input id={`${id}-duration`} type="number" min="0" step="any" value={duration} onChange={(event) => setDuration(event.target.value)} /></label>
        </div>
        <button type="submit" className="primary-button">{saving || busy ? 'Saving…' : 'Save outcome'}</button>
      </fieldset>
    </form> : <p className="gap-muted">Outcome capture is available only during the Measure stage. Existing evidence remains visible.</p>}
  </section>
}
