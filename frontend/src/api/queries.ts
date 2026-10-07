import { computed, onScopeDispose, ref, toValue, watch, type MaybeRefOrGetter } from 'vue'
import { QueryClient, useQuery } from '@tanstack/vue-query'
import { socket } from './client'
import type { ApiMethods } from './types'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      gcTime: 300000,
      retry: false,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
    },
  },
})
export const visible = ref(document.visibilityState !== 'hidden')
document.addEventListener('visibilitychange', () => {
  visible.value = document.visibilityState !== 'hidden'
  if (visible.value)
    queueMicrotask(() => {
      void queryClient.invalidateQueries({ refetchType: 'active' }, { cancelRefetch: false })
    })
})
socket.onReconnect = () => {
  void queryClient.invalidateQueries({ refetchType: 'active' })
}
const scheduled = new Set<string>()
function invalidate(method: string) {
  if (scheduled.has(method)) return
  scheduled.add(method)
  queueMicrotask(() => {
    scheduled.delete(method)
    void queryClient.invalidateQueries({ queryKey: ['rpc', method] })
  })
}

export function useRpcQuery<M extends keyof ApiMethods>(
  method: MaybeRefOrGetter<M>,
  params: MaybeRefOrGetter<ApiMethods[M]['params']>,
  topic: MaybeRefOrGetter<string>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  const active = computed(() => toValue(enabled) && visible.value)
  const queryKey = computed(() => ['rpc', toValue(method), toValue(params)] as const)
  const result = useQuery({
    queryKey,
    enabled: active,
    queryFn: ({ signal }) => socket.read(toValue(method), toValue(params), signal),
  })
  let unsubscribe: (() => void) | undefined
  watch(
    [active, () => toValue(topic)],
    ([isActive, currentTopic]) => {
      unsubscribe?.()
      unsubscribe = undefined
      if (isActive && currentTopic)
        unsubscribe = socket.subscribe(currentTopic, () => {
          invalidate(toValue(method))
        })
    },
    { immediate: true },
  )
  watch(active, (next) => {
    if (!next) void queryClient.cancelQueries({ queryKey: queryKey.value })
  })
  onScopeDispose(() => {
    unsubscribe?.()
    void queryClient.cancelQueries({ queryKey: queryKey.value })
  })
  return result
}
