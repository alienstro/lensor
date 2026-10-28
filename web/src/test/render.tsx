import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { vi } from 'vitest'

/** Render one page at a URL, with a router and a fresh query cache. */
export function renderAt(path: string, pattern: string, page: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [
      { path: pattern, element: page },
      { path: '*', element: <p>Other page</p> },
    ],
    { initialEntries: [path] },
  )
  const view = render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { ...view, router }
}

type Handler = (init: RequestInit | undefined) => Response | Promise<Response>

/** Replace fetch. Keys are "METHOD /path". An unknown request fails the test. */
export function mockFetch(handlers: Record<string, Handler>) {
  const calls: string[] = []
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.pathname : input.url
    const key = `${(init?.method ?? 'GET').toUpperCase()} ${url}`
    calls.push(key)
    const handler = handlers[key]
    if (!handler) throw new Error(`Unexpected request: ${key}`)
    return handler(init)
  })
  vi.stubGlobal('fetch', fn)
  return { fn, calls }
}

/** A Server-Sent Events response with one `data` line for each object. */
export function sseResponse(events: unknown[]): Response {
  const text = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join('')
  return new Response(text, { headers: { 'content-type': 'text/event-stream' } })
}
