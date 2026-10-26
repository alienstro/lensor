import type { ReactNode } from 'react'
import { Link, type LinkProps } from 'react-router'
import type { RiskLevel } from '@/api/types'
import { cn } from '@/lib/utils'

/** The diagonal arrow of the action buttons. */
export function ArrowIcon({ size = 18 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="square"
      aria-hidden="true"
    >
      <path d="M6 6l12 12" />
      <path d="M18 7v11H7" />
    </svg>
  )
}

type Tone = 'black' | 'blue'

const TONES: Record<Tone, { label: string; tile: string }> = {
  black: { label: 'bg-black text-white', tile: 'bg-blue text-white' },
  blue: { label: 'bg-blue text-white', tile: 'bg-white text-ink' },
}

function ArrowParts({ tone, children, tall }: { tone: Tone; children: ReactNode; tall?: boolean }) {
  const t = TONES[tone]
  return (
    <>
      <span
        className={cn(
          'flex flex-1 items-center rounded-l px-5 text-sm',
          tall ? 'min-h-13 justify-center text-base' : 'min-h-12',
          t.label,
        )}
      >
        {children}
      </span>
      <span
        className={cn(
          'inline-flex items-center justify-center rounded-r',
          tall ? 'w-13' : 'w-12',
          t.tile,
        )}
      >
        <ArrowIcon size={tall ? 18 : 16} />
      </span>
    </>
  )
}

/** A link with a label and a square arrow tile. */
export function ArrowLink({
  tone = 'black',
  tall,
  className,
  children,
  ...props
}: LinkProps & { tone?: Tone; tall?: boolean }) {
  return (
    <Link {...props} className={cn('group flex items-stretch no-underline', className)}>
      <ArrowParts tone={tone} tall={tall}>
        {children}
      </ArrowParts>
    </Link>
  )
}

/** A button with a label and a square arrow tile. */
export function ArrowButton({
  tone = 'black',
  tall,
  className,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { tone?: Tone; tall?: boolean }) {
  return (
    <button
      type="button"
      {...props}
      className={cn(
        'flex cursor-pointer items-stretch border-0 bg-transparent p-0 font-[inherit] disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
    >
      <ArrowParts tone={tone} tall={tall}>
        {children}
      </ArrowParts>
    </button>
  )
}

export type PillLevel = RiskLevel | 'none'

const PILL_TEXT: Record<PillLevel, string> = {
  high: 'High risk',
  medium: 'Medium risk',
  low: 'Low risk',
  none: 'Not found',
}

/** The risk level of a contract or a clause. */
export function RiskPill({
  level,
  onDark,
  short,
}: {
  level: PillLevel
  onDark?: boolean
  short?: boolean
}) {
  const style: Record<PillLevel, string> = {
    high: onDark ? 'bg-risk-on-dark text-black' : 'bg-risk text-white',
    medium: onDark ? 'border border-white/70 text-white' : 'border border-ink text-ink',
    low: onDark ? 'bg-white/15 text-white' : 'bg-[#e6e6e6] text-ink',
    none: onDark
      ? 'border border-dashed border-white/60 text-white/80'
      : 'border border-dashed border-muted-ink text-muted-ink',
  }
  const text = short && level !== 'none' ? PILL_TEXT[level].replace(' risk', '') : PILL_TEXT[level]
  return (
    <span
      className={cn(
        'inline-flex h-7 shrink-0 items-center self-start rounded-full px-3 text-[13px] whitespace-nowrap',
        style[level],
      )}
    >
      {text}
    </span>
  )
}

/** A small blue label, a centred heading, and one line of grey text. */
export function SectionHeading({
  eyebrow,
  title,
  text,
  id,
}: {
  eyebrow: string
  title: ReactNode
  text?: ReactNode
  id?: string
}) {
  return (
    <div className="flex flex-col items-center gap-4 text-center">
      <p className="m-0 text-[13px] font-medium text-blue">{eyebrow}</p>
      <h2
        id={id}
        className="m-0 max-w-[14em] text-[34px] leading-[1.04] font-medium tracking-[-0.035em] sm:text-[52px]"
      >
        {title}
      </h2>
      {text ? <p className="m-0 max-w-[46ch] text-muted-ink">{text}</p> : null}
    </div>
  )
}

/** A white card with a blue icon tile. */
export function IconCard({
  icon,
  title,
  children,
  footer,
  className,
}: {
  icon: ReactNode
  title: ReactNode
  children?: ReactNode
  footer?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex flex-col gap-4 rounded-lg bg-surface p-6', className)}>
      <span className="inline-flex size-8 items-center justify-center rounded bg-blue text-white">
        {icon}
      </span>
      <h3 className="m-0 text-xl leading-tight font-medium tracking-[-0.02em]">{title}</h3>
      {children ? <div className="text-sm text-muted-ink">{children}</div> : null}
      {footer ? <div className="mt-auto">{footer}</div> : null}
    </div>
  )
}

/** A black card with a title and rows of a large value and a short label. */
export function StatCard({
  title,
  rows,
  action,
}: {
  title: string
  rows: { value: ReactNode; label: ReactNode }[]
  action?: ReactNode
}) {
  return (
    <div className="min-w-0 rounded-lg bg-black p-6 text-white">
      <p className="m-0 mb-1 text-[13px] text-[#bdbdbd]">{title}</p>
      <dl className="m-0">
        {rows.map((row, i) => (
          <div
            key={i}
            className="flex items-baseline justify-between gap-6 border-b border-[#333] py-4"
          >
            <dt className="max-w-[250px] text-right text-sm text-[#e0e0e0] order-2">{row.label}</dt>
            <dd className="m-0 text-[22px] font-medium order-1">{row.value}</dd>
          </div>
        ))}
      </dl>
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  )
}

/** A black band with a large white heading and a hairline. */
export function BlackBand({
  title,
  id,
  children,
}: {
  title: ReactNode
  id: string
  children: ReactNode
}) {
  return (
    <section aria-labelledby={id} className="bg-black px-4 py-16 text-white sm:px-10 sm:py-20">
      <h2
        id={id}
        className="m-0 max-w-[12em] text-[34px] leading-[1.04] font-medium tracking-[-0.035em] sm:text-[52px]"
      >
        {title}
      </h2>
      <div className="my-8 h-px bg-[#333]" />
      {children}
    </section>
  )
}

/** A short message for a loading or an error state. */
export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'error' }) {
  return (
    <p
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn(
        'm-0 rounded-lg bg-surface p-6 text-sm',
        tone === 'error' ? 'text-risk' : 'text-muted-ink',
      )}
    >
      {children}
    </p>
  )
}
