<template>
  <AdminLayout>
    <PageHeader :title="config.title" :subtitle="config.subtitle">
      <slot name="header" />
      <v-btn :prepend-icon="mdiPlus" @click="openCreate">新增</v-btn>
    </PageHeader>
    <div ref="tableHost">
      <ResourceTable ref="table" :resource="resource" :headers="config.columns">
        <template #drag>
          <v-btn
            variant="text"
            size="small"
            :icon="mdiDrag"
            class="drag-handle"
            aria-label="拖动调整优先级"
            :disabled="busy || table?.filtered"
          />
        </template>
        <template #actions="{ row, position }">
          <div class="d-flex ga-1 flex-wrap py-2">
            <v-btn size="small" variant="text" @click="edit(row)">编辑</v-btn>
            <v-btn size="small" variant="text" :disabled="busy" @click="toggle(row)">
              {{ row.enabled ? '停用' : '启用' }}
            </v-btn>
            <v-btn
              v-if="resource === 'groups'"
              size="small"
              variant="text"
              :disabled="busy"
              @click="syncGroup(row)"
            >
              同步
            </v-btn>
            <v-btn
              v-if="resource === 'groups'"
              size="small"
              variant="text"
              @click="openMove(row, position)"
            >
              移动
            </v-btn>
            <v-btn size="small" variant="text" color="error" @click="deleting = row">删除</v-btn>
          </div>
        </template>
      </ResourceTable>
    </div>
    <JobPanel :job-id="jobId" class="mt-5" @completed="table?.refetch()" />
    <v-dialog v-model="dialog" max-width="640" scrollable>
      <v-card :title="editingId ? '编辑' + config.title : '新增' + config.title">
        <v-card-text>
          <v-progress-linear v-if="fetching" indeterminate class="mb-4" />
          <v-form ref="formRef" @submit.prevent="save">
            <template v-for="field in config.fields" :key="field.key">
              <v-switch
                v-if="field.type === 'switch'"
                v-model="form[field.key]"
                :label="field.label"
                color="primary"
                hide-details
                class="mb-4"
              />
              <GroupPicker
                v-else-if="field.type === 'group'"
                :model-value="form[field.key] == null ? null : Number(form[field.key])"
                :label-text="field.label"
                @update:model-value="form[field.key] = $event"
              />
              <v-select
                v-else-if="field.type === 'select'"
                v-model="form[field.key]"
                :label="field.label"
                :items="field.options"
              />
              <v-textarea
                v-else-if="field.type === 'textarea'"
                v-model="form[field.key]"
                :label="field.label"
                :hint="field.hint"
                persistent-hint
                :rules="field.required ? requiredRules : []"
                rows="3"
                class="mb-2"
              />
              <v-text-field
                v-else
                v-model="form[field.key]"
                :label="field.label"
                :type="field.type === 'number' ? 'number' : 'text'"
                :hint="field.hint"
                :persistent-hint="!!field.hint"
                :disabled="!!editingId && (field.key === 'group_id' || field.key === 'user_id')"
                :rules="field.required ? requiredRules : []"
              />
            </template>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :disabled="busy" @click="dialog = false">取消</v-btn>
          <v-btn :loading="busy" :disabled="fetching" @click="save">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog
      :model-value="!!deleting"
      max-width="420"
      @update:model-value="!$event && (deleting = null)"
    >
      <v-card title="确认删除" text="删除后该配置将立即停止生效。">
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleting = null">取消</v-btn>
          <v-btn color="error" :loading="busy" @click="remove">删除</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog
      :model-value="!!moveRow"
      max-width="420"
      @update:model-value="!$event && (moveRow = null)"
    >
      <v-card title="移动群顺序">
        <v-card-text>
          <v-text-field
            v-model.number="movePosition"
            type="number"
            label="目标位置（可跨页）"
            :min="1"
            :max="table?.filtered ? undefined : table?.total"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="moveRow = null">取消</v-btn>
          <v-btn :loading="busy" @click="move">移动</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <slot />
  </AdminLayout>
</template>
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import Sortable from 'sortablejs'
import { mdiPlus, mdiDrag } from '@mdi/js'
import { socket } from '../api/client'
import { queryClient } from '../api/queries'
import { submitJob } from '../api/jobs'
import type { ApiMethods, DataRow, Editable, ResourceInputs } from '../api/types'
import { notify, report } from '../stores/ui'
import { configs } from '../views/resourceConfig'
import AdminLayout from './AdminLayout.vue'
import PageHeader from './PageHeader.vue'
import ResourceTable from './ResourceTable.vue'
import GroupPicker from './GroupPicker.vue'
import JobPanel from './JobPanel.vue'
const props = defineProps<{ resource: Editable }>()
const config = computed(() => configs[props.resource])
const table = ref<InstanceType<typeof ResourceTable> | null>(null),
  tableHost = ref<HTMLElement | null>(null)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)
const dialog = ref(false),
  editingId = ref<number | null>(null),
  busy = ref(false),
  fetching = ref(false),
  deleting = ref<DataRow | null>(null)
const form = reactive<Record<string, unknown>>({}),
  jobId = ref<number | null>(null)
const moveRow = ref<DataRow | null>(null),
  movePosition = ref(1)
let sortable: Sortable | null = null,
  controller: AbortController | null = null
const requiredRules = [
  (value: unknown) => (String(value ?? '').trim().length > 0 && value !== 0) || '请填写此项',
]
function assign(data: Record<string, unknown>) {
  Object.keys(form).forEach((key) => delete form[key])
  Object.assign(form, config.value.defaults, data)
  if (Array.isArray(form.patterns)) form.patterns = form.patterns.join('\n')
}
function openCreate() {
  editingId.value = null
  assign({})
  dialog.value = true
}
function openMove(row: DataRow, position: number) {
  moveRow.value = row
  movePosition.value = table.value?.filtered ? 1 : position
}
async function edit(row: DataRow) {
  editingId.value = row.id
  assign({})
  dialog.value = true
  fetching.value = true
  controller = new AbortController()
  try {
    assign(await socket.read(`${props.resource}.get`, { id: row.id }, controller.signal))
  } catch (error) {
    if (!(error instanceof DOMException && error.name === 'AbortError')) {
      report(error)
      dialog.value = false
    }
  } finally {
    fetching.value = false
  }
}
watch(dialog, (value) => {
  if (!value) controller?.abort()
})
function invalidate() {
  void queryClient.invalidateQueries({ queryKey: ['rpc', `${props.resource}.list`] })
}
async function save() {
  if (busy.value || fetching.value || !(await formRef.value?.validate())?.valid) return
  const data: Record<string, unknown> = {}
  for (const field of config.value.fields) {
    if (editingId.value && ['user_id'].includes(field.key)) continue
    if (editingId.value && props.resource === 'groups' && field.key === 'group_id') continue
    data[field.key] =
      field.key === 'patterns'
        ? String(form[field.key])
            .split('\n')
            .map((line) => line.trim())
            .filter(Boolean)
        : field.type === 'number'
          ? Number(form[field.key])
          : form[field.key]
  }
  busy.value = true
  try {
    // This shared form is driven by resource metadata; the server validates the same Pydantic contract.
    if (editingId.value) {
      await socket.request(`${props.resource}.update`, {
        id: editingId.value,
        data: data as ResourceInputs[Editable]['update'],
      })
    } else {
      await socket.request(`${props.resource}.create`, {
        data,
      } as ApiMethods[`${Editable}.create`]['params'])
    }
    dialog.value = false
    invalidate()
    notify('已保存')
  } catch (error) {
    report(error)
  } finally {
    busy.value = false
  }
}
async function toggle(row: DataRow) {
  busy.value = true
  try {
    await socket.request(`${props.resource}.update`, {
      id: row.id,
      data: { enabled: !row.enabled },
    })
    invalidate()
  } catch (error) {
    report(error)
  } finally {
    busy.value = false
  }
}
async function remove() {
  if (!deleting.value) return
  busy.value = true
  try {
    await socket.request(`${props.resource}.delete`, { id: deleting.value.id })
    deleting.value = null
    invalidate()
  } catch (error) {
    report(error)
  } finally {
    busy.value = false
  }
}
async function syncGroup(row: DataRow) {
  busy.value = true
  try {
    jobId.value = (await submitJob('groups.sync', { group_id: Number(row.group_id) })).id
  } catch (error) {
    report(error)
  } finally {
    busy.value = false
  }
}
async function move() {
  if (!moveRow.value || busy.value) return
  busy.value = true
  try {
    await socket.request('groups.move', {
      group_id: Number(moveRow.value.group_id),
      position: Number(movePosition.value),
    })
    moveRow.value = null
    invalidate()
  } catch (error) {
    report(error)
    void table.value?.refetch()
  } finally {
    busy.value = false
  }
}
watch(
  () => table.value?.rows,
  async () => {
    if (props.resource !== 'groups') return
    await nextTick()
    sortable?.destroy()
    const body = tableHost.value?.querySelector('tbody')
    if (body)
      sortable = Sortable.create(body, {
        handle: '.drag-handle',
        animation: matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 120,
        onEnd: (event) => {
          if (event.oldIndex == null || event.newIndex == null || event.oldIndex === event.newIndex)
            return
          // Restore DOM ownership to Vue; the server response supplies the final row order.
          event.item.remove()
          body.insertBefore(event.item, body.children[event.oldIndex] || null)
          if (busy.value || table.value?.filtered) return
          moveRow.value = table.value?.rows[event.oldIndex] || null
          movePosition.value = ((table.value?.page || 1) - 1) * 25 + event.newIndex + 1
          void move()
        },
      })
  },
  { deep: true },
)
onBeforeUnmount(() => {
  sortable?.destroy()
  controller?.abort()
})
</script>
