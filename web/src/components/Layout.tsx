import { Link, NavLink, Outlet } from 'react-router'
import { cn } from '@/lib/utils'

export const NOTICE = 'Lensor helps you read contracts faster. It does not give legal advice.'

function Logo() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="9" cy="12" r="7" stroke="#201D1D" strokeWidth="2" />
      <circle cx="15" cy="12" r="7" fill="#0004F6" />
    </svg>
  )
}

const NAV = [
  { to: '/', label: 'Contracts', end: true },
  { to: '/ask', label: 'Ask', end: false },
  { to: '/eval', label: 'Accuracy', end: false },
]

export function Layout() {
  return (
    <div className="flex min-h-svh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:z-10 focus:bg-white focus:p-3"
      >
        Skip to the content
      </a>
      <header className="flex flex-wrap items-stretch border-b border-line bg-surface">
        <Link
          to="/"
          className="inline-flex min-h-[72px] items-center gap-2.5 px-6 text-[26px] font-medium tracking-[-0.035em] text-ink no-underline"
        >
          <Logo />
          Lensor
        </Link>
        <p className="m-0 hidden w-[150px] items-center px-5 text-[13px] leading-[1.3] md:flex">
          Contract review, checked against lawyer labels
        </p>
        <nav aria-label="Main" className="flex flex-[1_1_380px] flex-wrap items-stretch">
          {NAV.map((item, i) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  'inline-flex min-h-[56px] flex-1 items-end gap-2 border-l border-line px-5 pb-3.5 text-sm text-ink no-underline sm:min-h-[72px] sm:min-w-[150px] sm:flex-none',
                  i === NAV.length - 1 && 'border-r',
                  isActive && 'font-semibold',
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive ? <span aria-hidden="true" className="mb-1.5 size-[7px] bg-blue" /> : null}
                  {item.label}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-stretch gap-2 p-2">
          <Link
            to="/upload"
            className="relative inline-flex min-h-12 min-w-[150px] items-end rounded-[2px] bg-blue px-4 pb-3 text-sm text-white no-underline"
          >
            Upload a contract
            <span
              aria-hidden="true"
              className="absolute top-[9px] right-[9px] size-[7px] border-t-[1.5px] border-r-[1.5px] border-white"
            />
          </Link>
          <span className="inline-flex items-end px-3 pb-3 text-[13px] text-muted-ink">
            Not legal advice
          </span>
        </div>
      </header>
      <main id="main" className="flex-1">
        <Outlet />
      </main>
      <footer className="flex flex-wrap justify-between gap-4 bg-surface px-4 py-8 text-[13px] text-muted-ink sm:px-10">
        <span>{NOTICE}</span>
        <span>
          Demo contracts from{' '}
          <a className="text-muted-ink" href="https://www.atticusprojectai.org/cuad">
            CUAD by The Atticus Project
          </a>
          , CC BY 4.0.
        </span>
      </footer>
    </div>
  )
}
