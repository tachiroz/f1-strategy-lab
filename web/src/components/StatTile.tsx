import { CircleAlert, CircleCheck, CircleMinus } from 'lucide-react'
import type { ReactNode } from 'react'

export type Verdict = 'better' | 'worse' | 'same'

const VERDICT_STYLE: Record<Verdict, { icon: typeof CircleCheck; className: string }> = {
  better: { icon: CircleCheck, className: 'text-success' },
  worse: { icon: CircleAlert, className: 'text-accent' },
  same: { icon: CircleMinus, className: 'text-ink-subtle' },
}

interface StatTileProps {
  label: string
  value: ReactNode
  /** Unit after the value, in small print so the number keeps one line on phones. */
  unit?: string
  /** Small print under the value: units, interval, sample size. */
  hint?: ReactNode
  /** Comparison against a named baseline; always an icon and words, never colour alone. */
  verdict?: { kind: Verdict; text: string }
}

export function StatTile({ label, value, unit, hint, verdict }: StatTileProps) {
  const style = verdict && VERDICT_STYLE[verdict.kind]
  const Icon = style?.icon
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <dt className="text-xs text-ink-subtle">{label}</dt>
      <dd className="mt-2">
        <span className="text-2xl font-semibold tracking-tight">{value}</span>
        {unit && <span className="ml-1 text-sm text-ink-muted">{unit}</span>}
        {hint && <span className="mt-1 block text-xs text-ink-subtle">{hint}</span>}
        {verdict && Icon && (
          <span className={`mt-2 flex items-center gap-1.5 text-xs ${style.className}`}>
            <Icon aria-hidden="true" className="size-3.5 shrink-0" />
            {verdict.text}
          </span>
        )}
      </dd>
    </div>
  )
}
