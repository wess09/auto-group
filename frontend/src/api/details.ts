import { ref, toValue, type MaybeRefOrGetter } from 'vue'
import { useRpcQuery } from './queries'
import type { DataRow, Resource } from './types'

export function useResourceDetail(resource: MaybeRefOrGetter<Exclude<Resource, 'jobs'>>) {
  const open = ref(false)
  const id = ref(0)
  const query = useRpcQuery(
    () => `${toValue(resource)}.get` as const,
    () => ({ id: id.value }),
    '',
    () => open.value && id.value > 0,
  )
  function show(row: DataRow) {
    id.value = row.id
    open.value = true
  }
  return { open, query, show }
}
