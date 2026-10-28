import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ContractDetail } from '@/api/types'
import { mockFetch, renderAt, sseResponse } from '@/test/render'
import { UploadPage } from './UploadPage'

const DETAIL: ContractDetail = {
  id: 7,
  title: 'Acme Supply',
  source: 'upload',
  status: 'ready',
  risk_score: 60,
  risk_level: 'high',
  reasons: [
    { clause_type: 'Uncapped Liability', points: 30, text: 'No limit on what you could owe for some claims' },
    { clause_type: 'Renewal Term', points: 15, text: 'The contract renews by itself' },
  ],
  created_at: null,
  text: 'x',
  overview: null,
  status_detail: null,
  clauses: [
    { clause_type: 'Renewal Term', found: true, quotes: ['q'], spans: [[0, 1]], summary: 's', risk_level: 'medium' },
    { clause_type: 'Governing Law', found: false, quotes: [], spans: [], summary: '', risk_level: null },
  ],
}

function file(name: string, body = 'This Agreement renews.') {
  return new File([body], name, { type: name.endsWith('.pdf') ? 'application/pdf' : 'text/plain' })
}

afterEach(() => vi.unstubAllGlobals())

describe('UploadPage', () => {
  it('shows each pipeline step in order, then the result', async () => {
    const encoder = new TextEncoder()
    let push: (status: string) => void = () => {}
    let close: () => void = () => {}
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        push = (status) =>
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ status, detail: null })}\n\n`))
        close = () => controller.close()
      },
    })
    mockFetch({
      'POST /api/contracts': () => Response.json({ id: 7, status: 'queued' }, { status: 201 }),
      'GET /api/contracts/7/status': () => new Response(body),
      'GET /api/contracts/7': () => Response.json(DETAIL),
    })
    renderAt('/upload', '/upload', <UploadPage />)

    await userEvent.upload(screen.getByLabelText(/choose a file/i), file('acme_supply.txt'))
    const steps = await screen.findByRole('list', { name: /steps/i })
    const states = () =>
      within(steps)
        .getAllByRole('listitem')
        .map((li) => `${li.dataset.step}:${li.dataset.state}`)

    expect(states()).toEqual([
      'parsing:waiting',
      'chunking:waiting',
      'embedding:waiting',
      'extracting:waiting',
    ])
    push('parsing')
    await waitFor(() => expect(states()[0]).toBe('parsing:active'))
    push('chunking')
    await waitFor(() => expect(states().slice(0, 2)).toEqual(['parsing:done', 'chunking:active']))
    push('embedding')
    await waitFor(() => expect(states()[2]).toBe('embedding:active'))
    push('extracting')
    await waitFor(() =>
      expect(states()).toEqual([
        'parsing:done',
        'chunking:done',
        'embedding:done',
        'extracting:active',
      ]),
    )
    push('ready')
    close()

    expect(await screen.findByRole('heading', { name: 'Acme Supply' })).toBeInTheDocument()
    expect(screen.getByText(/1 of the 10 clauses/)).toBeInTheDocument()
    expect(screen.getByText('No limit on what you could owe for some claims')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /open the contract/i })).toHaveAttribute(
      'href',
      '/contracts/7',
    )
  })

  it('shows status_detail when the pipeline fails', async () => {
    mockFetch({
      'POST /api/contracts': () => Response.json({ id: 8, status: 'queued' }, { status: 201 }),
      'GET /api/contracts/8/status': () =>
        sseResponse([
          { status: 'parsing', detail: null },
          { status: 'failed', detail: 'Lensor found no text in this file.' },
        ]),
    })
    renderAt('/upload', '/upload', <UploadPage />)

    await userEvent.upload(screen.getByLabelText(/choose a file/i), file('scan.pdf'))

    expect(await screen.findByRole('alert')).toHaveTextContent('Lensor found no text in this file.')
    expect(screen.getByRole('button', { name: /choose another file/i })).toBeInTheDocument()
  })

  it.each([
    [413, 'The file is larger than 10 MB.'],
    [415, 'Lensor reads only PDF and TXT files.'],
  ])('shows the server detail on a %i error', async (status, detail) => {
    mockFetch({ 'POST /api/contracts': () => Response.json({ detail }, { status }) })
    renderAt('/upload', '/upload', <UploadPage />)

    await userEvent.upload(screen.getByLabelText(/choose a file/i), file('deal.pdf'), {
      applyAccept: false,
    })

    expect(await screen.findByRole('alert')).toHaveTextContent(detail)
  })
})
