import { useState } from 'react'
import { Link, NavLink, useParams } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { Bars, Card, Delta, Pills } from '../components/ui'
import {
  METRIC_LABEL, RANGES, TODAY, addDays, buckets, daysBetween, formatMetric, metricOf, pctChange, rangeWindow, shortDate, totals,
  type Metric, type RangeKey,
} from '../lib/data'

const VALID: Metric[] = ['sales', 'orders', 'avg', 'tips']

export default function History() {
  const { metric: m } = useParams()
  const metric: Metric = VALID.includes(m as Metric) ? (m as Metric) : 'sales'
  const [range, setRange] = useState<RangeKey>('3M')
  const w = rangeWindow(range)
  const now = metricOf(totals(daysBetween(w.from, w.to)), metric)
  const prev = metricOf(totals(daysBetween(w.prevFrom, w.prevTo)), metric)
  const label = RANGES.find((r) => r.key === range)!.label
  const bars = buckets(range, w.from, w.to, metric)

  // Week by week for the last 12 weeks, newest first.
  const weeks = []
  for (let i = 0; i < 12; i++) {
    const to = addDays(TODAY, -7 * i), from = addDays(to, -6)
    const t = totals(daysBetween(from, to))
    const pt = totals(daysBetween(addDays(from, -7), addDays(from, -1)))
    weeks.push({ from, to, value: metricOf(t, metric), prev: metricOf(pt, metric), days: t.tradingDays })
  }
  const nonZero = weeks.filter((x) => x.value > 0)
  const best = nonZero.reduce((a, b) => (b.value > a.value ? b : a), nonZero[0])
  const worst = nonZero.reduce((a, b) => (b.value < a.value ? b : a), nonZero[0])
  const avgWeek = nonZero.length ? nonZero.reduce((a, b) => a + b.value, 0) / nonZero.length : 0

  return (
    <>
      <section className="grad gold">
        <header className="top">
          <Link to="/" className="back">‹ Home</Link>
          <Brand />
        </header>
        <nav className="seg">
          {VALID.map((k) => (
            <NavLink key={k} to={`/history/${k}`} className={({ isActive }) => (isActive ? 'on' : '')}>{k === 'avg' ? 'Avg order' : METRIC_LABEL[k]}</NavLink>
          ))}
        </nav>
        <div className="row hero-row">
          <div>
            <div className="label">{METRIC_LABEL[metric]}, this {label}</div>
            <div className="big">{formatMetric(now, metric)}</div>
            <Delta value={pctChange(now, prev)} suffix={`vs previous ${label}`} />
          </div>
          <Pills value={range} onChange={setRange} />
        </div>
      </section>

      <Card>
        <h2>{METRIC_LABEL[metric]} by {range === '1Y' ? 'month' : range === '3M' ? 'week' : 'day'}</h2>
        <Bars bars={bars} height={150} format={(v) => formatMetric(v, metric)} />
      </Card>

      {best && (
        <div className="tiles plain">
          <div className="card tile"><div className="num">{formatMetric(best.value, metric)}</div><div className="label">best week</div><div className="sub">Week of {shortDate(best.from)}</div></div>
          <div className="card tile"><div className="num">{formatMetric(avgWeek, metric)}</div><div className="label">typical week</div><div className="sub">last 12</div></div>
          <div className="card tile"><div className="num">{formatMetric(worst.value, metric)}</div><div className="label">worst week</div><div className="sub">Week of {shortDate(worst.from)}</div></div>
        </div>
      )}

      <section className="block">
        <h2>Week by week</h2>
        <ul className="log">
          {weeks.map((x) => {
            const ch = pctChange(x.value, x.prev)
            return (
              <li key={x.from}>
                <span className="name">Week of {shortDate(x.from)} <small className="muted">{x.days} days</small></span>
                <span className="val">{formatMetric(x.value, metric)}</span>
                <span className="pills-sm">
                  {ch !== null && <span className={`pill ${ch >= 0 ? 'green' : 'amber'}`}>{ch >= 0 ? '+' : ''}{Math.round(ch * 100)}% vs week before</span>}
                </span>
              </li>
            )
          })}
        </ul>
      </section>
    </>
  )
}
