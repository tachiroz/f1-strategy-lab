import { ArrowUpRight } from 'lucide-react'
import { NavLink, useSearchParams } from 'react-router'
import { REPO_URL } from '../config'
import { LAST_DONE_STAGE, STAGES } from '../data/stages'
import { LogoMark } from './LogoMark'

interface NavItem {
  label: string
  to?: string
  /** Carry the selected race over to this section. */
  keepsRace?: boolean
  hint?: string
}

const NAV_ITEMS: readonly NavItem[] = [
  { label: 'Обзор', to: '/' },
  { label: 'Гонки', to: '/races', keepsRace: true },
  { label: 'Шины', to: '/tyres', keepsRace: true },
  { label: 'Стратегии', to: '/strategy', keepsRace: true },
  { label: 'Отчёты', hint: 'Появится на Этапе 6: авто-разбор гонки' },
]

const LINK_CLASS =
  'rounded-md px-3 py-1.5 whitespace-nowrap text-ink-muted transition-colors hover:bg-white/5 hover:text-ink aria-[current=page]:bg-white/8 aria-[current=page]:font-medium aria-[current=page]:text-ink'

function NavItems() {
  const [params] = useSearchParams()
  const race = params.get('race')
  return NAV_ITEMS.map(({ label, to, keepsRace, hint }) => (
    <li key={label}>
      {to ? (
        <NavLink to={keepsRace && race ? `${to}?race=${race}` : to} end className={LINK_CLASS}>
          {label}
        </NavLink>
      ) : (
        <span
          aria-disabled="true"
          title={hint}
          className="cursor-not-allowed rounded-md px-3 py-1.5 whitespace-nowrap text-ink-subtle/70"
        >
          {label}
        </span>
      )}
    </li>
  ))
}

export function Header() {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-canvas/75 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-8 px-4 sm:px-6">
        <NavLink to="/" className="flex items-center gap-3">
          <LogoMark />
          <span className="font-semibold tracking-tight">F1 Strategy Lab</span>
        </NavLink>

        <nav aria-label="Разделы" className="hidden md:block">
          <ul className="flex items-center gap-1 text-sm">
            <NavItems />
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

      <nav aria-label="Разделы (мобильная версия)" className="border-t border-line md:hidden">
        <ul className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-2 py-2 text-sm">
          <NavItems />
        </ul>
      </nav>
    </header>
  )
}
