<template>
  <AdminLayout>
    <PageHeader
      :title="isNotices ? '公告管理' : '精华管理'"
      :subtitle="
        isNotices
          ? '按群浏览公告，支持批量发送、同步和删除。'
          : '按群浏览精华，发送内容后自动设为精华。'
      "
    >
      <v-btn @click="compose = true">{{ isNotices ? '发送公告' : '创建精华' }}</v-btn>
      <v-btn variant="tonal" @click="syncDialog = true">批量同步</v-btn>
    </PageHeader>
    <div class="toolbar"><GroupPicker v-model="groupId" /></div>
    <v-card v-if="!groupId" class="surface-card pa-10 text-center muted">
      选择一个群后加载{{ isNotices ? '公告' : '精华' }}
    </v-card>
    <ResourceTable
      v-else
      ref="table"
      :resource="resource"
      :headers="headers"
      :filters="{ group_id: groupId }"
    >
      <template #actions="{ row }">
        <v-btn size="small" variant="text" @click="showDetail(row)">查看</v-btn>
        <v-btn size="small" variant="text" color="error" @click="deleting = row">删除</v-btn>
      </template>
    </ResourceTable>
    <JobPanel :job-id="jobId" class="mt-6" @completed="table?.refetch()" />
    <v-dialog v-model="compose" max-width="720" scrollable>
      <v-card :title="isNotices ? '发送公告' : '创建精华'">
        <v-card-text>
          <GroupSelector v-if="compose" v-model="selection" />
          <v-textarea v-model="content" label="内容" rows="5" class="mt-5" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="compose = false">取消</v-btn>
          <v-btn :loading="busy" :disabled="!content.trim()" @click="send">提交任务</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog v-model="syncDialog" max-width="640" scrollable>
      <v-card title="选择同步目标群">
        <v-card-text><GroupSelector v-if="syncDialog" v-model="selection" /></v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="syncDialog = false">取消</v-btn>
          <v-btn :loading="busy" @click="sync">同步</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog v-model="detailOpen" max-width="720" scrollable>
      <v-card :title="isNotices ? '公告内容' : '精华内容'">
        <v-card-text>
          <v-progress-linear v-if="detailLoading" indeterminate />
          <div class="mono">{{ detail }}</div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="detailOpen = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog
      :model-value="!!deleting"
      max-width="420"
      @update:model-value="!$event && (deleting = null)"
    >
      <v-card title="确认删除" :text="isNotices ? '将从群中删除此公告。' : '将移除此精华标记。'">
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleting = null">取消</v-btn>
          <v-btn color="error" :loading="busy" @click="remove">删除</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </AdminLayout>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useResourceDetail } from '../api/details'
import QueryError from './QueryError.vue'
import { submitJob } from '../api/jobs'
import { emptySelection, type DataRow } from '../api/types'
import { pageStates, report } from '../stores/ui'
import AdminLayout from './AdminLayout.vue'
import PageHeader from './PageHeader.vue'
import ResourceTable from './ResourceTable.vue'
import GroupPicker from './GroupPicker.vue'
import GroupSelector from './GroupSelector.vue'
import JobPanel from './JobPanel.vue'
const props = defineProps<{ resource: 'notices' | 'essence' }>()
const isNotices = computed(() => props.resource === 'notices'),
  route = useRoute()
const pagePath = route.path
const groupId = ref<number | null>(pageStates.get(pagePath)?.group || null),
  compose = ref(false),
  syncDialog = ref(false),
  content = ref(''),
  selection = ref(emptySelection()),
  busy = ref(false),
  jobId = ref<number | null>(pageStates.get(pagePath)?.jobId || null)
const table = ref<InstanceType<typeof ResourceTable> | null>(null),
  deleting = ref<DataRow | null>(null)
const {
  open: detailOpen,
  query: detailQuery,
  show: showDetail,
} = useResourceDetail(() => props.resource)
const detailLoading = computed(() => detailQuery.isFetching.value)
const detail = computed(() => String(detailQuery.data.value?.content || ''))
const headers = computed(() => [
  {
    title: isNotices.value ? '公告编号' : '消息编号',
    key: isNotices.value ? 'notice_id' : 'message_id',
    sortable: false,
  },
  { title: '内容预览', key: 'content', sortable: false },
  { title: '发送者', key: 'sender_id', sortable: false },
  { title: '时间', key: 'created_at', sortable: false },
  { title: '操作', key: 'actions', sortable: false },
])
async function send() {
  busy.value = true
  try {
    jobId.value = (
      await submitJob(isNotices.value ? 'notices.send' : 'essence.create', {
        selection: selection.value,
        content: content.value,
      })
    ).id
    compose.value = false
    content.value = ''
  } catch (error) {
    report(error)
  } finally {
    busy.value = false
  }
}
async function sync() {
  busy.value = true
  try {
    jobId.value = (await submitJob(`${props.resource}.sync`, { selection: selection.value })).id
    syncDialog.value = false
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
    jobId.value = (
      await submitJob(`${props.resource}.delete`, {
        group_id: Number(deleting.value.group_id),
        ...(isNotices.value
          ? { notice_id: String(deleting.value.notice_id) }
          : { message_id: Number(deleting.value.message_id) }),
      })
    ).id
    deleting.value = null
  } catch (error) {
    report(error)
  } finally {
    busy.value = false
  }
}
onBeforeUnmount(() =>
  pageStates.set(pagePath, {
    page: 1,
    search: '',
    group: groupId.value || undefined,
    jobId: jobId.value || undefined,
  }),
)
</script>
