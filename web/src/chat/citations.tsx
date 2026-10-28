import type { ReactNode } from 'react'
import { Link } from 'react-router'
import type { Citation } from '@/api/types'

export const CITATION_RE = /\[c:(\d+):(\d+)-(\d+)\]/g

export function citationKey(contractId: number, start: number, end: number) {
  return `${contractId}:${start}-${end}`
}

export function sourceHref(citation: Citation) {
  return `/contracts/${citation.contract_id}?from=ask#${citation.start}`
}

/**
 * Replace each [c:id:start-end] marker with a numbered source. A verified source is a link to
 * the viewer. An unverified source has no link. The numbers follow the order of `citations`.
 */
export function renderWithCitations(text: string, citations: Citation[]): ReactNode[] {
  const index = new Map(citations.map((c, i) => [citationKey(c.contract_id, c.start, c.end), i]))
  const out: ReactNode[] = []
  let last = 0
  for (const match of text.matchAll(CITATION_RE)) {
    const at = match.index ?? 0
    if (at > last) out.push(text.slice(last, at))
    last = at + match[0].length
    const i = index.get(citationKey(Number(match[1]), Number(match[2]), Number(match[3])))
    if (i === undefined) continue // The citation list has not arrived yet.
    const citation = citations[i]
    const label = `[${i + 1}]`
    out.push(
      citation.verified ? (
        <Link
          key={at}
          to={sourceHref(citation)}
          aria-label={`Source ${i + 1}`}
          className="mx-0.5 text-[13px] font-semibold text-blue no-underline"
        >
          {label}
        </Link>
      ) : (
        <span
          key={at}
          title="Not found in the contract text"
          className="mx-0.5 text-[13px] font-semibold text-risk line-through"
        >
          {label}
        </span>
      ),
    )
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}
