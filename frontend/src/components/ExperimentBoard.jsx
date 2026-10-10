import { useId } from 'react'
import './gaps.css'

const stages = [
  ['hypothesis', 'Hypothesis'], ['design', 'Design'], ['plan', 'Plan'], ['build', 'Build'],
  ['measure', 'Measure'], ['decision', 'Decision'], ['complete', 'Complete'], ['stopped', 'Stopped'],
]

export default function ExperimentBoard({ experiments = [], onSelect }) {
  const id = useId()
  return <section className="gap-scope gap-board-wrap" aria-labelledby={`${id}-heading`}>
    <div className="gap-kicker">EXPERIMENT LIFECYCLE</div>
    <h2 id={`${id}-heading`}>Experiment board</h2>
    <p className="gap-muted">Select an experiment to review its details. Stage changes follow approval gates; cards cannot be dragged past them.</p>
    <div className="gap-board">
      {stages.map(([stage, label]) => {
        const items = experiments.filter((experiment) => experiment.stage === stage)
        return <section className={`gap-board-column gap-stage-${stage}`} key={stage} aria-labelledby={`${id}-${stage}`}>
          <header><h3 id={`${id}-${stage}`}>{label}</h3><span className="gap-tag">{items.length}</span></header>
          {!items.length && <p className="gap-board-empty">No experiments</p>}
          {items.map((experiment) => {
            const tasks = experiment.tasks || []
            const total = experiment.task_progress?.total ?? tasks.length
            const done = experiment.task_progress?.completed ?? tasks.filter((task) => task.status === 'done').length
            return <button type="button" className="gap-board-card" key={experiment.id} onClick={() => onSelect(experiment.id)} aria-label={`Open ${experiment.name}`}>
              <strong>{experiment.name}</strong>
              {experiment.target_metric && <span className="gap-muted">Target: {experiment.target_metric}</span>}
              <span className="gap-card-progress">{total ? `${done} / ${total} build tasks complete` : 'No build tasks yet'}</span>
              {total > 0 && <progress max={total} value={done} aria-label={`${experiment.name} build task progress`} />}
              {experiment.blocker && <span className="gap-card-blocker"><strong>Blocked:</strong> {experiment.blocker}</span>}
              <span className="gap-card-open">Review experiment →</span>
            </button>
          })}
        </section>
      })}
    </div>
  </section>
}
