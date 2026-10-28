import { useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useParams, useSearchParams } from 'react-router'
import { getContract } from '@/api/client'
import type { Clause, ContractDetail, RiskReason } from '@/api/types'
import { ClauseHighlighter } from '@/components/ClauseHighlighter'
import { ClausePanel } from '@/components/ClausePanel'
import { ArrowLink, Notice, SectionHeading } from '@/components/ui-kit'
import { clauseInfo } from '@/lib/clauses'

const LEVEL_TEXT = { high: 'High risk', medium: 'Medium risk', low: 'Low risk' } as const
const LEVEL_DOT = { high: 'var(--risk-on-dark)', medium: '#ffffff', low: '#9a9a9a' } as const

/** The clause type whose span contains a character offset. */
function clauseAt(clauses: Clause[], offset: number): Clause | undefined {
  return clauses.find((c) => c.spans.some(([start, end]) => start <= offset && offset < end))
}

function scrollToMark(start: number) {
  const mark = document.querySelector<HTMLElement>(`mark[data-start="${start}"]`)
  mark?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
}

function WarnIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
      <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
    </svg>
  )
}

function WatchCards({
  contract,
  onShow,
}: {
  contract: ContractDetail
  onShow: (clauseType: string, start: number) => void
}) {
  const reasons: RiskReason[] = contract.reasons.slice(0, 3)
  const byType = new Map(contract.clauses.map((c) => [c.clause_type, c]))
  const title =
    reasons.length === 0
      ? 'Nothing stands out'
      : reasons.length === 1
        ? '1 thing to read with care'
        : `${reasons.length} things to read with care`
  return (
    <section className="flex flex-col items-center gap-4 px-4 pt-18 pb-6 sm:px-10">
      <SectionHeading
        eyebrow="What to watch"
        title={title}
        text={reasons.length === 0 ? 'Lensor found no clause that adds to the risk score.' : undefined}
      />
      {reasons.length ? (
        <ul className="m-0 mt-6 grid w-full list-none grid-cols-[repeat(auto-fit,minmax(min(280px,100%),1fr))] gap-4 p-0">
          {reasons.map((reason) => {
            const clause = byType.get(reason.clause_type)
            const first = clause?.found ? clause.spans[0][0] : null
            return (
              <li key={reason.clause_type} className="flex flex-col gap-3 rounded-lg bg-surface p-6">
                <span className="inline-flex size-8 items-center justify-center rounded bg-blue text-white">
                  <WarnIcon />
                </span>
                <h3 className="m-0 mt-2 text-2xl leading-[1.15] font-medium tracking-[-0.02em]">
                  {reason.text}
                </h3>
                <p className="m-0 text-sm text-[#3a3a3a]">
                  {clause?.found
                    ? clause.summary || clauseInfo(reason.clause_type).plain
                    : clauseInfo(reason.clause_type).missing}{' '}
                  <span className="text-muted-ink">{reason.points} points.</span>
                </p>
                {first !== null ? (
                  <button
                    type="button"
                    onClick={() => onShow(reason.clause_type, first)}
                    className="mt-auto cursor-pointer self-start border-0 bg-transparent p-0 pt-2 font-[inherit] text-sm font-medium text-blue underline"
                  >
                    Show in the contract
                  </button>
                ) : null}
              </li>
            )
          })}
        </ul>
      ) : null}
    </section>
  )
}

export function ContractView() {
  const { id } = useParams()
  const contractId = Number(id)
  const [params] = useSearchParams()
  const { hash } = useLocation()
  const fromAsk = params.get('from') === 'ask'
  const [open, setOpen] = useState<string | null>(null)

  const query = useQuery({
    queryKey: ['contract', contractId],
    queryFn: () => getContract(contractId),
    enabled: Number.isInteger(contractId),
    refetchInterval: (q) => {
      const status = q.state.data?.status
      return status && status !== 'ready' && status !== 'failed' ? 3000 : false
    },
  })
  const contract = query.data

  // A link from a source in Ask ends with #<start>. Open that clause and show it.
  useEffect(() => {
    if (!contract || !hash) return
    const offset = Number(hash.slice(1))
    if (!Number.isInteger(offset)) return
    const clause = clauseAt(contract.clauses, offset)
    if (clause) setOpen(clause.clause_type)
    const span = clause?.spans.find(([s, e]) => s <= offset && offset < e)
    const timer = window.setTimeout(() => scrollToMark(span?.[0] ?? offset), 50)
    return () => window.clearTimeout(timer)
  }, [contract, hash])

  const show = useCallback((clauseType: string, start: number) => {
    setOpen(clauseType)
    window.setTimeout(() => scrollToMark(start), 0)
  }, [])
  const toggle = useCallback(
    (clauseType: string) => setOpen((current) => (current === clauseType ? null : clauseType)),
    [],
  )

  if (!Number.isInteger(contractId)) return <Page><Notice tone="error">This link has no valid contract id.</Notice></Page>
  if (query.isPending) return <Page><Notice>Lensor is loading the contract.</Notice></Page>
  if (query.isError || !contract) {
    return (
      <Page>
        <Notice tone="error">{query.error?.message ?? 'Lensor could not load this contract.'}</Notice>
      </Page>
    )
  }
  if (contract.status === 'failed') {
    return (
      <Page>
        <h1 className="m-0 mb-6 text-4xl font-medium">{contract.title}</h1>
        <Notice tone="error">{contract.status_detail ?? 'Lensor could not read this contract.'}</Notice>
      </Page>
    )
  }
  if (contract.status !== 'ready' || !contract.risk_level) {
    return (
      <Page>
        <h1 className="m-0 mb-6 text-4xl font-medium">{contract.title}</h1>
        <Notice>Lensor is still reading this contract. This page updates when it is ready.</Notice>
      </Page>
    )
  }

  const foundCount = contract.clauses.filter((c) => c.found).length
  const level = contract.risk_level
  return (
    <>
      {fromAsk ? (
        <div
          role="status"
          className="flex flex-wrap items-center justify-between gap-3 bg-blue px-4 py-3.5 text-white sm:px-10"
        >
          <span>
            You opened this from an answer. The cited clause is open on the right and outlined in
            the text.
          </span>
          <Link
            to="/ask"
            className="inline-flex min-h-10 items-center rounded border border-white px-4 text-white no-underline"
          >
            Back to the answer
          </Link>
        </div>
      ) : null}

      <div className="flex flex-wrap border-b border-line bg-surface">
        <div className="min-w-0 flex-[999_1_600px] px-4 pt-6 pb-12 sm:px-10">
          <Link to="/" className="inline-flex min-h-9 items-center text-sm text-muted-ink">
            Back to your contracts
          </Link>
          <h1 className="m-0 mt-4 max-w-[12em] text-[48px] leading-[0.92] font-normal tracking-[-0.055em] break-words sm:text-[88px]">
            {contract.title}
          </h1>
          {contract.overview ? <p className="m-0 mt-6 max-w-[60ch]">{contract.overview}</p> : null}
        </div>
        <aside className="min-w-0 flex-[1_1_400px] border-t border-line p-4 sm:border-t-0 sm:border-l sm:p-8">
          <div className="rounded-lg bg-black p-6 text-white">
            <p className="m-0 mb-1 text-[13px] text-[#bdbdbd]">Risk level</p>
            <div className="flex items-baseline justify-between gap-6 border-b border-[#333] py-4">
              <span className="inline-flex items-center gap-2.5 text-[22px] font-medium">
                <span
                  aria-hidden="true"
                  className="size-3 rounded-full"
                  style={{ background: LEVEL_DOT[level] }}
                />
                {LEVEL_TEXT[level]}
              </span>
              <span className="text-right text-sm text-[#e0e0e0]">
                {contract.risk_score} of 100 points
              </span>
            </div>
            <div className="flex items-baseline justify-between gap-6 border-b border-[#333] py-4">
              <span className="text-[22px] font-medium">{foundCount} of 10</span>
              <span className="text-right text-sm text-[#e0e0e0]">clauses found</span>
            </div>
            <ArrowLink
              to={`/ask?q=${encodeURIComponent(`What should I read with care in ${contract.title}?`)}`}
              tone="blue"
              tall
              className="mt-6"
            >
              Ask about this contract
            </ArrowLink>
          </div>
        </aside>
      </div>

      <WatchCards contract={contract} onShow={show} />

      <section className="flex flex-wrap items-start gap-4 px-4 pt-8 pb-20 sm:px-10">
        <article
          aria-label="Contract text"
          className="min-w-0 flex-[999_1_560px] rounded-lg bg-surface px-5 py-8 font-serif text-[17px] leading-[1.85] sm:px-12 sm:py-10"
        >
          <div className="mb-6 flex flex-wrap justify-between gap-2 font-sans text-sm">
            <span className="font-semibold">The contract</span>
            <span className="text-muted-ink">Coloured text is a clause Lensor found.</span>
          </div>
          <ClauseHighlighter
            text={contract.text}
            clauses={contract.clauses}
            selected={open}
            onSelect={toggle}
          />
        </article>
        <ClausePanel
          clauses={contract.clauses}
          open={open}
          onToggle={toggle}
          onShow={show}
          textLength={contract.text.length}
        />
      </section>
    </>
  )
}

function Page({ children }: { children: React.ReactNode }) {
  return <section className="mx-auto max-w-[880px] px-4 py-14 sm:px-6">{children}</section>
}
