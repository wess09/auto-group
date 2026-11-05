import { createServer } from 'node:http'
import { mkdtemp, writeFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, isAbsolute, join, relative } from 'node:path'
import { afterAll, beforeAll, expect, it } from 'vitest'
import { build, createServer as createViteServer } from 'vite'
import { brandingPlugin } from '../build/branding'

const svg =
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><circle cx="16" cy="16" r="12" fill="purple"/></svg>'
let root: string
let origin: string
let requests = 0
const server = createServer((request, response) => {
  requests++
  switch (request.url) {
    case '/icon.svg':
      response.writeHead(200, { 'Content-Type': 'image/svg+xml; charset=utf-8' })
      return response.end(svg)
    case '/octet.svg':
      response.writeHead(200, { 'Content-Type': 'application/octet-stream' })
      return response.end(svg)
    case '/redirect':
      response.writeHead(302, { Location: '/icon.svg' })
      return response.end()
    case '/html':
      response.writeHead(200, { 'Content-Type': 'text/html' })
      return response.end('<html>not an icon</html>')
    case '/empty.png':
      response.writeHead(200, { 'Content-Type': 'image/png' })
      return response.end()
    case '/large.png':
      response.writeHead(200, { 'Content-Type': 'image/png' })
      return response.end(Buffer.alloc(2 * 1024 * 1024 + 1))
    default:
      response.writeHead(404)
      response.end()
  }
})

beforeAll(async () => {
  root = await mkdtemp(join(tmpdir(), 'auto-group-branding-'))
  await writeFile(
    join(root, 'index.html'),
    '<html><head><title>Auto Group</title></head><body></body></html>',
  )
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
  const address = server.address()
  if (!address || typeof address === 'string') throw new Error('test server did not start')
  origin = `http://127.0.0.1:${address.port}`
})

afterAll(async () => {
  server.closeAllConnections()
  await new Promise<void>((resolve) => server.close(() => resolve()))
  const location = relative(tmpdir(), root)
  if (
    location.startsWith('..') ||
    isAbsolute(location) ||
    !basename(root).startsWith('auto-group-branding-')
  ) {
    throw new Error('refusing to remove an unexpected test directory')
  }
  await rm(root, { recursive: true, force: true })
})

async function compile(iconUrl = '', base = '/') {
  const result = await build({
    configFile: false,
    root,
    base,
    logLevel: 'silent',
    plugins: [brandingPlugin('群 <助手> & "朋友" $&', iconUrl)],
    build: { write: false },
  })
  if (Array.isArray(result) || !('output' in result)) throw new Error('unexpected build result')
  const html = result.output.find((item) => item.fileName === 'index.html')
  if (!html || html.type !== 'asset') throw new Error('index.html missing from build')
  return { html: String(html.source), output: result.output }
}

it('escapes custom titles and performs no download when the icon is unset', async () => {
  const before = requests
  const { html, output } = await compile()
  expect(html).toContain('<title>群 &lt;助手&gt; &amp; &quot;朋友&quot; $&amp;</title>')
  expect(html).not.toContain('rel="icon"')
  expect(output.some((asset) => asset.fileName.includes('favicon'))).toBe(false)
  expect(requests).toBe(before)
})

it.each(['/', '/console/', './'])(
  'downloads and bundles a hashed local icon with base %s',
  async (base) => {
    const before = requests
    const { html, output } = await compile(`${origin}/icon.svg`, base)
    const asset = output.find((item) => /assets\/favicon-[\w-]+\.svg$/.test(item.fileName))
    expect(asset?.type).toBe('asset')
    if (!asset || asset.type !== 'asset') throw new Error('favicon missing from build')
    expect(Buffer.from(asset.source).toString()).toBe(svg)
    expect(html).toContain(`rel="icon" href="${base}${asset.fileName}"`)
    expect(html).not.toContain(origin)
    expect(requests - before).toBe(1)
  },
)

it.each(['/redirect', '/octet.svg'])(
  'supports redirected and generic binary image responses: %s',
  async (path) => {
    const { html } = await compile(origin + path)
    expect(html).toMatch(/rel="icon" href="\/assets\/favicon-[\w-]+\.svg"/)
  },
)

it.each([
  ['/missing', 'HTTP 404'],
  ['/html', '未返回支持的图片'],
  ['/empty.png', '空图片'],
  ['/large.png', '2 MiB'],
])('fails the build for an unusable icon: %s', async (path, error) => {
  await expect(compile(origin + path)).rejects.toThrow(error)
})

it.each(['invalid-url', 'file:///C:/icon.png'])('rejects non-HTTP image URLs: %s', async (url) => {
  await expect(compile(url)).rejects.toThrow('HTTP/HTTPS')
})

it('serves the downloaded icon in development without repeating origin requests', async () => {
  const before = requests
  const vite = await createViteServer({
    configFile: false,
    root,
    logLevel: 'silent',
    plugins: [brandingPlugin('测试名称', `${origin}/icon.svg`)],
    server: { host: '127.0.0.1', port: 0 },
  })
  try {
    await vite.listen()
    const address = vite.httpServer!.address()
    if (!address || typeof address === 'string') throw new Error('dev server did not start')
    const local = `http://127.0.0.1:${address.port}`
    const html = await fetch(local).then((response) => response.text())
    expect(html).toContain('<title>测试名称</title>')
    expect(html).toContain('href="/__app-icon"')
    for (let index = 0; index < 2; index++) {
      const response = await fetch(`${local}/__app-icon`)
      expect(response.headers.get('content-type')).toBe('image/svg+xml')
      expect(await response.text()).toBe(svg)
    }
    expect(requests - before).toBe(1)
  } finally {
    await vite.close()
  }
})
