<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">精华管理</h1>
        <p class="page-subtitle">把指定内容发送到单群或多群，并自动设为精华。</p>
      </div>
      <div class="toolbar">
        <el-button @click="loadAll">刷新</el-button>
      </div>
    </div>

    <div v-loading="loading" element-loading-text="正在加载群精华消息数据..." style="min-height: 400px;">
      <div class="publish-section">
        <div class="publish-header">
          <el-icon class="publish-icon"><EditPen /></el-icon>
          <span class="publish-title">发布精华消息</span>
        </div>
        <div class="publish-body">
          <div class="form-section">
            <div class="section-label">
              <span class="label-dot"></span>
              选择目标群
            </div>
            <GroupSelector v-model="selectedGroups" :groups="groups" />
          </div>
          <div class="form-section" style="margin-top: 18px">
            <div class="section-label">
              <span class="label-dot"></span>
              精华内容
            </div>
            <el-input 
              v-model="content" 
              type="textarea" 
              placeholder="请输入要设为精华的消息内容，支持换行..." 
              :rows="4"
              class="custom-textarea"
            />
          </div>
          <div class="publish-actions">
            <el-button 
              type="primary" 
              :disabled="!selectedGroups.length || !content" 
              @click="create"
              :icon="Promotion"
              class="publish-btn"
            >
              发送并设精
            </el-button>
            <el-button 
              :disabled="!selectedGroups.length" 
              @click="syncSelected"
              :icon="Refresh"
              class="sync-btn"
            >
              同步选中群精华
            </el-button>
          </div>
        </div>
      </div>

      <div class="content-band">
        <el-tabs v-model="activeTab" style="margin-bottom: 12px">
          <el-tab-pane
            v-for="g in groups"
            :key="g.group_id"
            :label="g.name ? `${g.name} (${g.group_id})` : String(g.group_id)"
            :name="String(g.group_id)"
          />
        </el-tabs>

        <div v-if="filteredEssence.length" class="essence-cards-grid">
          <el-card v-for="item in filteredEssence" :key="item.message_id" class="essence-card" shadow="hover">
            <div class="essence-card-header">
              <div class="user-profile">
                <el-avatar 
                  :size="36" 
                  :src="getQQAvatar(item.sender_id)" 
                  class="user-avatar"
                >
                  <el-icon><User /></el-icon>
                </el-avatar>
                <div class="user-meta">
                  <span class="user-qq">{{ item.sender_id || '系统/未知' }}</span>
                  <span class="essence-msg-id">ID: {{ item.message_id }}</span>
                </div>
              </div>
            </div>

            <div class="essence-card-body">
              <div class="chat-bubble">
                <p class="essence-content-text">{{ item.content }}</p>
              </div>
            </div>

            <div class="essence-card-footer">
              <div class="sync-time-wrap">
                <el-icon class="time-icon"><Clock /></el-icon>
                <span class="essence-time">{{ formatTime(item.synced_at) }}</span>
              </div>
              <el-popconfirm title="确认移出精华？" @confirm="remove(item)">
                <template #reference>
                  <el-tooltip content="移出精华" placement="top" :show-after="300">
                    <el-button type="danger" link :icon="Delete" class="remove-btn" />
                  </el-tooltip>
                </template>
              </el-popconfirm>
            </div>
          </el-card>
        </div>
        <el-empty v-else description="当前暂无精华消息数据" :image-size="120" style="padding: 40px 0" />
      </div>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { User, Clock, Delete, EditPen, Promotion, Refresh } from '@element-plus/icons-vue'
import AdminLayout from '../components/AdminLayout.vue'
import GroupSelector from '../components/GroupSelector.vue'
import { api, type ManagedGroup } from '../api/client'

const groups = ref<ManagedGroup[]>([])
const essence = ref<any[]>([])
const selectedGroups = ref<number[]>([])
const content = ref('')
const activeTab = ref('')
const loading = ref(true)

const filteredEssence = computed(() => {
  if (!activeTab.value) return []
  const gid = Number(activeTab.value)
  return essence.value.filter((e) => e.group_id === gid)
})

function getGroupName(groupId: number): string {
  const group = groups.value.find((g) => g.group_id === groupId)
  return group ? (group.name || String(groupId)) : String(groupId)
}

function getQQAvatar(qq: any): string {
  if (!qq) return ''
  const qqNum = String(qq).trim()
  if (!/^\d+$/.test(qqNum)) return '' // Only numbers are valid QQ accounts
  return `https://q1.qlogo.cn/g?b=qq&nk=${qqNum}&s=100`
}

function formatTime(val: string | undefined) {
  if (!val) return '-'
  const cleaned = val.replace('T', ' ')
  if (cleaned.length >= 19) {
    return cleaned.substring(0, 19)
  }
  return cleaned
}

async function loadAll() {
  loading.value = true
  try {
    const [groupRes, essenceRes] = await Promise.all([api.get('/admin/groups'), api.get('/admin/essence')])
    groups.value = groupRes.data
    essence.value = essenceRes.data
    if (!activeTab.value && groups.value.length > 0) {
      activeTab.value = String(groups.value[0].group_id)
    }
  } catch (error: any) {
    ElMessage.error('加载精华消息失败：' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

async function create() {
  const { data } = await api.post('/admin/essence/create', { group_ids: selectedGroups.value, content: content.value })
  ElMessage[data.ok ? 'success' : 'warning']('任务完成')
  content.value = ''
  loadAll()
}

async function syncSelected() {
  for (const groupId of selectedGroups.value) {
    await api.post(`/admin/essence/sync/${groupId}`)
  }
  ElMessage.success('同步完成')
  loadAll()
}

async function remove(row: any) {
  await api.post('/admin/essence/delete', { group_id: row.group_id, message_ids: [row.message_id] })
  ElMessage.success('已移出')
  loadAll()
}

onMounted(loadAll)
</script>

<style scoped>
.essence-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
  margin-top: 16px;
}

.essence-card {
  display: flex;
  flex-direction: column;
  height: 320px;
  border-radius: 16px !important;
  border: 1px solid rgba(226, 232, 240, 0.8) !important;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px -2px rgba(0, 0, 0, 0.02) !important;
  background: #ffffff !important;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

.essence-card:hover {
  border-color: color-mix(in srgb, var(--md-primary) 25%, #e2e8f0) !important;
  box-shadow: 0 10px 15px -3px rgba(15, 23, 42, 0.08) !important;
}

:deep(.essence-card .el-card__body) {
  padding: 16px !important;
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

.essence-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
  flex-shrink: 0;
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.user-avatar {
  border: 1px solid rgba(226, 232, 240, 0.8);
  background-color: #f1f5f9;
  flex-shrink: 0;
}

.user-meta {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.user-qq {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--geeker-text);
  line-height: 1.2;
}

.essence-msg-id {
  font-size: 11px;
  color: var(--geeker-text-secondary);
}

.essence-group-tag {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border-radius: 6px !important;
}

.essence-card-body {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 14px;
  padding-right: 4px;
}

.essence-card-body::-webkit-scrollbar {
  width: 4px;
}

.essence-card-body::-webkit-scrollbar-thumb {
  background: rgba(15, 23, 42, 0.08);
  border-radius: 4px;
}

.chat-bubble {
  background: #f8fafc;
  padding: 10px 12px;
  border-radius: 4px 12px 12px 12px;
  border: 1px solid rgba(226, 232, 240, 0.5);
  display: inline-block;
  width: 100%;
  box-sizing: border-box;
}

.essence-content-text {
  font-size: 13px;
  line-height: 1.6;
  color: #334155;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

.essence-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid #f1f5f9;
  padding-top: 12px;
  margin-top: auto;
  flex-shrink: 0;
}

.sync-time-wrap {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--geeker-text-secondary);
}

.time-icon {
  font-size: 12px;
}

.essence-time {
  font-size: 11px;
}

.remove-btn {
  font-size: 16px !important;
  padding: 6px !important;
  height: 32px !important;
  width: 32px !important;
  border-radius: 50% !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

.remove-btn:hover {
  background-color: var(--el-color-danger-light-9) !important;
  color: var(--el-color-danger) !important;
  transform: scale(1.12) !important;
}

/* 发布面板样式 */
.publish-section {
  background: #ffffff;
  border: 1px solid rgba(226, 232, 240, 0.8);
  border-radius: 16px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px -2px rgba(0, 0, 0, 0.02);
  margin-bottom: 24px;
  overflow: hidden;
  transition: border-color 0.25s ease, box-shadow 0.25s ease;
}

.publish-section:hover {
  border-color: rgba(226, 232, 240, 1);
  box-shadow: 0 10px 15px -3px rgba(15, 23, 42, 0.04);
}

.publish-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  border-bottom: 1px solid #f1f5f9;
  background: #fafbfd;
}

.publish-icon {
  font-size: 18px;
  color: var(--md-primary);
  background-color: color-mix(in srgb, var(--md-primary) 10%, #ffffff);
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.publish-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--geeker-text);
}

.publish-body {
  padding: 20px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--geeker-text);
}

.label-dot {
  width: 6px;
  height: 6px;
  background-color: var(--md-primary);
  border-radius: 50%;
  display: inline-block;
}

.publish-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f1f5f9;
}

.publish-btn {
  padding: 10px 20px !important;
  font-size: 14px !important;
  height: 38px !important;
  background: linear-gradient(135deg, var(--md-primary) 0%, color-mix(in srgb, var(--md-primary) 85%, #000) 100%) !important;
  border: none !important;
  color: #ffffff !important;
  font-weight: 600 !important;
  box-shadow: 0 4px 10px color-mix(in srgb, var(--md-primary) 20%, transparent) !important;
}

.publish-btn:hover {
  opacity: 0.92;
  box-shadow: 0 6px 14px color-mix(in srgb, var(--md-primary) 30%, transparent) !important;
}

.sync-btn {
  padding: 10px 20px !important;
  font-size: 14px !important;
  height: 38px !important;
  font-weight: 500 !important;
  border: 1px solid #e2e8f0 !important;
  background-color: #ffffff !important;
  color: var(--geeker-text-secondary) !important;
}

.sync-btn:hover {
  border-color: var(--md-primary) !important;
  color: var(--md-primary) !important;
  background-color: color-mix(in srgb, var(--md-primary) 3%, #ffffff) !important;
}

:deep(.custom-textarea .el-textarea__inner) {
  border-radius: 10px !important;
  border: 1px solid rgba(226, 232, 240, 0.8) !important;
  padding: 12px !important;
  font-size: 13.5px !important;
  background-color: #fcfdfe !important;
  transition: all 0.2s ease !important;
  font-family: inherit;
}

:deep(.custom-textarea .el-textarea__inner:focus) {
  border-color: var(--md-primary) !important;
  background-color: #ffffff !important;
  box-shadow: 0 0 0 1px var(--md-primary) inset, 0 0 0 3px color-mix(in srgb, var(--md-primary) 10%, transparent) !important;
}
</style>
