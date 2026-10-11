import { useEffect, useRef, useState } from 'react'
import { Bars, Card, Pills } from '../components/ui'
import { hourLabel, hourlyFor, money, pct, rangeWindow, spotStats, type RangeKey } from '../lib/data'

export default function Spots({ range, setRange }: { range: RangeKey; setRange: (k: RangeKey) => void }) {
  const w = rangeWindow(range)
  const spots = spotStats(w.from, w.to)
  const [sel, setSel] = useState<string | null>(null)
  const max = Math.max(1, ...spots.map((s) => s.netPerHour))
  const s = spots.find((x) => x.loc.id === sel) ?? null
  const feeShare = s && s.gross ? s.fees / s.gross : 0
  const hourly = s ? hourlyFor(s.loc.id) : []
  const detailRef = useRef<HTMLDivElement>(null)
  useEffect(() => { if (sel) detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }, [sel])
  const short = (n: string) => n.replace(/ \(.*\)/, '').split(',')[0]

  return (
    <>
      <section className="block-hero turquoise page">
        <header className="top">
          <h1>Spots</h1>
          <Pills value={range} onChange={setRange} />
        </header>
        <div className="label">What each spot makes per hour, after fees. Tap one.</div>
      </section>

      {spots.length === 0 && <Card>No trading days in this range.</Card>}

      {spots.length > 0 && (
        <Card className="hbars">
          {spots.map((x) => {
            const fee = x.gross ? x.fees / x.gross : 0
            const on = x.loc.id === sel
            return (
              <button key={x.loc.id} className={`hbar ${on ? 'on' : ''}`} onClick={() => setSel(on ? null : x.loc.id)}>
                <span className="hbar-name">{short(x.loc.name)}</span>
                <span className="hbar-track">
                  <span className={`hbar-fill ${fee > 0.12 ? 'warn' : ''}`} style={{ width: `${Math.max(3, (x.netPerHour / max) * 100)}%` }} />
                </span>
                <span className="hbar-val">{money(x.netPerHour)}</span>
              </button>
            )
          })}
          <div className="hbar-key"><span className="sw" /> no or low fees <span className="sw warn" /> venue takes over 12%</div>
        </Card>
      )}

      {s && (
        <div ref={detailRef} style={{ scrollMarginTop: 12 }}>
        <Card className="spot-detail">
          <div className="row">
            <div>
              <h2>{s.loc.name}</h2>
              <div className="sub">{s.loc.neighbourhood} · {s.days} {s.days === 1 ? 'day' : 'days'} this {range === '1W' ? 'week' : range === '1M' ? 'month' : range === '3M' ? 'quarter' : 'year'}</div>
            </div>
            <div className="val-stack">
              <div className="val">{money(s.netPerHour)}<small>/hr</small></div>
              <div className="sub">after fees</div>
            </div>
          </div>
          <div className="facts">
            <div><b>{money(s.gross)}</b><span>sales</span></div>
            <div><b>{money(s.fees)}</b><span>in fees{feeShare > 0.12 ? ` (${pct(feeShare, false)})` : ''}</span></div>
            <div><b>{money(s.tips)}</b><span>tips</span></div>
            <div><b>{s.orders.toLocaleString()}</b><span>orders</span></div>
          </div>
          {s.loc.pctFee > 0 || s.loc.flatFee > 0 ? (
            <p className="note">Venue takes {s.loc.pctFee > 0 ? `${pct(s.loc.pctFee, false)} of sales` : ''}{s.loc.pctFee > 0 && s.loc.flatFee > 0 ? ' plus ' : ''}{s.loc.flatFee > 0 ? `${money(s.loc.flatFee)} a day` : ''}.</p>
          ) : (
            <p className="note">No venue fee. Only card processing comes off.</p>
          )}
          <h3>Sales by hour of the day, all visits</h3>
          <Bars
            bars={hourly.map((h) => ({ label: hourLabel(h.hour), value: h.days ? h.gross_sales / h.days : 0, sub: `${hourLabel(h.hour)}: ${money(h.days ? h.gross_sales / h.days : 0)} an hour on average` }))}
            height={80}
            highlightLast={false}
          />
        </Card>
        </div>
      )}
    </>
  )
}
