export type RawSSEEvent = { event?: string; data: string }
export type SSEEvent = { event?: string; data: unknown }

/** Split a text buffer into complete events. The incomplete tail comes back as `rest`. */
export function parseSSE(buffer: string): { events: RawSSEEvent[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, '\n')
  const blocks = normalized.split('\n\n')
  const rest = blocks.pop() ?? ''
  const events: RawSSEEvent[] = []
  for (const block of blocks) {
    let event: string | undefined
    const data: string[] = []
    for (const line of block.split('\n')) {
      if (line === '' || line.startsWith(':')) continue
      const colon = line.indexOf(':')
      const field = colon === -1 ? line : line.slice(0, colon)
      let value = colon === -1 ? '' : line.slice(colon + 1)
      if (value.startsWith(' ')) value = value.slice(1)
      if (field === 'event') event = value
      else if (field === 'data') data.push(value)
    }
    if (data.length === 0) continue
    events.push(event === undefined ? { data: data.join('\n') } : { event, data: data.join('\n') })
  }
  return { events, rest }
}

/** Read the error message of a failed response. FastAPI puts it in `detail`. */
export async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown; error?: unknown }
    const detail = body.detail ?? body.error
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return 'The request is not valid.'
  } catch {
    // The body is not JSON.
  }
  return `The server answered with status ${response.status}.`
}

/**
 * POST or GET a Server-Sent Events stream with fetch, because EventSource cannot POST.
 * Each `data` field is parsed as JSON when it can be.
 */
export async function streamSSE(
  url: string,
  init: RequestInit,
  onEvent: (e: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(url, { ...init, signal })
  if (!response.ok) throw new Error(await errorMessage(response))
  if (!response.body) throw new Error('The server sent no stream.')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const { events, rest } = parseSSE(done ? buffer + '\n\n' : buffer)
    buffer = rest
    for (const e of events) {
      let data: unknown = e.data
      try {
        data = JSON.parse(e.data)
      } catch {
        // Keep the text.
      }
      onEvent(e.event === undefined ? { data } : { event: e.event, data })
    }
    if (done) return
  }
}
