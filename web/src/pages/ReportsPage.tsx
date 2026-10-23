import { Check, Copy, Download } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'
import { useRace, useRaces, useReport, useSimulation } from '../api/queries'
import type { RaceReport, RaceSummary } from '../api/types'
import { OutcomeCard } from '../charts/OutcomeCard'
import { Badge, Page, PageHeader } from '../components/PageHeader'
import { RacePicker } from '../components/RacePicker'
import { ReportMarkdown } from '../components/ReportMarkdown'
import { ErrorState, Loading, Notice } from '../components/States'
import {
  headingId,
  markdownDataUrl,
  reportCommand,
  reportHeadings,
  withoutTitle,
} from '../lib/report'
import { resolveRaceId } from '../lib/selection'

const COPIED_MS = 2000
const CHART_TITLE = 'График: прогноз против факта'
const CHART_ID = headingId(CHART_TITLE)

const BUTTON =
  'inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors'

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    if (!copied) return
    const timer = setTimeout(() => setCopied(false), COPIED_MS)
    return () => clearTimeout(timer)
  }, [copied])

  // The Clipboard API exists only in secure contexts (localhost, https).
  if (!navigator.clipboard) return null
  const Icon = copied ? Check : Copy
  return (
    <button
      type="button"
      onClick={() => navigator.clipboard.writeText(text).then(() => setCopied(true))}
      className={`${BUTTON} border border-line-strong text-ink-muted hover:bg-white/5 hover:text-ink`}
    >
      <Icon aria-hidden="true" className="size-4" />
      <span aria-live="polite">{copied ? 'Скопировано' : 'Копировать'}</span>
    </button>
  )
}

interface ReportAsideProps {
  report: RaceReport
  summary: RaceSummary
  withChart: boolean
}

function ReportAside({ report, summary, withChart }: ReportAsideProps) {
  const sections = reportHeadings(report.markdown)
  if (withChart) sections.push({ id: CHART_ID, text: CHART_TITLE })
  return (
    <aside className="space-y-6 lg:sticky lg:top-24 lg:col-start-2 lg:row-start-1 lg:self-start">
      <nav aria-label="Разделы отчёта" className="hidden lg:block">
        <p className="font-mono text-xs tracking-wider text-ink-subtle uppercase">Содержание</p>
        <ul className="mt-3 space-y-0.5 border-l border-line text-sm">
          {sections.map((section) => (
            <li key={section.id}>
              <a
                href={`#${section.id}`}
                className="-ml-px block border-l border-transparent py-1 pl-3 text-ink-muted transition-colors hover:border-ink-subtle hover:text-ink"
              >
                {section.text}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <div className="flex flex-wrap gap-2 lg:flex-col">
        <a
          href={markdownDataUrl(report.markdown)}
          download={report.file_name}
          className={`${BUTTON} bg-ink text-canvas hover:bg-ink-muted`}
        >
          <Download aria-hidden="true" className="size-4" />
          Скачать .md
        </a>
        <CopyButton text={report.markdown} />
      </div>

      <div className="hidden rounded-xl border border-line bg-surface/60 p-4 text-xs text-ink-subtle lg:block">
        То же с графиками в PNG:
        <code className="mt-2 block font-mono break-words text-ink-muted">
          {reportCommand(summary.season, summary.round)}
        </code>
      </div>
    </aside>
  )
}

export function ReportsPage() {
  const [params, setParams] = useSearchParams()
  const races = useRaces()
  const raceId = resolveRaceId(params.get('race'), races.data)
  const summary = races.data?.find((item) => item.race_id === raceId)
  const simulatable = summary?.simulatable ?? false
  const report = useReport(raceId)
  const race = useRace(simulatable ? raceId : undefined)
  const simulation = useSimulation(raceId, simulatable)

  if (races.isError)
    return (
      <Page>
        <title>Отчёты · F1 Strategy Lab</title>
        <ErrorState error={races.error} />
      </Page>
    )
  if (!races.data)
    return (
      <Page>
        <title>Отчёты · F1 Strategy Lab</title>
        <Loading label="Калибруем симулятор и загружаем гонки…" />
      </Page>
    )
  if (raceId === undefined || !summary) {
    return (
      <Page>
        <title>Отчёты · F1 Strategy Lab</title>
        <Notice title="В базе нет гонок">
          Загрузите данные: <code className="font-mono">python -m f1lab.ingest</code>.
        </Notice>
      </Page>
    )
  }

  const chart =
    race.data && simulation.data?.race_id === raceId ? (
      <section id={CHART_ID} aria-label={CHART_TITLE} className="scroll-mt-24">
        <OutcomeCard race={race.data} simulation={simulation.data} />
      </section>
    ) : null

  return (
    <Page>
      <title>{`Отчёт: ${summary.race_name} ${summary.season} · F1 Strategy Lab`}</title>
      <PageHeader
        eyebrow={`Отчёты · ${summary.season} · этап ${summary.round}`}
        title={summary.race_name}
        description="Авто-разбор гонки по шаблону: факты взяты из протоколов как есть, а оценки симулятора помечены отдельно."
        aside={
          simulatable ? (
            <Badge tone="success">со взглядом симулятора</Badge>
          ) : (
            <Badge>без симуляции</Badge>
          )
        }
      />

      <RacePicker
        races={races.data}
        value={raceId}
        onChange={(next) => setParams({ race: String(next) })}
      />

      {report.isError && <ErrorState error={report.error} />}
      {!report.data && !report.isError && (
        <Loading
          label={
            simulatable
              ? 'Собираем отчёт: симулятор прогоняет гонку и стратегии призёров…'
              : 'Собираем отчёт…'
          }
        />
      )}
      {report.data?.race_id === raceId && (
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_15rem]">
          {/* Actions first: on phones they stay above the long text. */}
          <ReportAside report={report.data} summary={summary} withChart={chart !== null} />
          <div className="min-w-0 space-y-8 lg:col-start-1 lg:row-start-1">
            <article
              aria-label="Отчёт"
              className="rounded-2xl border border-line bg-surface p-5 sm:p-8"
            >
              <ReportMarkdown markdown={withoutTitle(report.data.markdown)} />
            </article>
            {chart}
          </div>
        </div>
      )}
    </Page>
  )
}
