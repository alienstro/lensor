import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Clause, ContractDetail } from '@/api/types'
import { CLAUSES } from '@/lib/clauses'
import { mockFetch, renderAt } from '@/test/render'
import { ContractView } from './ContractView'

const TEXT = 'Intro. This Agreement renews each year. Fraud liability is not capped. End.'

const clauses: Clause[] = CLAUSES.map((c) => ({
  clause_type: c.cuad,
  found: false,
  quotes: [],
  spans: [],
  summary: '',
  risk_level: null,
}))
clauses[1] = { ...clauses[1], found: true, quotes: [TEXT.slice(7, 39)], spans: [[7, 39]], summary: 'It renews each year.', risk_level: 'medium' }
clauses[9] = { ...clauses[9], found: true, quotes: [TEXT.slice(40, 70)], spans: [[40, 70]], summary: 'No limit for fraud.', risk_level: 'high' }

const DETAIL: ContractDetail = {
  id: 3,
  title: 'Distributor Agreement',
  source: 'cuad',
  status: 'ready',
  risk_score: 60,
  risk_level: 'high',
  reasons: [
    { clause_type: 'Uncapped Liability', points: 30, text: 'No limit on what you could owe for some claims' },
    { clause_type: 'Cap on Liability', points: 15, text: 'No general limit on what you could owe' },
    { clause_type: 'Renewal Term', points: 15, text: 'The contract renews by itself' },
  ],
  created_at: null,
  text: TEXT,
  overview: 'A distributor deal.',
  status_detail: null,
  clauses,
}

afterEach(() => vi.unstubAllGlobals())

describe('ContractView', () => {
  it('lists all 10 clauses and shows Not found for a missing one', async () => {
    mockFetch({ 'GET /api/contracts/3': () => Response.json(DETAIL) })
    renderAt('/contracts/3', '/contracts/:id', <ContractView />)

    const panel = await screen.findByRole('complementary', { name: 'All 10 clauses' })
    const rows = within(panel).getAllByRole('button', { expanded: false })
    expect(rows).toHaveLength(10)
    expect(within(panel).getAllByText('Not found')).toHaveLength(8)
    expect(screen.queryByText(/opened this from an answer/i)).not.toBeInTheDocument()

    await userEvent.click(within(panel).getByRole('button', { name: /governing law/i }))
    expect(within(panel).getByText('Lensor found no clause that names the governing law.')).toBeInTheDocument()
  })

  it('opens the cited clause when it comes from an answer', async () => {
    mockFetch({ 'GET /api/contracts/3': () => Response.json(DETAIL) })
    renderAt('/contracts/3?from=ask#40', '/contracts/:id', <ContractView />)

    expect(await screen.findByText(/opened this from an answer/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to the answer/i })).toHaveAttribute('href', '/ask')
    const open = await screen.findByRole('button', { expanded: true })
    expect(open).toHaveTextContent('No limit')
    const mark = document.querySelector('mark[data-start="40"]') as HTMLElement
    expect(mark.style.outline).toContain('solid')
  })

  it('shows the pipeline message for a contract that failed', async () => {
    mockFetch({
      'GET /api/contracts/3': () =>
        Response.json({ ...DETAIL, status: 'failed', risk_level: null, status_detail: 'Lensor found no text in this file.' }),
    })
    renderAt('/contracts/3', '/contracts/:id', <ContractView />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Lensor found no text in this file.')
  })
})
