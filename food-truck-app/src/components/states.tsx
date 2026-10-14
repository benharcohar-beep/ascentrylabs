import type { ReactNode } from 'react'
import { useEffect, useRef, useState } from 'react'
import { markSynced } from '../lib/sync'

/** Grey placeholder blocks shown for a moment on a screen's first visit. */
export function Skeleton({ hero = true, rows = 5 }: { hero?: boolean; rows?: number }) {
  return (
    <div className="skel" aria-hidden>
      {hero && <><div className="sk sk-label" /><div className="sk sk-hero" /><div className="sk sk-sub" /></>}
      <div className="panel">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="sk-row"><div className="sk sk-ico" /><div className="sk-main"><div className="sk sk-t" /><div className="sk sk-s" /></div><div className="sk sk-amt" /></div>
        ))}
      </div>
    </div>
  )
}

/** Something to say when a list has nothing in it. */
export function Empty({ icon, title, text, children }: { icon: ReactNode; title: string; text?: string; children?: ReactNode }) {
  return (
    <div className="empty-state">
      <span className="empty-ico">{icon}</span>
      <b>{title}</b>
      {text && <span>{text}</span>}
      {children}
    </div>
  )
}

/** Pull down from the top of any screen to refresh. The demo data is static, so this just re-syncs the clock. */
export function PullToRefresh({ children }: { children: ReactNode }) {
  const [pull, setPull] = useState(0)
  const [busy, setBusy] = useState(false)
  const start = useRef<number | null>(null)
  useEffect(() => {
    const onStart = (e: TouchEvent) => { start.current = window.scrollY <= 0 ? e.touches[0].clientY : null }
    const onMove = (e: TouchEvent) => {
      if (start.current === null || busy) return
      const d = e.touches[0].clientY - start.current
      if (d > 0 && window.scrollY <= 0) setPull(Math.min(90, d * 0.5))
    }
    const onEnd = () => {
      if (pull > 60 && !busy) {
        setBusy(true); setPull(56)
        setTimeout(() => { markSynced(); setBusy(false); setPull(0) }, 900)
      } else setPull(0)
      start.current = null
    }
    window.addEventListener('touchstart', onStart, { passive: true })
    window.addEventListener('touchmove', onMove, { passive: true })
    window.addEventListener('touchend', onEnd)
    return () => { window.removeEventListener('touchstart', onStart); window.removeEventListener('touchmove', onMove); window.removeEventListener('touchend', onEnd) }
  }, [pull, busy])
  return (
    <>
      <div className={`ptr ${pull > 0 ? 'show' : ''} ${busy ? 'busy' : ''}`} style={{ height: pull }}>
        <span className="ptr-dot" /> {busy ? 'Updating from Eventini…' : pull > 60 ? 'Release to update' : 'Pull to update'}
      </div>
      {children}
    </>
  )
}
