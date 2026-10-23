import { isValidElement, type ReactNode } from 'react'
import Markdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { headingId } from '../lib/report'

/** Plain text of rendered children (for heading anchors). */
function textOf(node: ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (isValidElement<{ children?: ReactNode }>(node)) return textOf(node.props.children)
  return ''
}

/** The report's Markdown elements in the dashboard style (raw HTML is never rendered). */
const COMPONENTS: Components = {
  h1: () => null,
  h2: ({ children }) => (
    <h2
      id={headingId(textOf(children))}
      className="mt-10 scroll-mt-24 border-t border-line pt-8 text-xl font-semibold tracking-tight text-ink"
    >
      {children}
    </h2>
  ),
  p: ({ children }) => <p className="mt-4 leading-7 text-pretty text-ink-muted">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
  ul: ({ children }) => (
    <ul className="mt-4 list-disc space-y-2 pl-5 marker:text-ink-subtle [li_&]:mt-2">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="mt-4 list-decimal space-y-1 pl-5 tabular-nums marker:text-ink-subtle">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="pl-1 leading-7 text-ink-muted">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="mt-4 rounded-xl border-l-2 border-accent bg-canvas/60 px-4 py-3 text-sm [&>p]:mt-0 [&>p+p]:mt-2">
      {children}
    </blockquote>
  ),
  code: ({ children }) => (
    <code className="rounded bg-canvas px-1.5 py-0.5 font-mono text-[0.85em] text-ink">
      {children}
    </code>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-ink underline decoration-line-strong underline-offset-4 transition-colors hover:decoration-ink"
    >
      {children}
    </a>
  ),
  hr: () => <hr className="mt-10 border-line" />,
  table: ({ children }) => (
    <div className="mt-4 overflow-x-auto rounded-xl border border-line">
      <table className="w-full text-sm tabular-nums">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-canvas/60 text-left text-xs text-ink-subtle">{children}</thead>
  ),
  th: ({ children, style }) => (
    <th style={style} className="px-3 py-2 font-medium whitespace-nowrap">
      {children}
    </th>
  ),
  td: ({ children, style }) => (
    <td style={style} className="border-t border-line px-3 py-2 whitespace-nowrap text-ink-muted">
      {children}
    </td>
  ),
}

/** A race report from the API, rendered from its Markdown. */
export function ReportMarkdown({ markdown }: { markdown: string }) {
  return (
    <div className="[&>*:first-child]:mt-0">
      <Markdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {markdown}
      </Markdown>
    </div>
  )
}
