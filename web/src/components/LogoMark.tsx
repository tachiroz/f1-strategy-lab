interface LogoMarkProps {
  className?: string
}

/** Red tile with three speed stripes; the same mark is used as the favicon. */
export function LogoMark({ className = 'size-8' }: LogoMarkProps) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={className}>
      <rect width="32" height="32" rx="8" className="fill-accent" />
      <path d="M6.5 23 10.5 9h3l-4 14z" className="fill-white" />
      <path d="M12.5 23 16.5 9h3l-4 14z" className="fill-white/70" />
      <path d="M18.5 23 22.5 9h3l-4 14z" className="fill-white/40" />
    </svg>
  )
}
