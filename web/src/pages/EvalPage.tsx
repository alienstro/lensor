import { useQuery } from '@tanstack/react-query'
import { getLatestEval } from '@/api/client'
import type { EvalResultRow, LatestEval } from '@/api/types'
import { ArrowLink, BlackBand, IconCard, Notice, SectionHeading, StatCard } from '@/components/ui-kit'
import { clauseInfo } from '@/lib/clauses'
import { cn } from '@/lib/utils'

const COMMAND = 'python -m lensor.eval --contracts 50 --mode full'

const pct = (value: number) => Math.round(value * 100)
const mean = (values: number[]) => (values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0)
const fixed = (value: number | null) => (value === null ? '-' : value.toFixed(2))

type Label = 'Strong' | 'Good' | 'Check by hand'

function label(score: number): Label {
  if (score >= 80) return 'Strong'
  if (score >= 70) return 'Good'
  return 'Check by hand'
}

function LabelPill({ value }: { value: Label }) {
  return (
    <span
      className={cn(
        'inline-flex h-7 shrink-0 items-center rounded-full px-3 text-[13px] whitespace-nowrap',
        value === 'Strong' && 'bg-blue text-white',
        value === 'Good' && 'border border-ink text-ink',
        value === 'Check by hand' && 'bg-risk text-white',
      )}
    >
      {value}
    </span>
  )
}

function Hero() {
  return (
    <section className="px-4 pt-14 pb-10 sm:px-10">
      <p className="m-0 inline-flex items-center gap-2.5 border border-[#e3e3e3] bg-surface py-1.5 pr-1.5 pl-3 text-[15px] font-medium">
        Tested on lawyer labels
        <span className="bg-black px-2 py-0.5 text-[11px] font-semibold text-white">50 contracts</span>
      </p>
      <h1 className="m-0 mt-7 max-w-[10.5em] text-[48px] leading-[0.98] font-medium tracking-[-0.045em] sm:text-[84px]">
        How often Lensor <span className="text-blue">gets it right</span>.
      </h1>
      <p className="m-0 mt-7 max-w-[52ch]">
        Lawyers marked the clauses in each test contract. Lensor never saw these contracts before
        the test. This page compares what Lensor found with what the lawyers marked.
      </p>
    </section>
  )
}

function Results({ data }: { data: LatestEval }) {
  const { run, results } = data
  const overall = pct(mean(results.map((r) => r.f1)))
  const sorted = [...results].sort((a, b) => b.f1 - a.f1)
  const date = new Date(run.started_at).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
  const facts: [string, string][] = [
    ['Test contracts', `${run.contract_count} CUAD contracts that the demo does not use`],
    ['Answer key', 'The clauses that lawyers marked in CUAD'],
    ['A match', 'Lensor quotes the same text as the lawyers, with at least half of it shared'],
    ['Model', run.model],
    ['What it reads', run.mode === 'full' ? 'Whole contract' : 'Passages from search'],
    ['Prompt', `Version ${run.prompt_version}`],
    ['Last test', date],
    ['Cost', `$${run.cost_usd.toFixed(2)}`],
  ]
  return (
    <>
      <section className="flex flex-wrap items-start gap-8 bg-[linear-gradient(var(--bg)_0,var(--bg)_40px,var(--surface)_40px)] px-4 pb-12 sm:px-10">
        <div className="min-w-0 flex-[0_1_540px] sm:min-w-[300px]">
          <StatCard
            title="Test result"
            rows={[
              { value: `${overall} / 100`, label: 'Overall score' },
              {
                value: `${pct(mean(results.map((r) => r.precision)))} in 100`,
                label: 'Clauses Lensor found that the lawyers also marked',
              },
              {
                value: `${pct(mean(results.map((r) => r.recall)))} in 100`,
                label: 'Clauses the lawyers marked that Lensor also found',
              },
            ]}
            action={
              <ArrowLink to="/" tone="blue" tall>
                See your contracts
              </ArrowLink>
            }
          />
        </div>
        <dl className="m-0 grid min-w-0 flex-[1_1_420px] grid-cols-[130px_minmax(0,1fr)] gap-x-6 gap-y-4 pt-10 text-sm">
          {facts.map(([term, value]) => (
            <div key={term} className="contents">
              <dt className="text-muted-ink">{term}</dt>
              <dd className="m-0 break-words">{value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="flex flex-col items-center gap-4 px-4 pt-18 pb-20 sm:px-10">
        <SectionHeading
          eyebrow="Score for each clause"
          title="Some clauses are easier to find"
          text="Strong is 80 or more. Good is 70 to 79. Below 70, check that clause by hand."
        />
        <ul
          aria-label="Score for each clause"
          className="m-0 mt-6 flex w-full max-w-[960px] list-none flex-col gap-2 p-0"
        >
          {sorted.map((row: EvalResultRow) => {
            const info = clauseInfo(row.clause_type)
            const score = pct(row.f1)
            return (
              <li
                key={row.clause_type}
                className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg bg-surface px-5 py-4"
              >
                <span className="flex min-w-[200px] flex-1 flex-col">
                  <span className="font-semibold">{info.plain}</span>
                  <span className="text-xs text-muted-ink">{info.cuad}</span>
                </span>
                <span aria-hidden="true" className="h-2 min-w-[120px] flex-[2] overflow-hidden rounded-full bg-[#e6e6e6]">
                  <span className="block h-2 bg-blue" style={{ width: `${score}%` }} />
                </span>
                <span className="w-20 text-right font-medium">{score} / 100</span>
                <LabelPill value={label(score)} />
              </li>
            )
          })}
        </ul>
      </section>

      <section className="px-4 pb-20 sm:px-10">
        <ul className="m-0 grid list-none grid-cols-[repeat(auto-fit,minmax(min(280px,100%),1fr))] gap-4 p-0">
          <li className="flex">
            <IconCard className="flex-1" icon={<Glyph d="M4 6h16M4 12h16M4 18h10" />} title="Whole contract or passages">
              Lensor can read the whole contract, or only the passages that a search returns. The
              second way costs less. Run both and compare.
            </IconCard>
          </li>
          <li className="flex">
            <IconCard className="flex-1" icon={<Glyph d="M12 3v18M3 12h18" />} title="Other models">
              The test takes a model id, so each model gets the same contracts and the same answer
              key.
            </IconCard>
          </li>
          <li className="flex">
            <IconCard className="flex-1" icon={<Glyph d="M5 5h14v14H5zM9 9h6v6H9z" />} title="Search engine">
              Recall at 5 shows how often the top 5 passages contain the clause. Compare pgvector
              and Qdrant with the same test.
            </IconCard>
          </li>
        </ul>
      </section>

      <BlackBand id="tech-h" title="Run the test yourself">
        <pre className="m-0 overflow-x-auto rounded bg-[#111] p-4 text-sm text-[#e0e0e0]">
          <code>{`${COMMAND} --model ${run.model}`}</code>
        </pre>
        <div className="mt-8 overflow-x-auto">
          <table aria-label="Technical scores" className="w-full min-w-[560px] border-collapse text-left text-sm">
            <thead>
              <tr className="text-[#bdbdbd]">
                <th className="border-b border-[#333] py-3 font-normal">Clause type</th>
                <th className="border-b border-[#333] py-3 text-right font-normal">Precision</th>
                <th className="border-b border-[#333] py-3 text-right font-normal">Recall</th>
                <th className="border-b border-[#333] py-3 text-right font-normal">F1</th>
                <th className="border-b border-[#333] py-3 text-right font-normal">Recall@5</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.clause_type}>
                  <td className="border-b border-[#333] py-3">{r.clause_type}</td>
                  <td className="border-b border-[#333] py-3 text-right">{fixed(r.precision)}</td>
                  <td className="border-b border-[#333] py-3 text-right">{fixed(r.recall)}</td>
                  <td className="border-b border-[#333] py-3 text-right">{fixed(r.f1)}</td>
                  <td className="border-b border-[#333] py-3 text-right">{fixed(r.recall_at_5)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </BlackBand>
    </>
  )
}

function Glyph({ d }: { d: string }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d={d} />
    </svg>
  )
}

export function EvalPage() {
  const query = useQuery({ queryKey: ['eval-latest'], queryFn: getLatestEval })
  return (
    <>
      <Hero />
      {query.isPending ? (
        <div className="px-4 pb-20 sm:px-10">
          <Notice>Lensor is loading the test result.</Notice>
        </div>
      ) : null}
      {query.isError ? (
        <div className="px-4 pb-20 sm:px-10">
          <Notice tone="error">Lensor could not load the test result. Try again later.</Notice>
        </div>
      ) : null}
      {query.isSuccess && query.data === null ? (
        <div className="px-4 pb-20 sm:px-10">
          <div className="flex flex-col gap-3 rounded-lg bg-surface p-7">
            <h2 className="m-0 text-2xl font-medium">No evaluation run yet</h2>
            <p className="m-0 text-muted-ink">Run the test once. This page then shows the result.</p>
            <pre className="m-0 overflow-x-auto rounded bg-black p-4 text-sm text-white">
              <code>{COMMAND}</code>
            </pre>
          </div>
        </div>
      ) : null}
      {query.data ? <Results data={query.data} /> : null}
    </>
  )
}
