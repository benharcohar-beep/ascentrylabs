import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Bars, Card, Delta, Pills } from '../components/ui'
import { RANGES, money, monthName, pct, pctChange, shortDate, type RangeKey } from '../lib/data'
import { cashAt, months, statementFor } from '../lib/money'

function Line({ label, value, sales, prev, sign = '', strong = false, muted = false }: {
  label: string; value: number; sales: number; prev?: number; sign?: string; strong?: boolean; muted?: boolean
}) {
  const ch = prev !== undefined ? pctChange(value, prev) : null
  return (
    <li className={`stmt-line ${strong ? 'strong' : ''} ${muted ? 'muted' : ''}`}>
      <span className="stmt-label">{label}</span>
      <span className="stmt-share">{sales && !muted ? pct(value / sales, false) : ''}</span>
      <span className="stmt-val">{sign}{money(Math.abs(value))}</span>
      <span className={`stmt-ch ${ch === null ? '' : ch >= 0 ? 'up' : 'down'}`}>{ch === null ? '' : `${ch >= 0 ? '+' : ''}${Math.round(ch * 100)}%`}</span>
    </li>
  )
}

export default function Money() {
  const [range, setRange] = useState<RangeKey>('1M')
  const { now, prev } = statementFor(range)
  const label = RANGES.find((r) => r.key === range)!.label
  const ms = months()
  const [showFixed, setShowFixed] = useState(false)
  const cash = cashAt()

  return (
    <>
      <section className="block-hero mint page">
        <header className="top">
          <Link to="/" className="back">‹ Home</Link>
        </header>
        <div className="row hero-row">
          <div>
            <div className="label">Profit this {label}</div>
            <div className="big">{now.profit < 0 ? '-' : ''}{money(Math.abs(now.profit))}</div>
            <Delta value={pctChange(now.profit, prev.profit)} suffix={`vs previous ${label}`} />
          </div>
          <Pills value={range} onChange={setRange} />
        </div>
        <div className="label" style={{ marginTop: 10 }}>
          {pct(now.sales ? now.profit / now.sales : 0, false)} of {money(now.sales)} sales, after every cost. {now.tradingDays} trading days.
        </div>
      </section>

      <Card>
        <h2>Cash</h2>
        <ul className="stmt">
          <li className="stmt-line strong"><span className="stmt-label">In the bank today</span><span className="stmt-share" /><span className="stmt-val">{money(cash.balance)}</span><span className="stmt-ch" /></li>
          <li className="stmt-line"><span className="stmt-label">Sales tax you owe{cash.nextRemittance ? ` (due ${shortDate(cash.nextRemittance.date)})` : ''}</span><span className="stmt-share" /><span className="stmt-val">-{money(cash.taxOwed)}</span><span className="stmt-ch" /></li>
          <li className="stmt-line strong"><span className="stmt-label">Yours to spend</span><span className="stmt-share" /><span className="stmt-val">{money(cash.available)}</span><span className="stmt-ch" /></li>
        </ul>
        <p className="note">Rolled forward from {money(cash.opening)} on day one: everything through the till and catering, less food, staff, fees and fixed bills, less sales tax when it is paid{cash.lastRemittance ? ` (last paid ${money(cash.lastRemittance.amount)} on ${shortDate(cash.lastRemittance.date)})` : ''}. Connect the bank for the real figure.</p>
      </Card>

      <Card>
        <h2>Where the money went</h2>
        <ul className="stmt">
          <li className="stmt-line head"><span className="stmt-label" /><span className="stmt-share">of sales</span><span className="stmt-val">amount</span><span className="stmt-ch">vs last</span></li>
          <Line label="Truck sales" value={now.truckSales} sales={now.sales} prev={prev.truckSales} />
          {now.catering > 0 && <Line label="Catering" value={now.catering} sales={now.sales} prev={prev.catering} />}
          <Line label="Food and packaging" value={now.food} sales={now.sales} prev={prev.food} sign="-" />
          <Line label="Staff wages" value={now.staff} sales={now.sales} prev={prev.staff} sign="-" />
          <Line label="Venue and card fees" value={now.fees} sales={now.sales} prev={prev.fees} sign="-" />
          <Line label="Profit before fixed bills" value={now.tradingProfit} sales={now.sales} prev={prev.tradingProfit} strong />
          <li className="stmt-line clickable" onClick={() => setShowFixed(!showFixed)}>
            <span className="stmt-label">Fixed bills {showFixed ? '▴' : '▾'}</span>
            <span className="stmt-share">{pct(now.sales ? now.fixed / now.sales : 0, false)}</span>
            <span className="stmt-val">-{money(now.fixed)}</span>
            <span className="stmt-ch" />
          </li>
          {showFixed && now.fixedLines.map((f) => (
            <li key={f.name} className="stmt-line sub">
              <span className="stmt-label">{f.name}</span><span className="stmt-share" /><span className="stmt-val">-{money(f.amount)}</span><span className="stmt-ch" />
            </li>
          ))}
          <Line label="Profit" value={now.profit} sales={now.sales} prev={prev.profit} strong sign={now.profit < 0 ? '-' : ''} />
        </ul>
        <p className="note">Fixed bills are spread evenly across the days of each month.</p>
      </Card>

      <Card>
        <h2>Set aside</h2>
        <ul className="stmt">
          <Line label="Sales tax collected" value={now.tax} sales={now.sales} muted />
          <Line label="Tips" value={now.tips} sales={now.sales} muted />
        </ul>
        <p className="note">Sales tax (7.9%) goes to the state and county. Tips go to the people who worked.</p>
      </Card>

      <Card>
        <h2>Profit by month</h2>
        <Bars
          bars={ms.slice().reverse().map((m) => ({ label: monthName(m.month), value: m.operating_profit, sub: monthName(m.month, true) }))}
          height={120}
          format={(v) => `${v < 0 ? '-' : ''}${money(Math.abs(v))}`}
        />
        <ul className="log">
          {ms.map((m) => (
            <li key={m.month}>
              <span className="name">{monthName(m.month, true)} <small className="muted">{m.trading_days} days</small></span>
              <span className={`val ${m.operating_profit < 0 ? 'down' : ''}`}>{m.operating_profit < 0 ? '-' : ''}{money(Math.abs(m.operating_profit))}</span>
              <span className="pills-sm">
                <span className="pill grey">{money(m.total_sales)} sales</span>
                <span className={`pill ${m.operating_profit >= 0 ? 'green' : 'amber'}`}>{m.operating_profit >= 0 ? 'profit' : 'loss'}</span>
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </>
  )
}
