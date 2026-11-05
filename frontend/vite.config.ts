import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vuetify from 'vite-plugin-vuetify'
import { brandingPlugin } from './build/branding'
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const appName = env.VITE_APP_NAME?.trim() || 'Auto Group'
  const iconUrl = env.VITE_APP_ICON_URL?.trim() || ''
  return {
    plugins: [vue(), vuetify({ autoImport: true }), brandingPlugin(appName, iconUrl)],
    server: {
      port: 5173,
      proxy: { '/api': { target: 'http://127.0.0.1:8080', ws: true, changeOrigin: true } },
    },
    preview: {
      port: 5173,
      proxy: { '/api': { target: 'http://127.0.0.1:8080', ws: true, changeOrigin: true } },
    },
  }
})
