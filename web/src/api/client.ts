import { errorMessage } from './sse'
import type { ContractDetail, ContractSummary, Dashboard, LatestEval } from './types'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response))
  return (await response.json()) as T
}

export const listContracts = () => request<ContractSummary[]>('/api/contracts')

export const getContract = (id: number) => request<ContractDetail>(`/api/contracts/${id}`)

export const getDashboard = () => request<Dashboard>('/api/dashboard')

export function uploadContract(file: File) {
  const body = new FormData()
  body.append('file', file)
  return request<{ id: number; status: 'queued' }>('/api/contracts', { method: 'POST', body })
}

/** The latest evaluation run, or null when no run exists yet. */
export async function getLatestEval(): Promise<LatestEval | null> {
  try {
    return await request<LatestEval>('/api/eval/runs/latest')
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}
