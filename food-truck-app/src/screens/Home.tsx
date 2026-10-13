import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'
import { Brand } from '../components/Brand'
import { Bars, Card } from '../components/ui'
import { METRIC_LABEL, RANGES, TODAY, addDays, buckets, data, daysBetween, formatMetric, itemTotals, locationById, money, pct, pctChange, rangeWindow, shortDate, totals, weekday, type RangeKey } from '../lib/data'
import { health } from '../lib/health'
import { cashAt, statementFor } from '../lib/money'

export default function Home({ range, setRange }: { range: RangeKey; setRange: (k: RangeKey) => void }) {
  const w = rangeWindow(range)
  const now = totals(daysBetween(w.from, w.to))
  const prev = totals(daysBetween(w.prevFrom, w.prevTo))
  const label = RANGES.find((r) => r.key === range)!.label
  const items = itemTotals(w.from, w.to).slice(0, 5)
  const avg = now.orders ? now.gross / now.orders : 0
  const prevAvg = prev.orders ? prev.gross / prev.orders : 0
  const h = health()
  const st = statementFor(range)
  const cash = cashAt()
  const navigate = useNavigate()

  // Day strip: this week, Monday to Sunday.
  const week = daysBetween(addDays(TODAY, -6), TODAY)
  const [sel, setSel] = useState<string>(week.filter((d) => d.trading).at(-1)?.date ?? TODAY)
  const day = week.find((d) => d.date === sel)!

  const metric = 'sales'
  const tone = h.tone === 'good' ? 'mint' : h.tone === 'warn' ? 'coral' : 'marigold'

  return (
    <>
      <header className="top head3">
        <div className="avatar" aria-hidden>{data.truck.owner[0]}</div>
        <div className="head-mid">
          <b>Hello {data.truck.owner.split(' ')[0]}</b>
          <span>Today {shortDate(TODAY)}</span>
        </div>
        <Brand />
      </header>

      <Link to="/money" className={`block-hero ${tone}`}>
        <div className="tag">Business is</div>
        <div className="block-title">{h.rating}</div>
        <div className="block-sub">{h.summary}</div>
        <ArrowUpRight className="corner" size={22} />
      </Link>

      <div className="strip">
        {week.map((d) => (
          <button key={d.date} className={`day ${d.date === sel ? 'on' : ''}`} onClick={() => setSel(d.date)}>
            <span className={`dot ${d.trading ? 'yes' : ''}`} />
            <span className="dow">{weekday(d.date)}</span>
            <span className="dom">{Number(d.date.slice(8))}</span>
          </button>
        ))}
      </div>
      <div className="strip-note">
        {day.trading
          ? <><b>{money(day.gross_sales ?? 0)}</b> at {locationById.get(day.location_id!)?.name} · {day.orders} orders · {day.condition}, {day.temp_f}°F</>
          : <>Day off · {day.condition}, {day.temp_f}°F</>}
      </div>

      <div className="row block-head">
        <h2>Your {label}</h2>
        <div className="pills">
          {RANGES.map((r) => (
            <button key={r.key} className={range === r.key ? 'on' : ''} onClick={() => setRange(r.key)}>{r.key}</button>
          ))}
        </div>
      </div>

      <div className="bento">
        <button className="bento-card coral" onClick={() => navigate('/history/sales')}>
          <span className="tag">Sales</span>
          <span className="bento-num">{money(st.now.sales)}</span>
          <Chg v={pctChange(st.now.sales, st.prev.sales)} label={label} />
          {st.now.catering > 0 && <span className="bento-sub">incl. {money(st.now.catering)} catering</span>}
        </button>
        <button className="bento-card mint" onClick={() => navigate('/money')}>
          <span className="tag">Profit</span>
          <span className="bento-num">{st.now.profit < 0 ? '-' : ''}{money(Math.abs(st.now.profit))}</span>
          <Chg v={pctChange(st.now.profit, st.prev.profit)} label={label} />
        </button>
        <button className="bento-card marigold wide cash" onClick={() => navigate('/money')}>
          <span className="tag">Cash in the bank</span>
          <span className="bento-num">{money(cash.balance)}</span>
          <span className="bento-sub">{money(cash.available)} is yours to spend. {money(cash.taxOwed)} is sales tax you owe{cash.nextRemittance ? `, due ${shortDate(cash.nextRemittance.date)}` : ''}.</span>
        </button>
        <button className="bento-card small" onClick={() => navigate('/history/orders')}>
          <span className="bento-num">{now.orders.toLocaleString()}</span><span className="bento-sub">orders</span><Chg v={pctChange(now.orders, prev.orders)} label={label} />
        </button>
        <button className="bento-card small" onClick={() => navigate('/history/avg')}>
          <span className="bento-num">{money(avg, { cents: true })}</span><span className="bento-sub">avg order</span><Chg v={pctChange(avg, prevAvg)} label={label} />
        </button>
        <button className="bento-card small" onClick={() => navigate('/history/tips')}>
          <span className="bento-num">{money(now.tips)}</span><span className="bento-sub">tips</span><Chg v={pctChange(now.tips, prev.tips)} label={label} />
        </button>
      </div>

      <Card>
        <div className="row">
          <h2>{METRIC_LABEL[metric]} by {range === '1Y' ? 'month' : range === '3M' ? 'week' : 'day'}</h2>
          <Link to="/history/sales" className="more">Full history</Link>
        </div>
        <Bars bars={buckets(range, w.from, w.to, metric)} format={(v) => formatMetric(v, metric)} />
      </Card>

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
                <span className={`pill ${i.margin < 0.6 ? 'amber' : 'green'}`}>{pct(i.margin, false)} margin</span>
              </span>
            </li>
          ))}
        </ul>
      </section>
    </>
  )
}

function Chg({ v, label }: { v: number | null; label: string }) {
  if (v === null) return null
  return <span className={`chg ${v >= 0 ? 'up' : 'down'}`}>{v >= 0 ? '▲' : '▼'} {Math.abs(Math.round(v * 100))}% vs last {label}</span>
}
