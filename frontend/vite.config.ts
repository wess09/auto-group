import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [
      vue(),
      {
        name: 'auto-group-html-env',
        transformIndexHtml(html) {
          return html
            .replaceAll(
              '__ALIYUN_CAPTCHA_REGION__',
              JSON.stringify(env.VITE_ALIYUN_CAPTCHA_REGION || 'cn')
            )
            .replaceAll(
              '__ALIYUN_CAPTCHA_PREFIX__',
              JSON.stringify(env.VITE_ALIYUN_CAPTCHA_PREFIX || '')
            )
        }
      }
    ],
    server: {
      port: 5173,
      proxy: {
        '/api': 'http://127.0.0.1:8080'
      }
    }
  }
})
