import { useEffect, useState } from 'react'

// Light or dark. Follows the phone's setting until the owner picks one; the pick is remembered on the device.
export type Theme = 'light' | 'dark'
const KEY = 'eventini-theme'

function stored(): Theme | null {
  try { const v = localStorage.getItem(KEY); return v === 'light' || v === 'dark' ? v : null } catch { return null }
}
function system(): Theme {
  return 'dark' // the app's native look is dark; light is there for owners who prefer it
}
export function currentTheme(): Theme { return stored() ?? system() }

export function applyTheme(t: Theme) {
  document.documentElement.dataset.theme = t
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', t === 'dark' ? '#0C2426' : '#EAF6F5')
  window.dispatchEvent(new Event('themechange'))
}
export function setTheme(t: Theme) {
  try { localStorage.setItem(KEY, t) } catch { /* private mode */ }
  applyTheme(t)
}

export function useTheme(): [Theme, () => void] {
  const [t, setT] = useState<Theme>(currentTheme)
  useEffect(() => {
    const sync = () => setT(currentTheme())
    window.addEventListener('themechange', sync)
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
    const onSys = () => { if (!stored()) applyTheme(system()) }
    mq?.addEventListener('change', onSys)
    return () => { window.removeEventListener('themechange', sync); mq?.removeEventListener('change', onSys) }
  }, [])
  return [t, () => setTheme(t === 'dark' ? 'light' : 'dark')]
}

// Read a CSS token at runtime (the map draws its dots in canvas/SVG and cannot use var()).
export function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}
