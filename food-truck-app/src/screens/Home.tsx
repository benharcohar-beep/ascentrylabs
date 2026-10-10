import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Bars, Card, Delta, Meter, Pills, Tile } from '../components/ui'
import { RANGES, buckets, data, daysBetween, itemTotals, money, pctChange, rangeWindow, totals, type RangeKey } from '../lib/data'
import { health } from '../lib/health'
import { weeklyInsights } from '../lib/insights'
import { stockAlerts } from '../lib/stock'

export default function Home({ range, setRange }: { range: RangeKey; setRange: (k: RangeKey) => void }) {
  const w = rangeWindow(range)
  const now = totals(daysBetween(w.from, w.to))
  const prev = totals(daysBetween(w.prevFrom, w.prevTo))
  const label = RANGES.find((r) => r.key === range)!.label
  const items = itemTotals(w.from, w.to).slice(0, 5)
  const topMax = items[0]?.revenue ?? 1
  const avg = now.orders ? now.gross / now.orders : 0
  const prevAvg = prev.orders ? prev.gross / prev.orders : 0
  const tips = weeklyInsights()
  const lead = tips.find((t) => t.id === 'fees') ?? tips[0]
  const h = health()
  const [why, setWhy] = useState(false)
  const stock = stockAlerts()

  return (
    <>
      <section className="grad gold">
        <header className="top">
          <div>
            <div className="eyebrow">Good morning,</div>
            <h1>{data.truck.owner.split(' ')[0]}</h1>
          </div>
          <div className="avatar" aria-hidden>{data.truck.owner[0]}</div>
        </header>

        <button className={`rating-pill ${h.tone}`} onClick={() => setWhy(!why)} aria-expanded={why}>
          <span className="dot" aria-hidden />
          <span>Business is <b>{h.rating}</b></span>
          <span className="chev">{why ? '▴' : '▾'}</span>
        </button>
        {why && (
          <ul className="checks glass">
            {h.checks.map((c) => (
              <li key={c.label} className={c.score > 0 ? 'good' : c.score < 0 ? 'warn' : 'info'}>
                <span className="dot" aria-hidden />
                <div><b>{c.label}</b><span>{c.detail}</span></div>
              </li>
            ))}
          </ul>
        )}

        <div className="row hero-row">
          <div className="label">Sales this {label}</div>
          <Pills value={range} onChange={setRange} />
        </div>
        <div className="big">{money(now.gross)}</div>
        <Delta value={pctChange(now.gross, prev.gross)} suffix={`vs previous ${label}`} />

        <div className="tiles">
          <Tile value={now.orders.toLocaleString()} label="orders" delta={pctChange(now.orders, prev.orders)} />
          <Tile value={money(avg, { cents: true })} label="avg order" delta={pctChange(avg, prevAvg)} />
          <Tile value={money(now.tips)} label="tips" delta={pctChange(now.tips, prev.tips)} />
        </div>
      </section>

      <Card>
        <Bars bars={buckets(range, w.from, w.to)} />
      </Card>

      {stock.length > 0 && (
        <Link to="/tips" className="plain">
          <Card className="insight warn">
            <div className="eyebrow">Use it or lose it</div>
            {stock.slice(0, 2).map((s) => (
              <div key={s.id} className="stock-row">
                <div className="insight-title">{s.item.name}: {s.unitsNow} sold this week, usually {s.unitsBase}</div>
                <div className="sub">About {s.surplusLabel} of {s.ingredient} a week going unsold, worth {money(s.wastePerWeek)}. Prep less first.</div>
              </div>
            ))}
            <div className="more">See what to do →</div>
          </Card>
        </Link>
      )}

      {lead && (
        <Link to="/tips" className="plain">
          <Card className={`insight ${lead.tone}`}>
            <div className="eyebrow">This week's tip</div>
            <div className="insight-title">{lead.title}</div>
            <div className="more">See all tips →</div>
          </Card>
        </Link>
      )}

      <Card>
        <div className="row">
          <h2>Top sellers</h2>
          <Link to="/menu" className="more">Full menu →</Link>
        </div>
        <ul className="list">
          {items.map((i) => (
            <li key={i.item.id}>
              <div className="list-main">
                <span className="name">{i.item.name}</span>
                <span className="val">{money(i.revenue)}</span>
              </div>
              <div className="list-sub">
                <Meter value={i.revenue} max={topMax} />
                <span>{i.qty.toLocaleString()} sold</span>
              </div>
            </li>
          ))}
        </ul>
      </Card>
    </>
  )
}
