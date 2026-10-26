import { screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { LatestEval } from '@/api/types'
import { CLAUSES } from '@/lib/clauses'
import { mockFetch, renderAt } from '@/test/render'
import { EvalPage } from './EvalPage'

afterEach(() => vi.unstubAllGlobals())

const f1s = [0.9, 0.85, 0.8, 0.95, 0.72, 0.7, 0.75, 0.5, 0.65, 0.6]

const LATEST: LatestEval = {
  run: {
    id: 4,
    started_at: '2026-10-26T10:00:00+00:00',
    model: 'deepseek/deepseek-v4.1-flash',
    mode: 'full',
    prompt_version: 1,
    contract_count: 50,
    cost_usd: 0.8123,
    status: 'done',
  },
  results: CLAUSES.map((c, i) => ({
    clause_type: c.cuad,
    precision: 0.8,
    recall: 0.7,
    f1: f1s[i],
    recall_at_5: i === 0 ? 0.96 : null,
  })),
}

describe('EvalPage', () => {
  it('shows the score and the label for each clause type, and the run facts', async () => {
    mockFetch({ 'GET /api/eval/runs/latest': () => Response.json(LATEST) })
    renderAt('/eval', '/eval', <EvalPage />)

    const card = await screen.findByRole('region', { name: 'Test result' })
    // Macro F1 = 0.742.
    expect(within(card).getByText('74 / 100')).toBeInTheDocument()
    expect(within(card).getByText('80 in 100')).toBeInTheDocument()
    expect(within(card).getByText('70 in 100')).toBeInTheDocument()

    const list = screen.getByRole('list', { name: /score for each clause/i })
    const rows = within(list).getAllByRole('listitem')
    expect(rows[0]).toHaveTextContent('Governing law')
    expect(rows[0]).toHaveTextContent('95 / 100')
    expect(rows[0]).toHaveTextContent('Strong')
    const ending = rows.find((r) => r.textContent?.includes('Ending early'))!
    expect(ending).toHaveTextContent('Good')
    const nonCompete = rows.find((r) => r.textContent?.includes('Non-compete'))!
    expect(nonCompete).toHaveTextContent('Check by hand')

    expect(screen.getByText('deepseek/deepseek-v4.1-flash')).toBeInTheDocument()
    expect(screen.getByText('Whole contract')).toBeInTheDocument()
    expect(screen.getByText('Version 1')).toBeInTheDocument()
    expect(screen.getByText('$0.81')).toBeInTheDocument()

    const table = screen.getByRole('table', { name: /technical scores/i })
    const first = within(table).getAllByRole('row')[1]
    expect(first).toHaveTextContent('Expiration Date')
    expect(first).toHaveTextContent('0.80')
    expect(first).toHaveTextContent('0.70')
    expect(first).toHaveTextContent('0.90')
    expect(first).toHaveTextContent('0.96')
  })

  it('says that no run exists on a 404', async () => {
    mockFetch({
      'GET /api/eval/runs/latest': () =>
        Response.json({ detail: 'No evaluation run yet.' }, { status: 404 }),
    })
    renderAt('/eval', '/eval', <EvalPage />)

    expect(await screen.findByText('No evaluation run yet')).toBeInTheDocument()
    expect(screen.getByText(/python -m lensor.eval/)).toBeInTheDocument()
  })
})
