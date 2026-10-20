import { Check } from 'lucide-react'
import type { Stage, StageStatus } from '../data/stages'

const STATUS_LABEL: Record<StageStatus, string> = {
  done: 'Готово',
  active: 'В работе',
  planned: 'Впереди',
}

const STATUS_BADGE: Record<StageStatus, string> = {
  done: 'border-success/30 bg-success/10 text-success',
  active: 'border-accent/40 bg-accent/10 text-accent',
  planned: 'border-line text-ink-subtle',
}

interface StageCardProps {
  stage: Stage
  status: StageStatus
}

export function StageCard({ stage, status }: StageCardProps) {
  const Icon = stage.icon
  const isActive = status === 'active'

  return (
    <li
      className={`relative overflow-hidden rounded-2xl border bg-surface/60 p-5 transition-colors hover:bg-surface ${
        isActive ? 'border-accent/50' : 'border-line hover:border-line-strong'
      }`}
    >
      {isActive && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-24 -right-24 size-48 rounded-full bg-accent/20 blur-3xl"
        />
      )}

      <div className="flex items-center justify-between">
        <span className="font-mono text-sm text-ink-subtle tabular-nums">
          {String(stage.id).padStart(2, '0')}
        </span>
        <span
          className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${STATUS_BADGE[status]}`}
        >
          {status === 'done' && <Check aria-hidden="true" className="size-3" />}
          {STATUS_LABEL[status]}
        </span>
      </div>

      <div
        className={`mt-5 inline-flex size-10 items-center justify-center rounded-xl border ${
          isActive
            ? 'border-accent/40 bg-accent/15 text-accent'
            : 'border-line bg-white/5 text-ink-muted'
        }`}
      >
        <Icon aria-hidden="true" className="size-5" />
      </div>

      <h3 className="mt-4 font-semibold">{stage.title}</h3>
      <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">{stage.description}</p>
    </li>
  )
}
