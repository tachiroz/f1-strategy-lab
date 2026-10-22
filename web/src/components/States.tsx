import { CircleAlert, LoaderCircle, PlugZap } from 'lucide-react'
import type { ReactNode } from 'react'
import { ApiError } from '../api/client'

const API_COMMAND = 'uvicorn f1lab.api.main:app'

export function Loading({ label = 'Загружаем данные…' }: { label?: string }) {
  return (
    <div
      role="status"
      className="flex min-h-40 items-center justify-center gap-3 rounded-2xl border border-line bg-surface/60 text-sm text-ink-muted"
    >
      <LoaderCircle aria-hidden="true" className="size-4 motion-safe:animate-spin" />
      {label}
    </div>
  )
}

interface NoticeProps {
  title: string
  children: ReactNode
  tone?: 'error' | 'info'
}

export function Notice({ title, children, tone = 'info' }: NoticeProps) {
  const Icon = tone === 'error' ? CircleAlert : PlugZap
  return (
    <div
      role={tone === 'error' ? 'alert' : 'note'}
      className="flex gap-3 rounded-2xl border border-line bg-surface p-5 text-sm"
    >
      <Icon
        aria-hidden="true"
        className={`mt-0.5 size-5 shrink-0 ${tone === 'error' ? 'text-accent' : 'text-ink-muted'}`}
      />
      <div className="min-w-0">
        <p className="font-medium">{title}</p>
        <div className="mt-1 text-ink-muted">{children}</div>
      </div>
    </div>
  )
}

/** Explains a failed request; when the API is down, says how to start it. */
export function ErrorState({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.unreachable) {
    return (
      <Notice title="API не запущен" tone="error">
        Дашборд берёт данные у локального API. Запустите его в корне репозитория:{' '}
        <code className="rounded bg-canvas px-1.5 py-0.5 font-mono text-xs text-ink">
          {API_COMMAND}
        </code>
        . Как загрузить данные, описано в README.
      </Notice>
    )
  }
  const message = error instanceof Error ? error.message : String(error)
  return (
    <Notice title="Не получилось загрузить данные" tone="error">
      {message}
    </Notice>
  )
}
