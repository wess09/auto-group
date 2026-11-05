import type { Plugin, ResolvedConfig } from 'vite'

const MAX_ICON_BYTES = 2 * 1024 * 1024
const ICON_TIMEOUT_MS = 15_000
const iconFormats: Record<string, string> = {
  'image/png': 'png',
  'image/x-icon': 'ico',
  'image/vnd.microsoft.icon': 'ico',
  'image/svg+xml': 'svg',
  'image/jpeg': 'jpg',
  'image/gif': 'gif',
  'image/webp': 'webp',
  'image/avif': 'avif',
}

type Icon = { source: Uint8Array; contentType: string; extension: string }

function escapeHtml(value: string): string {
  return value.replace(
    /[&<>"']/g,
    (character) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]!,
  )
}

async function downloadIcon(address: string): Promise<Icon> {
  let url: URL
  try {
    url = new URL(address)
  } catch {
    throw new Error('VITE_APP_ICON_URL 必须是完整的 HTTP/HTTPS 图片链接')
  }
  if (!['http:', 'https:'].includes(url.protocol)) {
    throw new Error('VITE_APP_ICON_URL 仅支持 HTTP/HTTPS 图片链接')
  }
  let response: Response
  try {
    response = await fetch(url, { signal: AbortSignal.timeout(ICON_TIMEOUT_MS) })
  } catch {
    throw new Error('下载 VITE_APP_ICON_URL 失败，请检查链接和网络（超时上限 15 秒）')
  }
  if (!response.ok) {
    await response.body?.cancel()
    throw new Error(`下载 VITE_APP_ICON_URL 失败：HTTP ${response.status}`)
  }
  const contentType = response.headers.get('content-type')?.split(';')[0].trim().toLowerCase() || ''
  let extension: string | undefined = iconFormats[contentType]
  if (!extension && (!contentType || contentType === 'application/octet-stream')) {
    extension = new URL(response.url || address).pathname
      .match(/\.(png|ico|svg|jpe?g|gif|webp|avif)$/i)?.[1]
      ?.toLowerCase()
  }
  if (!extension) {
    await response.body?.cancel()
    throw new Error(
      'VITE_APP_ICON_URL 未返回支持的图片，请使用 PNG、ICO、SVG、JPEG、GIF、WebP 或 AVIF',
    )
  }
  const reader = response.body?.getReader()
  if (!reader) throw new Error('VITE_APP_ICON_URL 返回了空图片')
  const chunks: Uint8Array[] = []
  let size = 0
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      size += value.length
      if (size > MAX_ICON_BYTES) throw new Error('VITE_APP_ICON_URL 图片不能超过 2 MiB')
      chunks.push(value)
    }
  } catch (error) {
    await reader.cancel().catch(() => {})
    throw error
  } finally {
    reader.releaseLock()
  }
  if (!size) throw new Error('VITE_APP_ICON_URL 返回了空图片')
  const source = new Uint8Array(size)
  let offset = 0
  for (const chunk of chunks) {
    source.set(chunk, offset)
    offset += chunk.length
  }
  return {
    source,
    extension,
    contentType:
      Object.keys(iconFormats).find((type) => iconFormats[type] === extension) || 'image/jpeg',
  }
}

export function brandingPlugin(appName: string, iconUrl: string): Plugin {
  let config: ResolvedConfig
  let iconPromise: Promise<Icon> | undefined
  let reference: string | undefined
  const icon = () => (iconPromise ??= downloadIcon(iconUrl))
  return {
    name: 'auto-group-branding',
    enforce: 'post',
    configResolved(resolved) {
      config = resolved
    },
    async buildStart() {
      if (!iconUrl || config.command !== 'build') return
      const downloaded = await icon()
      reference = this.emitFile({
        type: 'asset',
        name: `favicon.${downloaded.extension}`,
        source: downloaded.source,
      })
    },
    configureServer(server) {
      server.middlewares.use(async (request, response, next) => {
        if (!iconUrl || request.url?.split('?')[0] !== `${config.base}__app-icon`) return next()
        try {
          const downloaded = await icon()
          response.setHeader('Content-Type', downloaded.contentType)
          response.end(downloaded.source)
        } catch (error) {
          next(error)
        }
      })
    },
    async transformIndexHtml(html) {
      const titled = html.replace(
        /<title>[\s\S]*?<\/title>/i,
        () => `<title>${escapeHtml(appName)}</title>`,
      )
      if (!iconUrl || config.command === 'build') return titled
      await icon()
      return {
        html: titled,
        tags: [
          {
            tag: 'link',
            attrs: { rel: 'icon', href: `${config.base}__app-icon` },
            injectTo: 'head',
          },
        ],
      }
    },
    generateBundle(_options, bundle) {
      if (!reference) return
      const href = escapeHtml(`${config.base}${this.getFileName(reference)}`)
      for (const output of Object.values(bundle)) {
        if (output.type === 'asset' && output.fileName.endsWith('.html')) {
          output.source = String(output.source).replace(
            '</head>',
            () => `  <link rel="icon" href="${href}" />\n  </head>`,
          )
        }
      }
    },
  }
}
