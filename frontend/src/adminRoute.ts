export const adminBase = (() => {
  const value = import.meta.env.VITE_ADMIN_ROUTE_PREFIX || '/admin'
  return normalizeAdminBase(value)
})()

export function normalizeAdminBase(value: string): string {
  const withSlash = value.startsWith('/') ? value : `/${value}`
  return withSlash.replace(/\/+$/, '') || '/admin'
}

export function adminPath(path = ''): string {
  if (!path || path === '/') return adminBase
  return `${adminBase}/${path.replace(/^\/+/, '')}`
}

export function isAdminPath(pathname: string): boolean {
  return pathname === adminBase || pathname.startsWith(`${adminBase}/`)
}

export function isLoginPath(pathname: string): boolean {
  return pathname === adminPath('login')
}
