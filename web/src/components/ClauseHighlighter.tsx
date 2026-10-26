import { memo } from 'react'
import type { Clause } from '@/api/types'
import { clauseInfo, FAMILY_COLOR } from '@/lib/clauses'

export type TypedSpan = { start: number; end: number; type: string }
export type Segment = { text: string; start: number; types: string[] }

/** Cut the text at each span edge. Each segment lists the span types that cover it. */
export function splitBySpans(text: string, spans: TypedSpan[]): Segment[] {
  const valid = spans
    .map((s) => ({ ...s, start: Math.max(0, s.start), end: Math.min(text.length, s.end) }))
    .filter((s) => s.start < s.end)
  const edges = new Set([0, text.length])
  for (const s of valid) {
    edges.add(s.start)
    edges.add(s.end)
  }
  const sorted = [...edges].sort((a, b) => a - b)
  const segments: Segment[] = []
  for (let i = 0; i < sorted.length - 1; i++) {
    const start = sorted[i]
    const end = sorted[i + 1]
    const types = valid.filter((s) => s.start <= start && end <= s.end).map((s) => s.type)
    segments.push({ text: text.slice(start, end), start, types })
  }
  return segments.length ? segments : [{ text, start: 0, types: [] }]
}

export function clauseSpans(clauses: Clause[]): TypedSpan[] {
  return clauses.flatMap((c) =>
    c.found ? c.spans.map(([start, end]) => ({ start, end, type: c.clause_type })) : [],
  )
}

type Props = {
  text: string
  clauses: Clause[]
  selected: string | null
  onSelect: (clauseType: string) => void
}

/** The contract text with a coloured mark on each clause that Lensor found. */
export const ClauseHighlighter = memo(function ClauseHighlighter({
  text,
  clauses,
  selected,
  onSelect,
}: Props) {
  const risk = new Map(clauses.map((c) => [c.clause_type, c.risk_level]))
  const segments = splitBySpans(text, clauseSpans(clauses))
  return (
    <div className="whitespace-pre-wrap break-words">
      {segments.map((segment) => {
        if (!segment.types.length) return <span key={segment.start}>{segment.text}</span>
        const main = segment.types.includes(selected ?? '') ? selected! : segment.types[0]
        const info = clauseInfo(main)
        const high = segment.types.some((t) => risk.get(t) === 'high')
        return (
          <mark
            key={segment.start}
            data-start={segment.start}
            data-types={segment.types.join('|')}
            title={segment.types.map((t) => clauseInfo(t).plain).join(', ')}
            onClick={() => onSelect(main)}
            className="cursor-pointer rounded-[2px] px-[3px] py-px text-inherit"
            style={{
              background: FAMILY_COLOR[info.family],
              boxShadow: high ? 'inset 0 -2px 0 var(--risk)' : undefined,
              outline: segment.types.includes(selected ?? '') ? '2px solid var(--blue)' : undefined,
              outlineOffset: 3,
            }}
          >
            {segment.text}
          </mark>
        )
      })}
    </div>
  )
})
