import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { RpcError, SocketClient, websocketUrl } from '../src/api/socket'

class FakeSocket {
  readyState = 0
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  onerror: (() => void) | null = null
  sent: { id: string; method: string; params: Record<string, unknown> }[] = []
  send(data: string) {
    this.sent.push(JSON.parse(data))
  }
  open() {
    this.readyState = 1
    this.onopen?.()
  }
  close(code = 1000) {
    this.readyState = 3
    this.onclose?.({ code })
  }
  respond(id: string, result: unknown) {
    this.onmessage?.({ data: JSON.stringify({ type: 'response', id, result }) })
  }
  respondLast(result: unknown = {}) {
    this.respond(this.sent[this.sent.length - 1].id, result)
  }
}

describe('WS transport', () => {
  let instances: FakeSocket[], client: SocketClient
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'setInterval'] })
    instances = []
    client = new SocketClient(
      () => 'ws://test/api/admin/ws',
      () => 'token',
      () => {
        const ws = new FakeSocket()
        instances.push(ws)
        return ws as unknown as WebSocket
      },
    )
  })
  afterEach(() => {
    client.close()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })
  async function connected() {
    const promise = client.connect()
    const ws = instances[0]
    ws.open()
    ws.respondLast({ admin_id: 1 })
    await promise
    return ws
  }

  it('shares one connection and authenticates before business requests', async () => {
    const first = client.connect(),
      second = client.connect()
    expect(first).toBe(second)
    expect(instances).toHaveLength(1)
    instances[0].open()
    expect(instances[0].sent[0].method).toBe('auth.authenticate')
    instances[0].respondLast()
    await first
    expect(client.status.value).toBe('connected')
  })
  it('correlates responses even when they arrive out of order', async () => {
    const ws = await connected()
    const first = client.request('groups.list', {}),
      second = client.request('rules.list', {})
    await flushPromises()
    const requests = ws.sent.filter((frame) => frame.method.endsWith('.list'))
    ws.respond(requests[1].id, { items: ['second'] })
    ws.respond(requests[0].id, { items: ['first'] })
    expect((await first).items).toEqual(['first'])
    expect((await second).items).toEqual(['second'])
  })
  it('limits reads to two and cancels queued queries', async () => {
    const ws = await connected(),
      abort = new AbortController()
    const first = client.read('groups.list', {}),
      second = client.read('rules.list', {})
    const third = client.read('blacklist.list', {}, abort.signal)
    const rejected = expect(third).rejects.toHaveProperty('name', 'AbortError')
    await flushPromises()
    expect(ws.sent.filter((frame) => frame.method.endsWith('.list'))).toHaveLength(2)
    abort.abort()
    await rejected
    for (const frame of ws.sent.filter((frame) => frame.method.endsWith('.list')))
      ws.respond(frame.id, { items: [] })
    await Promise.all([first, second])
    expect(ws.sent.some((frame) => frame.method === 'blacklist.list')).toBe(false)
  })
  it('ignores a cancelled response and does not overwrite a later page', async () => {
    const ws = await connected(),
      controller = new AbortController()
    const old = client.read('groups.list', { page: 1 }, controller.signal)
    const rejection = expect(old).rejects.toHaveProperty('name', 'AbortError')
    await flushPromises()
    const oldId = ws.sent[ws.sent.length - 1].id
    controller.abort()
    await rejection
    const current = client.read('groups.list', { page: 2 })
    await flushPromises()
    ws.respond(oldId, { items: ['stale'] })
    ws.respondLast({ items: ['current'] })
    expect((await current).items).toEqual(['current'])
  })
  it('does not replay a write after a disconnect', async () => {
    const ws = await connected()
    const write = client.request('groups.create', { data: { group_id: 42 } })
    const rejected = expect(write).rejects.toBeInstanceOf(RpcError)
    await flushPromises()
    ws.close(1006)
    await rejected
    vi.spyOn(Math, 'random').mockReturnValue(0.5)
    await vi.advanceTimersByTimeAsync(1300)
    const next = instances[1]
    next.open()
    next.respondLast()
    await flushPromises()
    expect(next.sent.map((frame) => frame.method)).toEqual(['auth.authenticate'])
  })
  it('restores subscriptions after reconnect and stops on logout', async () => {
    const ws = await connected(),
      callback = vi.fn()
    const unsubscribe = client.subscribe('groups', callback)
    expect(ws.sent[ws.sent.length - 1].method).toBe('subscribe')
    ws.respondLast()
    ws.onmessage?.({ data: JSON.stringify({ type: 'event', topic: 'groups' }) })
    expect(callback).toHaveBeenCalledOnce()
    ws.close(1006)
    await vi.advanceTimersByTimeAsync(1300)
    const next = instances[1]
    next.open()
    next.respondLast()
    await flushPromises()
    expect(next.sent.some((frame) => frame.method === 'subscribe')).toBe(true)
    next.respondLast()
    unsubscribe()
    expect(next.sent[next.sent.length - 1].method).toBe('unsubscribe')
    next.respondLast()
    client.close()
    await vi.advanceTimersByTimeAsync(40000)
    expect(instances).toHaveLength(2)
  })
  it('expires authentication instead of reconnecting indefinitely', async () => {
    const ws = await connected()
    client.onAuthExpired = vi.fn()
    ws.close(4001)
    await vi.advanceTimersByTimeAsync(40000)
    expect(client.onAuthExpired).toHaveBeenCalledOnce()
    expect(instances).toHaveLength(1)
  })
})

it('derives same-origin and secure CDN WS URLs', () => {
  expect(websocketUrl('/api', undefined, 'http://localhost/#/admin')).toBe(
    'ws://localhost/api/admin/ws',
  )
  expect(websocketUrl('https://bot.example/api/', undefined, 'https://cdn.example')).toBe(
    'wss://bot.example/api/admin/ws',
  )
  expect(websocketUrl('/api', 'wss://socket.example/manage', 'https://cdn.example')).toBe(
    'wss://socket.example/manage',
  )
})
