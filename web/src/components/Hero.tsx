import { ArrowDown, ArrowUpRight } from 'lucide-react'
import { REPO_URL } from '../config'
import { LAST_DONE_STAGE, STAGES, stageStatus } from '../data/stages'
import { StrategyPreview } from './StrategyPreview'

export function Hero() {
  const nextStage = STAGES.find((stage) => stageStatus(stage.id) === 'next')

  return (
    <section className="relative overflow-hidden">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-grid" />

      <div className="relative mx-auto grid max-w-6xl gap-12 px-4 py-16 sm:px-6 sm:py-24 lg:grid-cols-[1.05fr_1fr] lg:items-center">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full border border-line bg-surface/60 px-3 py-1 font-mono text-xs tracking-wider text-ink-muted uppercase">
            <span className="relative flex size-2">
              <span className="absolute inline-flex size-full rounded-full bg-accent opacity-75 motion-safe:animate-ping" />
              <span className="relative inline-flex size-2 rounded-full bg-accent" />
            </span>
            {nextStage
              ? `Этап ${LAST_DONE_STAGE}/${STAGES.length} готов · далее: ${nextStage.title}`
              : 'Все этапы готовы'}
          </p>

          <h1 className="mt-6 text-4xl font-semibold tracking-tight text-balance sm:text-5xl lg:text-6xl">
            Гоночная стратегия F1,{' '}
            <span className="bg-linear-to-r from-accent to-tyre-medium bg-clip-text text-transparent">
              просчитанная
            </span>{' '}
            на данных
          </h1>

          <p className="mt-6 max-w-xl text-lg text-pretty text-ink-muted">
            Оцениваем деградацию шин по реальным гонкам, моделируем пит-стопы и методом Монте-Карло
            считаем распределение результатов: финишную позицию, время и вероятность подиума.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href="#roadmap"
              className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white shadow-lg shadow-accent/25 transition hover:brightness-110"
            >
              Дорожная карта
              <ArrowDown aria-hidden="true" className="size-4" />
            </a>
            <a
              href={REPO_URL}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-lg border border-line-strong px-4 py-2.5 text-sm font-medium text-ink transition-colors hover:bg-white/5"
            >
              Исходный код
              <ArrowUpRight aria-hidden="true" className="size-4" />
            </a>
          </div>
        </div>

        <StrategyPreview />
      </div>
    </section>
  )
}
