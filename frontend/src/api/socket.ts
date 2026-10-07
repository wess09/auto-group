import { shallowRef } from 'vue'
import type { ApiMethods } from './types'

export class RpcError extends Error {
  constructor(
    public code: string,
    message: string,
    public requestId = '',
  ) {
    super(message)
  }
}
type Pending = {
  resolve: (value: unknown) => void
  reject: (error: Error) => void
  timer: ReturnType<typeof setTimeout>
  cleanup: () => void
}
type SocketFactory = (url: string) => WebSocket

export class SocketClient {
  readonly status = shallowRef<'disconnected' | 'connecting' | 'connected' | 'reconnecting'>(
    'disconnected',
  )
  private socket: WebSocket | null = null
  private connection: Promise<void> | null = null
  private pending = new Map<string, Pending>()
  private topics = new Map<string, Set<() => void>>()
  private reconnectTimer?: ReturnType<typeof setTimeout>
  private heartbeat?: ReturnType<typeof setInterval>
  private stopped = true
  private attempts = 0
  private readers = 0
  private waiting: (() => void)[] = []
  onReconnect: () => void = () => {}
  onAuthExpired: () => void = () => {}

  constructor(
    private url: () => string,
    private token: () => string,
    private factory: SocketFactory = (url) => new WebSocket(url),
  ) {}

  connect(): Promise<void> {
    if (!this.token()) return Promise.reject(new RpcError('AUTH_REQUIRED', '请先登录'))
    if (this.status.value === 'connected') return Promise.resolve()
    if (this.connection) return this.connection
    this.stopped = false
    this.status.value = this.attempts ? 'reconnecting' : 'connecting'
    this.connection = new Promise<void>((resolve, reject) => {
      const socket = this.factory(this.url())
      this.socket = socket
      const deadline = setTimeout(() => {
        reject(new RpcError('TIMEOUT', '连接超时'))
        socket.close()
      }, 10000)
      socket.onopen = () => {
        void this.send('auth.authenticate', { token: this.token() }, undefined, 5000)
          .then(() => {
            clearTimeout(deadline)
            this.status.value = 'connected'
            const reconnected = this.attempts > 0
            this.attempts = 0
            this.connection = null
            this.syncSubscriptions()
            this.heartbeat = setInterval(() => {
              void this.send('ping', {}, undefined, 10000).catch(() => socket.close())
            }, 20000)
            if (reconnected) this.onReconnect()
            resolve()
          })
          .catch((error) => {
            clearTimeout(deadline)
            reject(error)
            socket.close(4001)
          })
      }
      socket.onmessage = (event) => {
        let frame: {
          id?: string
          type?: string
          topic?: string
          result?: unknown
          error?: { code: string; message: string }
        }
        try {
          frame = JSON.parse(String(event.data))
        } catch {
          socket.close(1002)
          return
        }
        if (frame.type === 'event' && frame.topic) {
          this.topics.get(frame.topic)?.forEach((callback) => callback())
          return
        }
        const pending = frame.id ? this.pending.get(frame.id) : undefined
        if (!pending) return
        this.pending.delete(frame.id!)
        clearTimeout(pending.timer)
        pending.cleanup()
        if (frame.error)
          pending.reject(new RpcError(frame.error.code, frame.error.message, frame.id))
        else pending.resolve(frame.result)
      }
      socket.onclose = (event) => {
        clearTimeout(deadline)
        if (this.socket !== socket) return
        clearInterval(this.heartbeat)
        this.connection = null
        this.status.value = 'disconnected'
        const error = new RpcError('DISCONNECTED', '连接已断开；写操作结果需重新确认')
        for (const [id, pending] of this.pending) {
          clearTimeout(pending.timer)
          pending.cleanup()
          pending.reject(new RpcError(error.code, error.message, id))
        }
        this.pending.clear()
        reject(error)
        if (event.code === 4001) {
          this.stopped = true
          this.onAuthExpired()
          return
        }
        if (!this.stopped) {
          this.status.value = 'reconnecting'
          const delay = Math.min(
            30000,
            Math.max(1000, 1000 * 2 ** this.attempts++ * (0.8 + Math.random() * 0.4)),
          )
          this.reconnectTimer = setTimeout(() => {
            void this.connect().catch(() => {})
          }, delay)
        }
      }
      socket.onerror = () => {
        /* onclose handles recovery */
      }
    })
    return this.connection
  }

  private send(
    method: string,
    params: unknown,
    signal?: AbortSignal,
    timeout = 30000,
  ): Promise<unknown> {
    const id = crypto.randomUUID()
    return new Promise((resolve, reject) => {
      if (signal?.aborted) {
        reject(new DOMException('Aborted', 'AbortError'))
        return
      }
      if (!this.socket || this.socket.readyState !== 1) {
        reject(new RpcError('DISCONNECTED', '连接尚未就绪', id))
        return
      }
      const abort = () => {
        const entry = this.pending.get(id)
        if (entry) {
          clearTimeout(entry.timer)
          entry.cleanup()
          this.pending.delete(id)
        }
        reject(new DOMException('Aborted', 'AbortError'))
      }
      const timer = setTimeout(() => {
        this.pending.delete(id)
        signal?.removeEventListener('abort', abort)
        reject(new RpcError('TIMEOUT', '请求超时；写操作结果需重新确认', id))
      }, timeout)
      this.pending.set(id, {
        resolve,
        reject,
        timer,
        cleanup: () => signal?.removeEventListener('abort', abort),
      })
      signal?.addEventListener('abort', abort, { once: true })
      this.socket.send(JSON.stringify({ v: 1, id, method, params }))
    })
  }

  async request<M extends keyof ApiMethods>(
    method: M,
    params: ApiMethods[M]['params'],
    signal?: AbortSignal,
  ): Promise<ApiMethods[M]['result']> {
    await this.connect()
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
    return this.send(method, params, signal) as Promise<ApiMethods[M]['result']>
  }

  async read<M extends keyof ApiMethods>(
    method: M,
    params: ApiMethods[M]['params'],
    signal?: AbortSignal,
  ): Promise<ApiMethods[M]['result']> {
    if (this.readers >= 2) {
      await new Promise<void>((resolve, reject) => {
        const resume = () => {
          signal?.removeEventListener('abort', abort)
          resolve()
        }
        const abort = () => {
          this.waiting = this.waiting.filter((entry) => entry !== resume)
          reject(new DOMException('Aborted', 'AbortError'))
        }
        if (signal?.aborted) {
          abort()
          return
        }
        this.waiting.push(resume)
        signal?.addEventListener('abort', abort, { once: true })
      })
    } else this.readers++
    try {
      return await this.request(method, params, signal)
    } finally {
      const next = this.waiting.shift()
      if (next) next()
      else this.readers--
    }
  }

  subscribe(topic: string, callback: () => void): () => void {
    const callbacks = this.topics.get(topic) ?? new Set<() => void>()
    const first = callbacks.size === 0
    callbacks.add(callback)
    this.topics.set(topic, callbacks)
    if (first && this.status.value === 'connected')
      void this.send('subscribe', { topics: [topic] }).catch(() => {})
    return () => {
      callbacks.delete(callback)
      if (!callbacks.size) {
        this.topics.delete(topic)
        if (this.status.value === 'connected')
          void this.send('unsubscribe', { topics: [topic] }).catch(() => {})
      }
    }
  }

  private syncSubscriptions() {
    if (this.topics.size)
      void this.send('subscribe', { topics: [...this.topics.keys()] }).catch(() => {})
  }

  close() {
    this.stopped = true
    clearTimeout(this.reconnectTimer)
    clearInterval(this.heartbeat)
    this.topics.clear()
    for (const [id, pending] of this.pending) {
      clearTimeout(pending.timer)
      pending.cleanup()
      pending.reject(new RpcError('DISCONNECTED', '连接已关闭', id))
    }
    this.pending.clear()
    const socket = this.socket
    this.socket = null
    this.connection = null
    socket?.close()
    this.status.value = 'disconnected'
  }
}

export function websocketUrl(apiBase: string, override: string | undefined, base: string): string {
  if (override) return new URL(override, base).href
  const url = new URL(apiBase.replace(/\/+$/, '') + '/admin/ws', base)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return url.href
}
