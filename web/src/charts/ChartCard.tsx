import { BarChart3, Table2 } from 'lucide-react'
import { type ReactNode, useId, useState } from 'react'

type View = 'chart' | 'table'

interface ChartCardProps {
  title: string
  description?: ReactNode
  legend?: ReactNode
  /** Table twin of the chart: every value is reachable without hovering. */
  table: ReactNode
  footnote?: ReactNode
  /** New data is loading: keep the previous render, dimmed, instead of a skeleton. */
  busy?: boolean
  children: ReactNode
}

const VIEWS: readonly { id: View; label: string; icon: typeof BarChart3 }[] = [
  { id: 'chart', label: 'График', icon: BarChart3 },
  { id: 'table', label: 'Таблица', icon: Table2 },
]

/** Card that owns a chart's title, legend, footnote and the chart/table switch. */
export function ChartCard({
  title,
  description,
  legend,
  table,
  footnote,
  busy = false,
  children,
}: ChartCardProps) {
  const [view, setView] = useState<View>('chart')
  const titleId = useId()

  return (
    <figure
      aria-labelledby={titleId}
      aria-busy={busy}
      className="min-w-0 rounded-2xl border border-line bg-surface p-4 sm:p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id={titleId} className="font-semibold tracking-tight">
            {title}
          </h2>
          {description && (
            <p className="mt-1 max-w-2xl text-sm text-pretty text-ink-muted">{description}</p>
          )}
        </div>
        <div
          role="group"
          aria-label="Вид"
          className="inline-flex rounded-lg border border-line bg-canvas/60 p-0.5"
        >
          {VIEWS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              aria-pressed={view === id}
              onClick={() => setView(id)}
              className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs text-ink-muted transition-colors hover:text-ink aria-pressed:bg-white/10 aria-pressed:text-ink"
            >
              <Icon aria-hidden="true" className="size-3.5" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {legend && view === 'chart' && <div className="mt-4">{legend}</div>}

      <div className={`mt-4 transition-opacity duration-300 ${busy ? 'opacity-50' : ''}`}>
        {view === 'chart' ? children : table}
      </div>

      {footnote && (
        <figcaption className="mt-4 text-xs leading-relaxed text-ink-subtle">{footnote}</figcaption>
      )}
    </figure>
  )
}
