import { useCallback, useEffect, useRef, useState } from 'react'
import { getContract, uploadContract } from '@/api/client'
import { streamSSE } from '@/api/sse'
import type { ContractDetail, ContractStatus, StatusEvent } from '@/api/types'

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024

export type UploadState =
  | { phase: 'idle' }
  | { phase: 'working'; fileName: string; status: ContractStatus }
  | { phase: 'done'; fileName: string; contract: ContractDetail }
  | { phase: 'error'; fileName: string; message: string }

/** Upload a file, follow the pipeline status stream, then load the result. */
export function useUpload() {
  const [state, setState] = useState<UploadState>({ phase: 'idle' })
  const abort = useRef<AbortController | null>(null)

  useEffect(() => () => abort.current?.abort(), [])

  const start = useCallback(async (file: File) => {
    abort.current?.abort()
    const controller = new AbortController()
    abort.current = controller
    const fileName = file.name
    if (!/\.(pdf|txt)$/i.test(fileName)) {
      setState({ phase: 'error', fileName, message: 'Lensor reads only PDF and TXT files.' })
      return
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setState({ phase: 'error', fileName, message: 'The file is larger than 10 MB.' })
      return
    }
    setState({ phase: 'working', fileName, status: 'queued' })
    try {
      const { id } = await uploadContract(file)
      let last: StatusEvent | null = null
      await streamSSE(
        `/api/contracts/${id}/status`,
        {},
        (event) => {
          last = event.data as StatusEvent
          const { status } = last
          if (status !== 'ready' && status !== 'failed') {
            setState({ phase: 'working', fileName, status })
          }
        },
        controller.signal,
      )
      const final = last as StatusEvent | null
      if (final?.status === 'ready') {
        setState({ phase: 'done', fileName, contract: await getContract(id) })
      } else {
        setState({
          phase: 'error',
          fileName,
          message: final?.detail ?? 'Lensor could not process this contract.',
        })
      }
    } catch (error) {
      if (controller.signal.aborted) return
      setState({
        phase: 'error',
        fileName,
        message: error instanceof Error ? error.message : 'The upload failed.',
      })
    }
  }, [])

  const reset = useCallback(() => {
    abort.current?.abort()
    setState({ phase: 'idle' })
  }, [])

  return { state, start, reset }
}
