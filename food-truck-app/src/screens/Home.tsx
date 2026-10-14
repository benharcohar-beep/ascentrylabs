import { Link, useNavigate } from 'react-router-dom'
import { ChevronRight, Store, MapPin, Beer, Trophy, Briefcase, GraduationCap, Tent, Stethoscope, PartyPopper, Receipt, Landmark, HandCoins } from 'lucide-react'
import { Brand } from '../components/Brand'
import { ThemeToggle } from '../components/ThemeToggle'
import { TODAY, data, daysBetween, locationById, money, pctChange, rangeWindow, shortDate, weekday, totals } from '../lib/data'
import { health } from '../lib/health'
import { cashAt, statementFor } from '../lib/money'

const ICON: Record<string, React.ComponentType<{ size?: number }>> = {
  food_park: Store, street: MapPin, brewery: Beer, event: Trophy, office: Briefcase, campus: GraduationCap,
  festival: Tent, hospital: Stethoscope, market: PartyPopper,
}

export default function Home() {
  const navigate = useNavigate()
  const h = health()
  const cash = cashAt()
  const wk = statementFor('1W')
  const w = rangeWindow('1W')
  const week = totals(daysBetween(w.from, w.to))
  const prevWeek = totals(daysBetween(w.prevFrom, w.prevTo))
  const weekDays = daysBetween(w.from, w.to).filter((d) => d.trading).length
  const prevDays = daysBetween(w.prevFrom, w.prevTo).filter((d) => d.trading).length
  const feed = daysBetween(rangeWindow('1M').from, TODAY).filter((d) => d.trading).reverse().slice(0, 12)
  const billsMonth = data.fixedCosts.filter((f) => f.month === TODAY.slice(0, 7)).reduce((a, f) => a + f.amount, 0)

  return (
    <div className="screen">
      <header className="top">
        <div className="head-mid">
          <span className="eyebrow">Numbers to {weekday(TODAY)} {shortDate(TODAY)}</span>
          <b>{data.truck.name}</b>
        </div>
        <div className="head-right"><ThemeToggle /><Brand /></div>
      </header>

      <section className={`status ${h.tone}`} onClick={() => navigate('/money')} role="link">
        <span className="label">Business is</span>
        <span className="status-word">{h.rating}</span>
        <span className="status-sub">{h.summary}</span>
      </section>

      <section className="hero" onClick={() => navigate('/money')} role="link">
        <div className="label">In the bank today</div>
        <div className="hero-num">{money(cash.balance)}</div>
        <div className="hero-sub">
          <span><b>{money(cash.available)}</b> yours to spend</span>
          <span className="dot-sep">·</span>
          <span><b>{money(cash.taxOwed)}</b> owed in sales tax</span>
        </div>
      </section>

      <section className="block">
      <div className="row"><h2>This week</h2><span className="sub">{weekDays} {weekDays === 1 ? 'day' : 'days'} traded · last week {prevDays}</span></div>
      <div className="swipe">
        <button className="swipe-card" onClick={() => navigate('/history/sales')}>
          <span className="label">Sales</span>
          <span className="card-num">{money(wk.now.sales)}</span>
          <Chg v={pctChange(wk.now.sales, wk.prev.sales)} />
        </button>
        <button className="swipe-card" onClick={() => navigate('/money')}>
          <span className="label">Profit</span>
          <span className="card-num">{wk.now.profit < 0 ? '-' : ''}{money(Math.abs(wk.now.profit))}</span>
          <Chg v={pctChange(wk.now.profit, wk.prev.profit)} />
        </button>
        <button className="swipe-card" onClick={() => navigate('/history/orders')}>
          <span className="label">Orders</span>
          <span className="card-num">{week.orders.toLocaleString()}</span>
          <Chg v={pctChange(week.orders, prevWeek.orders)} />
        </button>
      </div>
      </section>

      <section className="block">
        <div className="row"><h2>Put away</h2><Link to="/money" className="more">Money <ChevronRight size={14} /></Link></div>
        <ul className="feed flat">
          <li className="feed-row" onClick={() => navigate('/money')}>
            <span className="feed-ico"><Receipt size={18} /></span>
            <span className="feed-main"><b>Sales tax</b><span>{cash.nextRemittance ? `due ${shortDate(cash.nextRemittance.date)}` : 'nothing due'}</span></span>
            <span className="feed-amt">{money(cash.taxOwed)}</span>
          </li>
          <li className="feed-row" onClick={() => navigate('/money')}>
            <span className="feed-ico"><Landmark size={18} /></span>
            <span className="feed-main"><b>Bills due this month</b><span>loan, insurance, kitchen</span></span>
            <span className="feed-amt">{money(billsMonth)}</span>
          </li>
          <li className="feed-row" onClick={() => navigate('/history/tips')}>
            <span className="feed-ico"><HandCoins size={18} /></span>
            <span className="feed-main"><b>Staff tips</b><span>this week</span></span>
            <span className="feed-amt">{money(wk.now.tips)}</span>
          </li>
        </ul>
      </section>

      <section className="block">
        <div className="row"><h2>Where we parked</h2><Link to="/history/sales" className="more">See all <ChevronRight size={14} /></Link></div>
        <ul className="feed flat">
          {feed.map((d) => {
            const loc = locationById.get(d.location_id!)!
            const Icon = ICON[loc.type] ?? MapPin
            return (
              <li key={d.date} className="feed-row" onClick={() => navigate('/spots')}>
                <span className="feed-ico"><Icon size={18} /></span>
                <span className="feed-main">
                  <b>{loc.name.replace(/ \(.*\)/, '').split(',')[0]}</b>
                  <span>{weekday(d.date)} {shortDate(d.date)} · {d.orders} orders · {d.condition}, {d.temp_f}°</span>
                </span>
                <span className="feed-amt">{money(d.gross_sales ?? 0)}</span>
              </li>
            )
          })}
        </ul>
      </section>
    </div>
  )
}

function Chg({ v }: { v: number | null }) {
  if (v === null) return <span className="chg flat">no comparison</span>
  return (
    <>
      <span className={`chg ${v >= 0 ? 'up' : 'down'}`}>{v >= 0 ? '▲' : '▼'} {Math.abs(Math.round(v * 100))}%</span>
      <span className="chg-vs">vs last week</span>
    </>
  )
}

