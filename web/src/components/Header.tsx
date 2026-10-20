import { ArrowUpRight } from 'lucide-react'
import { REPO_URL } from '../config'
import { LAST_DONE_STAGE, STAGES } from '../data/stages'
import { LogoMark } from './LogoMark'

/** Sections of the future dashboard; only the overview exists for now. */
const NAV_ITEMS = [
  { label: 'Обзор', available: true },
  { label: 'Гонки', available: false },
  { label: 'Шины', available: false },
  { label: 'Стратегии', available: false },
  { label: 'Отчёты', available: false },
] as const

export function Header() {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-canvas/70 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-8 px-4 sm:px-6">
        <a href="/" className="flex items-center gap-3">
          <LogoMark />
          <span className="font-semibold tracking-tight">F1 Strategy Lab</span>
        </a>

        <nav aria-label="Разделы" className="hidden md:block">
          <ul className="flex items-center gap-1 text-sm">
            {NAV_ITEMS.map(({ label, available }) => (
              <li key={label}>
                {available ? (
                  <a
                    href="/"
                    aria-current="page"
                    className="rounded-md bg-white/5 px-3 py-1.5 font-medium text-ink"
                  >
                    {label}
                  </a>
                ) : (
                  <span
                    aria-disabled="true"
                    title="Появится вместе с дашбордом"
                    className="cursor-not-allowed rounded-md px-3 py-1.5 text-ink-subtle"
                  >
                    {label}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </nav>

        <div className="ml-auto flex items-center gap-4">
          <span className="hidden font-mono text-xs text-ink-subtle tabular-nums sm:inline">
            Готово {LAST_DONE_STAGE}/{STAGES.length}
          </span>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 rounded-lg border border-line-strong px-3 py-1.5 text-sm text-ink-muted transition-colors hover:bg-white/5 hover:text-ink"
          >
            GitHub
            <ArrowUpRight aria-hidden="true" className="size-4" />
          </a>
        </div>
      </div>
    </header>
  )
}
