import { createContext, type ReactNode, useCallback, useContext, useMemo, useRef, useState } from 'react'
import { streamSSE } from '@/api/sse'
import type { ChatEvent, ChatMessage, Citation } from '@/api/types'

export type Step = { id: string; name: string; args: Record<string, unknown>; ok: boolean | null }

export type Turn = {
  question: string
  steps: Step[]
  answer: string
  citations: Citation[]
  status: 'working' | 'done' | 'stopped' | 'error'
  error: string | null
}

type ChatState = {
  turns: Turn[]
  draft: string
  busy: boolean
  setDraft: (text: string) => void
  ask: (question: string) => void
  retry: () => void
  stop: () => void
  reset: () => void
}

const ChatContext = createContext<ChatState | null>(null)

const MAX_HISTORY = 10

function history(turns: Turn[]): ChatMessage[] {
  return turns
    .filter((t) => t.status === 'done' && t.answer)
    .flatMap((t): ChatMessage[] => [
      { role: 'user', content: t.question },
      { role: 'assistant', content: t.answer.slice(0, 4000) },
    ])
    .slice(-MAX_HISTORY)
}

function apply(turn: Turn, event: ChatEvent): Turn {
  switch (event.type) {
    case 'tool_call':
      return { ...turn, steps: [...turn.steps, { id: event.id, name: event.name, args: event.args, ok: null }] }
    case 'tool_result':
      return {
        ...turn,
        steps: turn.steps.map((s) => (s.id === event.id && s.ok === null ? { ...s, ok: event.ok } : s)),
      }
    case 'token':
      return { ...turn, answer: turn.answer + event.text }
    case 'citations':
      return { ...turn, citations: event.items }
    case 'done':
      return { ...turn, status: 'done' }
    case 'error':
      return { ...turn, status: 'error', error: event.message }
  }
}

/** Keeps the conversation above the routes, so "Back to the answer" shows the same answer. */
export function ChatProvider({ children }: { children: ReactNode }) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [draft, setDraft] = useState('')
  const abort = useRef<AbortController | null>(null)
  const busy = turns.at(-1)?.status === 'working'

  const update = useCallback((fn: (turn: Turn) => Turn) => {
    setTurns((all) => (all.length ? [...all.slice(0, -1), fn(all[all.length - 1])] : all))
  }, [])

  const run = useCallback(
    async (question: string, previous: Turn[]) => {
      const controller = new AbortController()
      abort.current = controller
      const fresh: Turn = { question, steps: [], answer: '', citations: [], status: 'working', error: null }
      setTurns([...previous, fresh])
      try {
        await streamSSE(
          '/api/chat',
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: [...history(previous), { role: 'user', content: question }] }),
          },
          (e) => update((turn) => apply(turn, e.data as ChatEvent)),
          controller.signal,
        )
        update((turn) => (turn.status === 'working' ? { ...turn, status: 'done' } : turn))
      } catch (error) {
        if (controller.signal.aborted) {
          update((turn) => ({ ...turn, status: 'stopped' }))
          return
        }
        update((turn) => ({
          ...turn,
          status: 'error',
          error: error instanceof Error ? error.message : 'The question failed.',
        }))
      }
    },
    [update],
  )

  const ask = useCallback(
    (question: string) => {
      const text = question.trim()
      if (!text || busy) return
      setDraft('')
      void run(text, turns)
    },
    [busy, run, turns],
  )

  const retry = useCallback(() => {
    const last = turns.at(-1)
    if (!last || busy) return
    void run(last.question, turns.slice(0, -1))
  }, [busy, run, turns])

  const stop = useCallback(() => abort.current?.abort(), [])

  const reset = useCallback(() => {
    abort.current?.abort()
    setTurns([])
    setDraft('')
  }, [])

  const value = useMemo(
    () => ({ turns, draft, busy, setDraft, ask, retry, stop, reset }),
    [turns, draft, busy, ask, retry, stop, reset],
  )
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}

export function useChat(): ChatState {
  const value = useContext(ChatContext)
  if (!value) throw new Error('useChat needs a ChatProvider')
  return value
}
