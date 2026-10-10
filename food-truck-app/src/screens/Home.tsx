import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Bars, Card, Delta, Pills, Ring, Tile } from '../components/ui'
import { METRIC_LABEL, RANGES, buckets, data, daysBetween, formatMetric, itemTotals, money, pct, pctChange, rangeWindow, totals, weeklyHistory, type Metric, type RangeKey } from '../lib/data'
import { health } from '../lib/health'
import { weeklyInsights } from '../lib/insights'
import { stockAlerts } from '../lib/stock'

const toneOf = (score: number): 'good' | 'info' | 'warn' => (score > 0 ? 'good' : score < 0 ? 'warn' : 'info')

export default function Home({ range, setRange }: { range: RangeKey; setRange: (k: RangeKey) => void }) {
  const w = rangeWindow(range)
  const now = totals(daysBetween(w.from, w.to))
  const prev = totals(daysBetween(w.prevFrom, w.prevTo))
  const label = RANGES.find((r) => r.key === range)!.label
  const items = itemTotals(w.from, w.to).slice(0, 5)
  const avg = now.orders ? now.gross / now.orders : 0
  const prevAvg = prev.orders ? prev.gross / prev.orders : 0
  const tips = weeklyInsights()
  const stock = stockAlerts()
  const h = health()
  const [why, setWhy] = useState<string | null>(null)
  const [metric, setMetric] = useState<Metric>('sales')
  const pick = (m: Metric) => setMetric(metric === m ? 'sales' : m)

  // Today: the stock alert first, then the strongest tips, as short actions.
  const today = [
    ...stock.slice(0, 1).map((s) => ({ id: s.id, title: `Prep less ${s.ingredient}`, sub: `${s.item.name}: ${s.unitsNow} sold, usually ${s.unitsBase}`, tone: 'warn' as const })),
    ...tips.filter((t) => t.id !== 'wow').map((t) => ({ id: t.id, title: t.short, sub: t.title, tone: t.tone })),
  ].slice(0, 4)

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

        <div className="rating-hero">
          <div className="label">Business is</div>
          <div className={`rating-big ${h.tone}`}>{h.rating}</div>
          <div className="rating-sum">{h.summary}</div>
        </div>

        <div className="rings">
          {h.checks.map((c) => (
            <button key={c.label} className="ring-btn" onClick={() => setWhy(why === c.label ? null : c.label)} aria-pressed={why === c.label}>
              <Ring fill={c.fill} tone={toneOf(c.score)} text={c.value} label={c.label} />
            </button>
          ))}
        </div>
        {why && <div className="ring-detail">{h.checks.find((c) => c.label === why)?.detail}</div>}

        <div className="row hero-row">
          <div>
            <div className="label">Sales this {label}</div>
            <div className="mid">{money(now.gross)}</div>
            <Delta value={pctChange(now.gross, prev.gross)} suffix={`vs previous ${label}`} />
          </div>
          <Pills value={range} onChange={setRange} />
        </div>

        <div className="tiles">
          <Tile value={now.orders.toLocaleString()} label="orders" delta={pctChange(now.orders, prev.orders)} spark={weeklyHistory('orders')} on={metric === 'orders'} onClick={() => pick('orders')} />
          <Tile value={money(avg, { cents: true })} label="avg order" delta={pctChange(avg, prevAvg)} spark={weeklyHistory('avg')} on={metric === 'avg'} onClick={() => pick('avg')} />
          <Tile value={money(now.tips)} label="tips" delta={pctChange(now.tips, prev.tips)} spark={weeklyHistory('tips')} on={metric === 'tips'} onClick={() => pick('tips')} />
        </div>
      </section>

      <Card>
        <div className="row">
          <h2>{METRIC_LABEL[metric]} by {range === '1Y' ? 'month' : range === '3M' ? 'week' : 'day'}</h2>
          {metric !== 'sales' && <button className="linkish" onClick={() => setMetric('sales')}>back to sales</button>}
        </div>
        <Bars bars={buckets(range, w.from, w.to, metric)} format={(v) => formatMetric(v, metric)} />
      </Card>

      <section className="block">
        <div className="row">
          <h2>Today</h2>
          <Link to="/tips" className="more">See all</Link>
        </div>
        <div className="today">
          {today.map((t) => (
            <Link key={t.id} to="/tips" className={`today-tile ${t.tone}`}>
              <span className="dot" aria-hidden />
              <b>{t.title}</b>
              <span>{t.sub}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="block">
        <div className="row">
          <h2>Top sellers</h2>
          <Link to="/menu" className="more">See all</Link>
        </div>
        <ul className="log">
          {items.map((i) => (
            <li key={i.item.id}>
              <span className="name">{i.item.name}</span>
              <span className="val">{money(i.revenue)}</span>
              <span className="pills-sm">
                <span className="pill grey">{i.qty.toLocaleString()} sold</span>
                <span className={`pill ${i.margin < 0.6 ? 'amber' : 'green'}`}>keeps {pct(i.margin, false)}</span>
              </span>
            </li>
          ))}
        </ul>
      </section>
    </>
  )
}
