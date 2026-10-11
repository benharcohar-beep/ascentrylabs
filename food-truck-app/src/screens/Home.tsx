import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bars, Card, Delta, Pills, Ring, Tile } from '../components/ui'
import { METRIC_LABEL, RANGES, buckets, data, daysBetween, formatMetric, itemTotals, money, pct, pctChange, rangeWindow, totals, weeklyHistory, type Metric, type RangeKey } from '../lib/data'
import { health } from '../lib/health'
import { weeklyInsights } from '../lib/insights'
import { stockAlerts } from '../lib/stock'
import { Brand } from '../components/Brand'

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
  const navigate = useNavigate()
  const metric: Metric = 'sales'
  const pick = (m: Metric) => navigate(`/history/${m}`)


  return (
    <>
      <section className="grad gold">
        <header className="top">
          <div>
            <div className="eyebrow">Good morning,</div>
            <h1>{data.truck.owner.split(' ')[0]}</h1>
          </div>
          <Brand />
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
          <div onClick={() => pick('sales')} role="link" style={{ cursor: 'pointer' }}>
            <div className="label">Sales this {label}</div>
            <div className="mid">{money(now.gross)}</div>
            <Delta value={pctChange(now.gross, prev.gross)} suffix={`vs previous ${label}`} />
          </div>
          <Pills value={range} onChange={setRange} />
        </div>

        <div className="tiles">
          <Tile value={now.orders.toLocaleString()} label="orders" delta={pctChange(now.orders, prev.orders)} spark={weeklyHistory('orders')} onClick={() => pick('orders')} />
          <Tile value={money(avg, { cents: true })} label="avg order" delta={pctChange(avg, prevAvg)} spark={weeklyHistory('avg')} onClick={() => pick('avg')} />
          <Tile value={money(now.tips)} label="tips" delta={pctChange(now.tips, prev.tips)} spark={weeklyHistory('tips')} onClick={() => pick('tips')} />
        </div>
      </section>

      <Card>
        <div className="row">
          <h2>{METRIC_LABEL[metric]} by {range === '1Y' ? 'month' : range === '3M' ? 'week' : 'day'}</h2>
          <Link to="/history/sales" className="more">Full history</Link>
        </div>
        <Bars bars={buckets(range, w.from, w.to, metric)} format={(v) => formatMetric(v, metric)} />
      </Card>

      <Link to="/insights" className="plain">
        <Card className="line">
          <span className="fig warn">{tips.length + stock.length}</span>
          <span className="txt">
            <b>Eventini insights this week</b>
            <span>{stock[0] ? `${stock[0].item.name} has stopped selling. ` : ''}{tips.find((t) => t.id === 'fees')?.title ?? tips[0]?.title}</span>
          </span>
          <span className="chev">›</span>
        </Card>
      </Link>

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
