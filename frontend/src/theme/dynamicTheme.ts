import type { GlobalThemeOverrides } from 'naive-ui'

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
  naive: GlobalThemeOverrides
}

type ThemeColors = typeof fallbackColors

export function createDynamicTheme(colors: ThemeColors): DynamicTheme {
  applyCssVars(colors)
  return {
    naive: {
      common: {
        primaryColor: colors.primary,
        primaryColorHover: colors.primaryHover,
        primaryColorPressed: colors.primaryPressed,
        primaryColorSuppl: colors.secondary,
        textColorBase: colors.onSurface,
        borderRadius: '8px'
      },
      Button: {
        textColorPrimary: colors.onPrimary,
        textColorHoverPrimary: colors.onPrimary,
        textColorPressedPrimary: colors.onPrimary,
        colorPrimary: colors.primary,
        colorHoverPrimary: colors.primaryHover,
        colorPressedPrimary: colors.primaryPressed,
        borderPrimary: `1px solid ${colors.primary}`,
        borderHoverPrimary: `1px solid ${colors.primaryHover}`,
        borderPressedPrimary: `1px solid ${colors.primaryPressed}`
      }
    }
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
    image.src = `${src}${src.includes('?') ? '&' : '?'}_theme=${Date.now()}`
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
}
