import { useEffect, useState } from 'react'

// When the numbers were last pulled from the Eventini POS. The demo data is static, so this is the moment the app
// opened (less a few minutes so it reads naturally); pull-to-refresh resets it to now.
let syncedAt = Date.now() - 4 * 60_000
const listeners = new Set<() => void>()
export function markSynced() { syncedAt = Date.now(); listeners.forEach((l) => l()) }

export function useSyncedAgo(): string {
  const [, tick] = useState(0)
  useEffect(() => {
    const l = () => tick((n) => n + 1)
    listeners.add(l)
    const id = setInterval(l, 30_000)
    return () => { listeners.delete(l); clearInterval(id) }
  }, [])
  const s = Math.max(0, Math.round((Date.now() - syncedAt) / 1000))
  if (s < 45) return 'just now'
  const m = Math.round(s / 60)
  if (m < 60) return `${m} min ago`
  const h = Math.round(m / 60)
  return `${h} ${h === 1 ? 'hour' : 'hours'} ago`
}

// First visit to a screen shows a skeleton for a moment; later visits are instant.
const seen = new Set<string>()
export function useFirstLoad(key: string, ms = 550): boolean {
  const [loading, setLoading] = useState(!seen.has(key))
  useEffect(() => {
    if (!loading) return
    const id = setTimeout(() => { seen.add(key); setLoading(false) }, ms)
    return () => clearTimeout(id)
  }, [key, ms, loading])
  return loading
}

// Count a number up from 0 on first render.
export function useCountUp(target: number, ms = 650): number {
  const [v, setV] = useState(0)
  useEffect(() => {
    let raf = 0
    const t0 = performance.now()
    const step = (t: number) => {
      const p = Math.min(1, (t - t0) / ms)
      const e = 1 - Math.pow(1 - p, 3)
      setV(target * e)
      if (p < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])
  return v
}
