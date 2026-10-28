import { describe, expect, it, vi } from 'vitest'
import { parseSSE, streamSSE } from './sse'

describe('parseSSE', () => {
  it('reads two events in one buffer', () => {
    const { events, rest } = parseSSE('data: {"a":1}\n\nevent: status\ndata: {"b":2}\n\n')
    expect(events).toEqual([
      { data: '{"a":1}' },
      { event: 'status', data: '{"b":2}' },
    ])
    expect(rest).toBe('')
  })

  it('keeps an event that is split across two chunks', () => {
    const first = parseSSE('data: {"a":1}\n\ndata: {"b"')
    expect(first.events).toEqual([{ data: '{"a":1}' }])
    expect(first.rest).toBe('data: {"b"')
    const second = parseSSE(first.rest + ':2}\n\n')
    expect(second.events).toEqual([{ data: '{"b":2}' }])
    expect(second.rest).toBe('')
  })

  it('joins a multi-line data field with newlines', () => {
    const { events } = parseSSE('data: line one\ndata: line two\n\n')
    expect(events).toEqual([{ data: 'line one\nline two' }])
  })

  it('accepts CRLF line ends and ignores comments', () => {
    const { events } = parseSSE(': ping\r\n\r\ndata: x\r\n\r\n')
    expect(events).toEqual([{ data: 'x' }])
  })
})

describe('streamSSE', () => {
  it('parses JSON data across stream chunks', async () => {
    const encoder = new TextEncoder()
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"type":"tok'))
        controller.enqueue(encoder.encode('en","text":"Hi"}\n\ndata: {"type":"done"}\n\n'))
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn(async () => new Response(body, { status: 200 })))
    const seen: unknown[] = []

    await streamSSE('/api/chat', { method: 'POST' }, (e) => seen.push(e.data))

    expect(seen).toEqual([{ type: 'token', text: 'Hi' }, { type: 'done' }])
    vi.unstubAllGlobals()
  })

  it('throws the server detail on an error status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Response.json({ detail: 'Rate limit exceeded' }, { status: 429 })),
    )
    await expect(streamSSE('/api/chat', {}, () => {})).rejects.toThrow('Rate limit exceeded')
    vi.unstubAllGlobals()
  })
})
