import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  use: { baseURL: 'http://127.0.0.1:5173', headless: true, trace: 'retain-on-failure' },
  webServer: [
    {
      command: 'uv run --project .. python ../tests/e2e_server.py',
      url: 'http://127.0.0.1:8080/api/public/recommended-group',
      timeout: 60000,
      reuseExistingServer: false,
    },
    {
      command: 'npm run preview -- --outDir dist-e2e',
      url: 'http://127.0.0.1:5173',
      timeout: 60000,
      reuseExistingServer: false,
    },
  ],
})
