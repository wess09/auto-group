<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">群文件</h1>
        <p class="page-subtitle">实时浏览群文件目录，支持上传、重命名和删除操作。</p>
      </div>
      <div class="toolbar">
        <el-button @click="refresh">刷新</el-button>
      </div>
    </div>

    <!-- 上传分发区域（仅在进入某群后显示） -->
    <div v-if="currentGroup" class="content-band" style="margin-bottom: 16px">
      <div class="form-grid">
        <el-form-item label="文件路径">
          <el-input v-model="filePath" placeholder="可上传，也可填写 LLBot 可读取的绝对路径" />
        </el-form-item>
        <el-form-item label="群内文件名">
          <el-input v-model="fileName" placeholder="留空使用原文件名" />
        </el-form-item>
      </div>
      <div class="toolbar" style="gap: 10px">
        <el-upload :http-request="upload" :show-file-list="false">
          <el-button>上传到后端</el-button>
        </el-upload>
        <el-button type="primary" :disabled="!filePath" @click="distribute">
          上传到{{ currentFolder ? '当前目录' : '根目录' }}
        </el-button>
      </div>
    </div>

    <div class="content-band" v-loading="loading" element-loading-text="正在加载群文件系统..." style="min-height: 200px;">
      <!-- Level 0: 群文件夹选择 -->
      <div v-if="!currentGroup" class="folder-grid">
        <div
          v-for="g in groups"
          :key="g.group_id"
          class="folder-card"
          @click="enterGroup(g)"
        >
          <div class="folder-icon-wrap">
            <el-icon class="folder-main-icon"><FolderOpened /></el-icon>
          </div>
          <div class="folder-info">
            <h4 class="folder-name">{{ g.name || '未命名群' }}</h4>
            <span class="folder-id">群号: {{ g.group_id }}</span>
          </div>
          <div class="folder-arrow">
            <el-icon><ArrowRight /></el-icon>
          </div>
        </div>
      </div>

      <!-- Level 1+: 文件浏览器 -->
      <div v-else>
        <!-- 面包屑导航 -->
        <div class="folder-header">
          <el-button @click="goBack" size="small" :icon="ArrowLeft" class="folder-back-btn">
            返回上一级
          </el-button>
          <div class="folder-path">
            <span class="path-item link" @click="exitGroup">
              <el-icon class="path-icon"><House /></el-icon>全部群
            </span>
            <el-icon class="path-separator"><ArrowRight /></el-icon>
            <span
              :class="['path-item', breadcrumbs.length === 0 ? 'active' : 'link']"
              @click="breadcrumbs.length > 0 && browseRoot()"
            >
              <el-icon class="path-icon"><Folder /></el-icon>{{ currentGroup.name || currentGroup.group_id }}
            </span>
            <template v-for="(crumb, idx) in breadcrumbs" :key="crumb.folder_id">
              <el-icon class="path-separator"><ArrowRight /></el-icon>
              <span
                :class="['path-item', idx === breadcrumbs.length - 1 ? 'active' : 'link']"
                @click="idx < breadcrumbs.length - 1 && navigateTo(idx)"
              >
                <el-icon class="path-icon"><Folder /></el-icon>{{ crumb.folder_name }}
              </span>
            </template>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="browsing" style="text-align: center; padding: 40px">
          <el-icon class="is-loading" :size="28"><Loading /></el-icon>
          <p style="color: #64748b; margin-top: 8px">正在加载目录…</p>
        </div>

        <!-- 文件夹 + 文件列表 -->
        <el-table
          v-else
          :data="[...currentFolders, ...currentFiles]"
          border
          :row-class-name="rowClassName"
          @row-dblclick="handleRowDblClick"
          empty-text="此目录下没有文件或文件夹"
        >
          <el-table-column label="名称" min-width="260" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="file-name-cell" style="cursor: pointer">
                <template v-if="row._type === 'folder'">
                  <el-icon class="file-icon" style="color: #d97706; font-size: 20px"><Folder /></el-icon>
                  <span class="file-name-text" style="font-weight: 700">{{ row.folder_name }}</span>
                  <el-tag size="small" type="info" style="margin-left: 8px">{{ row.total_file_count ?? 0 }} 个文件</el-tag>
                </template>
                <template v-else>
                  <el-icon class="file-icon" :style="{ color: getFileIcon(row.file_name).color }">
                    <component :is="getFileIcon(row.file_name).icon" />
                  </el-icon>
                  <span class="file-name-text">{{ row.file_name }}</span>
                </template>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="大小" width="110" align="center">
            <template #default="{ row }">
              <span v-if="row._type === 'file'">{{ formatFileSize(row.file_size) }}</span>
              <span v-else class="text-muted">-</span>
            </template>
          </el-table-column>
          <el-table-column label="上传者" width="130" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row._type === 'file'">{{ row.uploader_name || row.uploader || '-' }}</span>
              <span v-else>{{ row.creator_name || row.creator || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="时间" width="140" align="center">
            <template #default="{ row }">
              <span v-if="row._type === 'file'">{{ formatTs(row.upload_time || row.modify_time) }}</span>
              <span v-else>{{ formatTs(row.create_time) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" align="center">
            <template #default="{ row }">
              <el-space v-if="row._type === 'file'" :size="12">
                <el-tooltip content="下载" placement="top">
                  <el-button type="primary" link :icon="Download" class="action-icon-btn" @click.stop="downloadFile(row)" />
                </el-tooltip>
                <el-tooltip content="链接" placement="top">
                  <el-button type="info" link :icon="Link" class="action-icon-btn" @click.stop="getUrl(row)" />
                </el-tooltip>
                <el-tooltip content="重命名" placement="top">
                  <el-button type="warning" link :icon="Edit" class="action-icon-btn" @click.stop="openRenameFile(row)" />
                </el-tooltip>
                <el-popconfirm title="确认删除此文件？" @confirm="removeFile(row)">
                  <template #reference>
                    <el-button type="danger" link :icon="Delete" class="action-icon-btn" @click.stop />
                  </template>
                </el-popconfirm>
              </el-space>
              <el-space v-else :size="12">
                <el-tooltip content="打开" placement="top">
                  <el-button type="primary" link :icon="FolderOpened" class="action-icon-btn" @click.stop="enterFolder(row)" />
                </el-tooltip>
                <el-tooltip content="重命名" placement="top">
                  <el-button type="warning" link :icon="Edit" class="action-icon-btn" @click.stop="openRenameFolder(row)" />
                </el-tooltip>
              </el-space>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 重命名弹窗 -->
    <el-dialog v-model="renameVisible" title="重命名" width="440px">
      <el-input v-model="renameNewName" placeholder="请输入新名称" @keyup.enter="submitRename" />
      <template #footer>
        <el-button @click="renameVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!renameNewName.trim()" @click="submitRename">确定</el-button>
      </template>
    </el-dialog>
  </AdminLayout>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, type UploadRequestOptions } from 'element-plus'
import {
  Folder,
  FolderOpened,
  Document,
  Picture,
  VideoPlay,
  Briefcase,
  ArrowLeft,
  ArrowRight,
  Loading,
  Edit,
  Link,
  Download,
  Delete,
  House
} from '@element-plus/icons-vue'
import AdminLayout from '../components/AdminLayout.vue'
import { api, type ManagedGroup } from '../api/client'

interface FolderItem {
  _type: 'folder'
  group_id: number
  folder_id: string
  folder_name: string
  create_time: number
  creator: number
  creator_name: string
  total_file_count: number
}

interface FileItem {
  _type: 'file'
  group_id: number
  file_id: string
  file_name: string
  busid: number
  file_size: number
  upload_time: number
  dead_time: number
  modify_time: number
  download_times: number
  uploader: number
  uploader_name: string
}

interface BreadcrumbItem {
  folder_id: string
  folder_name: string
}

const groups = ref<ManagedGroup[]>([])
const currentGroup = ref<ManagedGroup | null>(null)
const currentFolder = ref<string | null>(null) // null = root
const breadcrumbs = ref<BreadcrumbItem[]>([])
const currentFolders = ref<FolderItem[]>([])
const currentFiles = ref<FileItem[]>([])
const browsing = ref(false)
const loading = ref(true)

const filePath = ref('')
const fileName = ref('')

// 重命名状态
const renameVisible = ref(false)
const renameNewName = ref('')
const renameTarget = ref<{ type: 'file' | 'folder'; row: any } | null>(null)

async function loadGroups() {
  loading.value = true
  try {
    const { data } = await api.get('/admin/groups')
    groups.value = data
  } catch (error: any) {
    ElMessage.error('加载群组失败：' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

function enterGroup(g: ManagedGroup) {
  currentGroup.value = g
  browseRoot()
}

function exitGroup() {
  currentGroup.value = null
  currentFolder.value = null
  breadcrumbs.value = []
  currentFolders.value = []
  currentFiles.value = []
}

function goBack() {
  if (breadcrumbs.value.length > 0) {
    breadcrumbs.value.pop()
    if (breadcrumbs.value.length === 0) {
      browseRoot()
    } else {
      const last = breadcrumbs.value[breadcrumbs.value.length - 1]
      currentFolder.value = last.folder_id
      browseFolderRaw(last.folder_id)
    }
  } else {
    exitGroup()
  }
}

function navigateTo(idx: number) {
  breadcrumbs.value = breadcrumbs.value.slice(0, idx + 1)
  const target = breadcrumbs.value[idx]
  currentFolder.value = target.folder_id
  browseFolderRaw(target.folder_id)
}

async function browseRoot() {
  if (!currentGroup.value) return
  currentFolder.value = null
  breadcrumbs.value = []
  browsing.value = true
  try {
    const { data } = await api.get(`/admin/files/browse/${currentGroup.value.group_id}`)
    applyBrowseData(data.data)
  } catch (e: any) {
    ElMessage.error('加载目录失败：' + (e.response?.data?.detail || e.message))
  } finally {
    browsing.value = false
  }
}

async function browseFolderRaw(folderId: string) {
  if (!currentGroup.value) return
  browsing.value = true
  try {
    const { data } = await api.get(`/admin/files/browse/${currentGroup.value.group_id}/${folderId}`)
    applyBrowseData(data.data)
  } catch (e: any) {
    ElMessage.error('加载目录失败：' + (e.response?.data?.detail || e.message))
  } finally {
    browsing.value = false
  }
}

function enterFolder(folder: FolderItem) {
  currentFolder.value = folder.folder_id
  breadcrumbs.value.push({ folder_id: folder.folder_id, folder_name: folder.folder_name })
  browseFolderRaw(folder.folder_id)
}

function applyBrowseData(data: any) {
  const folders = (data?.folders || []).map((f: any) => ({ ...f, _type: 'folder' }))
  const files = (data?.files || []).map((f: any) => ({ ...f, _type: 'file' }))
  currentFolders.value = folders
  currentFiles.value = files
}

function rowClassName({ row }: { row: any }) {
  return row._type === 'folder' ? 'folder-row' : ''
}

function handleRowDblClick(row: any) {
  if (row._type === 'folder') {
    enterFolder(row)
  }
}

function refresh() {
  if (!currentGroup.value) {
    loadGroups()
    return
  }
  if (currentFolder.value) {
    browseFolderRaw(currentFolder.value)
  } else {
    browseRoot()
  }
}

// 文件大小格式化
function formatFileSize(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return '-'
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 时间戳格式化
function formatTs(ts: number | undefined): string {
  if (!ts) return '-'
  const d = new Date(ts * 1000)
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hour = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${month}-${day} ${hour}:${min}`
}

// 文件图标
function getFileIcon(name: string) {
  if (!name) return { icon: Document, color: '#94a3b8' }
  const ext = name.split('.').pop()?.toLowerCase() || ''
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'].includes(ext)) return { icon: Picture, color: '#10b981' }
  if (['mp4', 'mkv', 'avi', 'mov', 'flv'].includes(ext)) return { icon: VideoPlay, color: '#8b5cf6' }
  if (['zip', 'rar', '7z', 'tar', 'gz'].includes(ext)) return { icon: Briefcase, color: '#f59e0b' }
  if (['txt', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'md', 'log'].includes(ext)) return { icon: Document, color: '#3b82f6' }
  return { icon: Document, color: '#64748b' }
}

// 获取文件下载链接
async function getUrl(row: FileItem) {
  try {
    const { data } = await api.get('/admin/files/url', {
      params: { group_id: row.group_id, file_id: row.file_id, busid: row.busid }
    })
    const url = data.data?.url
    if (url) {
      await navigator.clipboard.writeText(url)
      ElMessage.success('链接已复制到剪贴板')
    } else {
      ElMessage.info(JSON.stringify(data.data))
    }
  } catch (e: any) {
    ElMessage.error('获取链接失败：' + (e.response?.data?.detail || e.message))
  }
}

// 下载文件
async function downloadFile(row: FileItem) {
  try {
    const { data } = await api.get('/admin/files/url', {
      params: { group_id: row.group_id, file_id: row.file_id, busid: row.busid }
    })
    const url = data.data?.url
    if (url) {
      window.open(url, '_blank')
      ElMessage.success('已在新标签页打开下载链接')
    } else {
      ElMessage.warning('未获取到有效的下载链接')
    }
  } catch (e: any) {
    ElMessage.error('下载失败：' + (e.response?.data?.detail || e.message))
  }
}

// 删除文件
async function removeFile(row: FileItem) {
  try {
    await api.post('/admin/files/delete', { group_id: row.group_id, file_id: row.file_id, busid: row.busid })
    ElMessage.success('已删除')
    refresh()
  } catch (e: any) {
    ElMessage.error('删除失败：' + (e.response?.data?.detail || e.message))
  }
}

// 重命名
function openRenameFile(row: FileItem) {
  renameTarget.value = { type: 'file', row }
  renameNewName.value = row.file_name
  renameVisible.value = true
}

function openRenameFolder(row: FolderItem) {
  renameTarget.value = { type: 'folder', row }
  renameNewName.value = row.folder_name
  renameVisible.value = true
}

async function submitRename() {
  if (!renameTarget.value || !renameNewName.value.trim()) return
  const { type, row } = renameTarget.value
  try {
    if (type === 'file') {
      const parentDir = currentFolder.value || '/'
      await api.post('/admin/files/rename', {
        group_id: row.group_id,
        file_id: row.file_id,
        current_parent_directory: parentDir,
        new_name: renameNewName.value.trim()
      })
    } else {
      await api.post('/admin/files/rename-folder', {
        group_id: row.group_id,
        folder_id: row.folder_id,
        new_folder_name: renameNewName.value.trim()
      })
    }
    ElMessage.success('已重命名')
    renameVisible.value = false
    refresh()
  } catch (e: any) {
    ElMessage.error('重命名失败：' + (e.response?.data?.detail || e.message))
  }
}

// 上传
async function upload(options: UploadRequestOptions) {
  const form = new FormData()
  form.append('file', options.file)
  try {
    const { data } = await api.post('/admin/uploads', form)
    filePath.value = data.file_path
    fileName.value = data.file_name
    ElMessage.success('上传完成')
    options.onSuccess(data)
  } catch (error) {
    options.onError(error as Parameters<typeof options.onError>[0])
  }
}

async function distribute() {
  if (!currentGroup.value || !filePath.value) return
  try {
    const { data } = await api.post('/admin/files/distribute', {
      group_ids: [currentGroup.value.group_id],
      file_path: filePath.value,
      name: fileName.value || undefined,
      folder_id: currentFolder.value || undefined
    })
    ElMessage[data.status === 'success' ? 'success' : 'warning']('分发任务完成')
    filePath.value = ''
    fileName.value = ''
    refresh()
  } catch (e: any) {
    ElMessage.error('分发失败：' + (e.response?.data?.detail || e.message))
  }
}

onMounted(loadGroups)
</script>

<style scoped>
.action-icon-btn {
  font-size: 20px !important;
  border: none !important;
  background: transparent !important;
  background-color: transparent !important;
  box-shadow: none !important;
  padding: 4px !important;
  min-width: auto !important;
  height: auto !important;
  border-radius: 4px !important;
  transition: all 0.2s ease !important;
}
.action-icon-btn:hover,
.action-icon-btn:focus,
.action-icon-btn:active {
  background: transparent !important;
  background-color: transparent !important;
  box-shadow: none !important;
  border: none !important;
  transform: scale(1.22) !important;
  opacity: 0.85;
}

/* 强制覆盖主题可能附带的背景和边框颜色 */
.el-button.action-icon-btn.el-button--primary {
  color: var(--el-color-primary) !important;
}
.el-button.action-icon-btn.el-button--info {
  color: var(--el-color-info) !important;
}
.el-button.action-icon-btn.el-button--warning {
  color: var(--el-color-warning) !important;
}
.el-button.action-icon-btn.el-button--danger {
  color: var(--el-color-danger) !important;
}

.path-icon {
  font-size: 16px !important;
  margin-right: 4px;
  vertical-align: -2px;
}

.file-icon {
  font-size: 20px !important;
}

/* 移除文件夹卡片的悬停上浮、缩放及阴影动画效果 */
.folder-card {
  transition: border-color 0.2s ease, background 0.2s ease !important;
}
.folder-card:hover {
  transform: none !important;
  box-shadow: none !important;
  border-color: color-mix(in srgb, var(--md-primary) 20%, #e2e8f0) !important;
  background: color-mix(in srgb, var(--md-primary) 2%, #ffffff) !important;
}
.folder-card:active {
  transform: none !important;
}
.folder-card:hover .folder-main-icon {
  transform: none !important;
}
.folder-card:hover .folder-arrow {
  transform: none !important;
}
</style>

