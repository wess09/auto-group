<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">消息审查</h1>
        <p class="page-subtitle">按群配置正则规则，支持 OCR 图片文字识别，可选择命中后交由腾讯云 AI 二次审核。</p>
      </div>
      <div class="toolbar">
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" @click="openCreate">新增规则</el-button>
      </div>
    </div>
    <div v-loading="loading" element-loading-text="正在加载审核配置与规则..." style="min-height: 400px;">
      <div class="content-band cloud-config-band">
      <div class="section-head">
        <div>
          <h3>腾讯云审核配置</h3>
          <span>规则开启 AI 二审后使用这组 TMS 配置。</span>
        </div>
        <el-tag :type="cloudConfig.secret_key_configured ? 'success' : 'warning'">
          {{ cloudConfig.secret_key_configured ? '密钥已配置' : '密钥未配置' }}
        </el-tag>
      </div>
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="SecretId">
            <el-input v-model="cloudForm.secret_id" autocomplete="off" />
          </el-form-item>
          <el-form-item label="SecretKey">
            <el-input
              v-model="cloudForm.secret_key"
              autocomplete="off"
              show-password
              :placeholder="cloudConfig.secret_key_configured ? '留空则保留已保存密钥' : '请输入 SecretKey'"
              type="password"
            />
          </el-form-item>
          <el-form-item label="地域">
            <el-input v-model="cloudForm.region" />
          </el-form-item>
          <el-form-item label="策略编号 BizType">
            <el-input v-model="cloudForm.biz_type" />
          </el-form-item>
          <el-form-item label="语言">
            <el-select v-model="cloudForm.source_language" :options="languageOptions" />
          </el-form-item>
          <el-form-item label="超时秒数">
            <el-input-number v-model="cloudForm.timeout_seconds" :min="1" :precision="1" />
          </el-form-item>
        </div>
        <div class="toolbar">
          <el-button type="primary" @click="saveCloudConfig">保存云审核配置</el-button>
        </div>
      </el-form>
    </div>
    <div class="content-band">
      <el-table :data="rules" border>
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column label="适用群" width="120">
          <template #default="{ row }">{{ row.group_id ?? '全局' }}</template>
        </el-table-column>
        <el-table-column label="动作" width="140">
          <template #default="{ row }">
            <el-tag :type="row.action === 'recall' ? 'primary' : 'warning'">{{ actionLabels[row.action] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="禁言" width="120">
          <template #default="{ row }">{{ row.action === 'recall' ? '-' : `${row.mute_duration_seconds} 秒` }}</template>
        </el-table-column>
        <el-table-column label="OCR" width="90">
          <template #default="{ row }">
            <el-tag :type="row.ocr_enabled ? 'success' : 'info'">
              {{ row.ocr_enabled ? '开启' : '关闭' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="AI二审" width="100">
          <template #default="{ row }">
            <el-tag :type="row.cloud_review_enabled ? 'success' : 'info'">
              {{ row.cloud_review_enabled ? '开启' : '关闭' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="正则" min-width="240">
          <template #default="{ row }">
            <el-tag v-for="pattern in row.patterns" :key="pattern" class="tag-gap">
              {{ pattern }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-space>
              <el-button size="small" @click="openEdit(row)">编辑</el-button>
              <el-popconfirm title="确认删除？" @confirm="remove(row.id)">
                <template #reference>
                  <el-button size="small" type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </el-space>
          </template>
        </el-table-column>
      </el-table>
      </div>
    </div>
    <el-dialog v-model="showModal" title="消息审查规则" width="min(720px, 96vw)">
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="适用群号"><el-input-number v-model="form.group_id" placeholder="留空为全局" /></el-form-item>
          <el-form-item label="动作"><el-select v-model="form.action" :options="actionOptions" /></el-form-item>
          <el-form-item label="禁言秒数"><el-input-number v-model="form.mute_duration_seconds" :min="1" /></el-form-item>
          <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
          <el-form-item label="OCR 图片识别"><el-switch v-model="form.ocr_enabled" /></el-form-item>
          <el-form-item label="AI二次审核"><el-switch v-model="form.cloud_review_enabled" /></el-form-item>
        </div>
        <el-form-item label="正则表达式">
          <el-input v-model="patternsText" type="textarea" placeholder="每行一个正则表达式" />
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="form.note" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showModal = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </AdminLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AdminLayout from '../components/AdminLayout.vue'
import { api, type MessageModerationRule, type TencentCloudTmsConfig } from '../api/client'

const rules = ref<MessageModerationRule[]>([])
const cloudConfig = reactive<TencentCloudTmsConfig>({
  secret_id: '',
  secret_key_configured: false,
  region: 'ap-guangzhou',
  biz_type: 'TencentCloudDefault',
  source_language: 'zh',
  timeout_seconds: 5
})
const cloudForm = reactive({
  secret_id: '',
  secret_key: '',
  region: 'ap-guangzhou',
  biz_type: 'TencentCloudDefault',
  source_language: 'zh',
  timeout_seconds: 5
})
const showModal = ref(false)
const editingId = ref<number | null>(null)
const loading = ref(true)
const defaultForm = {
  name: '',
  enabled: true,
  group_id: null as number | null,
  patterns: [] as string[],
  cloud_review_enabled: false,
  ocr_enabled: false,
  action: 'recall' as MessageModerationRule['action'],
  mute_duration_seconds: 600,
  note: ''
}
const form = reactive({ ...defaultForm })
const patternsText = computed({
  get: () => form.patterns.join('\n'),
  set: (value: string) => {
    form.patterns = value.split('\n').map((item) => item.trim()).filter(Boolean)
  }
})
const actionOptions = [
  { label: '撤回', value: 'recall' },
  { label: '禁言', value: 'mute' },
  { label: '撤回并禁言', value: 'recall_and_mute' }
]
const languageOptions = [
  { label: '中文', value: 'zh' },
  { label: '英文', value: 'en' }
]
const actionLabels: Record<string, string> = {
  recall: '撤回',
  mute: '禁言',
  recall_and_mute: '撤回并禁言'
}
async function load() {
  loading.value = true
  try {
    await Promise.all([loadRules(), loadCloudConfig()])
  } catch (error: any) {
    ElMessage.error('加载配置失败：' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

async function loadRules() {
  const { data } = await api.get('/admin/message-moderation-rules')
  rules.value = data
}

async function loadCloudConfig() {
  const { data } = await api.get('/admin/message-moderation-cloud-config')
  Object.assign(cloudConfig, data)
  Object.assign(cloudForm, {
    secret_id: data.secret_id,
    secret_key: '',
    region: data.region,
    biz_type: data.biz_type,
    source_language: data.source_language,
    timeout_seconds: data.timeout_seconds
  })
}

async function saveCloudConfig() {
  const { data } = await api.put('/admin/message-moderation-cloud-config', cloudForm)
  Object.assign(cloudConfig, data)
  cloudForm.secret_key = ''
  ElMessage.success('云审核配置已保存')
}

function openCreate() {
  editingId.value = null
  Object.assign(form, { ...defaultForm, patterns: [] })
  showModal.value = true
}

function openEdit(row: MessageModerationRule) {
  editingId.value = row.id
  Object.assign(form, { ...row, patterns: [...row.patterns] })
  showModal.value = true
}

async function save() {
  if (editingId.value) {
    await api.patch(`/admin/message-moderation-rules/${editingId.value}`, form)
  } else {
    await api.post('/admin/message-moderation-rules', form)
  }
  ElMessage.success('已保存')
  showModal.value = false
  loadRules()
}

async function remove(id: number) {
  await api.delete(`/admin/message-moderation-rules/${id}`)
  ElMessage.success('已删除')
  loadRules()
}

onMounted(load)
</script>

<style scoped>
.cloud-config-band {
  margin-bottom: 16px;
}
</style>
