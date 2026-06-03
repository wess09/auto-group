<template>
  <section class="login-page">
    <div class="login-panel">
      <h1 class="join-title">Auto Group</h1>
      <p class="join-meta">登录群管理后台</p>
      <n-form @submit.prevent="submit">
        <n-form-item label="账号">
          <n-input v-model:value="form.username" placeholder="请输入账号" />
        </n-form-item>
        <n-form-item label="密码">
          <n-input v-model:value="form.password" type="password" placeholder="请输入密码" />
        </n-form-item>
        <div id="aliyun-captcha-element" class="captcha-element"></div>
        <button
          id="aliyun-captcha-button"
          ref="captchaButton"
          class="captcha-trigger"
          type="button"
          tabindex="-1"
          aria-hidden="true"
        ></button>
        <n-button type="primary" block :loading="loading || captchaLoading" @click="submit">
          登录
        </n-button>
      </n-form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { api } from '../api/client'
import { adminBase } from '../adminRoute'

type AliyunCaptchaConfig = {
  region: string
  prefix: string
}

type AliyunCaptchaInstance = {
  refresh?: () => void
}

type AliyunCaptchaOptions = {
  SceneId: string
  mode: 'popup' | 'embed'
  element: string
  button: string
  success: (captchaVerifyParam: string) => void
  fail: (result: unknown) => void
  getInstance: (instance: AliyunCaptchaInstance) => void
  server: string[]
  slideStyle: {
    width: number
    height: number
  }
}

declare global {
  interface Window {
    AliyunCaptchaConfig?: AliyunCaptchaConfig
    initAliyunCaptcha?: (options: AliyunCaptchaOptions) => void
  }
}

const aliyunCaptchaScriptSrc =
  'https://o.alicdn.com/captcha-frontend/aliyunCaptcha/AliyunCaptcha.js'
let aliyunCaptchaScriptPromise: Promise<void> | null = null

const router = useRouter()
const message = useMessage()
const loading = ref(false)
const captchaLoading = ref(false)
const captchaReady = ref(false)
const captchaError = ref('')
const captchaButton = ref<HTMLButtonElement | null>(null)
const captcha = ref<AliyunCaptchaInstance | null>(null)
const form = reactive({ username: '', password: '' })
const captchaConfig = {
  region: import.meta.env.VITE_ALIYUN_CAPTCHA_REGION || 'cn',
  prefix: import.meta.env.VITE_ALIYUN_CAPTCHA_PREFIX || '',
  sceneId: import.meta.env.VITE_ALIYUN_CAPTCHA_SCENE_ID || ''
}
const captchaEnabled = computed(() => Boolean(captchaConfig.prefix && captchaConfig.sceneId))

onMounted(() => {
  void setupCaptcha()
})

async function submit() {
  if (loading.value) return
  if (!validateForm()) return
  if (captchaEnabled.value) {
    if (captchaError.value) {
      message.error(captchaError.value)
      return
    }
    if (!captchaReady.value) {
      message.warning(captchaLoading.value ? '验证码加载中，请稍后再试' : '验证码尚未就绪，请刷新页面')
      return
    }
    captchaButton.value?.click()
    return
  }
  await login()
}

function validateForm() {
  if (!form.username.trim()) {
    message.warning('请输入账号')
    return false
  }
  if (!form.password) {
    message.warning('请输入密码')
    return false
  }
  return true
}

async function login(captchaVerifyParam?: string) {
  loading.value = true
  try {
    const { data, headers } = await api.post(
      '/auth/login',
      { ...form },
      captchaVerifyParam ? { headers: { 'captcha-verify-param': captchaVerifyParam } } : undefined
    )
    const verifyCode = getCaptchaVerifyCode(headers)
    if (verifyCode && verifyCode !== 'T001') {
      message.error(`验证码验证失败：${verifyCode}`)
      return false
    }
    localStorage.setItem('token', data.access_token)
    router.push(adminBase)
    return true
  } catch (error: any) {
    const verifyCode = getCaptchaVerifyCode(error.response?.headers)
    if (verifyCode && verifyCode !== 'T001') {
      message.error(`验证码验证失败：${verifyCode}`)
    } else {
      message.error(error.response?.data?.detail ?? '登录失败')
    }
    return false
  } finally {
    loading.value = false
  }
}

async function setupCaptcha() {
  if (!captchaEnabled.value) return
  captchaLoading.value = true
  try {
    await loadAliyunCaptchaScript({
      region: captchaConfig.region,
      prefix: captchaConfig.prefix
    })
    if (!window.initAliyunCaptcha) {
      throw new Error('Aliyun captcha initializer is missing')
    }
    window.initAliyunCaptcha({
      SceneId: captchaConfig.sceneId,
      mode: 'popup',
      element: '#aliyun-captcha-element',
      button: '#aliyun-captcha-button',
      success: (captchaVerifyParam: string) => {
        void handleCaptchaSuccess(captchaVerifyParam)
      },
      fail: (result: unknown) => {
        console.error(result)
      },
      getInstance: (instance: AliyunCaptchaInstance) => {
        captcha.value = instance
        captchaReady.value = true
        captchaError.value = ''
      },
      server: ['captcha-esa-open.aliyuncs.com', 'captcha-esa-open-b.aliyuncs.com'],
      slideStyle: {
        width: 360,
        height: 40
      }
    })
  } catch {
    captchaError.value = '验证码初始化失败，请刷新页面后重试'
    message.error(captchaError.value)
  } finally {
    captchaLoading.value = false
  }
}

async function handleCaptchaSuccess(captchaVerifyParam: string) {
  const ok = await login(captchaVerifyParam)
  if (!ok) {
    captcha.value?.refresh?.()
  }
}

function loadAliyunCaptchaScript(config: AliyunCaptchaConfig) {
  window.AliyunCaptchaConfig = config
  if (window.initAliyunCaptcha) return Promise.resolve()
  if (aliyunCaptchaScriptPromise) return aliyunCaptchaScriptPromise

  aliyunCaptchaScriptPromise = new Promise<void>((resolve, reject) => {
    const existingScript = document.querySelector<HTMLScriptElement>(
      `script[src="${aliyunCaptchaScriptSrc}"]`
    )
    if (existingScript?.dataset.loaded === 'true' && !window.initAliyunCaptcha) {
      reject(new Error('Aliyun captcha script loaded without initializer'))
      return
    }

    const script = existingScript ?? document.createElement('script')
    const handleLoad = () => {
      script.dataset.loaded = 'true'
      resolve()
    }
    const handleError = () => {
      aliyunCaptchaScriptPromise = null
      reject(new Error('Aliyun captcha script failed to load'))
    }

    script.addEventListener('load', handleLoad, { once: true })
    script.addEventListener('error', handleError, { once: true })
    if (!existingScript) {
      script.type = 'text/javascript'
      script.src = aliyunCaptchaScriptSrc
      script.dataset.aliyunCaptchaScript = 'true'
      document.head.appendChild(script)
    }
  })
  return aliyunCaptchaScriptPromise
}

function getCaptchaVerifyCode(headers: any) {
  return (
    headers?.['x-captcha-verify-code'] ??
    headers?.['X-Captcha-Verify-Code'] ??
    (typeof headers?.get === 'function' ? headers.get('X-Captcha-Verify-Code') : undefined)
  )
}
</script>
