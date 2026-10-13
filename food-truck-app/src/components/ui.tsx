import React, { useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { Home as HomeIcon, MapPin, UtensilsCrossed, Store, Sparkles, MessageCircle } from 'lucide-react'
import { RANGES, money, type RangeKey } from '../lib/data'

export function Card({ children, className = '', onClick }: { children: ReactNode; className?: string; onClick?: () => void }) {
  return (
    <section className={`card ${className}`} onClick={onClick}>
      {children}
    </section>
  )
}

export function Tile({ value, label, delta, spark, on, onClick }: {
  value: string; label: string; delta?: number | null; spark?: number[]; on?: boolean; onClick?: () => void
}) {
  const Tag = onClick ? 'button' : 'div'
  return (
    <Tag className={`card tile ${on ? 'on' : ''}`} onClick={onClick} aria-pressed={onClick ? on : undefined}>
      <div className="num">{value}</div>
      <div className="label">{label}</div>
      {delta !== undefined && delta !== null && (
        <div className={`delta small ${delta >= 0 ? 'up' : 'down'}`}>{delta >= 0 ? '+' : ''}{Math.round(delta * 100)}%</div>
      )}
      {spark && <Spark values={spark} />}
    </Tag>
  )
}

export function Pills({ value, onChange }: { value: RangeKey; onChange: (k: RangeKey) => void }) {
  return (
    <div className="pills" role="tablist">
      {RANGES.map((r) => (
        <button key={r.key} role="tab" aria-selected={value === r.key} className={value === r.key ? 'on' : ''} onClick={() => onChange(r.key)}>
          {r.key}
        </button>
      ))}
    </div>
  )
}

export function Nav() {
  const items: [string, string, React.ComponentType<{ size?: number; strokeWidth?: number }>][] = [
    ['/', 'Home', HomeIcon], ['/spots', 'Spots', MapPin], ['/menu', 'Menu', UtensilsCrossed], ['/market', 'Market', Store], ['/insights', 'Insights', Sparkles], ['/ask', 'Ask', MessageCircle],
  ]
  return (
    <nav className="nav">
      {items.map(([to, label, Icon]) => (
        <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => (isActive ? 'on' : '')} aria-label={label}>
          <Icon size={20} strokeWidth={2.2} />
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  )
}

/** Thin column chart. One series: ink, last bar in accent, zero days faint. Tap a bar for its value. */
export function Bars({ bars, height = 120, highlightLast = true, format = (v: number) => money(v) }: {
  bars: { label: string; value: number; sub?: string }[]
  height?: number
  highlightLast?: boolean
  format?: (v: number) => string
}) {
  const [sel, setSel] = useState<number | null>(null)
  const max = Math.max(1, ...bars.map((b) => b.value))
  const min = Math.min(0, ...bars.map((b) => b.value))
  const span = max - min || 1
  const n = bars.length
  const W = 100
  const gap = n > 20 ? 0.6 : 1.2
  const bw = (W - gap * (n - 1)) / n
  const labelEvery = n > 8 ? Math.ceil(n / 5) : 1
  // Default highlight: the last bar with anything in it, so a day off is not the headline.
  let lastNonZero = n - 1
  while (lastNonZero > 0 && bars[lastNonZero].value === 0) lastNonZero--
  const active = sel ?? (highlightLast ? lastNonZero : null)
  return (
    <div className="bars">
      {active !== null && bars[active] && (
        <div className="bars-tip">
          <strong>{format(bars[active].value)}</strong>
          <span>{bars[active].sub ?? bars[active].label}</span>
        </div>
      )}
      <svg viewBox={`0 0 ${W} ${height}`} preserveAspectRatio="none" width="100%" height={height} onMouseLeave={() => setSel(null)}>
        {bars.map((b, i) => {
          const base = height - 2 - ((0 - min) / span) * (height - 4)
          const h = Math.max(b.value === 0 ? 1 : 2, (Math.abs(b.value) / span) * (height - 4))
          const y = b.value >= 0 ? base - h : base
          const x = i * (bw + gap)
          const cls = i === active ? 'bar on' : b.value === 0 ? 'bar zero' : b.value < 0 ? 'bar neg' : 'bar'
          return (
            <g key={i} onClick={() => setSel(i === sel ? null : i)} onMouseEnter={() => setSel(i)}>
              <rect x={x} y={0} width={bw} height={height} fill="transparent" />
              <rect className={cls} x={x} y={y} width={bw} height={h} rx={Math.min(1.5, bw / 2)} />
            </g>
          )
        })}
        {min < 0 && <line x1={0} x2={W} y1={height - 2 - ((0 - min) / span) * (height - 4)} y2={height - 2 - ((0 - min) / span) * (height - 4)} className="baseline" />}
      </svg>
      <div className="bars-x">
        {bars.map((b, i) => (
          <span key={i} style={{ width: `${100 / n}%` }}>{i % labelEvery === 0 || i === n - 1 ? b.label : ''}</span>
        ))}
      </div>
    </div>
  )
}

/** Horizontal share bar used in lists (top items, spots). */
export function Meter({ value, max, tone = 'ink' }: { value: number; max: number; tone?: 'ink' | 'accent' | 'warn' }) {
  return (
    <div className="meter">
      <div className={`meter-fill ${tone}`} style={{ width: `${Math.max(2, (value / max) * 100)}%` }} />
    </div>
  )
}

/** Market range bar: min..max track, median tick, "you" marker. */
export function RangeBar({ min, max, median, you }: { min: number; max: number; median: number; you: number }) {
  const lo = Math.min(min, you), hi = Math.max(max, you)
  const span = hi - lo || 1
  const p = (v: number) => `${((v - lo) / span) * 100}%`
  return (
    <div className="range">
      <div className="range-track" style={{ left: p(min), width: `calc(${p(max)} - ${p(min)})` }} />
      <div className="range-median" style={{ left: p(median) }} />
      <div className={`range-you ${you < median ? 'below' : 'above'}`} style={{ left: p(you) }} />
    </div>
  )
}

export function Spark({ values }: { values: number[] }) {
  const w = 72, h = 24
  const max = Math.max(1, ...values), min = Math.min(...values)
  const pts = values.map((v, i) => `${(i / (values.length - 1 || 1)) * w},${h - 2 - ((v - min) / (max - min || 1)) * (h - 4)}`)
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} width={w} height={h}>
      <polyline points={pts.join(' ')} fill="none" strokeWidth="1.5" />
      <circle cx={w} cy={pts[pts.length - 1]?.split(',')[1]} r="2" />
    </svg>
  )
}

/** Small ring meter: value 0..1 of the ring filled, label inside. */
export function Ring({ fill, tone, text, label }: { fill: number; tone: 'good' | 'info' | 'warn'; text: string; label: string }) {
  const r = 22, c = 2 * Math.PI * r
  const f = Math.max(0.04, Math.min(1, fill))
  return (
    <div className={`ring ${tone}`}>
      <svg viewBox="0 0 56 56" width="56" height="56">
        <circle cx="28" cy="28" r={r} className="ring-track" />
        <circle cx="28" cy="28" r={r} className="ring-fill" strokeDasharray={`${c * f} ${c}`} transform="rotate(-90 28 28)" />
      </svg>
      <span className="ring-text">{text}</span>
      <span className="ring-label">{label}</span>
    </div>
  )
}

export function Delta({ value, suffix = 'vs last' }: { value: number | null; suffix?: string }) {
  if (value === null) return <div className="delta muted">no comparison</div>
  return (
    <div className={`delta ${value >= 0 ? 'up' : 'down'}`}>
      {value >= 0 ? '▲' : '▼'} {Math.abs(Math.round(value * 100))}% {suffix}
    </div>
  )
}
