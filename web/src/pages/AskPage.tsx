import { type FormEvent, type ReactNode, useEffect, useRef } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ArrowButton } from '@/components/ui-kit'
import { type Step, type Turn, useChat } from '@/chat/ChatContext'
import { renderWithCitations, sourceHref } from '@/chat/citations'
import { clauseInfo } from '@/lib/clauses'
import { cn } from '@/lib/utils'

const MAX_STEPS = 8

const TOOL_TEXT: Record<string, string> = {
  search_clauses: 'Search the contract text',
  list_contracts_by_clause: 'Find contracts with this clause',
  get_contract_summary: 'Read the clause list of a contract',
  compare_clauses: 'Compare the clauses side by side',
}

const EXAMPLES: { question: string; hint: string; icon: ReactNode }[] = [
  {
    question: 'Which contracts have no limit on what we could owe and also renew by themselves?',
    hint: 'Combines two clauses across all contracts.',
    icon: <path d="M4 12h16M12 4v16" />,
  },
  {
    question: 'Which contracts let the other party end the contract without a reason?',
    hint: 'Finds the "Ending early" clauses.',
    icon: <path d="M5 12h14M13 6l6 6-6 6" />,
  },
  {
    question: 'Compare the governing law of the three riskiest contracts.',
    hint: 'Shows the clauses side by side.',
    icon: <path d="M8 4v16M16 4v16M4 8h4M16 16h4" />,
  },
]

function stepDetail(step: Step): string {
  const { clause_type, query, contract_id, contract_ids } = step.args as {
    clause_type?: unknown
    query?: unknown
    contract_id?: unknown
    contract_ids?: unknown
  }
  if (typeof clause_type === 'string') return clauseInfo(clause_type).plain
  if (typeof query === 'string') return query
  if (typeof contract_id === 'number') return `contract ${contract_id}`
  if (Array.isArray(contract_ids)) return `${contract_ids.length} contracts`
  return ''
}

function StatusPill({ turn }: { turn: Turn }) {
  const text = { working: 'Working on it', done: 'Answer ready', stopped: 'Stopped', error: 'Could not answer' }[turn.status]
  return (
    <span
      className={cn(
        'inline-flex h-7 items-center self-start rounded-full px-3 text-[13px]',
        turn.status === 'working' && 'bg-blue text-white',
        turn.status === 'done' && 'border border-ink text-ink',
        turn.status === 'stopped' && 'bg-[#e6e6e6] text-ink',
        turn.status === 'error' && 'bg-risk text-white',
      )}
    >
      {text}
    </span>
  )
}

function Answer({ turn, last, onRetry }: { turn: Turn; last: boolean; onRetry: () => void }) {
  return (
    <article className="flex flex-col gap-2 rounded-lg bg-surface p-6 sm:p-7">
      <StatusPill turn={turn} />
      <p className="m-0 mt-2 text-sm text-muted-ink">
        {turn.steps.length} of {MAX_STEPS} steps. One question can use up to {MAX_STEPS}.
      </p>
      {turn.steps.length ? (
        <ol aria-label="Steps" className="m-0 mt-1 list-none p-0">
          {turn.steps.map((step) => (
            <li
              key={step.id}
              className="flex items-baseline justify-between gap-4 border-b border-[#e6e6e6] py-3"
            >
              <span className="min-w-0">
                {TOOL_TEXT[step.name] ?? step.name}
                {stepDetail(step) ? (
                  <span className="text-muted-ink">: {stepDetail(step)}</span>
                ) : null}
              </span>
              <span
                className={cn(
                  'shrink-0 text-sm font-medium',
                  step.ok === null ? 'text-blue' : step.ok ? 'text-ink' : 'text-risk',
                )}
              >
                {step.ok === null ? 'Working' : step.ok ? 'Done' : 'No result'}
              </span>
            </li>
          ))}
        </ol>
      ) : null}
      {turn.answer ? (
        <div
          data-testid="answer"
          className="m-0 mt-4 text-[19px] leading-[1.45] font-medium tracking-[-0.01em] whitespace-pre-wrap"
        >
          {renderWithCitations(turn.answer, turn.citations)}
        </div>
      ) : null}
      {turn.status === 'error' ? (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <p role="alert" className="m-0 text-risk">
            {turn.error}
          </p>
          {last ? (
            <button
              type="button"
              onClick={onRetry}
              className="min-h-10 cursor-pointer rounded border border-ink bg-transparent px-4 font-[inherit] text-sm"
            >
              Try again
            </button>
          ) : null}
        </div>
      ) : null}
      {turn.citations.some((c) => !c.verified) ? (
        <div className="mt-3 rounded bg-[#fdecea] p-4">
          <p className="m-0 font-semibold text-[#b42318]">A source could not be checked</p>
          <p className="m-0 mt-1 text-sm">
            Lensor did not find the cited text in the contract. Do not rely on the claim before
            that source.
          </p>
        </div>
      ) : null}
    </article>
  )
}

function Sources({ turn }: { turn: Turn }) {
  if (!turn.citations.length) return null
  return (
    <section aria-labelledby="src-h" className="bg-surface px-4 py-12 sm:px-10">
      <h2 id="src-h" className="m-0 mb-6 text-[40px] font-medium tracking-[-0.035em]">
        Sources
      </h2>
      <ul
        aria-label="Sources"
        className="m-0 grid list-none grid-cols-[repeat(auto-fill,minmax(min(300px,100%),1fr))] gap-4 p-0"
      >
        {turn.citations.map((citation, i) => {
          const body = (
            <>
              <span className="text-[13px] font-semibold text-blue">Source {i + 1}</span>
              <span className="text-lg font-medium">
                {citation.title ?? `Contract ${citation.contract_id}`}
              </span>
              {citation.verified ? (
                <span className="font-serif text-sm leading-[1.6] italic">“{citation.quote}”</span>
              ) : (
                <span className="text-sm font-semibold text-risk">Not found in the contract text</span>
              )}
            </>
          )
          return (
            <li key={`${citation.contract_id}:${citation.start}`} className="flex">
              {citation.verified ? (
                <Link
                  to={sourceHref(citation)}
                  className="flex flex-1 flex-col gap-3 rounded-lg bg-bg p-5 text-ink no-underline"
                >
                  {body}
                  <span className="mt-auto text-sm font-medium text-blue underline">
                    Open in the contract
                  </span>
                </Link>
              ) : (
                <div className="flex flex-1 flex-col gap-3 rounded-lg bg-bg p-5">{body}</div>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}

export function AskPage() {
  const { turns, draft, busy, setDraft, ask, retry, stop, reset } = useChat()
  const [params] = useSearchParams()
  const prefill = params.get('q')
  const input = useRef<HTMLTextAreaElement>(null)
  const last = turns.at(-1)

  useEffect(() => {
    if (prefill) setDraft(prefill)
  }, [prefill, setDraft])

  function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) stop()
    else ask(draft)
  }

  return (
    <>
      <section className="flex flex-col items-center gap-4 px-4 pt-14 pb-8 text-center sm:px-10">
        <p className="m-0 text-[13px] font-medium text-blue">Ask</p>
        <h1 className="m-0 text-[44px] leading-none font-medium tracking-[-0.045em] sm:text-[72px]">
          Ask about your contracts
        </h1>
        <p className="m-0 max-w-[52ch] text-muted-ink">
          Lensor searches the contracts, shows each step, and links every claim to the clause text.
        </p>
      </section>

      <div className="mx-auto flex max-w-[960px] flex-col gap-4 px-4 pb-6 sm:px-6">
        {turns.length === 0 ? (
          <ul className="m-0 grid list-none grid-cols-[repeat(auto-fit,minmax(min(260px,100%),1fr))] gap-4 p-0">
            {EXAMPLES.map((example) => (
              <li key={example.question} className="flex">
                <button
                  type="button"
                  onClick={() => ask(example.question)}
                  className="flex flex-1 cursor-pointer flex-col gap-3 rounded-lg border-0 bg-surface p-6 text-left font-[inherit] text-ink"
                >
                  <span className="inline-flex size-8 items-center justify-center rounded bg-blue text-white">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                      {example.icon}
                    </svg>
                  </span>
                  <span className="text-lg leading-tight font-medium">{example.question}</span>
                  <span className="text-sm text-muted-ink">{example.hint}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        {turns.map((turn, i) => (
          <div key={i} className="flex flex-col gap-3">
            <p className="m-0 max-w-[560px] self-end rounded-lg bg-black px-5 py-4 text-[17px] text-white">
              {turn.question}
            </p>
            <Answer turn={turn} last={i === turns.length - 1} onRetry={retry} />
          </div>
        ))}
      </div>

      {last ? <Sources turn={last} /> : null}

      <section aria-label="Ask a question" className="px-4 pt-8 pb-18 sm:px-10">
        <form onSubmit={submit} className="mx-auto flex max-w-[960px] flex-wrap items-stretch gap-3">
          <label htmlFor="question" className="sr-only">
            Your question
          </label>
          <textarea
            id="question"
            ref={input}
            rows={2}
            value={draft}
            maxLength={4000}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                if (!busy) ask(draft)
              }
            }}
            placeholder="For example, which contracts end this year?"
            className="min-w-0 flex-[1_1_400px] resize-none rounded border border-line bg-surface px-4 py-3.5 font-[inherit] text-base text-ink"
          />
          <ArrowButton type="submit" tall disabled={!busy && !draft.trim()}>
            {busy ? 'Stop' : 'Ask'}
          </ArrowButton>
        </form>
        {turns.length ? (
          <div className="mx-auto mt-3 max-w-[960px]">
            <button
              type="button"
              onClick={() => {
                reset()
                input.current?.focus()
              }}
              className="min-h-9 cursor-pointer rounded border border-ink bg-transparent px-3 font-[inherit] text-[13px] text-ink"
            >
              Start a new question
            </button>
          </div>
        ) : null}
      </section>
    </>
  )
}
