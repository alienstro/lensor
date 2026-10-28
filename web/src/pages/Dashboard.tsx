import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { getDashboard, listContracts } from '@/api/client'
import type { ContractSummary, Dashboard as DashboardData, RiskLevel } from '@/api/types'
import {
  ArrowLink,
  BlackBand,
  Notice,
  RiskPill,
  SectionHeading,
  StatCard,
} from '@/components/ui-kit'
import { CLAUSES, clauseInfo, FAMILY_COLOR } from '@/lib/clauses'
import { cn } from '@/lib/utils'

type Filter = 'all' | RiskLevel

const TABS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'high', label: 'High risk' },
  { key: 'medium', label: 'Medium risk' },
  { key: 'low', label: 'Low risk' },
]

function found(dashboard: DashboardData | undefined, clauseType: string) {
  return dashboard?.by_clause.find((row) => row.clause_type === clauseType)?.found ?? 0
}

function needHeading(high: number) {
  if (high === 0) return 'No contract needs a close read'
  return high === 1 ? '1 contract needs a close read' : `${high} contracts need a close read`
}

function DocIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="mt-0.5 flex-none"
    >
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
      <path d="M9 14h6" />
    </svg>
  )
}

const STATUS_TEXT: Record<string, string> = {
  queued: 'Waiting to start',
  parsing: 'Lensor is reading it',
  chunking: 'Lensor is reading it',
  embedding: 'Lensor is reading it',
  extracting: 'Lensor is finding the clauses',
  failed: 'Lensor could not read it',
}

function ContractCard({ contract }: { contract: ContractSummary }) {
  const dark = contract.risk_level === 'high'
  const ready = contract.status === 'ready' && contract.risk_level !== null
  return (
    <li
      className={cn(
        'flex flex-col gap-4 rounded-lg p-6',
        dark ? 'bg-night text-white' : 'bg-surface text-ink',
      )}
    >
      {ready ? (
        <RiskPill level={contract.risk_level!} onDark={dark} />
      ) : (
        <span className="inline-flex h-7 items-center self-start rounded-full border border-dashed border-muted-ink px-3 text-[13px] text-muted-ink">
          {STATUS_TEXT[contract.status] ?? contract.status}
        </span>
      )}
      <div>
        <h3 className="m-0 mt-2 text-[26px] leading-[1.1] font-medium tracking-[-0.025em] break-words">
          {contract.title}
        </h3>
        <p className={cn('m-0 mt-1.5 text-sm', dark ? 'text-[#bdbdbd]' : 'text-muted-ink')}>
          {contract.source === 'upload' ? 'Uploaded' : 'Demo contract from CUAD'}
          {ready ? `, ${contract.risk_score} of 100 points` : ''}
        </p>
      </div>
      {ready ? (
        <div>
          <p className="m-0 mb-2 text-sm font-semibold">Main points:</p>
          {contract.reasons.length ? (
            <ul className="m-0 flex list-none flex-col gap-2 p-0 text-sm">
              {contract.reasons.slice(0, 3).map((reason) => (
                <li key={reason.clause_type} className="flex items-start gap-2.5">
                  <DocIcon />
                  {reason.text}
                </li>
              ))}
            </ul>
          ) : (
            <p className="m-0 text-sm">Lensor found no risky clause.</p>
          )}
        </div>
      ) : null}
      {contract.status !== 'failed' ? (
        <ArrowLink
          to={`/contracts/${contract.id}`}
          tone={dark ? 'blue' : 'black'}
          className="mt-auto pt-2"
        >
          Open the contract
        </ArrowLink>
      ) : null}
    </li>
  )
}

export function Dashboard() {
  const dashboard = useQuery({ queryKey: ['dashboard'], queryFn: getDashboard })
  const contracts = useQuery({
    queryKey: ['contracts'],
    queryFn: listContracts,
    // Poll while a contract is still in the pipeline.
    refetchInterval: (query) =>
      query.state.data?.some((c) => c.status !== 'ready' && c.status !== 'failed') ? 3000 : false,
  })
  const [filter, setFilter] = useState<Filter>('all')

  const all = contracts.data ?? []
  const counts: Record<Filter, number> = {
    all: all.length,
    high: all.filter((c) => c.risk_level === 'high').length,
    medium: all.filter((c) => c.risk_level === 'medium').length,
    low: all.filter((c) => c.risk_level === 'low').length,
  }
  const shown = filter === 'all' ? all : all.filter((c) => c.risk_level === filter)
  const high = dashboard.data?.by_level.high ?? 0

  return (
    <>
      <section className="px-4 pt-14 pb-10 sm:px-10">
        <p className="m-0 inline-flex items-center gap-2.5 border border-[#e3e3e3] bg-surface py-1.5 pr-1.5 pl-3 text-[15px] font-medium">
          Demo workspace
          <span className="bg-black px-2 py-0.5 text-[11px] font-semibold text-white">CUAD</span>
        </p>
        <h1 className="m-0 mt-7 max-w-[10.5em] text-[48px] leading-[0.98] font-medium tracking-[-0.045em] sm:text-[84px]">
          Your contracts, <span className="text-blue">checked for risk</span>.
        </h1>
        <p className="m-0 mt-7 max-w-[44ch]">
          Lensor reads each supplier contract and finds the 10 clauses that matter most. Every
          finding links to the exact text in the contract.
        </p>
      </section>

      <section className="flex flex-wrap items-center gap-8 bg-[linear-gradient(var(--bg)_0,var(--bg)_40px,var(--surface)_40px)] px-4 pb-12 sm:px-10">
        <div className="min-w-0 flex-[0_1_540px] sm:min-w-[300px]">
          <StatCard
            title="What needs a look"
            rows={[
              { value: high, label: 'Contracts with a high risk level' },
              {
                value: found(dashboard.data, 'Uncapped Liability'),
                label: 'Contracts with no limit for some claims',
              },
              {
                value: found(dashboard.data, 'Renewal Term'),
                label: 'Contracts that renew by themselves',
              },
            ]}
            action={
              <ArrowLink to="/ask" tone="blue" tall>
                Ask about these contracts
              </ArrowLink>
            }
          />
        </div>
        <div className="min-w-0 flex-[1_1_420px] pt-10">
          <p className="m-0 mb-5 text-[15px] font-medium">
            The 10 clauses Lensor checks in every contract
          </p>
          <ul className="m-0 grid list-none grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-x-6 gap-y-5 p-0">
            {CLAUSES.map((clause) => (
              <li
                key={clause.cuad}
                className="flex items-center gap-2.5 text-[17px] font-semibold tracking-[-0.01em] text-[#3a3a3a]"
              >
                <span
                  aria-hidden="true"
                  className="size-2.5 flex-none rounded-[2px]"
                  style={{ background: FAMILY_COLOR[clause.family] }}
                />
                {clause.plain}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="flex flex-col items-center gap-4 px-4 pt-18 pb-20 sm:px-10">
        <SectionHeading
          eyebrow="Contracts"
          title={needHeading(high)}
          text="Open a contract to see each risky clause, what it means, and where it is in the text."
        />
        <div
          role="group"
          aria-label="Show contracts by risk"
          className="mt-6 mb-2 flex flex-wrap justify-center border border-line bg-surface"
        >
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              aria-pressed={filter === tab.key}
              onClick={() => setFilter(tab.key)}
              className={cn(
                'min-h-12 min-w-[140px] cursor-pointer border-0 border-r border-line px-5 font-[inherit] text-sm last:border-r-0',
                filter === tab.key ? 'bg-black text-white' : 'bg-surface text-ink',
              )}
            >
              {tab.label} ({counts[tab.key]})
            </button>
          ))}
        </div>
        {contracts.isPending ? <Notice>Lensor is loading the contracts.</Notice> : null}
        {contracts.isError ? (
          <Notice tone="error">Lensor could not load the contracts. Try again later.</Notice>
        ) : null}
        {contracts.isSuccess && all.length === 0 ? (
          <div className="flex flex-col items-center gap-4 rounded-lg bg-surface p-8 text-center">
            <p className="m-0">There are no contracts yet. Upload one to start.</p>
            <ArrowLink to="/upload">Upload a contract</ArrowLink>
          </div>
        ) : null}
        {contracts.isSuccess && all.length > 0 && shown.length === 0 ? (
          <Notice>No contract has this risk level.</Notice>
        ) : null}
        {shown.length ? (
          <ul
            aria-label="Contracts"
            className="m-0 grid w-full list-none grid-cols-[repeat(auto-fill,minmax(min(300px,100%),1fr))] gap-4 p-0"
          >
            {shown.map((contract) => (
              <ContractCard key={contract.id} contract={contract} />
            ))}
          </ul>
        ) : null}
      </section>

      <BlackBand id="score-h" title="How Lensor sets the risk level">
        <div className="flex flex-wrap gap-x-16 gap-y-8">
          <p className="m-0 max-w-[40ch] flex-[1_1_300px] text-[15px] text-[#e0e0e0]">
            Lensor adds points for each risky clause it finds.
            <span className="mt-3 block text-xl leading-[1.35] text-[#bdbdbd]">
              60 points or more is high risk. 30 to 59 is medium risk. Below 30 is low risk.
            </span>
          </p>
          <dl className="m-0 grid flex-[1_1_420px] grid-cols-[minmax(0,1fr)_auto] text-[15px]">
            {(dashboard.data?.risk_rules ?? []).map((rule) => (
              <div key={rule.clause_type} className="contents">
                <dt className="border-b border-[#333] py-3">
                  {rule.text}
                  <span className="block text-[13px] text-[#9a9a9a]">
                    {clauseInfo(rule.clause_type).plain}
                    {rule.when_found ? ' found' : ' not found'}
                  </span>
                </dt>
                <dd className="m-0 border-b border-[#333] py-3 text-right text-[#bdbdbd]">
                  {rule.points} points
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </BlackBand>
    </>
  )
}
