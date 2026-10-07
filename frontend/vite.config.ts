import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vuetify from 'vite-plugin-vuetify'
export default defineConfig({
  plugins: [vue(), vuetify({ autoImport: true })],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8080', ws: true, changeOrigin: true } },
  },
  preview: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8080', ws: true, changeOrigin: true } },
  },
})
