import type { ReactNode } from 'react'

export interface Column<T> {
  key: string
  header: ReactNode
  cell: (row: T) => ReactNode
  /** Numbers align right and use tabular figures. */
  numeric?: boolean
  className?: string
}

interface DataTableProps<T> {
  columns: readonly Column<T>[]
  rows: readonly T[]
  rowKey: (row: T) => string
  caption?: string
  /** Rows to tone down (e.g. drivers who did not finish). */
  muted?: (row: T) => boolean
}

/** Compact table used as the accessible twin of every chart and for race tables. */
export function DataTable<T>({ columns, rows, rowKey, caption, muted }: DataTableProps<T>) {
  return (
    <div className="relative -mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
      <table className="w-full min-w-max border-collapse text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr className="border-b border-line text-left text-xs text-ink-subtle">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={`px-2 py-2 font-medium first:pl-0 last:pr-0 ${
                  column.numeric ? 'text-right' : ''
                } ${column.className ?? ''}`}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              className={`border-b border-line/60 last:border-0 ${muted?.(row) ? 'text-ink-subtle' : ''}`}
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={`px-2 py-2 first:pl-0 last:pr-0 ${
                    column.numeric ? 'text-right font-mono tabular-nums' : ''
                  } ${column.className ?? ''}`}
                >
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
