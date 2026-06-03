export const authBackgroundUrl = 'https://api.yppp.net/api.php'

const fallbackColors = {
  primary: '#2f6f62',
  primaryHover: '#4b8375',
  primaryPressed: '#25574d',
  onPrimary: '#ffffff',
  surface: '#fbfdf9',
  onSurface: '#191c1a',
  outline: '#c0c9c3',
  secondary: '#4f635b',
  scrim: '#000000'
}

export type DynamicTheme = {
  colors: ThemeColors
}

type ThemeColors = typeof fallbackColors

export function createDynamicTheme(colors: ThemeColors): DynamicTheme {
  applyCssVars(colors)
  return {
    colors
  }
}

export function fallbackDynamicTheme() {
  return createDynamicTheme(fallbackColors)
}

export async function themeFromBackgroundImage() {
  try {
    const { hexFromArgb, sourceColorFromImage, themeFromSourceColor } = await import(
      '@material/material-color-utilities'
    )
    const image = await loadImage(authBackgroundUrl)
    const sourceArgb = await sourceColorFromImage(image)
    const scheme = themeFromSourceColor(sourceArgb).schemes.light
    return createDynamicTheme({
      primary: hexFromArgb(scheme.primary),
      primaryHover: hexFromArgb(scheme.primaryContainer),
      primaryPressed: hexFromArgb(scheme.tertiary),
      onPrimary: hexFromArgb(scheme.onPrimary),
      surface: hexFromArgb(scheme.surface),
      onSurface: hexFromArgb(scheme.onSurface),
      outline: hexFromArgb(scheme.outlineVariant),
      secondary: hexFromArgb(scheme.secondary),
      scrim: hexFromArgb(scheme.scrim)
    })
  } catch {
    return fallbackDynamicTheme()
  }
}

function loadImage(src: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image()
    image.crossOrigin = 'anonymous'
    image.decoding = 'async'
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('Background image failed to load'))
    image.src = src
  })
}

function applyCssVars(colors: ThemeColors) {
  const style = document.documentElement.style
  style.setProperty('--md-primary', colors.primary)
  style.setProperty('--md-primary-hover', colors.primaryHover)
  style.setProperty('--md-primary-pressed', colors.primaryPressed)
  style.setProperty('--md-on-primary', colors.onPrimary)
  style.setProperty('--md-surface', colors.surface)
  style.setProperty('--md-on-surface', colors.onSurface)
  style.setProperty('--md-outline', colors.outline)
  style.setProperty('--md-secondary', colors.secondary)
  style.setProperty('--md-scrim', colors.scrim)
  style.setProperty('--el-color-primary', colors.primary)
  style.setProperty('--el-color-primary-light-3', colors.primaryHover)
  style.setProperty('--el-color-primary-dark-2', colors.primaryPressed)
  style.setProperty('--el-border-radius-base', '8px')
}
