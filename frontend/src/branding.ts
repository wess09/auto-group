export const appName = import.meta.env.VITE_APP_NAME?.trim() || 'Auto Group'

export function pageTitle(title: string): string {
  return title && title !== appName ? `${title} - ${appName}` : appName
}
