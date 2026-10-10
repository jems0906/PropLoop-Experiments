import { lazy, startTransition, Suspense, useEffect, useState } from 'react'
import {
  Activity, AlertCircle, ArrowDownRight, ArrowRight, ArrowUpRight, BarChart3,
  Check, CheckCircle2, ChevronDown, Circle, ClipboardCheck, Clock3,
  FileText, FlaskConical, GitPullRequest, LayoutDashboard, ListChecks, Plus,
  RefreshCw, ShieldCheck, Sparkles, TrendingUp, X,
} from 'lucide-react'
import { api } from './api/client'
import './App.css'
import AccountAccess from './components/AccountAccess'
import TeamSettings from './components/TeamSettings'
import OutcomeCapture from './components/OutcomeCapture'
import ExperimentBoard from './components/ExperimentBoard'
import './components/gaps.css'

const LearningTrend = lazy(() => import('./components/LearningTrend.jsx'))
const stageOrder = ['hypothesis', 'design', 'plan', 'build', 'measure', 'decision']
const stageLabel = { hypothesis: 'Hypothesis', design: 'Design brief', plan: 'Build plan', build: 'Build', measure: 'Measure', decision: 'Decision', complete: 'Shipped', stopped: 'Stopped' }
const qualityTools = [
  { id: 'pr-checklist', label: 'PR review checklist', icon: GitPullRequest, detail: 'Review the change before it ships' },
  { id: 'adr', label: 'ADR template', icon: FileText, detail: 'Capture the architecture decision' },
  { id: 'refactor-risk', label: 'Refactor risk score', icon: ShieldCheck, detail: 'Assess change scope and test risk' },
  { id: 'coverage', label: 'Test coverage', icon: ClipboardCheck, detail: 'Compare before and after coverage' },
  { id: 'release-notes', label: 'Release notes', icon: ListChecks, detail: 'Summarize what changed and why' },
  { id: 'code-quality', label: 'Code quality trend', icon: TrendingUp, detail: 'Track lint and test health' },
]

function App() {
  const [experiments, setExperiments] = useState([])
  const [templates, setTemplates] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [view, setView] = useState('overview')
  const [modal, setModal] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [qualityRecords, setQualityRecords] = useState([])
  const [qualityTrends, setQualityTrends] = useState([])
  const [user, setUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [trend, setTrend] = useState([])
  const [todayLabel] = useState(() => new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' }))

  const refresh = async (keepNotice = true) => {
    try {
      const [overview, availableTemplates] = await Promise.all([api.overview(), api.templates()])
      startTransition(() => {
        setExperiments(overview.experiments)
        setTemplates(availableTemplates)
        setTrend(overview.trend)
        setSelectedId((current) => current ?? overview.experiments[0]?.id ?? null)
        setError('')
        if (!keepNotice) setNotice('')
      })
    } catch (err) {
      if (err.status === 401) setUser(null)
      setError(err.message || 'Could not connect to the PropLoop API.')
    }
  }

  useEffect(() => {
    let active = true
    api.me().then((session) => { if (active) setUser(session.user) }).catch((err) => {
      if (active && err.status !== 401) setError(err.message)
    }).finally(() => { if (active) setAuthLoading(false) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!user) return undefined
    let active = true
    Promise.all([api.overview(), api.templates()]).then(([overview, availableTemplates]) => {
      if (!active) return
      startTransition(() => {
        setExperiments(overview.experiments)
        setTemplates(availableTemplates)
        setTrend(overview.trend)
        setSelectedId((current) => current ?? overview.experiments[0]?.id ?? null)
      })
    }).catch((err) => {
      if (active) setError(err.message || 'Could not connect to the PropLoop API.')
    })
    return () => { active = false }
  }, [user])

  const selected = experiments.find((item) => item.id === selectedId)
  const summary = {
    active: experiments.filter((item) => !['complete', 'stopped'].includes(item.stage)).length,
    shipped: experiments.filter((item) => item.stage === 'complete').length,
    approvals: experiments.filter((item) => ['design', 'plan', 'decision'].includes(item.stage)).length,
    blocked: experiments.filter((item) => item.blocker).length,
  }

  const run = async (operation, message) => {
    if (!selected) return
    setBusy(true)
    setError('')
    try {
      const result = await operation()
      await refresh()
      setNotice(message)
      return result
    } catch (err) {
      setError(err.message || 'That action could not be completed.')
      return null
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (!user || view !== 'quality' || !selectedId) return undefined
    let active = true
    Promise.all([api.quality(selectedId), api.qualityTrends()]).then(([records, trends]) => {
      if (active) startTransition(() => { setQualityRecords(records); setQualityTrends(trends) })
    }).catch((err) => {
      if (active) setError(err.message)
    })
    return () => { active = false }
  }, [view, selectedId, user])

  const generateArtifact = async (kind, evidence) => {
    await run(async () => {
      const artifact = await api.generateQuality(selected.id, kind, evidence)
      const [records, trends] = await Promise.all([api.quality(selected.id), api.qualityTrends()])
      setQualityRecords(records)
      setQualityTrends(trends)
      return artifact
    }, 'Quality artifact generated')
  }

  const selectView = (next) => setView(next)
  const canReview = ['admin', 'reviewer'].includes(user?.role)

  if (authLoading) return <main className="auth-loading">Checking your session...</main>
  if (!user) return <AccountAccess onAuthenticated={(session) => { setUser(session.user); setError('') }} />

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#overview" onClick={() => selectView('overview')}>
          <span className="brand-mark"><FlaskConical size={17} strokeWidth={2.2} /></span>
          <span>prop<span className="brand-loop">loop</span><small>EXPERIMENTS</small></span>
        </a>
        <div className="workspace-switcher">
          <span className="workspace-avatar">PL</span>
          <span><strong>Product lab</strong><small>Growth & operations</small></span>
          <ChevronDown size={14} />
        </div>
        <div className="nav-caption">WORKSPACE</div>
        <nav className="main-nav" aria-label="Main navigation">
          <button className={view === 'overview' ? 'nav-item active' : 'nav-item'} onClick={() => selectView('overview')}><LayoutDashboard size={17} /> Overview</button>
          <button className={view === 'experiments' ? 'nav-item active' : 'nav-item'} onClick={() => selectView('experiments')}><FlaskConical size={17} /> Experiments <span className="nav-count">{experiments.length}</span></button>
          <button className={view === 'quality' ? 'nav-item active' : 'nav-item'} onClick={() => selectView('quality')}><ShieldCheck size={17} /> Dev-loop quality</button>
          <button className={view === 'board' ? 'nav-item active' : 'nav-item'} onClick={() => selectView('board')}><ListChecks size={17} /> Experiment board</button>
          <button className={view === 'team' ? 'nav-item active' : 'nav-item'} onClick={() => selectView('team')}><ShieldCheck size={17} /> Team accounts</button>
        </nav>
        <div className="sidebar-divider" />
        <div className="nav-caption recent-caption">RECENT EXPERIMENTS <button aria-label="Create experiment" title="Create experiment" onClick={() => setModal(true)}><Plus size={15} /></button></div>
        <div className="recent-list">
          {experiments.slice(0, 5).map((item) => <button key={item.id} className={`recent-item ${selectedId === item.id ? 'selected' : ''}`} onClick={() => { setSelectedId(item.id); setView('experiments') }}><span className={`recent-dot ${item.stage}`} /><span>{item.name}</span></button>)}
          {!experiments.length && <p className="sidebar-empty">Your experiments will appear here.</p>}
        </div>
        <div className="sidebar-bottom"><span className="online-dot" /> All systems operational <span className="version">v1.0</span></div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs"><span>Workspace</span><span className="crumb-slash">/</span><strong>{view === 'overview' ? 'Overview' : view === 'quality' ? 'Dev-loop quality' : selected?.name || 'Experiments'}</strong></div>
          <div className="topbar-actions"><span className="today-label">{todayLabel}</span><button className="icon-button" title="Refresh data" aria-label="Refresh data" onClick={() => refresh(false)}><RefreshCw size={16} /></button><span className="user-avatar" title={`${user.name} (${user.role})`}>{user.name.slice(0, 2).toUpperCase()}</span><button className="quiet-button" onClick={async () => { try { await api.logout(); setUser(null); setExperiments([]); setSelectedId(null) } catch (err) { setError(err.message) } }}>Sign out</button></div>
        </header>

        {error && <div className="alert alert-error"><AlertCircle size={17} /><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError('')}><X size={15} /></button></div>}
        {notice && <div className="alert alert-success"><CheckCircle2 size={17} /><span>{notice}</span><button aria-label="Dismiss message" onClick={() => setNotice('')}><X size={15} /></button></div>}

        {view === 'overview' && <Overview experiments={experiments} trend={trend} summary={summary} selectExperiment={(id) => { setSelectedId(id); setView('experiments') }} onCreate={() => setModal(true)} />}
        {view === 'board' && <ExperimentBoard experiments={experiments} onSelect={(id) => { setSelectedId(id); setView('experiments') }} />}
        {view === 'team' && <TeamSettings user={user} />}
        {view === 'experiments' && selected && <ExperimentDetail key={`${selected.id}-${selected.cycle}`} experiment={selected} canReview={canReview} busy={busy} run={run} onEdit={() => setModal(true)} />}
        {view === 'experiments' && !selected && <EmptyState onCreate={() => setModal(true)} />}
        {view === 'quality' && selected && <QualityView experiment={selected} records={qualityRecords} trends={qualityTrends} onGenerate={generateArtifact} busy={busy} />}
        {view === 'quality' && !selected && <EmptyState onCreate={() => setModal(true)} />}
      </main>
      {modal && <NewExperimentModal templates={templates} onClose={() => setModal(false)} onCreate={async (payload) => {
        setBusy(true)
        try {
          const created = await api.createExperiment(payload)
          setModal(false)
          await refresh()
          setSelectedId(created.id)
          setView('experiments')
          setNotice('Experiment created. Define the brief to get started.')
        } catch (err) { setError(err.message) } finally { setBusy(false) }
      }} busy={busy} />}
    </div>
  )
}

function Overview({ experiments, summary, selectExperiment, onCreate, trend = [] }) {
  const stages = ['hypothesis', 'design', 'plan', 'build', 'measure', 'decision']
  const chartData = trend
  return <div className="page-content page-enter">
    <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-mark" /> EXPERIMENTATION WORKSPACE</div><h1>Make the next move <em>measurable.</em></h1><p>Run a focused hypothesis from first brief to a decision you can stand behind.</p></div><button className="primary-button" onClick={onCreate}><Plus size={17} /> New experiment</button></div>
    <section className="metric-strip" aria-label="Workspace summary">
      <SummaryMetric label="Active experiments" value={summary.active} icon={Activity} accent="green" foot="In the learning loop" />
      <SummaryMetric label="Awaiting approval" value={summary.approvals} icon={Clock3} accent="yellow" foot="Human gate required" />
      <SummaryMetric label="Shipped" value={summary.shipped} icon={CheckCircle2} accent="blue" foot="Released with evidence" />
      <SummaryMetric label="Blockers raised" value={summary.blocked} icon={AlertCircle} accent="coral" foot="Needs a team response" />
    </section>
    <section className="journey-panel">
      <div className="section-head"><div><div className="section-kicker">THE LEARNING LOOP</div><h2>From question to decision</h2></div><span className="cycle-tag"><RefreshCw size={13} /> Repeatable by design</span></div>
      <div className="journey-rail">{stages.map((stage, index) => <div className="journey-step" key={stage}><span className={`journey-icon journey-${stage}`}><JourneyIcon stage={stage} /></span><span className="journey-copy"><strong>{stageLabel[stage]}</strong><small>{['Frame the opportunity', 'Shape the experience', 'Approve the work', 'Build the smallest test', 'Read the evidence', 'Ship, iterate, or stop'][index]}</small></span>{index < stages.length - 1 && <ArrowRight className="journey-arrow" size={15} />}</div>)}</div>
      <div className="gate-note"><ShieldCheck size={15} /><span>Named reviewers approve every lifecycle stage.</span><span className="gate-count">6 APPROVAL POINTS</span></div>
    </section>
    <div className="overview-grid">
      <section className="panel experiments-panel"><div className="section-head panel-head"><div><div className="section-kicker">IN MOTION</div><h2>Experiments</h2></div><button className="text-button" onClick={() => experiments[0] && selectExperiment(experiments[0].id)}>View all <ArrowRight size={15} /></button></div>
        {experiments.length ? <div className="experiment-table"><div className="table-labels"><span>EXPERIMENT</span><span>STAGE</span><span>BUILD</span><span>PRIMARY METRIC</span></div>{experiments.slice(0, 5).map((item) => <button className="experiment-row" key={item.id} onClick={() => selectExperiment(item.id)}><span className="exp-name"><span className={`exp-type-icon ${item.stage}`}><FlaskConical size={15} /></span><span><strong>{item.name}</strong><small>{item.template_id?.replaceAll('-', ' ') || 'Custom experiment'}</small></span></span><span><StatusBadge stage={item.stage} /></span><span className="progress-cell"><span className="progress-track"><i style={{ width: `${item.task_progress.total ? (item.task_progress.completed / item.task_progress.total) * 100 : 0}%` }} /></span><small>{item.task_progress.completed}/{item.task_progress.total}</small></span><span className="table-metric">{item.target_metric}<ArrowRight size={14} /></span></button>)}</div> : <EmptyRows onCreate={onCreate} />}
      </section>
      <section className="panel trend-panel"><div className="section-head panel-head"><div><div className="section-kicker">TEAM MOMENTUM</div><h2>Learning velocity</h2></div><span className="period-button">Last 5 weeks</span></div><div className="trend-legend"><span><i className="legend-dot active-dot" /> Created</span><span><i className="legend-dot shipped-dot" /> Shipped</span></div><div className="trend-chart"><Suspense fallback={<div className="chart-loading" />}><LearningTrend data={chartData} /></Suspense></div><div className="trend-foot"><span>Recorded creation and release dates</span><span>Actual experiment history</span></div></section>
    </div>
  </div>
}

function SummaryMetric({ label, value, icon: Icon, accent, foot }) {
  return <div className="summary-metric"><span className={`summary-icon ${accent}`}><Icon size={17} /></span><div className="summary-info"><span>{label}</span><strong>{value}</strong><small>{foot}</small></div><span className="metric-sparkline" aria-hidden="true"><i /><i /><i /><i /><i /><i /><i /></span></div>
}

function JourneyIcon({ stage }) {
  const icons = { hypothesis: FlaskConical, design: FileText, plan: ClipboardCheck, build: Activity, measure: BarChart3, decision: CheckCircle2 }
  const Icon = icons[stage]
  return <Icon size={16} />
}

function ExperimentDetail({ experiment, canReview, busy, run }) {
  const [metricOpen, setMetricOpen] = useState(false)
  const [decisionOpen, setDecisionOpen] = useState(false)
  const [blockerOpen, setBlockerOpen] = useState(false)
  const [metric, setMetric] = useState({ name: experiment.target_metric, baseline: '', observed: '', unit: '%', direction: 'higher', comparison_mode: 'before_after', sample_size: 100 })
  const [rationale, setRationale] = useState('')
  const [blocker, setBlocker] = useState(experiment.blocker || '')
  const [participantKey, setParticipantKey] = useState('')
  const [lastAssignment, setLastAssignment] = useState(null)
  const [specState, setSpecState] = useState({ id: null, value: null })
  const [briefOpen, setBriefOpen] = useState(false)
  const [brief, setBrief] = useState({ name: experiment.name, hypothesis: experiment.hypothesis, problem_statement: experiment.problem_statement, target_metric: experiment.target_metric, template_id: experiment.template_id })
  const specDraft = specState.id === experiment.id ? specState.value : experiment.spec
  const metrics = experiment.metrics || []

  const updateSpec = (field, value) => setSpecState((current) => {
    const source = current.id === experiment.id ? current.value : experiment.spec
    return { id: experiment.id, value: { ...source, [field]: value } }
  })
  const saveSpec = async () => {
    const saved = await run(() => api.saveSpec(experiment.id, specDraft), 'Spec changes saved for review')
    if (saved) setSpecState({ id: null, value: null })
  }
  const saveMetric = async (event) => {
    event.preventDefault()
    await run(() => api.addMetric(experiment.id, { ...metric, baseline: Number(metric.baseline), observed: Number(metric.observed), sample_size: Number(metric.sample_size) }), 'Outcome metric recorded')
    setMetricOpen(false)
  }
  const assignParticipant = async (event) => {
    event.preventDefault()
    const result = await run(() => api.assignVariant(experiment.id, participantKey), 'Participant assigned to a test arm')
    if (result) {
      setLastAssignment(result)
      setParticipantKey('')
    }
  }
  const submitDecision = async (outcome) => {
    if (rationale.trim().length < 8) return
    await run(() => api.decide(experiment.id, { outcome, rationale }), `Decision recorded: ${outcome}`)
    setDecisionOpen(false)
    setRationale('')
  }
  const saveBlocker = async (event) => {
    event.preventDefault()
    await run(() => api.blocker(experiment.id, blocker), blocker ? 'Blocker flagged for the team' : 'Blocker cleared')
    setBlockerOpen(false)
  }
  const canDecide = canReview && experiment.stage === 'decision' && !experiment.blocker
  const hypothesisApproved = experiment.approvals?.some((item) => item.stage === 'hypothesis' && item.cycle === experiment.cycle)
  const stageGate = ['hypothesis', 'build', 'measure'].includes(experiment.stage)
  const approveDraft = async (stage) => {
    const saved = await run(async () => {
      await api.saveSpec(experiment.id, specDraft)
      return stage === 'design' ? api.approveSpec(experiment.id) : api.approvePlan(experiment.id)
    }, `${stage} approved by reviewer`)
    if (saved) setSpecState({ id: null, value: null })
  }
  const onEdit = () => {
    if (experiment.stage === 'hypothesis' && !hypothesisApproved) setBriefOpen(!briefOpen)
  }

  return <div className="page-content detail-page page-enter">
    <div className="detail-breadcrumb"><span className="exp-type-icon small"><FlaskConical size={14} /></span><span>{experiment.template_id?.replaceAll('-', ' ') || 'Custom experiment'}</span><span>/</span><strong>{experiment.name}</strong></div>
    <div className="detail-title-row"><div><div className="eyebrow"><span className="eyebrow-mark" /> EXPERIMENT {String(experiment.id).padStart(3, '0')}</div><h1>{experiment.name}</h1><div className="title-meta"><StatusBadge stage={experiment.stage} /><span className="meta-separator" /> Started {new Date(experiment.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}<span className="meta-separator" /><span className="owner-chip">JD</span> Product team</div></div><div className="title-actions"><button className="secondary-button" onClick={() => setBlockerOpen(!blockerOpen)}><AlertCircle size={15} /> {experiment.blocker ? 'Update blocker' : 'Flag blocker'}</button><button className="icon-button" title="More experiment actions" aria-label="More experiment actions" onClick={() => window.print()}><FileText size={16} /></button></div></div>
    {blockerOpen && <form className="blocker-form" onSubmit={saveBlocker}><AlertCircle size={16} /><input aria-label="Blocker description" placeholder="What is blocking progress?" value={blocker} onChange={(event) => setBlocker(event.target.value)} /><button className="primary-button small-button" disabled={busy}>Save blocker</button></form>}
    {experiment.blocker && <div className="blocker-banner"><AlertCircle size={16} /><span><strong>Blocker raised</strong> {experiment.blocker}</span><button onClick={() => { setBlocker(''); setBlockerOpen(true) }}>Resolve</button></div>}
    <LifecycleRail stage={experiment.stage} />
    {stageGate && !(experiment.stage === 'hypothesis' && hypothesisApproved) && <section className="panel stage-gate-panel"><strong>Approve {stageLabel[experiment.stage]} to progress</strong><p>{experiment.stage === 'hypothesis' ? 'Review the hypothesis before AI drafts a design.' : experiment.stage === 'build' ? 'Complete all implementation tasks before approving the build for measurement.' : 'Review observations, sample sizes and guardrails before approving the release review.'}</p><button className="primary-button" disabled={busy || !canReview || !!experiment.blocker} onClick={() => run(() => api.approveStage(experiment.id, experiment.stage), `${stageLabel[experiment.stage]} approved`)}>Approve {stageLabel[experiment.stage]}</button>{!canReview && <small>A reviewer or admin must approve this stage.</small>}</section>}
    {briefOpen && <form className="panel brief-editor" onSubmit={async (event) => { event.preventDefault(); const result = await run(() => api.saveBrief(experiment.id, brief), 'Hypothesis updated'); if (result) setBriefOpen(false) }}>{['name', 'hypothesis', 'problem_statement', 'target_metric'].map((field) => <label key={field}>{field.replaceAll('_', ' ')}<textarea required value={brief[field]} onChange={(event) => setBrief({ ...brief, [field]: event.target.value })} /></label>)}<button className="primary-button" disabled={busy}>Save hypothesis</button></form>}
    {!!experiment.approvals?.length && <details className="panel approval-history"><summary>Approval audit · cycle {experiment.cycle}</summary>{experiment.approvals.map((entry, index) => <p key={index}>Cycle {entry.cycle} · {entry.stage} · {entry.reviewer_name} · {new Date(entry.approved_at).toLocaleString()}</p>)}</details>}
    {!!experiment.history?.length && <details className="panel approval-history"><summary>Archived iteration evidence ({experiment.history.length})</summary>{experiment.history.map((entry) => <details key={entry.cycle}><summary>Cycle {entry.cycle}: {entry.rationale}</summary><pre>{JSON.stringify(entry.snapshot, null, 2)}</pre></details>)}</details>}
    <div className="detail-columns">
      <div className="detail-main-column">
        <section className="panel hypothesis-panel"><div className="section-head panel-head"><div><div className="section-kicker">THE BET</div><h2>Experiment hypothesis</h2></div><span className="hypothesis-number">01</span></div><blockquote>“{experiment.hypothesis}”</blockquote><div className="problem-note"><span>PROBLEM</span><p>{experiment.problem_statement}</p></div><div className="hypothesis-footer"><span><TrendingUp size={14} /> Target metric</span><strong>{experiment.target_metric}</strong><button className="quiet-button" onClick={onEdit}>Edit brief</button></div></section>
        <section className="panel spec-panel"><div className="section-head panel-head"><div><div className="section-kicker">DESIGN & PLAN</div><h2>AI-assisted spec</h2></div><span className={`approval-pill ${experiment.spec_approved ? 'approved' : ''}`}>{experiment.spec_approved ? <><Check size={13} /> Spec approved</> : <><Clock3 size={13} /> Review required</>}</span></div>
          {!experiment.spec ? <div className="spec-empty"><span className="ai-orbit"><Sparkles size={20} /></span><div><strong>Turn this hypothesis into a build-ready brief.</strong><p>Generate a user story, success definition, risks, acceptance criteria, and an implementation plan.</p></div><button className="primary-button" disabled={busy || !hypothesisApproved} onClick={() => run(() => api.generateSpec(experiment.id), 'Draft spec generated. Review and edit it before approval.')}><Sparkles size={16} /> Generate spec</button></div> : <div className="spec-content">
            <div className="spec-field"><label>DESIGN BRIEF<textarea value={specDraft?.design_brief || ''} disabled={experiment.spec_approved} onChange={(event) => updateSpec('design_brief', event.target.value)} /></label></div>
            <div className="spec-field"><label>METRIC NAME<input value={specDraft?.success_metric?.name || ''} disabled={experiment.spec_approved} onChange={(event) => updateSpec('success_metric', { ...specDraft.success_metric, name: event.target.value })} /></label></div>
            <div className="spec-field"><label>METRIC GUARDRAILS<textarea value={(specDraft?.success_metric?.guardrails || []).join('\n')} disabled={experiment.spec_approved} onChange={(event) => updateSpec('success_metric', { ...specDraft.success_metric, guardrails: event.target.value.split('\n').filter((item) => item.trim()) })} /></label></div>
            <div className="spec-field"><label htmlFor="spec-story">USER STORY</label><textarea id="spec-story" value={specDraft?.user_story || ''} disabled={experiment.spec_approved} onChange={(event) => updateSpec('user_story', event.target.value)} rows={2} /></div>
            <div className="spec-field"><label htmlFor="spec-definition">SUCCESS METRIC DEFINITION</label><textarea id="spec-definition" value={specDraft?.success_metric?.definition || ''} disabled={experiment.spec_approved} onChange={(event) => updateSpec('success_metric', { ...specDraft.success_metric, definition: event.target.value })} rows={2} /></div>
            <div className="spec-split"><div><label className="mini-heading" htmlFor="spec-risks">RISKS & MITIGATIONS</label><textarea className="spec-edit-list" id="spec-risks" rows={4} disabled={experiment.spec_approved} value={(specDraft?.risks || []).map((risk) => `${risk.risk} | ${risk.mitigation}`).join('\n')} onChange={(event) => updateSpec('risks', event.target.value.split('\n').filter((line) => line.trim()).map((line) => { const [risk, ...mitigation] = line.split('|'); return { risk: risk.trim(), mitigation: mitigation.join('|').trim() } }))} /></div><div><label className="mini-heading" htmlFor="spec-criteria">ACCEPTANCE CRITERIA</label><textarea className="spec-edit-list" id="spec-criteria" rows={4} disabled={experiment.spec_approved} value={(specDraft?.acceptance_criteria || []).join('\n')} onChange={(event) => updateSpec('acceptance_criteria', event.target.value.split('\n').map((item) => item.trim()).filter(Boolean))} /></div></div>
            {!experiment.plan_approved && <div className="draft-plan-editor"><label>ESTIMATED EFFORT<input value={specDraft?.estimated_effort || ''} onChange={(event) => updateSpec('estimated_effort', event.target.value)} /></label>{(specDraft?.implementation_checklist || []).map((task, index) => <div className="draft-task-editor" key={index}><label>Task {index + 1}<input value={task.title} onChange={(event) => updateSpec('implementation_checklist', specDraft.implementation_checklist.map((entry, i) => i === index ? { ...entry, title: event.target.value } : entry))} /></label><label>Description<textarea value={task.description} onChange={(event) => updateSpec('implementation_checklist', specDraft.implementation_checklist.map((entry, i) => i === index ? { ...entry, description: event.target.value } : entry))} /></label><button className="quiet-button" disabled={busy} onClick={() => updateSpec('implementation_checklist', specDraft.implementation_checklist.filter((_, i) => i !== index))}>Remove task</button></div>)}<button className="secondary-button" onClick={() => updateSpec('implementation_checklist', [...specDraft.implementation_checklist, { title: '', description: '' }])}>Add task</button></div>}
            <div className="spec-footer"><span className="provider-tag"><Sparkles size={12} /> {specDraft?.provider || 'mock'} provider · {specDraft?.estimated_effort || 'Effort TBD'}</span>{!experiment.plan_approved && <button className="secondary-button" disabled={busy} onClick={saveSpec}>Save edits</button>}{!experiment.spec_approved ? <button className="primary-button" disabled={busy || !canReview || !!experiment.blocker} onClick={() => approveDraft('design')}><Check size={15} /> Approve spec</button> : <span className="locked-note"><CheckCircle2 size={14} /> Design approved and locked</span>}</div>
          </div>}
        </section>
        <section className="panel build-panel"><div className="section-head panel-head"><div><div className="section-kicker">IMPLEMENTATION</div><h2>Build checklist <span className="count-badge">{experiment.task_progress.completed}/{experiment.task_progress.total}</span></h2></div><span className={`approval-pill ${experiment.plan_approved ? 'approved' : ''}`}>{experiment.plan_approved ? <><Check size={13} /> Plan approved</> : <><Clock3 size={13} /> Plan approval required</>}</span></div>
          {!experiment.plan_approved ? <div className="approval-gate"><span className="gate-lock"><ShieldCheck size={17} /></span><span><strong>Pause before implementation.</strong><small>Review the generated tasks below. Approve the plan to start implementation tracking.</small><div className="plan-preview">{(specDraft?.implementation_checklist || []).map((task, index) => <div className="plan-preview-item" key={`${task.title}-${index}`}><span>{String(index + 1).padStart(2, '0')}</span><strong>{task.title}</strong><small>{task.description}</small></div>)}</div></span><button className="primary-button" disabled={busy || !canReview || !experiment.spec_approved || !!experiment.blocker} onClick={() => approveDraft('plan')}><Check size={15} /> Approve task plan</button></div> : <>
            <div className="task-list">{experiment.tasks.map((task, index) => <label className={`task-row ${task.status === 'done' ? 'task-done' : ''}`} key={task.id}><button disabled={busy || experiment.stage !== 'build'} className={`task-check ${task.status === 'done' ? 'checked' : ''}`} aria-label={`Mark ${task.title} ${task.status === 'done' ? 'not done' : 'done'}`} onClick={(event) => { event.preventDefault(); run(() => api.updateTask(task.id, task.status === 'done' ? 'todo' : 'done'), task.status === 'done' ? 'Task reopened' : 'Task marked complete') }}>{task.status === 'done' ? <Check size={13} /> : <span>{String(index + 1).padStart(2, '0')}</span>}</button><span className="task-copy"><strong>{task.title}</strong><small>{task.description}</small></span><span className={`task-state ${task.status}`}>{task.status === 'done' ? 'Done' : task.status === 'in_progress' ? 'In progress' : 'To do'}</span></label>)}</div>
            {!experiment.tasks.length && <p className="no-tasks">The approved plan did not include tasks. Generate a new spec to create a checklist.</p>}
            <div className="build-foot"><div className="build-progress"><span>Build progress</span><strong>{experiment.task_progress.total ? Math.round(experiment.task_progress.completed / experiment.task_progress.total * 100) : 0}%</strong><span className="progress-track"><i style={{ width: `${experiment.task_progress.total ? (experiment.task_progress.completed / experiment.task_progress.total) * 100 : 0}%` }} /></span></div><span className="build-footnote"><ShieldCheck size={13} /> Plan approved by product team</span></div>
          </>}
        </section>
      </div>
      <div className="detail-side-column">
        <OutcomeCapture experiment={experiment} busy={busy} run={run} />
        <section className="panel metrics-panel"><div className="section-head panel-head"><div><div className="section-kicker">MEASURE THE CHANGE</div><h2>Outcome metrics</h2></div><button disabled={busy || experiment.stage !== 'measure'} className="icon-button compact" title="Add metric result" aria-label="Add metric result" onClick={() => setMetricOpen(!metricOpen)}><Plus size={16} /></button></div>
          {experiment.plan_approved && ['build', 'measure'].includes(experiment.stage) && <div className="assignment-panel"><div className="mini-heading">CONTROLLED TEST ENROLLMENT</div><p>Use an opaque participant key, never a resident name or email. Assignment is stable at a 50/50 split.</p><form onSubmit={assignParticipant}><input minLength={8} maxLength={128} required value={participantKey} onChange={(event) => setParticipantKey(event.target.value)} placeholder="e.g. resident-cohort-014" aria-label="Opaque participant key" /><button className="secondary-button" disabled={busy}>Assign arm</button></form><div className="assignment-counts"><span>Control <strong>{experiment.assignment_summary?.control || 0}</strong></span><span>Treatment <strong>{experiment.assignment_summary?.treatment || 0}</strong></span>{lastAssignment && <span className={`assignment-result ${lastAssignment.variant}`}>Latest: {lastAssignment.variant}</span>}</div></div>}
          {metrics.length ? <div className="metric-results">{metrics.map((item) => <MetricResult key={item.id} metric={item} />)}</div> : <div className="metrics-empty"><BarChart3 size={23} /><strong>No results recorded yet</strong><span>Capture a baseline and observed outcome to start the learning loop.</span></div>}
          {metricOpen && <form className="metric-form" onSubmit={saveMetric}><p>Manual before/after observations are descriptive. Use participant outcomes above for controlled-test significance.</p><label>Metric name<input required value={metric.name} onChange={(event) => setMetric({ ...metric, name: event.target.value })} /></label><label>Unit<select value={metric.unit} onChange={(event) => setMetric({ ...metric, unit: event.target.value })}><option>%</option><option>min</option><option>hrs</option><option>score</option></select></label><div className="form-row"><label>Baseline<input type="number" step="any" required value={metric.baseline} onChange={(event) => setMetric({ ...metric, baseline: event.target.value })} /></label><label>Observed<input type="number" step="any" required value={metric.observed} onChange={(event) => setMetric({ ...metric, observed: event.target.value })} /></label></div><div className="form-row"><label>Better when<select value={metric.direction} onChange={(event) => setMetric({ ...metric, direction: event.target.value })}><option value="higher">Higher</option><option value="lower">Lower</option></select></label><label>Sample size<input type="number" min="1" required value={metric.sample_size} onChange={(event) => setMetric({ ...metric, sample_size: event.target.value })} /></label></div><button className="primary-button full-button" disabled={busy || experiment.stage !== 'measure'}>Record descriptive result</button></form>}
          <div className="metrics-footer"><span>Activation</span><span>Completion</span><span>CSAT</span><span>Time saved</span><span>Error rate</span></div>
        </section>
        <section className="panel decision-panel"><div className="section-head panel-head"><div><div className="section-kicker">THE RELEASE GATE</div><h2>Make the call</h2></div><span className="decision-step">07</span></div><p className="decision-copy">Use the evidence to decide what happens next. Every outcome is recorded.</p>{decisionOpen ? <div className="decision-form"><label htmlFor="decision-rationale">Why this decision?</label><textarea id="decision-rationale" rows={3} placeholder="Connect the outcome to what you learned…" value={rationale} onChange={(event) => setRationale(event.target.value)} /><div className="decision-options"><button className="decision-option ship" disabled={!canDecide || busy || rationale.trim().length < 8} onClick={() => submitDecision('ship')}><ArrowUpRight size={15} /> Ship</button><button className="decision-option iterate" disabled={!canDecide || busy || rationale.trim().length < 8} onClick={() => submitDecision('iterate')}><RefreshCw size={14} /> Iterate</button><button className="decision-option stop" disabled={!canDecide || busy || rationale.trim().length < 8} onClick={() => submitDecision('stop')}><X size={15} /> Stop</button></div><button className="quiet-button cancel-decision" onClick={() => setDecisionOpen(false)}>Cancel</button></div> : <><div className="decision-buttons"><button className="decision-button ship" disabled={!canDecide || busy} onClick={() => setDecisionOpen(true)}><ArrowUpRight size={15} /><span>Ship</span></button><button className="decision-button iterate" disabled={!canDecide || busy} onClick={() => setDecisionOpen(true)}><RefreshCw size={14} /><span>Iterate</span></button><button className="decision-button stop" disabled={!canDecide || busy} onClick={() => setDecisionOpen(true)}><X size={15} /><span>Stop</span></button></div><div className="decision-hint"><ShieldCheck size={14} /> {canDecide ? 'Evidence ready. Choose an outcome.' : 'Complete the build and record metrics to unlock.'}</div></>}{experiment.decisions?.length > 0 && <div className="decision-history"><div className="mini-heading">DECISION HISTORY</div>{experiment.decisions.slice().reverse().map((entry) => <div className="decision-history-row" key={entry.id}><span className={`history-dot ${entry.outcome}`} /><span><strong>{entry.outcome}</strong><small>{entry.rationale}</small></span></div>)}</div>}</section>
        <section className="human-note"><span className="human-note-icon"><ShieldCheck size={16} /></span><span><strong>Human judgment stays in the loop.</strong><small>AI drafts the plan. Your team owns the call.</small></span></section>
      </div>
    </div>
  </div>
}

function LifecycleRail({ stage }) {
  const current = stageOrder.indexOf(stage)
  return <div className="lifecycle-rail" aria-label="Experiment lifecycle">{stageOrder.map((item, index) => <div className={`lifecycle-stage ${index < current || stage === 'complete' ? 'past' : ''} ${index === current ? 'current' : ''}`} key={item}><span className="lifecycle-node">{index < current || stage === 'complete' ? <Check size={12} /> : <span>{String(index + 1).padStart(2, '0')}</span>}</span><span>{stageLabel[item]}</span>{index < stageOrder.length - 1 && <i />}</div>)}</div>
}

function MetricResult({ metric }) {
  const positive = metric.improved
  const controlled = metric.comparison_mode === 'controlled'
  const confidenceLabel = metric.confidence?.p_value != null
    ? `${metric.confidence.significant ? 'Significant' : 'Directional'} · p=${metric.confidence.p_value}`
    : metric.confidence?.label || 'Insufficient data'
  return <div className="metric-result"><div className="metric-result-top"><span>{metric.name}</span><span className={`metric-delta ${positive ? 'positive' : 'negative'}`}>{positive ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}{metric.relative_change === null ? `${metric.change > 0 ? '+' : ''}${metric.change}` : `${Math.abs(metric.relative_change)}%`}</span></div><div className="metric-values"><span><strong>{metric.baseline}{metric.unit}</strong><small>{controlled ? `Control · n=${metric.control_sample_size}` : 'Before'}</small></span><ArrowRight size={15} /><span className="observed-value"><strong>{metric.observed}{metric.unit}</strong><small>{controlled ? `Treatment · n=${metric.treatment_sample_size}` : 'Observed'}</small></span><span className="confidence-tag">{confidenceLabel}</span></div><div className="metric-bar"><i style={{ width: `${Math.max(6, Math.min(100, metric.observed / Math.max(metric.baseline, metric.observed, 1) * 100))}%` }} /></div><small className="sample-caption">{controlled ? `${metric.control_sample_size + metric.treatment_sample_size} assigned participants` : `${metric.sample_size} participants`} · {metric.confidence?.label || 'Directional'}</small></div>
}

function QualityView({ experiment, records, trends, onGenerate, busy }) {
  const latest = new Map(records.map((record) => [record.kind, record]))
  const [evidence, setEvidence] = useState({ files_changed: '', lines_changed: '', dependency_changes: '', coverage_before: '', coverage_after: '', lint_issues: '', tests_passed: '', tests_total: '' })
  const qualityHistory = trends.filter((record) => record.kind === 'code-quality')
  const evidenceFields = [
    ['files_changed', 'Files changed'], ['lines_changed', 'Lines changed'], ['dependency_changes', 'Dependencies changed'],
    ['coverage_before', 'Coverage before (%)'], ['coverage_after', 'Coverage after (%)'], ['lint_issues', 'Lint issues'],
    ['tests_passed', 'Tests passed'], ['tests_total', 'Tests total'],
  ]
  const payloadFor = (kind) => {
    const fields = kind === 'refactor-risk'
      ? ['files_changed', 'lines_changed', 'dependency_changes', 'coverage_before', 'coverage_after', 'tests_passed', 'tests_total']
      : kind === 'coverage' ? ['coverage_before', 'coverage_after']
        : kind === 'code-quality' ? ['lint_issues', 'tests_passed', 'tests_total', 'coverage_after'] : []
    const missing = fields.filter((field) => evidence[field] === '')
    if (missing.length) return null
    return Object.fromEntries(fields.map((field) => [field, Number(evidence[field])]))
  }

  return <div className="page-content quality-page page-enter">
    <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-mark" /> QUALITY SYSTEM</div><h1>Keep the loop <em>healthy.</em></h1><p>Review measured change evidence alongside the experiment decision.</p></div><span className="quality-experiment"><FlaskConical size={15} /> {experiment.name}</span></div>
    <div className="quality-summary"><span className="quality-summary-icon"><ShieldCheck size={20} /></span><span><strong>Evidence-backed quality checks</strong><small>Coverage, test results, lint counts, and change scope come from recorded inputs.</small></span><span className="quality-summary-status"><i /> Connected to experiment</span></div>
    <section className="panel quality-evidence"><div className="section-head panel-head"><div><div className="section-kicker">MEASURED INPUTS</div><h2>Build and test evidence</h2></div><span className="provider-tag">Used by coverage, risk, and quality trend tools</span></div><div className="quality-evidence-grid">{evidenceFields.map(([field, label]) => <label key={field}>{label}<input type="number" min="0" max={field.startsWith('coverage_') ? 100 : undefined} step="any" value={evidence[field]} onChange={(event) => setEvidence({ ...evidence, [field]: event.target.value })} /></label>)}</div><p>Enter values from CI or the reviewed change. Use the CI workflow for automatic test, coverage, and lint snapshots.</p></section>
    <div className="quality-grid">{qualityTools.map(({ id, label, icon: Icon, detail }) => { const ready = payloadFor(id) !== null; return <section className="panel quality-card" key={id}><div className="quality-card-top"><span className="quality-tool-icon"><Icon size={18} /></span><span className="tool-state">{latest.has(id) ? 'RECORDED' : 'READY'}</span></div><h2>{label}</h2><p>{detail}</p>{latest.has(id) ? <QualityArtifact record={latest.get(id)} /> : <div className="quality-placeholder"><Circle size={13} /> No evidence recorded</div>}<button className="secondary-button quality-generate" disabled={busy || !ready} onClick={() => onGenerate(id, payloadFor(id))}>{latest.has(id) ? <RefreshCw size={14} /> : <Plus size={15} />}{latest.has(id) ? 'Record new snapshot' : 'Generate artifact'}</button></section> })}</div>
    <section className="panel quality-history"><div className="section-head panel-head"><div><div className="section-kicker">ACROSS EXPERIMENTS</div><h2>Code quality trend</h2></div><span className="provider-tag">Measured snapshots</span></div>{qualityHistory.length ? <div className="quality-history-list">{qualityHistory.slice().reverse().map((record) => <div className="quality-history-row" key={`${record.experiment_id}-${record.created_at}`}><span className="history-experiment"><strong>{record.experiment_name}</strong><small>{new Date(record.created_at).toLocaleDateString()}</small></span><span><strong>{record.content.lint_issues}</strong><small>Lint issues</small></span><span><strong>{record.content.test_pass_rate}%</strong><small>Test pass</small></span><span><strong>{record.content.coverage}%</strong><small>Coverage</small></span><span className={`trend-state ${record.content.trend}`}>{record.content.trend}</span></div>)}</div> : <div className="quality-placeholder"><Circle size={13} /> Generate a measured code-quality snapshot to start the trend.</div>}</section>
  </div>
}

function QualityArtifact({ record }) {
  const data = record.content
  if (record.kind === 'pr-checklist') return <div className="artifact-preview">{data.items.slice(0, 3).map((item) => <span key={item}><Check size={12} /> {item}</span>)}<small>+{Math.max(0, data.items.length - 3)} checklist items</small></div>
  if (record.kind === 'refactor-risk') return <div className="risk-score"><strong>{data.score}</strong><span><b>{data.level} risk</b><small>{data.recommendation}</small></span></div>
  if (record.kind === 'coverage') return <div className="coverage-preview"><span>BEFORE <strong>{data.before}%</strong></span><ArrowRight size={14} /><span>AFTER <strong>{data.after}%</strong></span></div>
  if (record.kind === 'release-notes') return <div className="text-preview">{data.summary}<small>{data.tasks_completed}/{data.total_tasks} tasks complete</small></div>
  if (record.kind === 'code-quality') return <div className="quality-numbers"><span><strong>{data.lint_issues}</strong><small>Lint issues</small></span><span><strong>{data.test_pass_rate}%</strong><small>Test pass rate</small></span><span><strong>{data.coverage}%</strong><small>Coverage</small></span></div>
  return <div className="text-preview">{data.context}<small>{data.template}</small></div>
}

function StatusBadge({ stage }) {
  return <span className={`status-badge status-${stage}`}><i /> {stageLabel[stage] || stage}</span>
}

function EmptyRows({ onCreate }) {
  return <div className="empty-rows"><span className="empty-icon"><FlaskConical size={20} /></span><strong>A clean slate for your next experiment.</strong><span>Choose a property-management template or start with your own hypothesis.</span><button className="secondary-button" onClick={onCreate}><Plus size={15} /> Create experiment</button></div>
}

function EmptyState({ onCreate }) {
  return <div className="empty-page"><span className="empty-icon"><FlaskConical size={22} /></span><h2>No experiment selected</h2><p>Start with a focused property-management opportunity and run it through a human-approved learning loop.</p><button className="primary-button" onClick={onCreate}><Plus size={16} /> Create experiment</button></div>
}

function NewExperimentModal({ templates, onClose, onCreate, busy }) {
  const [selectedTemplate, setSelectedTemplate] = useState(null)
  const [form, setForm] = useState({ name: '', problem_statement: '', hypothesis: '', target_metric: '' })
  const chooseTemplate = (template) => {
    setSelectedTemplate(template)
    setForm({ name: template.name, problem_statement: template.problem_statement, hypothesis: template.hypothesis, target_metric: template.target_metric })
  }
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }))
  return <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}><form className="create-modal" onSubmit={(event) => { event.preventDefault(); onCreate({ ...form, template_id: selectedTemplate?.id || null }) }}><div className="modal-head"><span className="modal-icon"><FlaskConical size={18} /></span><button type="button" className="icon-button" aria-label="Close" onClick={onClose}><X size={17} /></button><div className="section-kicker">START WITH A GOOD QUESTION</div><h2>New experiment</h2><p>Pick a domain template or bring your own problem.</p></div><div className="template-picker"><div className="field-heading">PROPERTY MANAGEMENT STARTERS</div><div className="template-grid">{templates.map((template) => <button key={template.id} type="button" className={`template-option ${selectedTemplate?.id === template.id ? 'chosen' : ''}`} onClick={() => chooseTemplate(template)}><span>{template.category}</span><strong>{template.name}</strong><i>{selectedTemplate?.id === template.id ? <Check size={13} /> : <ArrowRight size={13} />}</i></button>)}</div></div><div className="modal-fields"><label>Experiment name<input required minLength="3" value={form.name} onChange={(event) => update('name', event.target.value)} placeholder="e.g. Resident move-in companion" /></label><label>Problem statement<textarea required minLength="10" rows={2} value={form.problem_statement} onChange={(event) => update('problem_statement', event.target.value)} placeholder="What is slow, unclear, or frustrating today?" /></label><label>Hypothesis<textarea required minLength="10" rows={2} value={form.hypothesis} onChange={(event) => update('hypothesis', event.target.value)} placeholder="If we..., then we expect..., because..." /></label><label>Primary target metric<input required value={form.target_metric} onChange={(event) => update('target_metric', event.target.value)} placeholder="e.g. Time to first response" /></label></div><div className="modal-footer"><span><ShieldCheck size={14} /> Spec and plan approvals are built in</span><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button type="submit" className="primary-button" disabled={busy || !form.name || !form.hypothesis || !form.target_metric}><Plus size={15} /> Create experiment</button></div></form></div>
}

export default App
