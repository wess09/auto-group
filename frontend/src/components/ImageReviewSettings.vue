<template>
  <v-btn variant="tonal" :prepend-icon="mdiImageSearchOutline" @click="dialog = true">
    LLM 图片审核配置
  </v-btn>
  <v-dialog v-model="dialog" max-width="720" scrollable>
    <v-card title="LLM 多模态图片审核">
      <v-card-text>
        <QueryError :error="query.error.value" @retry="query.refetch()" />
        <v-progress-linear v-if="query.isFetching.value" indeterminate class="mb-4" />
        <v-form ref="formRef" @submit.prevent="save">
          <v-switch v-model="form.enabled" label="启用图片审核服务" color="primary" />
          <p class="text-body-2 mb-4">
            按排列顺序使用启用渠道；接口失败或输出无效时自动切换，正常结论直接结束审核。
          </p>
          <div class="d-flex ga-2 mb-4 flex-wrap">
            <v-select
              v-if="form.channels.length"
              v-model="selected"
              label="当前渠道（按优先级）"
              :items="channelOptions"
              hide-details
            />
            <v-btn variant="tonal" :disabled="form.channels.length >= 8" @click="addChannel">
              新增渠道
            </v-btn>
          </div>
          <template v-if="channel">
            <div class="d-flex ga-2 mb-4">
              <v-btn
                variant="text"
                size="small"
                :disabled="selected === 0"
                @click="moveChannel(-1)"
              >
                上移
              </v-btn>
              <v-btn
                variant="text"
                size="small"
                :disabled="selected === form.channels.length - 1"
                @click="moveChannel(1)"
              >
                下移
              </v-btn>
              <v-btn variant="text" size="small" color="error" @click="removeChannel">
                移除渠道
              </v-btn>
            </div>
            <v-text-field v-model="channel.name" label="渠道名称" />
            <v-switch v-model="channel.enabled" label="启用此渠道" color="primary" />
            <v-text-field
              v-model="channel.base_url"
              label="API Base URL"
              :rules="required"
              hint="例如 https://api.openai.com/v1；也可填兼容接口的完整 /chat/completions 地址"
              persistent-hint
            />
            <v-text-field
              v-model="channel.api_key"
              label="API Key"
              type="password"
              autocomplete="new-password"
              :disabled="channel.clear_api_key"
              :hint="
                channel.api_key_configured
                  ? '已配置；留空保留原密钥'
                  : '未配置；本地无鉴权服务可留空'
              "
              persistent-hint
            />
            <v-checkbox
              v-if="channel.api_key_configured"
              v-model="channel.clear_api_key"
              label="清除已保存的 API Key"
            />
            <v-text-field
              v-model="channel.model"
              label="多模态模型名称"
              :rules="channel.enabled ? required : []"
              hint="填写服务商实际支持的图片理解模型"
              persistent-hint
            />
            <v-select
              v-model="channel.response_format"
              label="输出模式"
              :items="outputModes"
              hint="小模型优先用 ToolCall；输出无效会记录日志并尝试下一个启用渠道"
              persistent-hint
            />
            <v-select
              v-model="channel.reasoning_effort"
              label="思考强度（reasoning_effort）"
              :items="efforts"
              hint="默认不发送此参数；可用值取决于模型和服务商"
              persistent-hint
            />
            <v-text-field
              v-model.number="channel.max_completion_tokens"
              label="输出总预算（max_completion_tokens）"
              type="number"
              min="128"
              max="131072"
              hint="包含思考 token 和最终结果；预算过小可能导致结果截断并跳过处理"
              persistent-hint
            />
            <v-textarea
              v-model="extraBodyText"
              label="服务商扩展参数（JSON）"
              rows="3"
              :rules="[validExtraBody]"
              hint='可设置独立思考预算，例如 {"thinking":{"type":"enabled","budget_tokens":1024}}；按服务商文档填写，不支持的参数请留空'
              persistent-hint
            />
            <v-select
              v-model="channel.image_detail"
              label="图片精细度"
              :items="['auto', 'low', 'high', 'original']"
            />
            <v-text-field
              v-model.number="channel.timeout_seconds"
              label="接口超时（秒）"
              type="number"
              min="1"
              max="180"
            />
          </template>
          <v-divider class="my-4" />
          <v-text-field
            v-model.number="form.min_confidence"
            label="动作最低置信度（0–1）"
            type="number"
            min="0"
            max="1"
            step="0.05"
          />
          <v-textarea v-model="form.system_prompt" label="审核提示词" :rules="required" rows="8" />
          <v-btn variant="text" size="small" :disabled="!query.data.value" @click="resetPrompt">
            恢复默认提示词
          </v-btn>
          <p class="text-body-2 mt-4">
            需在消息审查规则中开启“LLM
            多模态图片审核”。按规则选择撤回、禁言或两者；接口失败自动尝试备用渠道，全部失败或低置信度仅打印日志。
          </p>
        </v-form>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="dialog = false">取消</v-btn>
        <v-btn
          :loading="saving"
          :disabled="!query.data.value || query.isFetching.value"
          @click="save"
        >
          保存
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { mdiImageSearchOutline } from '@mdi/js'
import { socket } from '../api/client'
import type { ImageReviewChannelIn } from '../api/generated'
import { queryClient, useRpcQuery } from '../api/queries'
import { notify, report } from '../stores/ui'
import QueryError from './QueryError.vue'

const dialog = ref(false),
  saving = ref(false)
const query = useRpcQuery('image-review.get', {}, 'image-review', () => dialog.value)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)
type ChannelForm = ImageReviewChannelIn & { api_key_configured: boolean }
const form = reactive({
  enabled: false,
  system_prompt: '',
  min_confidence: 0.85,
  channels: [] as ChannelForm[],
})
const selected = ref(0)
const channel = computed(() => form.channels[selected.value])
const channelOptions = computed(() =>
  form.channels.map((item, index) => ({
    title: `${index + 1}. ${item.name || item.model || '未命名'}${item.enabled ? '' : '（停用）'}`,
    value: index,
  })),
)
const extraBodies = reactive<Record<string, string>>({})
const extraBodyText = computed({
  get: () => (channel.value ? extraBodies[channel.value.id] || '{}' : '{}'),
  set: (value) => {
    if (channel.value) extraBodies[channel.value.id] = value
  },
})
function addChannel() {
  if (form.channels.length >= 8) return
  form.channels.push({
    id: crypto.randomUUID(),
    name: `渠道 ${form.channels.length + 1}`,
    enabled: true,
    base_url: 'https://api.openai.com/v1',
    api_key: '',
    api_key_configured: false,
    clear_api_key: false,
    model: '',
    response_format: 'tool_call',
    reasoning_effort: '',
    max_completion_tokens: 2048,
    image_detail: 'auto',
    timeout_seconds: 30,
    extra_body: {},
  })
  selected.value = form.channels.length - 1
}
function moveChannel(offset: number) {
  const destination = selected.value + offset
  const item = form.channels.splice(selected.value, 1)[0]
  if (!item) return
  form.channels.splice(destination, 0, item)
  selected.value = destination
}
function removeChannel() {
  const item = form.channels.splice(selected.value, 1)[0]
  if (item) delete extraBodies[item.id]
  selected.value = Math.max(0, Math.min(selected.value, form.channels.length - 1))
}
const required = [(value: unknown) => !!String(value ?? '').trim() || '请填写此项']
const outputModes = [
  { title: 'ToolCall（推荐小模型）', value: 'tool_call' },
  { title: '严格 JSON Schema', value: 'json_schema' },
  { title: 'JSON 对象', value: 'json_object' },
  { title: '仅提示词约束', value: 'none' },
]
const efforts = [
  { title: '模型默认（不发送参数）', value: '' },
  ...['none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'].map((value) => ({
    title: value,
    value,
  })),
]
function parseExtraBody(text = extraBodyText.value) {
  const value = JSON.parse(text.trim() || '{}')
  if (!value || Array.isArray(value) || typeof value !== 'object')
    throw new Error('扩展参数必须为 JSON 对象')
  return value
}
function validExtraBody() {
  try {
    parseExtraBody()
    return true
  } catch {
    return '请输入合法的 JSON 对象'
  }
}
watch(
  () => query.data.value,
  (value) => {
    if (value && !saving.value) {
      form.enabled = value.enabled
      form.system_prompt = value.system_prompt
      form.min_confidence = value.min_confidence
      form.channels = value.channels.map((item) => ({ ...item, api_key: '', clear_api_key: false }))
      Object.keys(extraBodies).forEach((key) => delete extraBodies[key])
      for (const item of value.channels)
        extraBodies[item.id] = JSON.stringify(item.extra_body, null, 2)
      selected.value = 0
    }
  },
)
watch(dialog, (value) => {
  if (!value)
    form.channels.forEach((item) => {
      item.api_key = ''
    })
})
watch(
  () => channel.value?.clear_api_key,
  (value) => {
    if (value && channel.value) channel.value.api_key = ''
  },
)
function resetPrompt() {
  form.system_prompt = query.data.value?.default_system_prompt || ''
}
async function save() {
  if (saving.value || !(await formRef.value?.validate())?.valid) return
  saving.value = true
  try {
    const channels = form.channels.map((item) => {
      const { api_key_configured: _, ...data } = item
      return { ...data, extra_body: parseExtraBody(extraBodies[item.id] || '{}') }
    })
    await socket.request('image-review.update', { ...form, channels })
    dialog.value = false
    void queryClient.invalidateQueries({ queryKey: ['rpc', 'image-review.get'] })
    notify('图片审核配置已保存')
  } catch (error) {
    report(error)
  } finally {
    saving.value = false
  }
}
</script>
