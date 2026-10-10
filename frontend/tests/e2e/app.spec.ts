import { test, expect, type Page } from '@playwright/test'

async function login(page: Page) {
  const response = await page.request.post('http://127.0.0.1:8080/api/auth/login', {
    data: { username: 'admin', password: 'browser-password' },
  })
  const { access_token } = await response.json()
  await page.addInitScript((token) => localStorage.setItem('token', token), access_token)
}

test('login and public entry use MD3 without opening a WS connection', async ({ page }) => {
  let connections = 0
  page.on('websocket', (ws) => {
    if (new URL(ws.url()).pathname === '/api/admin/ws') connections++
  })
  await page.goto('/#/join')
  await expect(page.getByRole('heading', { name: '找到你的群' })).toBeVisible()
  await expect(page.getByRole('link', { name: '申请加入' })).toBeVisible()
  await page.goto('/#/admin/login')
  await page.getByLabel('账号', { exact: true }).fill('admin')
  await page.getByLabel('密码', { exact: true }).fill('browser-password')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('heading', { name: '仪表盘', exact: true })).toBeVisible()
  expect(connections).toBe(1)
})

test('logs request only the selected tab and one page of ten thousand rows', async ({ page }) => {
  await login(page)
  const chunks: string[] = []
  page.on('response', (response) => {
    if (response.url().endsWith('.js')) chunks.push(response.url())
  })
  const methods: string[] = [],
    responses: { items?: unknown[]; total?: number }[] = []
  page.on('websocket', (ws) => {
    ws.on('framesent', (frame) => {
      const message = JSON.parse(String(frame.payload))
      methods.push(message.method)
    })
    ws.on('framereceived', (frame) => {
      const message = JSON.parse(String(frame.payload))
      if (message.result?.total === 10000) responses.push(message.result)
    })
  })
  await page.goto('/#/admin/events')
  await expect(page.getByRole('cell', { name: '示例答案', exact: true }).first()).toBeVisible()
  expect(methods).toContain('joins.list')
  expect(methods).not.toContain('leaves.list')
  expect(methods).not.toContain('audits.list')
  expect(responses[0].items).toHaveLength(25)
  expect(chunks.some((url) => /DashboardView|FilesView|DedupeView|engine-/.test(url))).toBe(false)
  await page.getByRole('button', { name: '下一页' }).click()
  await expect.poll(() => responses.length).toBeGreaterThan(1)
  await page.getByRole('tab', { name: '操作日志', exact: true }).click()
  await expect(page.getByRole('cell', { name: /example\./ }).first()).toBeVisible()
  expect(methods).toContain('audits.list')
  await page.getByRole('button', { name: '退出登录' }).click()
  await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible()
  expect(await page.evaluate(() => localStorage.getItem('token'))).toBeNull()
})

test('CRUD and remote search work through one WS connection', async ({ page }) => {
  await login(page)
  let connections = 0
  page.on('websocket', (ws) => {
    if (new URL(ws.url()).pathname === '/api/admin/ws') connections++
  })
  await page.goto('/#/admin/join-blacklist')
  await page.getByRole('button', { name: '新增', exact: true }).click()
  await page.getByLabel('QQ 号', { exact: true }).fill('123456789')
  await page.getByLabel('备注', { exact: true }).fill('浏览器测试')
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByRole('cell', { name: '123456789', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '停用', exact: true }).click()
  await expect(page.getByRole('button', { name: '启用', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '删除', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: '删除', exact: true }).click()
  await expect(page.getByRole('cell', { name: '123456789', exact: true })).toHaveCount(0)
  await page.getByRole('link', { name: '群配置', exact: true }).first().click()
  await expect(page.getByRole('heading', { name: '群配置', exact: true })).toBeVisible()
  await page.getByLabel('搜索', { exact: true }).fill('测试群 59')
  await expect(page.getByRole('cell', { name: '测试群 59', exact: true })).toBeVisible()
  await expect(page.locator('tbody tr')).toHaveCount(1)
  await page.getByRole('tab', { name: '加群黑名单', exact: true }).click()
  await expect(page.getByRole('heading', { name: '加群黑名单', exact: true })).toBeVisible()
  await page.getByRole('tab', { name: '群配置', exact: true }).click()
  await expect(page.getByLabel('搜索', { exact: true })).toHaveValue('测试群 59')
  await expect(page.getByRole('cell', { name: '测试群 59', exact: true })).toBeVisible()
  expect(connections).toBe(1)
})

test('recall administrators can be managed by QQ number', async ({ page }) => {
  await login(page)
  await page.goto('/#/admin/recall')
  await expect(page.getByRole('heading', { name: '批量撤回', exact: true })).toBeVisible()
  await expect(page.getByText(/无法撤回的消息自动跳过/)).toBeVisible()
  await page.getByRole('button', { name: '新增', exact: true }).click()
  await page.getByLabel('QQ 号', { exact: true }).fill('987654321')
  await page.getByLabel('备注', { exact: true }).fill('撤回管理员测试')
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByRole('cell', { name: '987654321', exact: true })).toBeVisible()
  await expect(page.getByRole('dialog')).toBeHidden()
  await page.screenshot({ path: test.info().outputPath('recall-admins.png'), fullPage: true })
  await page.getByRole('button', { name: '停用', exact: true }).click()
  await expect(page.getByRole('button', { name: '启用', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '删除', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: '删除', exact: true }).click()
  await expect(page.getByRole('cell', { name: '987654321', exact: true })).toHaveCount(0)
})

test('hidden dashboard sections and closed cloud settings are lazy', async ({ page }) => {
  await login(page)
  await page.setViewportSize({ width: 390, height: 640 })
  const methods: string[] = []
  page.on('websocket', (ws) =>
    ws.on('framesent', (frame) => methods.push(JSON.parse(String(frame.payload)).method)),
  )
  await page.goto('/#/admin')
  await expect(page.getByText('今日消息', { exact: true })).toBeVisible()
  expect(methods).toContain('dashboard.summary')
  expect(methods).not.toContain('dashboard.rankings')
  expect(methods).not.toContain('dashboard.recent')
  await page.locator('[data-section="rankings"]').scrollIntoViewIfNeeded()
  await expect.poll(() => methods.includes('dashboard.rankings')).toBe(true)
  await page.goto('/#/admin/message-moderation')
  await expect(page.getByRole('heading', { name: '消息审查', exact: true })).toBeVisible()
  expect(methods).not.toContain('cloud.get')
  await page.getByRole('button', { name: '腾讯云配置', exact: true }).click()
  await expect.poll(() => methods.includes('cloud.get')).toBe(true)
})

test('file folders load on entry and content sync runs as a background task', async ({ page }) => {
  await login(page)
  const requests: { method: string; params: Record<string, unknown> }[] = []
  page.on('websocket', (ws) =>
    ws.on('framesent', (frame) => requests.push(JSON.parse(String(frame.payload)))),
  )
  await page.goto('/#/admin/files')
  await expect(page.getByRole('heading', { name: '群文件', exact: true })).toBeVisible()
  expect(requests.some((request) => request.method === 'files.browse')).toBe(false)
  await page.getByLabel('选择群', { exact: true }).click()
  await page.getByRole('option', { name: /测试群 1 · 1001/ }).click()
  await expect(page.getByRole('listbox', { name: '选择群' })).toBeHidden()
  await expect(page.getByRole('button', { name: '资料', exact: true })).toBeVisible()
  expect(
    requests
      .filter((request) => request.method === 'files.browse')
      .every((request) => request.params.folder_id === ''),
  ).toBe(true)
  await page.getByRole('button', { name: '下一页' }).click()
  await expect
    .poll(() =>
      requests.some((request) => request.method === 'files.browse' && request.params.page === 2),
    )
    .toBe(true)
  await page.getByRole('button', { name: '上一页' }).click()
  await expect(page.getByRole('button', { name: '资料', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '资料', exact: true }).click()
  await expect
    .poll(() =>
      requests.some(
        (request) => request.method === 'files.browse' && request.params.folder_id === 'folder-1',
      ),
    )
    .toBe(true)
  await page.goto('/#/admin/notices')
  await page.getByRole('button', { name: '批量同步', exact: true }).click()
  await page.getByText('测试群 1', { exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: '同步', exact: true }).click()
  await expect(page.getByText('已完成', { exact: true })).toBeVisible()
})

test('responsive MD3 layout and theme modes have no page errors', async ({ page }) => {
  await login(page)
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  for (const width of [390, 800, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/#/admin/groups')
    await expect(page.getByRole('heading', { name: '群配置', exact: true })).toBeVisible()
    await page.getByRole('button', { name: '切换主题' }).click()
    await page.getByText('深色', { exact: true }).click()
    await expect(page.locator('.v-application')).toHaveClass(/v-theme--dark/)
    await page.screenshot({ path: `test-results/md3-${width}-dark.png`, fullPage: true })
    await page.getByRole('button', { name: '切换主题' }).click()
    await page.getByText('浅色', { exact: true }).click()
    await expect(page.locator('.v-application')).toHaveClass(/v-theme--light/)
    await page.screenshot({ path: `test-results/md3-${width}-light.png`, fullPage: true })
  }
  expect(errors).toEqual([])
})

test('dedupe requires preview and explicit confirmation before a durable execution', async ({
  page,
}) => {
  await login(page)
  const methods: string[] = []
  page.on('websocket', (ws) =>
    ws.on('framesent', (frame) => methods.push(JSON.parse(String(frame.payload)).method)),
  )
  await page.goto('/#/admin/dedupe')
  await page.getByRole('button', { name: '生成预览', exact: true }).click()
  await expect(page.getByText('预览完成', { exact: true })).toBeVisible()
  await expect(page.locator('tbody tr')).toHaveCount(25)
  expect(methods).not.toContain('dedupe.execute')
  await page.getByRole('button', { name: '确认执行踢人', exact: true }).click()
  expect(methods).not.toContain('dedupe.execute')
  await page.getByRole('dialog').getByRole('button', { name: '执行踢人', exact: true }).click()
  await expect(page.getByText('已完成', { exact: true })).toBeVisible({ timeout: 15000 })
  expect(methods.filter((method) => method === 'dedupe.execute')).toHaveLength(1)
})

test('mobile navigation supports keyboard focus and reduced motion', async ({ page }) => {
  await login(page)
  await page.emulateMedia({ reducedMotion: 'reduce', colorScheme: 'dark' })
  await page.setViewportSize({ width: 390, height: 900 })
  await page.goto('/#/admin/groups')
  await expect(page.locator('.v-application')).toHaveClass(/v-theme--dark/)
  await page.keyboard.press('Tab')
  const navigation = page.getByRole('button', { name: '打开导航', exact: true })
  await expect(navigation).toBeFocused()
  await expect(navigation).toHaveCSS('outline-style', 'solid')
  const duration = await navigation.evaluate((element) =>
    parseFloat(getComputedStyle(element).transitionDuration),
  )
  expect(duration).toBeLessThan(0.01)
  await navigation.press('Enter')
  const rules = page.getByRole('link', { name: '入群规则', exact: true })
  await expect(rules).toBeVisible()
  await rules.focus()
  await rules.press('Enter')
  await expect(page.getByRole('heading', { name: '入群规则', exact: true })).toBeVisible()
})

test('QQ limits and ordered image review channels can be configured', async ({ page }) => {
  await login(page)
  await page.goto('/#/admin/groups')
  await page.getByRole('button', { name: '编辑', exact: true }).first().click()
  await page.getByLabel('最低 QQ 等级（0 表示不限）', { exact: true }).fill('16')
  await page.getByLabel('答错拉黑次数（0 表示关闭）', { exact: true }).fill('3')
  await page.getByLabel('答错统计窗口（小时）', { exact: true }).fill('24')
  await page.getByRole('dialog').getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByRole('button', { name: '编辑', exact: true }).first().click()
  await expect(page.getByLabel('最低 QQ 等级（0 表示不限）', { exact: true })).toHaveValue('16')
  await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click()

  await page.goto('/#/admin/message-moderation')
  await page.getByRole('button', { name: 'LLM 图片审核配置', exact: true }).click()
  await expect(page.getByLabel('审核提示词', { exact: true })).not.toHaveValue('')
  await page.getByText('启用图片审核服务', { exact: true }).click()
  await expect(page.getByLabel('启用图片审核服务', { exact: true })).toBeChecked()
  await page.getByRole('button', { name: '新增渠道', exact: true }).click()
  await page.getByLabel('渠道名称', { exact: true }).fill('主渠道')
  await page.getByLabel('多模态模型名称', { exact: true }).fill('small-vision-a')
  await page.getByLabel('API Key', { exact: true }).fill('browser-test-key-a')
  await page.getByRole('button', { name: '新增渠道', exact: true }).click()
  await page.getByLabel('渠道名称', { exact: true }).fill('备用渠道')
  await page.getByLabel('API Base URL', { exact: true }).fill('https://backup.example/v1')
  await page.getByLabel('多模态模型名称', { exact: true }).fill('small-vision-b')
  await page.getByLabel('输出总预算（max_completion_tokens）', { exact: true }).fill('4096')
  await page
    .getByLabel('服务商扩展参数（JSON）', { exact: true })
    .fill('{"thinking":{"budget_tokens":1024}}')
  await page.getByRole('button', { name: '上移', exact: true }).click()
  await expect(page.getByText('1. 备用渠道', { exact: true })).toBeVisible()
  await page.getByRole('dialog').getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByRole('button', { name: 'LLM 图片审核配置', exact: true }).click()
  await expect(page.getByLabel('渠道名称', { exact: true })).toHaveValue('备用渠道')
  await expect(page.getByLabel('输出总预算（max_completion_tokens）', { exact: true })).toHaveValue(
    '4096',
  )
  await page.getByLabel('当前渠道（按优先级）', { exact: true }).press('Enter')
  await page.getByRole('option', { name: '2. 主渠道', exact: true }).click()
  await expect(page.getByLabel('API Key', { exact: true })).toHaveValue('')
  await expect(page.getByText('已配置；留空保留原密钥', { exact: true })).toBeVisible()
  await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click()

  await page.getByRole('button', { name: '新增', exact: true }).click()
  await page.getByLabel('规则名称', { exact: true }).fill('仅图片审核')
  await page.getByText('LLM 多模态图片审核（无需正则命中）', { exact: true }).click()
  await expect(page.getByLabel('LLM 多模态图片审核（无需正则命中）', { exact: true })).toBeChecked()
  await page.getByRole('dialog').getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByRole('cell', { name: '仅图片审核', exact: true })).toBeVisible()
})

test('omni moderation automatically hides chat settings and saves the channel', async ({
  page,
}) => {
  await login(page)
  await page.goto('/#/admin/message-moderation')
  await page.getByRole('button', { name: 'LLM 图片审核配置', exact: true }).click()
  await expect(page.getByLabel('审核提示词', { exact: true })).not.toHaveValue('')
  await page.getByRole('button', { name: '新增渠道', exact: true }).click()
  await page.getByLabel('渠道名称', { exact: true }).fill('OpenAI 专用审核')
  await page.getByLabel('多模态模型名称', { exact: true }).fill('vision')
  await page.getByLabel('输出总预算（max_completion_tokens）', { exact: true }).fill('4096')
  await page.getByLabel('服务商扩展参数（JSON）', { exact: true }).fill('{')
  await page.getByLabel('多模态模型名称', { exact: true }).fill('omni-moderation-latest')
  await expect(page.getByText(/已自动使用 Moderations 接口/)).toBeVisible()
  await expect(page.getByLabel('输出模式', { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('输出总预算（max_completion_tokens）', { exact: true })).toHaveCount(
    0,
  )
  await expect(page.getByLabel('服务商扩展参数（JSON）', { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('思考强度（reasoning_effort）', { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('图片精细度', { exact: true })).toHaveCount(0)
  while (await page.getByRole('button', { name: '上移', exact: true }).isEnabled()) {
    await page.getByRole('button', { name: '上移', exact: true }).click()
  }
  await page.getByRole('dialog').getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByRole('button', { name: 'LLM 图片审核配置', exact: true }).click()
  await expect(page.getByLabel('多模态模型名称', { exact: true })).toHaveValue(
    'omni-moderation-latest',
  )
  await expect(page.getByText(/已自动使用 Moderations 接口/)).toBeVisible()
  await page.getByLabel('多模态模型名称', { exact: true }).fill('vision')
  await expect(page.getByLabel('输出总预算（max_completion_tokens）', { exact: true })).toHaveValue(
    '4096',
  )
  await expect(page.getByLabel('服务商扩展参数（JSON）', { exact: true })).toHaveValue('{}')
  await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click()
})
