import { COMPOUND_BY_ID, COMPOUNDS, type CompoundId } from '../data/compounds'

/** Illustrative strategy only (not a real race): it shows what the simulator will compare. */
const EXAMPLE_STINTS: readonly { compound: CompoundId; laps: number }[] = [
  { compound: 'medium', laps: 18 },
  { compound: 'hard', laps: 25 },
  { compound: 'soft', laps: 15 },
]
const RACE_LAPS = EXAMPLE_STINTS.reduce((total, stint) => total + stint.laps, 0)

/** Laps after which the car pits: every stint end except the last one. */
const PIT_LAPS = EXAMPLE_STINTS.slice(0, -1).map((_, index) =>
  EXAMPLE_STINTS.slice(0, index + 1).reduce((total, stint) => total + stint.laps, 0),
)

const SIMULATOR_STAGE = 4
const METRICS = ['Средняя позиция', 'P(подиум)', 'P(очки)'] as const

export function StrategyPreview() {
  return (
    <div className="relative rounded-2xl border border-line bg-surface/70 p-5 shadow-2xl shadow-black/40 backdrop-blur sm:p-6">
      <div
        aria-hidden="true"
        className="absolute inset-x-10 -top-px h-px bg-linear-to-r from-transparent via-accent/80 to-transparent"
      />

      <div className="flex items-center justify-between gap-4">
        <h2 className="text-sm font-medium">Анатомия стратегии</h2>
        <span className="rounded-full border border-line px-2.5 py-0.5 font-mono text-[11px] text-ink-subtle">
          иллюстрация
        </span>
      </div>
      <p className="mt-1 text-sm text-ink-muted">
        Стратегия: список пит-стопов (круг, состав шин). {PIT_LAPS.length} остановки, {RACE_LAPS}{' '}
        кругов.
      </p>

      <div className="mt-6 flex h-11 gap-1" role="img" aria-label="Пример стратегии по стинтам">
        {EXAMPLE_STINTS.map((stint, index) => {
          const compound = COMPOUND_BY_ID[stint.compound]
          return (
            <div
              key={index}
              style={{ flexGrow: stint.laps }}
              className={`${compound.swatch} flex basis-0 items-center overflow-hidden rounded-md px-2.5 first:rounded-l-lg last:rounded-r-lg`}
            >
              <span
                className={`${compound.onSwatch} truncate font-mono text-[11px] font-semibold uppercase`}
              >
                {compound.label} · {stint.laps}
              </span>
            </div>
          )
        })}
      </div>

      <div className="relative mt-2 h-4 font-mono text-[10px] text-ink-subtle tabular-nums">
        <span className="absolute left-0">L1</span>
        {PIT_LAPS.map((lap) => (
          <span
            key={lap}
            style={{ left: `${(lap / RACE_LAPS) * 100}%` }}
            className="absolute -translate-x-1/2 text-ink-muted"
          >
            PIT L{lap}
          </span>
        ))}
        <span className="absolute right-0">L{RACE_LAPS}</span>
      </div>

      <ul className="mt-5 flex flex-wrap gap-x-4 gap-y-2" aria-label="Цвета составов шин">
        {COMPOUNDS.map((compound) => (
          <li key={compound.id} className="flex items-center gap-1.5 text-xs text-ink-muted">
            <span aria-hidden="true" className={`${compound.swatch} size-2.5 rounded-full`} />
            {compound.label}
          </li>
        ))}
      </ul>

      <dl className="mt-6 grid grid-cols-3 gap-2 sm:gap-3">
        {METRICS.map((metric) => (
          <div key={metric} className="rounded-xl border border-line bg-canvas/60 p-3">
            <dt className="text-[11px] leading-tight text-ink-subtle sm:text-xs">{metric}</dt>
            <dd className="mt-2 font-mono text-2xl text-ink-muted tabular-nums">—</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-ink-subtle">
        Метрики посчитает симулятор на Этапе {SIMULATOR_STAGE}.
      </p>
    </div>
  )
}
