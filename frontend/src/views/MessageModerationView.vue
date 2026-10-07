<template>
  <ResourceEditor resource="moderation">
    <template #header>
      <v-btn variant="tonal" :prepend-icon="mdiCloudOutline" @click="dialog = true">
        腾讯云配置
      </v-btn>
    </template>
    <v-dialog v-model="dialog" max-width="600" scrollable>
      <v-card title="腾讯云文本审核配置">
        <v-card-text>
          <QueryError :error="query.error.value" @retry="query.refetch()" />
          <v-progress-linear v-if="query.isFetching.value" indeterminate class="mb-4" />
          <v-text-field v-model="form.secret_id" label="SecretId" />
          <v-text-field
            v-model="form.secret_key"
            label="SecretKey"
            type="password"
            :hint="
              query.data.value?.secret_key_configured
                ? '密钥已配置；留空保留现有密钥'
                : '尚未配置密钥'
            "
            persistent-hint
            class="mb-2"
          />
          <v-text-field v-model="form.region" label="地域" />
          <v-text-field v-model="form.biz_type" label="策略编号（BizType）" />
          <v-text-field v-model="form.source_language" label="语言" />
          <v-text-field
            v-model.number="form.timeout_seconds"
            label="超时秒数"
            type="number"
            min="1"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="dialog = false">取消</v-btn>
          <v-btn :loading="saving" :disabled="!query.data.value" @click="save">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </ResourceEditor>
</template>
<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { mdiCloudOutline } from '@mdi/js'
import ResourceEditor from '../components/ResourceEditor.vue'
import QueryError from '../components/QueryError.vue'
import { socket } from '../api/client'
import { queryClient, useRpcQuery } from '../api/queries'
import { notify, report } from '../stores/ui'
const dialog = ref(false),
  saving = ref(false)
const query = useRpcQuery('cloud.get', {}, 'cloud', () => dialog.value)
const form = reactive({
  secret_id: '',
  secret_key: '',
  region: 'ap-guangzhou',
  biz_type: '',
  source_language: 'zh',
  timeout_seconds: 5,
})
watch(
  () => query.data.value,
  (value) => {
    if (value) {
      const { secret_key_configured: _, ...data } = value
      Object.assign(form, data, { secret_key: '' })
    }
  },
)
async function save() {
  saving.value = true
  try {
    await socket.request('cloud.update', form)
    form.secret_key = ''
    dialog.value = false
    void queryClient.invalidateQueries({ queryKey: ['rpc', 'cloud.get'] })
    notify('配置已保存')
  } catch (error) {
    report(error)
  } finally {
    saving.value = false
  }
}
</script>
