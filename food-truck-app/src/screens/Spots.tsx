import { useState } from 'react'
import { Brand } from '../components/Brand'
import { Bars, Card, Meter, Pills } from '../components/ui'
import { hourLabel, hourlyFor, money, pct, rangeWindow, spotStats, type RangeKey } from '../lib/data'

export default function Spots({ range, setRange }: { range: RangeKey; setRange: (k: RangeKey) => void }) {
  const w = rangeWindow(range)
  const spots = spotStats(w.from, w.to)
  const [open, setOpen] = useState<string | null>(null)
  const maxNet = Math.max(1, ...spots.map((s) => s.netPerHour))

  return (
    <>
      <section className="grad slate">
        <header className="top">
          <h1>Spots</h1>
          <div className="hstack"><Pills value={range} onChange={setRange} /><Brand /></div>
        </header>
        {spots[0] && (
          <>
            <div className="label">Best spot, per hour after fees</div>
            <div className="big">{money(spots[0].netPerHour)}<small>/hr</small></div>
            <div className="label">{spots[0].loc.name}</div>
          </>
        )}
      </section>

      {spots.length === 0 && <Card>No trading days in this range.</Card>}

      {spots.map((s, i) => {
        const feeShare = s.gross ? s.fees / s.gross : 0
        const isOpen = open === s.loc.id
        const hourly = hourlyFor(s.loc.id)
        return (
          <Card key={s.loc.id} className={`spot ${isOpen ? 'open' : ''}`} onClick={() => setOpen(isOpen ? null : s.loc.id)}>
            <div className="row">
              <div>
                <div className="name">{i + 1}. {s.loc.name}</div>
                <div className="sub">{s.loc.neighbourhood} · {s.days} {s.days === 1 ? 'day' : 'days'}{feeShare > 0.12 ? ` · fees take ${pct(feeShare, false)}` : ''}</div>
              </div>
              <div className="val-stack">
                <div className="val">{money(s.netPerHour)}<small>/hr</small></div>
                <div className="sub">per hour, after fees</div>
              </div>
            </div>
            <div className="dual">
              <div className="dual-row one">
                <Meter value={s.netPerHour} max={maxNet} tone={feeShare > 0.12 ? 'warn' : 'accent'} />
              </div>
            </div>
            {isOpen && (
              <div className="detail">
                <div className="facts">
                  <div><b>{money(s.gross)}</b><span>sales</span></div>
                  <div><b>{money(s.fees)}</b><span>fees ({pct(feeShare, false)})</span></div>
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
              </div>
            )}
          </Card>
        )
      })}
    </>
  )
}
