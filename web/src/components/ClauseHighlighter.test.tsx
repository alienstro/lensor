import { describe, expect, it } from 'vitest'
import { splitBySpans } from './ClauseHighlighter'

const plain = (segments: ReturnType<typeof splitBySpans>) =>
  segments.map((s) => [s.text, s.start, s.types])

describe('splitBySpans', () => {
  it('returns one segment when there are no spans', () => {
    expect(plain(splitBySpans('abcdef', []))).toEqual([['abcdef', 0, []]])
  })

  it('splits around two separate spans', () => {
    const spans = [
      { start: 1, end: 3, type: 'A' },
      { start: 4, end: 5, type: 'B' },
    ]
    expect(plain(splitBySpans('abcdef', spans))).toEqual([
      ['a', 0, []],
      ['bc', 1, ['A']],
      ['d', 3, []],
      ['e', 4, ['B']],
      ['f', 5, []],
    ])
  })

  it('gives the overlap segment both types', () => {
    const spans = [
      { start: 0, end: 4, type: 'A' },
      { start: 2, end: 6, type: 'B' },
    ]
    expect(plain(splitBySpans('abcdef', spans))).toEqual([
      ['ab', 0, ['A']],
      ['cd', 2, ['A', 'B']],
      ['ef', 4, ['B']],
    ])
  })

  it('handles adjacent spans and a span at the end of the text', () => {
    const spans = [
      { start: 0, end: 2, type: 'A' },
      { start: 2, end: 6, type: 'B' },
    ]
    expect(plain(splitBySpans('abcdef', spans))).toEqual([
      ['ab', 0, ['A']],
      ['cdef', 2, ['B']],
    ])
  })

  it('ignores spans outside the text or with no length', () => {
    const spans = [
      { start: 4, end: 99, type: 'A' },
      { start: 2, end: 2, type: 'B' },
    ]
    expect(plain(splitBySpans('abcdef', spans))).toEqual([
      ['abcd', 0, []],
      ['ef', 4, ['A']],
    ])
  })
})
