const STACK = [
  'Python 3.12',
  'OpenF1',
  'Jolpica-F1',
  'SQLite',
  'SQLAlchemy',
  'pandas',
  'NumPy',
  'SciPy',
  'FastAPI',
  'Jinja2',
  'React',
  'React Router',
  'TanStack Query',
  'D3',
  'react-markdown',
  'TypeScript',
  'Tailwind CSS',
] as const

export function Footer() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <p className="font-mono text-xs tracking-wider text-ink-subtle uppercase">Под капотом</p>
        <ul className="mt-3 flex flex-wrap gap-2">
          {STACK.map((item) => (
            <li
              key={item}
              className="rounded-md border border-line bg-surface/60 px-2.5 py-1 font-mono text-xs text-ink-muted"
            >
              {item}
            </li>
          ))}
        </ul>
        <div className="mt-8 flex flex-col gap-2 text-sm text-ink-subtle sm:flex-row sm:justify-between">
          <p>Данные: OpenF1 и Jolpica-F1. Неофициальный проект, не связан с Formula 1 и FIA.</p>
          <p>MIT License</p>
        </div>
      </div>
    </footer>
  )
}
