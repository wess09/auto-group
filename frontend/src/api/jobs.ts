import { socket } from './client'
import { RpcError } from './socket'
import type { JobInput, JobKind, JobRef } from './types'
import { notify } from '../stores/ui'

export async function submitJob(kind: JobKind, params: JobInput): Promise<JobRef> {
  try {
    return await socket.request(kind, params)
  } catch (error) {
    if (
      error instanceof RpcError &&
      ['DISCONNECTED', 'TIMEOUT'].includes(error.code) &&
      error.requestId
    ) {
      // Do not replay an external action. Recover its durable receipt by request id.
      notify('连接中断，正在核实任务是否已提交', 'warning')
      await socket.connect()
      const existing = await socket.read('jobs.findByRequestId', { request_id: error.requestId })
      if (existing) return existing
    }
    throw error
  }
}
