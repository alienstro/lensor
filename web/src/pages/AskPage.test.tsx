import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChatProvider } from '@/chat/ChatContext'
import { mockFetch, renderAt, sseResponse } from '@/test/render'
import { AskPage } from './AskPage'

afterEach(() => vi.unstubAllGlobals())

function renderAsk(path = '/ask') {
  return renderAt(
    path,
    '/ask',
    <ChatProvider>
      <AskPage />
    </ChatProvider>,
  )
}

async function ask(text: string) {
  await userEvent.type(screen.getByLabelText(/your question/i), text)
  await userEvent.click(screen.getByRole('button', { name: /^ask$/i }))
}

describe('AskPage', () => {
  it('shows tool steps in plain words, the joined answer, and its sources', async () => {
    const { fn } = mockFetch({
      'POST /api/chat': () =>
        sseResponse([
          { type: 'tool_call', id: 't1', name: 'list_contracts_by_clause', args: { clause_type: 'Uncapped Liability', found: true } },
          { type: 'tool_result', id: 't1', name: 'list_contracts_by_clause', ok: true },
          { type: 'tool_call', id: 't2', name: 'search_clauses', args: { query: 'renewal' } },
          { type: 'tool_result', id: 't2', name: 'search_clauses', ok: true },
          { type: 'token', text: 'The Distributor Agreement has no limit ' },
          { type: 'token', text: '[c:3:40-70] and renews [c:9:0-10].' },
          {
            type: 'citations',
            items: [
              { contract_id: 3, start: 40, end: 70, verified: true, title: 'Distributor Agreement', quote: 'Fraud liability is not capped.' },
              { contract_id: 9, start: 0, end: 10, verified: false, title: null, quote: null },
            ],
          },
          { type: 'done' },
        ]),
    })
    renderAsk()

    await ask('Which contracts have no limit?')

    const steps = await screen.findByRole('list', { name: /steps/i })
    expect(within(steps).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      expect.stringContaining('Find contracts with this clause: No limit'),
      expect.stringContaining('Search the contract text: renewal'),
    ])
    expect(await screen.findByText('Answer ready')).toBeInTheDocument()
    const answer = screen.getByTestId('answer')
    expect(answer).toHaveTextContent('The Distributor Agreement has no limit [1] and renews [2].')
    expect(within(answer).getByRole('link', { name: /source 1/i })).toHaveAttribute(
      'href',
      '/contracts/3?from=ask#40',
    )
    expect(within(answer).queryByRole('link', { name: /source 2/i })).not.toBeInTheDocument()
    const sources = screen.getByRole('list', { name: /sources/i })
    expect(within(sources).getByText('Fraud liability is not capped.', { exact: false })).toBeInTheDocument()
    expect(within(sources).getByText('Not found in the contract text')).toBeInTheDocument()
    const body = JSON.parse((fn.mock.calls[0][1] as RequestInit).body as string)
    expect(body.messages).toEqual([{ role: 'user', content: 'Which contracts have no limit?' }])
  })

  it('shows an error message and a retry button', async () => {
    let calls = 0
    mockFetch({
      'POST /api/chat': () => {
        calls += 1
        return calls === 1
          ? sseResponse([{ type: 'error', message: 'OpenRouter error 429: rate limited' }])
          : sseResponse([{ type: 'token', text: 'Now it works.' }, { type: 'citations', items: [] }, { type: 'done' }])
      },
    })
    renderAsk()

    await ask('Which contracts renew?')

    expect(await screen.findByRole('alert')).toHaveTextContent('OpenRouter error 429: rate limited')
    await userEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(await screen.findByText('Now it works.')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('fills the question from the link of a contract', async () => {
    mockFetch({})
    renderAsk('/ask?q=What%20should%20I%20read%3F')

    expect(screen.getByLabelText(/your question/i)).toHaveValue('What should I read?')
  })
})
