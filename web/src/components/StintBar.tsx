import type { Stint } from '../api/types'
import { useElementWidth } from '../charts/useElementWidth'
import { compoundFromApi, compoundLabel } from '../data/compounds'
import { describeStints, SEGMENT_GAP_PX, stintLabel, stintLaps } from '../lib/stints'

interface StintBarProps {
  stints: readonly Stint[]
  raceLaps: number
  /** `sm`: thin bar for tables; `md`: labelled bar for cards; `lg`: hero. */
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

/** A strategy as coloured stints; each stint's width is its number of laps. */
export function StintBar({ stints, raceLaps, size = 'md', className = '' }: StintBarProps) {
  const [ref, width] = useElementWidth<HTMLDivElement>()
  const height = { sm: 'h-2', md: 'h-7', lg: 'h-11' }[size]
  const labelled = size !== 'sm'
  const usable = width - SEGMENT_GAP_PX * (stints.length - 1)
  return (
    <div
      ref={ref}
      role="img"
      aria-label={describeStints(stints)}
      className={`flex gap-0.5 ${height} ${className}`}
    >
      {stints.map((stint, index) => {
        const compound = compoundFromApi(stint.compound)
        const laps = stintLaps(stint)
        const label = labelled
          ? stintLabel(compound?.label ?? stint.compound, laps, (usable * laps) / raceLaps)
          : ''
        return (
          <div
            key={index}
            title={`${compoundLabel(stint.compound)}: круги ${stint.first_lap}–${stint.last_lap}`}
            style={{ flexGrow: laps }}
            className={`${compound?.swatch ?? 'bg-ink-subtle'} flex basis-0 items-center rounded-[3px] first:rounded-l-md last:rounded-r-md ${
              labelled ? 'px-2' : ''
            }`}
          >
            {label && (
              <span
                aria-hidden="true"
                className={`${compound?.onSwatch ?? 'text-white'} font-mono text-[11px] font-semibold whitespace-nowrap uppercase`}
              >
                {label}
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}
