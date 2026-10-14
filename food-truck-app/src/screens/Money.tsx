import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Amt, Bars } from '../components/ui'
import { TODAY, daysBetween, money, monthName, pct, pctChange, shortDate } from '../lib/data'
import { cashAt, months, statement } from '../lib/money'

function Line({ label, value, sales, prev, sign = '', strong = false }: { label: string; value: number; sales: number; prev?: number; sign?: string; strong?: boolean }) {
  const ch = prev !== undefined ? pctChange(value, prev) : null
  const share = sales ? Math.abs(value) / sales : 0
  return (
    <li className={`bd-row ${strong ? 'strong' : ''}`}>
      <span className="bd-label">{label}</span>
      <span className="bd-bar"><span style={{ width: `${Math.min(100, share * 100)}%` }} /></span>
      <span className="bd-share">{pct(share, false)}</span>
      <span className="bd-val">{sign}{money(Math.abs(value))}</span>
      <span className={`bd-ch ${ch === null ? '' : ch >= 0 ? 'up' : 'down'}`}>{ch === null ? '' : `${ch >= 0 ? '+' : ''}${Math.round(ch * 100)}%`}</span>
    </li>
  )
}

export default function Money() {
  const ms = months() // newest first
  const [ym, setYm] = useState(ms[0].month)
  const idx = ms.findIndex((m) => m.month === ym)
  const prevYm = ms[idx + 1]?.month
  const first = `${ym}-01`
  const last = ym === TODAY.slice(0, 7) ? TODAY : `${ym}-${new Date(Date.UTC(Number(ym.slice(0, 4)), Number(ym.slice(5, 7)), 0)).getUTCDate()}`
  const now = statement(first, last)
  const partial = ym === TODAY.slice(0, 7)
  const prev = partial || !prevYm ? null : statement(`${prevYm}-01`, `${prevYm}-${new Date(Date.UTC(Number(prevYm.slice(0, 4)), Number(prevYm.slice(5, 7)), 0)).getUTCDate()}`)
  const cash = cashAt()
  const [showFixed, setShowFixed] = useState(false)
  const days = daysBetween(first, last)

  return (
    <div className="screen">
      <header className="top">
        <Link to="/" className="back">‹</Link>
        <h1>Money</h1>
        <span />
      </header>

      <div className="chips">
        {ms.map((m) => (
          <button key={m.month} className={`chip-btn ${m.month === ym ? 'on' : ''}`} onClick={() => setYm(m.month)}>{monthName(m.month, true).split(' ')[0].slice(0, 3)} {m.month.slice(2, 4)}</button>
        ))}
      </div>

      <section className="hero">
        <div className="label">Profit, {monthName(ym, true)}{partial ? ' so far' : ''}</div>
        <div className="hero-num"><Amt v={now.profit} /></div>
        <div className="hero-sub">
          <span>{pct(now.sales ? now.profit / now.sales : 0, false)} of {money(now.sales)} sales</span>
          <span className="dot-sep">·</span>
          <span>{now.tradingDays} working days</span>
        </div>
      </section>

      <section className="card flat">
        <h2>Sales by day</h2>
        <Bars bars={days.map((d) => ({ label: String(Number(d.date.slice(8))), value: d.gross_sales ?? 0, sub: d.trading ? `${shortDate(d.date)}` : 'Day off' }))} height={110} highlightLast />
      </section>

      <section className="card flat">
        <h2>Breakdown</h2>
        <ul className="bd">
          <Line label="Sales" value={now.sales} sales={now.sales} prev={prev?.sales} strong />
          <Line label="Food and packaging" value={now.food} sales={now.sales} prev={prev?.food} sign="-" />
          <Line label="Staff wages" value={now.staff} sales={now.sales} prev={prev?.staff} sign="-" />
          <Line label="Venue and card fees" value={now.fees} sales={now.sales} prev={prev?.fees} sign="-" />
          <li className="bd-row clickable" onClick={() => setShowFixed(!showFixed)}>
            <span className="bd-label">Fixed bills {showFixed ? '▴' : '▾'}</span>
            <span className="bd-bar"><span style={{ width: `${Math.min(100, (now.sales ? now.fixed / now.sales : 0) * 100)}%` }} /></span>
            <span className="bd-share">{pct(now.sales ? now.fixed / now.sales : 0, false)}</span>
            <span className="bd-val">-{money(now.fixed)}</span>
            <span className="bd-ch" />
          </li>
          {showFixed && now.fixedLines.map((f) => (
            <li key={f.name} className="bd-row plain sub"><span className="bd-label">{f.name}</span><span className="bd-val">-{money(f.amount)}</span></li>
          ))}
          <Line label="Profit" value={now.profit} sales={now.sales} prev={prev?.profit} strong sign={now.profit < 0 ? '-' : ''} />
        </ul>
      </section>

      <section className="card flat">
        <h2>Put away</h2>
        <ul className="bd">
          <li className="bd-row plain"><span className="bd-label">Sales tax collected</span><span className="bd-val">{money(now.tax)}</span></li>
          <li className="bd-row plain"><span className="bd-label">Staff tips</span><span className="bd-val">{money(now.tips)}</span></li>
          <li className="bd-row plain strong"><span className="bd-label">Cash in the bank today</span><span className="bd-val">{money(cash.balance)}</span></li>
        </ul>
        <p className="note">Sales tax is paid on the 20th of the following month. Cash is rolled forward from {money(cash.opening)} on day one; connect the bank for the real figure.</p>
      </section>
    </div>
  )
}
