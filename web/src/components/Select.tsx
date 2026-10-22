import { ChevronDown } from 'lucide-react'
import { type ReactNode, useId } from 'react'

export interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

interface SelectProps {
  label: string
  value: string
  options: readonly SelectOption[]
  onChange: (value: string) => void
  className?: string
}

/** Native select (keyboard and screen-reader friendly) styled for the dark theme. */
export function Select({ label, value, options, onChange, className = '' }: SelectProps) {
  const id = useId()
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${className}`}>
      <label htmlFor={id} className="text-xs text-ink-subtle">
        {label}
      </label>
      <div className="relative">
        <select
          id={id}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="w-full appearance-none truncate rounded-lg border border-line-strong bg-surface py-2 pr-9 pl-3 text-sm text-ink transition-colors hover:border-ink-subtle focus-visible:border-accent focus-visible:outline-none"
        >
          {options.map((option) => (
            <option key={option.value} value={option.value} disabled={option.disabled}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown
          aria-hidden="true"
          className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-ink-subtle"
        />
      </div>
    </div>
  )
}

interface SegmentedProps<T extends string | number> {
  label: string
  value: T
  options: readonly { value: T; label: ReactNode }[]
  onChange: (value: T) => void
}

/** Small button group for a handful of mutually exclusive choices. */
export function Segmented<T extends string | number>({
  label,
  value,
  options,
  onChange,
}: SegmentedProps<T>) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs text-ink-subtle">{label}</span>
      <div
        role="group"
        aria-label={label}
        className="inline-flex rounded-lg border border-line-strong bg-surface p-0.5"
      >
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={option.value === value}
            onClick={() => onChange(option.value)}
            className="rounded-md px-3 py-1.5 font-mono text-sm text-ink-muted tabular-nums transition-colors hover:text-ink aria-pressed:bg-white/10 aria-pressed:text-ink"
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  )
}
