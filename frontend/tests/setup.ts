import { vi } from 'vitest'
Object.defineProperty(window, 'matchMedia', {
  value: vi.fn(() => ({ matches: false, addEventListener() {}, removeEventListener() {} })),
  configurable: true,
})
