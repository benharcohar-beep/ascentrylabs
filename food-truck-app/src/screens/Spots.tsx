import { useEffect, useRef, useState } from 'react'
import { Amt, Bars, Pills } from '../components/ui'
import { SpotMap } from '../components/SpotMap'
import { hourLabel, hourlyFor, money, pct, rangeWindow, spotStats, type RangeKey } from '../lib/data'

export default function Spots({ range, setRange }: { range: RangeKey; setRange: (k: RangeKey) => void }) {
  const w = rangeWindow(range)
  const all = spotStats(w.from, w.to)
  const [kind, setKind] = useState<string | null>(null)
  const kinds = [...new Set(all.map((s) => s.loc.type))]
  const KIND: Record<string, string> = { campus: 'Campus', office: 'Offices', market: 'Markets', street: 'Street', brewery: 'Breweries', event: 'Games', festival: 'Festivals', food_park: 'Food park', hospital: 'Hospital' }
  const spots = kind ? all.filter((s) => s.loc.type === kind) : all
  const [sel, setSel] = useState<string | null>(null)
  const max = Math.max(1, ...spots.map((s) => s.netPerHour))
  const s = spots.find((x) => x.loc.id === sel) ?? null
  const feeShare = s && s.gross ? s.fees / s.gross : 0
  const hourly = s ? hourlyFor(s.loc.id) : []
  const detailRef = useRef<HTMLDivElement>(null)
  useEffect(() => { if (sel) detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }, [sel])
  const short = (n: string) => n.replace(/ \(.*\)/, '').split(',')[0]

  return (
    <div className="screen">
      <header className="top">
        <h1>Spots</h1>
        <Pills value={range} onChange={setRange} />
      </header>
      <div className="chips">
        <button className={`chip-btn ${kind === null ? 'on' : ''}`} onClick={() => setKind(null)}>All</button>
        {kinds.map((k) => <button key={k} className={`chip-btn ${kind === k ? 'on' : ''}`} onClick={() => setKind(kind === k ? null : k)}>{KIND[k] ?? k}</button>)}
      </div>

      {spots.length > 0 && (
        <div className="card mapcard">
          <SpotMap spots={spots} sel={sel} onSelect={setSel} />
          <div className="hbar-key"><span className="sw" /> low fees <span className="sw warn" /> venue takes over 12% <span className="sw sel" /> selected</div>
        </div>
      )}

      {spots.length === 0 && <section className="card empty">No working days in this range.</section>}

      {spots.length > 0 && (
        <ul className="feed flat">
          {spots.map((x, i) => {
            const fee = x.gross ? x.fees / x.gross : 0
            const on = x.loc.id === sel
            return (
              <li key={x.loc.id} className={`feed-row ${on ? 'on' : ''}`} onClick={() => setSel(on ? null : x.loc.id)}>
                <span className="feed-rank">{i + 1}</span>
                <span className="feed-main">
                  <b>{short(x.loc.name)}</b>
                  <span>{x.days} {x.days === 1 ? 'day' : 'days'}{fee > 0.12 ? ` · venue takes ${pct(fee, false)}` : ''}</span>
                </span>
                <span className="feed-right">
                  <span className="feed-amt"><Amt v={x.netPerHour} /><small>/hr</small></span>
                  <span className="feed-bar"><span className={fee > 0.12 ? 'warn' : ''} style={{ width: `${Math.max(3, (x.netPerHour / max) * 100)}%` }} /></span>
                </span>
              </li>
            )
          })}
        </ul>
      )}

      {s && (
        <div ref={detailRef} style={{ scrollMarginTop: 12 }}>
        <section className="card spot-detail">
          <div className="row">
            <div>
              <h2>{s.loc.name}</h2>
              <div className="sub">{s.loc.neighbourhood} · {s.days} {s.days === 1 ? 'day' : 'days'} this {range === '1W' ? 'week' : range === '1M' ? 'month' : range === '3M' ? 'quarter' : 'year'}</div>
            </div>
            <div className="val-stack">
              <div className="val"><Amt v={s.netPerHour} /><small>/hr</small></div>
              <div className="sub">after the venue's cut</div>
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
        </section>
        </div>
      )}
    </div>
  )
}
