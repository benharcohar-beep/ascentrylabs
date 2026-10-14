import { Link, useNavigate } from 'react-router-dom'
import { ChevronRight, Store, MapPin, Beer, Trophy, Briefcase, GraduationCap, Tent, Stethoscope, PartyPopper, Receipt, Landmark, HandCoins, Wallet, Sparkles } from 'lucide-react'
import { Brand } from '../components/Brand'
import { ThemeToggle } from '../components/ThemeToggle'
import { Amt } from '../components/ui'
import { TODAY, data, daysBetween, locationById, pctChange, rangeWindow, shortDate, weekday, totals } from '../lib/data'
import { health } from '../lib/health'
import { cashAt, statementFor } from '../lib/money'
import { useFirstLoad, useSyncedAgo } from '../lib/sync'
import { Skeleton } from '../components/states'

export const VENUE_ICON: Record<string, React.ComponentType<{ size?: number }>> = {
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
  const putAway = cash.taxOwed + billsMonth + wk.now.tips
  const ago = useSyncedAgo()
  const loading = useFirstLoad('home')

  return (
    <div className="screen">
      <header className="top">
        <div className="head-mid">
          <b>{data.truck.name}</b>
          <span className="eyebrow">Updated {ago}</span>
        </div>
        <div className="head-right"><ThemeToggle /><Brand /></div>
      </header>
      {loading ? <Skeleton rows={4} /> : <>

      <section className={`status ${h.tone}`} onClick={() => navigate('/money')} role="link">
        <span className="label">Business is</span>
        <span className="status-word">{h.rating}</span>
        <span className="status-sub">{h.summary}</span>
        <div className="status-actions">
          <button className="status-btn" onClick={(e) => { e.stopPropagation(); navigate('/money') }}><Wallet size={15} /> See money</button>
          <button className="status-btn" onClick={(e) => { e.stopPropagation(); navigate('/insights') }}><Sparkles size={15} /> Ask AI</button>
        </div>
      </section>

      <section className="hero" onClick={() => navigate('/money')} role="link">
        <div className="label">In the bank today</div>
        <div className="hero-num"><Amt v={cash.balance} animate /></div>
        <div className="hero-sub">
          <span className="hero-pill">Yours to spend <Amt v={cash.available} /></span>
          <span>after <Amt v={cash.taxOwed} cents={false} /> sales tax</span>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head"><h2>This week</h2><span className="panel-note">{weekDays} {weekDays === 1 ? 'day' : 'days'} worked · last week {prevDays}</span></div>
        <div className="swipe">
          <button className="swipe-card" onClick={() => navigate('/history/sales')}>
            <span className="label">Sales</span>
            <span className="card-num"><Amt v={wk.now.sales} cents={false} /></span>
            <Chg v={pctChange(wk.now.sales, wk.prev.sales)} />
          </button>
          <button className="swipe-card" onClick={() => navigate('/money')}>
            <span className="label">Profit</span>
            <span className="card-num"><Amt v={wk.now.profit} cents={false} /></span>
            <Chg v={pctChange(wk.now.profit, wk.prev.profit)} />
          </button>
          <button className="swipe-card" onClick={() => navigate('/history/orders')}>
            <span className="label">Orders</span>
            <span className="card-num">{week.orders.toLocaleString()}</span>
            <Chg v={pctChange(week.orders, prevWeek.orders)} />
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head"><h2>Put away <span className="tot">· <Amt v={putAway} cents={false} /></span></h2><Link to="/money" className="more">Money <ChevronRight size={14} /></Link></div>
        <ul className="feed plain">
          <li className="feed-row" onClick={() => navigate('/money')}>
            <span className="feed-ico tile-tax"><Receipt size={18} /></span>
            <span className="feed-main"><b>Sales tax</b><span>{cash.nextRemittance ? `due ${shortDate(cash.nextRemittance.date)}` : 'nothing due'}</span></span>
            <span className="feed-amt"><Amt v={cash.taxOwed} /></span>
          </li>
          <li className="feed-row" onClick={() => navigate('/money')}>
            <span className="feed-ico tile-bills"><Landmark size={18} /></span>
            <span className="feed-main"><b>Bills due this month</b><span>loan, insurance, kitchen</span></span>
            <span className="feed-amt"><Amt v={billsMonth} /></span>
          </li>
          <li className="feed-row" onClick={() => navigate('/history/tips')}>
            <span className="feed-ico tile-tips"><HandCoins size={18} /></span>
            <span className="feed-main"><b>Staff tips</b><span>this week</span></span>
            <span className="feed-amt"><Amt v={wk.now.tips} /></span>
          </li>
        </ul>
      </section>

      <section className="panel">
        <div className="panel-head"><h2>Where we parked <span className="tot">· {feed.length} days</span></h2><Link to="/history/sales" className="more">See all <ChevronRight size={14} /></Link></div>
        <ul className="feed plain">
          {feed.map((d) => {
            const loc = locationById.get(d.location_id!)!
            const Icon = VENUE_ICON[loc.type] ?? MapPin
            return (
              <li key={d.date} className="feed-row" onClick={() => navigate('/spots')}>
                <span className={`feed-ico tile-${loc.type}`}><Icon size={18} /></span>
                <span className="feed-main">
                  <b>{loc.name.replace(/ \(.*\)/, '').split(',')[0]}</b>
                  <span>{weekday(d.date)} {shortDate(d.date)} · {d.orders} orders · {d.condition}, {d.temp_f}°</span>
                </span>
                <span className="feed-amt pos"><Amt v={d.gross_sales ?? 0} /></span>
              </li>
            )
          })}
        </ul>
      </section>
      </>}
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
