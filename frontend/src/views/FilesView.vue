<template>
  <AdminLayout>
    <PageHeader title="群文件" subtitle="进入群后读取当前目录，子目录在打开时加载。">
      <v-btn @click="uploadDialog = true">上传与分发</v-btn>
    </PageHeader>
    <div class="toolbar">
      <GroupPicker v-model="groupId" />
      <v-btn v-if="groupId" variant="tonal" :loading="busy" @click="sync">同步群文件</v-btn>
    </div>
    <template v-if="groupId">
      <v-breadcrumbs :items="breadcrumbs" class="px-0">
        <template #item="{ item, index }">
          <v-btn variant="text" size="small" @click="navigate(index - 1)">{{ item.title }}</v-btn>
        </template>
      </v-breadcrumbs>
      <div class="toolbar">
        <v-text-field
          v-model="search"
          label="搜索当前目录"
          class="search"
          hide-details
          :prepend-inner-icon="mdiMagnify"
          @update:model-value="updateSearch"
        />
        <v-spacer />
        <v-btn variant="text" :loading="query.isFetching.value" @click="query.refetch()">
          刷新目录
        </v-btn>
      </div>
      <QueryError :error="query.error.value" @retry="query.refetch()" />
      <v-card class="surface-card">
        <v-data-table-server
          class="resource-table"
          :mobile="false"
          :headers="headers"
          :items="query.data.value?.items || []"
          :items-length="total"
          :items-per-page="25"
          :items-per-page-options="[25]"
          v-model:page="page"
          :loading="query.isFetching.value"
        >
          <template #item.name="{ item }">
            <v-btn
              v-if="item.type === 'folder'"
              variant="text"
              :prepend-icon="mdiFolderOutline"
              @click="enter(item)"
            >
              {{ item.name }}
            </v-btn>
            <span v-else>
              <v-icon :icon="mdiFileOutline" size="18" class="mr-2" />
              {{ item.name }}
            </span>
          </template>
          <template #item.size="{ item }">
            {{ item.type === 'folder' ? '—' : sizeLabel(item.size) }}
          </template>
          <template #item.actions="{ item }">
            <v-btn v-if="item.type === 'file'" size="small" variant="text" @click="download(item)">
              下载
            </v-btn>
            <v-btn size="small" variant="text" @click="openRename(item)">重命名</v-btn>
            <v-btn
              v-if="item.type === 'file'"
              size="small"
              variant="text"
              color="error"
              @click="deleting = item"
            >
              删除
            </v-btn>
          </template>
        </v-data-table-server>
      </v-card>
    </template>
    <v-card v-else class="surface-card text-center pa-12 muted">选择群后浏览文件</v-card>
    <JobPanel :job-id="jobId" class="mt-6" @completed="query.refetch()" />
    <v-dialog v-model="uploadDialog" max-width="720" scrollable>
      <v-card title="上传并分发群文件">
        <v-card-text>
          <v-file-input v-model="uploadFile" label="选择文件" />
          <v-text-field v-model="uploadName" label="分发文件名（留空使用原名）" />
          <v-text-field v-model="targetFolder" label="目标目录 ID（留空为根目录）" />
          <v-progress-linear v-if="uploading" :model-value="uploadProgress" class="mb-4" />
          <GroupSelector v-if="uploadDialog" v-model="selection" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :disabled="uploading" @click="uploadDialog = false">取消</v-btn>
          <v-btn :loading="uploading || busy" :disabled="!uploadFile" @click="distribute">
            上传并提交
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog
      :model-value="!!renaming"
      max-width="480"
      @update:model-value="!$event && (renaming = null)"
    >
      <v-card title="重命名">
        <v-card-text><v-text-field v-model="newName" label="新名称" /></v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="renaming = null">取消</v-btn>
          <v-btn :loading="busy" :disabled="!newName.trim()" @click="rename">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog
      :model-value="!!deleting"
      max-width="420"
      @update:model-value="!$event && (deleting = null)"
    >
      <v-card title="确认删除文件" :text="deleting?.name">
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
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { mdiMagnify, mdiFolderOutline, mdiFileOutline } from '@mdi/js'
import { api, socket } from '../api/client'
import { useRpcQuery } from '../api/queries'
import { submitJob } from '../api/jobs'
import { emptySelection, type BrowseEntry } from '../api/types'
import { pageStates, report } from '../stores/ui'
import AdminLayout from '../components/AdminLayout.vue'
import PageHeader from '../components/PageHeader.vue'
import GroupPicker from '../components/GroupPicker.vue'
import GroupSelector from '../components/GroupSelector.vue'
import QueryError from '../components/QueryError.vue'
import JobPanel from '../components/JobPanel.vue'
const route = useRoute(),
  pagePath = route.path,
  state = pageStates.get(pagePath),
  groupId = ref<number | null>(state?.group || null),
  folders = ref<{ id: string; name: string }[]>(state?.folders || []),
  page = ref(state?.page || 1),
  search = ref(state?.search || ''),
  q = ref(state?.search || '')
const busy = ref(false),
  jobId = ref<number | null>(state?.jobId || null),
  uploadDialog = ref(false),
  uploadFile = ref<File | File[] | null>(null),
  uploadName = ref(''),
  targetFolder = ref(''),
  uploading = ref(false),
  uploadProgress = ref(0),
  selection = ref(emptySelection())
const renaming = ref<BrowseEntry | null>(null),
  deleting = ref<BrowseEntry | null>(null),
  newName = ref('')
const folderId = computed(() => folders.value[folders.value.length - 1]?.id || '')
const query = useRpcQuery(
  'files.browse',
  () => ({ group_id: groupId.value || 0, folder_id: folderId.value, page: page.value, q: q.value }),
  () => `files:${groupId.value}`,
  () => !!groupId.value,
)
const total = ref(0)
watch(
  query.data,
  (data) => {
    if (data) total.value = data.total
  },
  { immediate: true },
)
function openRename(item: BrowseEntry) {
  renaming.value = item
  newName.value = item.name
}
const headers = [
  { title: '名称', key: 'name', sortable: false },
  { title: '大小', key: 'size', sortable: false },
  { title: '操作', key: 'actions', sortable: false },
]
const breadcrumbs = computed(() => [
  { title: '根目录', value: -1 },
  ...folders.value.map((folder, index) => ({ title: folder.name, value: index })),
])
let timer: ReturnType<typeof setTimeout> | undefined
function updateSearch() {
  clearTimeout(timer)
  timer = setTimeout(() => {
    q.value = search.value || ''
    page.value = 1
  }, 300)
}
function navigate(index: number) {
  folders.value = folders.value.slice(0, index + 1)
  page.value = 1
  search.value = q.value = ''
}
function enter(item: BrowseEntry) {
  if (item.folder_id) {
    folders.value.push({ id: item.folder_id, name: item.name })
    page.value = 1
    search.value = q.value = ''
  }
}
watch(groupId, () => {
  folders.value = []
  page.value = 1
  search.value = q.value = ''
})
function sizeLabel(value?: number) {
  if (!value) return '0 B'
  const i = Math.min(3, Math.floor(Math.log(value) / Math.log(1024)))
  return `${(value / 1024 ** i).toFixed(i ? 1 : 0)} ${['B', 'KB', 'MB', 'GB'][i]}`
}
async function sync() {
  busy.value = true
  try {
    jobId.value = (await submitJob('files.sync', { group_id: groupId.value! })).id
  } catch (error) {
    report(error)
  } finally {
    busy.value = false
  }
}
async function download(item: BrowseEntry) {
  try {
    const result = await socket.read('files.url', {
      group_id: groupId.value!,
      file_id: item.file_id!,
      busid: item.busid || 0,
    })
    const url = new URL(result.url)
    if (!['https:', 'http:'].includes(url.protocol)) throw new Error('下载链接无效')
    const anchor = document.createElement('a')
    anchor.href = url.href
    anchor.target = '_blank'
    anchor.rel = 'noopener noreferrer'
    anchor.click()
  } catch (error) {
    report(error)
  }
}
async function rename() {
  if (!renaming.value) return
  busy.value = true
  try {
    const item = renaming.value
    jobId.value = (
      await submitJob(item.type === 'folder' ? 'files.rename-folder' : 'files.rename', {
        group_id: groupId.value!,
        folder_id: item.folder_id,
        file_id: item.file_id,
        new_name: newName.value,
        current_parent_directory: folderId.value || '/',
      })
    ).id
    renaming.value = null
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
      await submitJob('files.delete', {
        group_id: groupId.value!,
        file_id: deleting.value.file_id,
        busid: deleting.value.busid || 0,
      })
    ).id
    deleting.value = null
  } catch (error) {
    report(error)
  } finally {
    busy.value = false
  }
}
async function distribute() {
  const file = Array.isArray(uploadFile.value) ? uploadFile.value[0] : uploadFile.value
  if (!file) return
  uploading.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    const result = await api.post<{ file_path: string; file_name: string }>(
      '/admin/uploads',
      form,
      {
        onUploadProgress: (event) => {
          uploadProgress.value = event.total ? (event.loaded / event.total) * 100 : 0
        },
      },
    )
    jobId.value = (
      await submitJob('files.distribute', {
        file_path: result.data.file_path,
        name: uploadName.value || result.data.file_name,
        folder_id: targetFolder.value,
        selection: selection.value,
      })
    ).id
    uploadDialog.value = false
    uploadFile.value = null
  } catch (error) {
    report(error)
  } finally {
    uploading.value = false
  }
}
onBeforeUnmount(() => {
  clearTimeout(timer)
  pageStates.set(pagePath, {
    page: page.value,
    search: search.value,
    group: groupId.value || undefined,
    folders: folders.value,
    jobId: jobId.value || undefined,
  })
})
</script>
