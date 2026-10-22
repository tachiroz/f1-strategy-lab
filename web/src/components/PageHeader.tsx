import type { ReactNode } from 'react'

interface PageHeaderProps {
  eyebrow: string
  title: ReactNode
  description?: ReactNode
  /** Badges or meta information next to the title. */
  aside?: ReactNode
}

export function PageHeader({ eyebrow, title, description, aside }: PageHeaderProps) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <p className="font-mono text-xs tracking-wider text-accent uppercase">{eyebrow}</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
          {title}
        </h1>
        {description && (
          <p className="mt-3 max-w-2xl text-sm text-pretty text-ink-muted sm:text-base">
            {description}
          </p>
        )}
      </div>
      {aside && <div className="flex shrink-0 flex-wrap gap-2">{aside}</div>}
    </div>
  )
}

export function Badge({
  children,
  tone = 'muted',
}: {
  children: ReactNode
  tone?: 'muted' | 'success'
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${
        tone === 'success'
          ? 'border-success/30 bg-success/10 text-success'
          : 'border-line-strong text-ink-muted'
      }`}
    >
      {children}
    </span>
  )
}

/** Page container shared by the dashboard sections. */
export function Page({ children }: { children: ReactNode }) {
  return <div className="mx-auto max-w-6xl space-y-8 px-4 py-10 sm:px-6 sm:py-14">{children}</div>
}
