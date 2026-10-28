import { type DragEvent, useState } from 'react'
import { Link } from 'react-router'
import type { ContractStatus } from '@/api/types'
import { ArrowButton, ArrowLink, RiskPill } from '@/components/ui-kit'
import { useUpload } from '@/lib/useUpload'
import { cn } from '@/lib/utils'

const STEPS: { status: ContractStatus; name: string; tech: string }[] = [
  { status: 'parsing', name: 'Read the file', tech: 'Takes the text out of the PDF or TXT file' },
  { status: 'chunking', name: 'Split the text', tech: 'Makes passages of about 500 tokens' },
  { status: 'embedding', name: 'Index the passages', tech: 'Stores a search vector for each passage' },
  {
    status: 'extracting',
    name: 'Find the 10 clauses',
    tech: 'An LLM finds each clause. Lensor keeps only quotes that are in the text.',
  },
]

const ORDER: ContractStatus[] = ['queued', 'parsing', 'chunking', 'embedding', 'extracting', 'ready']

const FACTS: [string, string][] = [
  ['What it does', 'Reads your contract and shows the risky parts'],
  ['Time', 'About one minute'],
  ['Files', 'PDF or TXT, up to 10 MB'],
  ['Not supported', 'Scanned pages, because Lensor needs text it can select'],
]

const cardTitle = 'm-0 mt-4 text-[32px] leading-[1.1] font-medium tracking-[-0.03em] break-words'

function StepList({ status }: { status: ContractStatus | 'ready' }) {
  const current = ORDER.indexOf(status)
  return (
    <ol aria-label="Steps" className="m-0 mt-4 list-none p-0">
      {STEPS.map((step) => {
        const index = ORDER.indexOf(step.status)
        const state = index < current ? 'done' : index === current ? 'active' : 'waiting'
        return (
          <li
            key={step.status}
            data-step={step.status}
            data-state={state}
            className="flex items-baseline justify-between gap-6 border-b border-[#e6e6e6] py-3.5"
          >
            <span className="flex flex-col">
              <span
                className={cn(
                  'text-[17px]',
                  state === 'active' ? 'font-semibold' : 'font-normal',
                  state === 'waiting' && 'text-muted-ink',
                )}
              >
                {step.name}
              </span>
              <span className="text-[13px] text-muted-ink">{step.tech}</span>
            </span>
            <span
              className={cn(
                'text-sm font-medium',
                state === 'done' ? 'text-ink' : state === 'active' ? 'text-blue' : 'text-muted-ink',
              )}
            >
              {state === 'done' ? 'Done' : state === 'active' ? 'Working' : 'Waiting'}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

export function UploadPage() {
  const { state, start, reset } = useUpload()
  const [dragging, setDragging] = useState(false)

  async function useSample() {
    const response = await fetch('/sample-contract.txt')
    const text = await response.text()
    void start(new File([text], 'sample-supply-agreement.txt', { type: 'text/plain' }))
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    setDragging(false)
    const file = event.dataTransfer.files[0]
    if (file) void start(file)
  }

  return (
    <>
      <div className="flex flex-wrap border-b border-line bg-surface">
        <div className="min-w-0 flex-[999_1_600px] px-4 pt-6 pb-12 sm:px-10">
          <Link to="/" className="inline-flex min-h-9 items-center text-sm text-muted-ink">
            Back to your contracts
          </Link>
          <h1 className="m-0 mt-4 text-[88px] leading-[0.9] font-normal tracking-[-0.06em] sm:text-[160px]">
            Upload
          </h1>
        </div>
        <aside className="min-w-0 flex-[1_1_380px] border-t border-line p-8 sm:border-t-0 sm:border-l">
          <dl className="m-0 grid grid-cols-[130px_minmax(0,1fr)] gap-x-6 gap-y-4 text-sm">
            {FACTS.map(([term, value]) => (
              <div key={term} className="contents">
                <dt>{term}</dt>
                <dd className="m-0">{value}</dd>
              </div>
            ))}
          </dl>
        </aside>
      </div>

      <div className="mx-auto max-w-[880px] px-4 pt-14 pb-20 sm:px-6">
        {state.phase === 'idle' ? (
          <section aria-labelledby="pick-h" className="rounded-lg bg-surface p-7">
            <span className="inline-flex h-7 items-center rounded-full border border-ink px-3 text-[13px]">
              Step 1
            </span>
            <h2 id="pick-h" className={cn(cardTitle, 'mb-5')}>
              Choose a contract
            </h2>
            <label
              onDragOver={(e) => {
                e.preventDefault()
                setDragging(true)
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={cn(
                'flex cursor-pointer flex-col items-start gap-2.5 rounded-md border-[1.5px] border-dashed p-7',
                dragging ? 'border-blue bg-[#eef0ff]' : 'border-[#9a9a9a] bg-[#f7f7f7]',
              )}
            >
              <span className="text-[17px] font-semibold">
                Drop a PDF or TXT file here, or choose a file
              </span>
              <input
                type="file"
                accept=".pdf,.txt"
                aria-label="Choose a file"
                className="max-w-full text-sm"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) void start(file)
                }}
              />
            </label>
            <p className="m-0 mt-6 mb-3 text-sm font-semibold">No file at hand? Try the demo:</p>
            <ArrowButton onClick={useSample}>Use a sample contract</ArrowButton>
          </section>
        ) : null}

        {state.phase === 'working' ? (
          <section aria-labelledby="work-h" aria-live="polite" className="rounded-lg bg-surface p-7">
            <span className="inline-flex h-7 items-center rounded-full bg-blue px-3 text-[13px] text-white">
              Reading
            </span>
            <h2 id="work-h" className={cn(cardTitle, 'mb-1')}>
              {state.fileName}
            </h2>
            <p className="m-0 mb-5 text-muted-ink">
              You can leave this page. Lensor keeps working.
            </p>
            <div
              role="progressbar"
              aria-label="Progress"
              aria-valuemin={0}
              aria-valuemax={STEPS.length}
              aria-valuenow={Math.max(0, ORDER.indexOf(state.status) - 1)}
              className="h-2 overflow-hidden rounded-full bg-[#e6e6e6]"
            >
              <div
                className="h-2 bg-blue transition-[width]"
                style={{
                  width: `${(Math.max(0, ORDER.indexOf(state.status) - 1) / STEPS.length) * 100}%`,
                }}
              />
            </div>
            <StepList status={state.status} />
          </section>
        ) : null}

        {state.phase === 'done' ? (
          <section
            aria-labelledby="done-h"
            aria-live="polite"
            className="rounded-lg bg-night p-7 text-white"
          >
            <span className="inline-flex h-7 items-center rounded-full bg-blue px-3 text-[13px]">
              Ready
            </span>
            <h2 id="done-h" className={cn(cardTitle, 'mb-1')}>
              {state.contract.title}
            </h2>
            <p className="m-0 text-[#bdbdbd]">
              Lensor found {state.contract.clauses.filter((c) => c.found).length} of the 10
              clauses.{' '}
              {state.contract.risk_level ? (
                <>
                  This contract is{' '}
                  <strong className="text-white">{state.contract.risk_level} risk</strong>.
                </>
              ) : null}
            </p>
            {state.contract.reasons.length ? (
              <>
                <p className="m-0 mt-6 mb-2 text-sm font-semibold">Main points:</p>
                <ul className="m-0 flex flex-col gap-1.5 pl-5 text-[15px]">
                  {state.contract.reasons.slice(0, 3).map((r) => (
                    <li key={r.clause_type}>{r.text}</li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="m-0 mt-6 text-[15px]">Lensor found no risky clause.</p>
            )}
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <ArrowLink to={`/contracts/${state.contract.id}`} tone="blue">
                Open the contract
              </ArrowLink>
              <button
                type="button"
                onClick={reset}
                className="min-h-12 cursor-pointer rounded border border-white/60 bg-transparent px-5 text-sm text-white"
              >
                Upload another contract
              </button>
            </div>
          </section>
        ) : null}

        {state.phase === 'error' ? (
          <section aria-labelledby="error-h" className="rounded-lg bg-surface p-7">
            <RiskPill level="high" />
            <h2 id="error-h" className={cn(cardTitle, 'mb-1')}>
              {state.fileName}
            </h2>
            <p role="alert" className="m-0 mb-6 text-risk">
              Could not read: {state.message}
            </p>
            <ArrowButton onClick={reset}>Choose another file</ArrowButton>
          </section>
        ) : null}
      </div>
    </>
  )
}
