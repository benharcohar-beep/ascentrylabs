import { Link, useNavigate } from 'react-router-dom'
import { Bars, Card, Delta, Pills, Tile } from '../components/ui'
import { METRIC_LABEL, RANGES, buckets, data, daysBetween, formatMetric, itemTotals, money, pct, pctChange, rangeWindow, totals, type Metric, type RangeKey } from '../lib/data'
import { health } from '../lib/health'
import { weeklyInsights } from '../lib/insights'
import { stockAlerts } from '../lib/stock'
import { statementFor } from '../lib/money'
import { Brand } from '../components/Brand'

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
  const navigate = useNavigate()
  const st = statementFor(range)
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

        <div className="row hero-row">
          <div className="label">This {label}</div>
          <Pills value={range} onChange={setRange} />
        </div>
        <div className="two">
          <div onClick={() => pick('sales')} role="link" style={{ cursor: 'pointer' }}>
            <div className="label">Sales</div>
            <div className="mid">{money(now.gross)}</div>
            <Delta value={pctChange(now.gross, prev.gross)} suffix={`vs last ${label}`} />
          </div>
          <div onClick={() => navigate('/money')} role="link" style={{ cursor: 'pointer' }}>
            <div className="label">Profit</div>
            <div className="mid">{st.now.profit < 0 ? '-' : ''}{money(Math.abs(st.now.profit))}</div>
            <Delta value={pctChange(st.now.profit, st.prev.profit)} suffix={`vs last ${label}`} />
          </div>
        </div>

        <div className="tiles">
          <Tile value={now.orders.toLocaleString()} label="orders" delta={pctChange(now.orders, prev.orders)} onClick={() => pick('orders')} />
          <Tile value={money(avg, { cents: true })} label="avg order" delta={pctChange(avg, prevAvg)} onClick={() => pick('avg')} />
          <Tile value={money(now.tips)} label="tips" delta={pctChange(now.tips, prev.tips)} onClick={() => pick('tips')} />
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
        <Card className="line noleft">
          <span className="txt">
            <b>{tips.filter((t) => t.id !== 'wow').length + stock.length} insights this week</b>
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
                <span className={`pill ${i.margin < 0.6 ? 'amber' : 'green'}`}>{pct(i.margin, false)} profit</span>
              </span>
            </li>
          ))}
        </ul>
      </section>
    </>
  )
}
