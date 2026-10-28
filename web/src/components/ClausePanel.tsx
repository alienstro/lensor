import type { Clause } from '@/api/types'
import { RiskPill } from '@/components/ui-kit'
import { clauseInfo, FAMILY_COLOR } from '@/lib/clauses'
import { cn } from '@/lib/utils'

type Props = {
  clauses: Clause[]
  open: string | null
  onToggle: (clauseType: string) => void
  onShow: (clauseType: string, start: number) => void
  textLength: number
}

/** All 10 clause types as an accordion: plain name, CUAD name, risk, quotes, and summary. */
export function ClausePanel({ clauses, open, onToggle, onShow, textLength }: Props) {
  return (
    <aside
      aria-labelledby="all-h"
      className="min-w-0 flex-[1_1_380px] self-start overflow-hidden rounded-lg bg-surface lg:sticky lg:top-4"
    >
      <div className="px-6 pt-6 pb-4">
        <h2 id="all-h" className="m-0 text-2xl font-medium tracking-[-0.02em]">
          All 10 clauses
        </h2>
        <p className="m-0 mt-1 text-sm text-muted-ink">
          Select a clause to read the quote and what it means.
        </p>
      </div>
      <ul className="m-0 list-none p-0">
        {clauses.map((clause) => {
          const info = clauseInfo(clause.clause_type)
          const expanded = open === clause.clause_type
          const panelId = `clause-${info.cuad.replace(/\W+/g, '-').toLowerCase()}`
          return (
            <li
              key={clause.clause_type}
              className={cn('border-t border-[#e6e6e6]', expanded && 'bg-[#f7f7ff]')}
            >
              <button
                type="button"
                aria-expanded={expanded}
                aria-controls={panelId}
                onClick={() => onToggle(clause.clause_type)}
                className="flex min-h-14 w-full cursor-pointer items-center gap-3 border-0 bg-transparent px-6 py-2.5 text-left font-[inherit] text-ink"
              >
                <span
                  aria-hidden="true"
                  className="size-2.5 flex-none rounded-[2px]"
                  style={{ background: FAMILY_COLOR[info.family] }}
                />
                <span className="flex flex-1 flex-col">
                  <span className="font-semibold">{info.plain}</span>
                  <span className="text-xs text-muted-ink">{info.cuad}</span>
                </span>
                <RiskPill level={clause.found ? (clause.risk_level ?? 'low') : 'none'} short />
              </button>
              {expanded ? (
                <div id={panelId} className="flex flex-col gap-2.5 pr-6 pb-5 pl-[46px]">
                  {clause.found ? (
                    <>
                      {clause.quotes.map((quote, i) => (
                        <div key={clause.spans[i][0]} className="flex flex-col gap-1.5">
                          <blockquote className="m-0 rounded bg-bg px-3.5 py-2.5 font-serif text-sm leading-[1.6] italic">
                            “{quote}”
                          </blockquote>
                          <button
                            type="button"
                            onClick={() => onShow(clause.clause_type, clause.spans[i][0])}
                            className="cursor-pointer self-start border-0 bg-transparent p-0 font-[inherit] text-sm font-medium text-blue underline"
                          >
                            Show in the contract
                          </button>
                        </div>
                      ))}
                      {clause.summary ? <p className="m-0 text-sm">{clause.summary}</p> : null}
                    </>
                  ) : (
                    <p className="m-0 text-sm">{info.missing}</p>
                  )}
                </div>
              ) : null}
            </li>
          )
        })}
      </ul>
      <details className="border-t border-[#e6e6e6] px-6">
        <summary className="flex min-h-13 cursor-pointer items-center text-sm font-semibold">
          Technical details
        </summary>
        <p className="m-0 mb-4 text-[13px] text-muted-ink">
          An LLM read the contract. Lensor kept a quote only when it found the same words in the
          contract text, so each quote links to real text. The contract has{' '}
          {textLength.toLocaleString('en')} characters.
        </p>
      </details>
    </aside>
  )
}
