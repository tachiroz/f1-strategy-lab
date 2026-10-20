import { STAGES, stageStatus } from '../data/stages'
import { StageCard } from './StageCard'

export function Roadmap() {
  return (
    <section
      id="roadmap"
      aria-labelledby="roadmap-title"
      className="mx-auto max-w-6xl scroll-mt-20 px-4 pt-4 pb-20 sm:px-6 sm:pb-24"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="font-mono text-xs tracking-wider text-accent uppercase">Дорожная карта</p>
          <h2 id="roadmap-title" className="mt-2 text-3xl font-semibold tracking-tight">
            От сырых данных до прогноза
          </h2>
        </div>
        <p className="max-w-sm text-sm text-ink-muted">
          {STAGES.length} этапов. Каждый этап: отдельная ветка и PR с тестами и зелёным CI.
        </p>
      </div>

      <ol className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {STAGES.map((stage) => (
          <StageCard key={stage.id} stage={stage} status={stageStatus(stage.id)} />
        ))}
      </ol>
    </section>
  )
}
