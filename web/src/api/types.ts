export type RiskLevel = 'low' | 'medium' | 'high'
export type ContractStatus = 'queued' | 'parsing' | 'embedding' | 'extracting' | 'ready' | 'failed'

export type RiskReason = { clause_type: string; points: number; text: string }
export type RiskRule = { clause_type: string; when_found: boolean; points: number; text: string }

export type ContractSummary = {
  id: number
  title: string
  source: 'cuad' | 'upload'
  status: ContractStatus
  risk_score: number | null
  risk_level: RiskLevel | null
  reasons: RiskReason[]
  created_at: string | null
}

export type Clause = {
  clause_type: string
  found: boolean
  quotes: string[]
  spans: [number, number][]
  summary: string
  risk_level: RiskLevel | null
}

export type ContractDetail = ContractSummary & {
  text: string
  overview: string | null
  status_detail: string | null
  clauses: Clause[]
}

export type Dashboard = {
  contracts: number
  by_level: Record<RiskLevel, number>
  by_clause: { clause_type: string; found: number; high: number; medium: number; low: number }[]
  top_risk: { id: number; title: string; risk_score: number | null }[]
  risk_rules: RiskRule[]
}

export type EvalRun = {
  id: number
  started_at: string
  model: string
  mode: 'full' | 'retrieval'
  prompt_version: number
  contract_count: number
  cost_usd: number
  status: 'done' | 'partial'
}

export type EvalResultRow = {
  clause_type: string
  precision: number
  recall: number
  f1: number
  recall_at_5: number | null
}

export type LatestEval = { run: EvalRun; results: EvalResultRow[] }

export type StatusEvent = { status: ContractStatus; detail: string | null }

export type Citation = {
  contract_id: number
  start: number
  end: number
  verified: boolean
  title: string | null
  quote: string | null
}

export type ChatEvent =
  | { type: 'tool_call'; id: string; name: string; args: Record<string, unknown> }
  | { type: 'tool_result'; id: string; name: string; ok: boolean }
  | { type: 'token'; text: string }
  | { type: 'citations'; items: Citation[] }
  | { type: 'done' }
  | { type: 'error'; message: string }

export type ChatMessage = { role: 'user' | 'assistant'; content: string }
