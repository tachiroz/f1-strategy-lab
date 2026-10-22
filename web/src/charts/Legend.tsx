import type { ReactNode } from 'react'
import { MarkerIcon } from './Marker'
import type { MarkerShape } from './series'

export interface LegendItem {
  label: ReactNode
  /** Key that mirrors the mark: a line, a bar swatch, a band or a marker. */
  key:
    | { kind: 'line'; swatch: string; marker?: { shape: MarkerShape; fill: string } }
    | { kind: 'bar'; swatch: string }
    | { kind: 'band'; swatch: string }
    | { kind: 'marker'; shape: MarkerShape; fill: string }
    | { kind: 'ring' }
}

function LegendKey({ itemKey }: { itemKey: LegendItem['key'] }) {
  switch (itemKey.kind) {
    case 'line':
      return (
        <span aria-hidden="true" className="relative inline-flex w-5 items-center justify-center">
          <span className={`h-0.5 w-5 rounded-full ${itemKey.swatch}`} />
          {itemKey.marker && (
            <span className="absolute">
              <MarkerIcon shape={itemKey.marker.shape} className={itemKey.marker.fill} />
            </span>
          )}
        </span>
      )
    case 'bar':
      return <span aria-hidden="true" className={`size-2.5 rounded-[3px] ${itemKey.swatch}`} />
    case 'band':
      return (
        <span aria-hidden="true" className={`h-2 w-5 rounded-full opacity-40 ${itemKey.swatch}`} />
      )
    case 'marker':
      return <MarkerIcon shape={itemKey.shape} className={itemKey.fill} />
    case 'ring':
      return (
        <span
          aria-hidden="true"
          className="size-2.5 rounded-full border-[1.5px] border-ink-subtle"
        />
      )
  }
}

export function Legend({ items }: { items: readonly LegendItem[] }) {
  return (
    <ul aria-label="Легенда" className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-ink-muted">
      {items.map((item, index) => (
        <li key={index} className="flex items-center gap-2">
          <LegendKey itemKey={item.key} />
          {item.label}
        </li>
      ))}
    </ul>
  )
}
