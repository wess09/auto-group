import {
  argbFromHex,
  hexFromArgb,
  Hct,
  MaterialDynamicColors,
  SchemeTonalSpot,
} from '@material/material-color-utilities'
import { ref } from 'vue'

export type ThemeMode = 'system' | 'light' | 'dark'
const saved = localStorage.getItem('md3.theme_mode')
export const themeMode = ref<ThemeMode>(saved === 'light' || saved === 'dark' ? saved : 'system')
export const systemDark = ref(matchMedia('(prefers-color-scheme: dark)').matches)
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (event) => {
  systemDark.value = event.matches
})

export function createMaterialTheme(dark: boolean) {
  const scheme = new SchemeTonalSpot(Hct.fromInt(argbFromHex('#6750A4')), dark, 0)
  const roles = new MaterialDynamicColors()
  const colors = {
    primary: roles.primary(),
    'on-primary': roles.onPrimary(),
    'primary-container': roles.primaryContainer(),
    'on-primary-container': roles.onPrimaryContainer(),
    secondary: roles.secondary(),
    'on-secondary': roles.onSecondary(),
    'secondary-container': roles.secondaryContainer(),
    'on-secondary-container': roles.onSecondaryContainer(),
    tertiary: roles.tertiary(),
    'on-tertiary': roles.onTertiary(),
    'tertiary-container': roles.tertiaryContainer(),
    'on-tertiary-container': roles.onTertiaryContainer(),
    background: roles.surface(),
    'on-background': roles.onSurface(),
    surface: roles.surface(),
    'on-surface': roles.onSurface(),
    'surface-variant': roles.surfaceVariant(),
    'on-surface-variant': roles.onSurfaceVariant(),
    'surface-container-lowest': roles.surfaceContainerLowest(),
    'surface-container-low': roles.surfaceContainerLow(),
    'surface-container': roles.surfaceContainer(),
    'surface-container-high': roles.surfaceContainerHigh(),
    'surface-container-highest': roles.surfaceContainerHighest(),
    outline: roles.outline(),
    'outline-variant': roles.outlineVariant(),
    error: roles.error(),
    'on-error': roles.onError(),
    'error-container': roles.errorContainer(),
    'on-error-container': roles.onErrorContainer(),
    'inverse-surface': roles.inverseSurface(),
    'inverse-on-surface': roles.inverseOnSurface(),
    'inverse-primary': roles.inversePrimary(),
  }
  return {
    dark,
    colors: Object.fromEntries(
      Object.entries(colors).map(([key, color]) => [key, hexFromArgb(color.getArgb(scheme))]),
    ),
  }
}
