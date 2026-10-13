// Builds the compact fact pack sent with every question, and calls /api/ask.
// Everything here is already on screen somewhere; this just gathers it.
import { TODAY, data, itemTotals, money, pct, rangeWindow, spotStats, totals, daysBetween } from './data'
import { health } from './health'
import { weeklyInsights } from './insights'
import { statementFor, months } from './money'
import { stockAlerts } from './stock'

export type ChatMsg = { role: 'user' | 'assistant'; content: string }

export function factPack() {
  const h = health()
  const wk = statementFor('1W'), mo = statementFor('1M'), yr = statementFor('1Y')
  const q = rangeWindow('3M'), y = rangeWindow('1Y')
  const r2 = (n: number) => Math.round(n * 100) / 100
  const stmt = (s: typeof wk.now) => ({
    from: s.from, to: s.to, tradingDays: s.tradingDays, sales: r2(s.sales), truckSales: r2(s.truckSales), catering: r2(s.catering),
    food: r2(s.food), staff: r2(s.staff), fees: r2(s.fees), profitBeforeFixedBills: r2(s.tradingProfit), fixedBills: r2(s.fixed),
    profit: r2(s.profit), salesTaxCollected: r2(s.tax), tips: r2(s.tips),
  })
  const week = totals(daysBetween(rangeWindow('1W').from, TODAY))
  return {
    today: TODAY,
    truck: data.truck,
    rating: { rating: h.rating, summary: h.summary, checks: h.checks.map((c) => ({ label: c.label, detail: c.detail })) },
    thisWeek: { ...stmt(wk.now), orders: week.orders, avgOrder: week.orders ? r2(week.gross / week.orders) : 0 },
    lastWeek: stmt(wk.prev),
    last30Days: stmt(mo.now), previous30Days: stmt(mo.prev),
    last12Months: stmt(yr.now),
    byMonth: months().map((m) => ({ month: m.month, tradingDays: m.trading_days, sales: m.total_sales, profit: m.operating_profit })),
    last7Days: daysBetween(rangeWindow('1W').from, TODAY).map((d) => ({
      date: d.date, trading: d.trading, spot: d.location_id ? data.locations.find((l) => l.id === d.location_id)?.name : null,
      sales: d.gross_sales ?? 0, orders: d.orders ?? 0, weather: `${d.condition}, ${d.temp_f}F`,
    })),
    spotsLast12Months: spotStats(y.from, y.to).map((s) => ({
      spot: s.loc.name, type: s.loc.type, days: s.days, sales: r2(s.gross), fees: r2(s.fees), perHourAfterFees: r2(s.netPerHour),
      venueFee: s.loc.pctFee ? `${pct(s.loc.pctFee, false)} of sales` + (s.loc.flatFee ? ` plus ${money(s.loc.flatFee)} a day` : '') : s.loc.flatFee ? `${money(s.loc.flatFee)} a day` : 'none',
    })),
    menuLast3Months: itemTotals(q.from, q.to).map((i) => ({
      item: i.item.name, price: i.item.price, ingredientCost: i.item.cost, sold: i.qty, sales: r2(i.revenue), margin: pct(i.margin, false),
    })),
    marketPrices: data.benchmarks.filter((b) => b.hero_price !== null).map((b) => ({
      item: b.item_label, you: b.hero_price, otherTrucksMin: b.min, otherTrucksTypical: b.median, otherTrucksMax: b.max, trucksCompared: b.n_trucks,
    })),
    insights: weeklyInsights().map((t) => ({ title: t.title, detail: t.body, action: t.action ?? null, evidence: t.evidence })),
    stockAlerts: stockAlerts().map((s) => ({ item: s.item.name, soldThisWeek: s.unitsNow, usualWeekly: s.unitsBase, ingredient: s.ingredient, surplusPerWeek: s.surplusLabel, wastePerWeek: r2(s.wastePerWeek), prepLine: s.prepLine, dealLine: s.dealLine })),
    note: 'Fixed bills are spread evenly across the days of each month. Sales tax is 7.9% and belongs to the state. Tips go to staff.',
  }
}

const PASS_KEY = 'eventini-ai-passcode'
export function getPasscode(): string { try { return localStorage.getItem(PASS_KEY) ?? '' } catch { return '' } }
export function setPasscode(v: string) { try { localStorage.setItem(PASS_KEY, v) } catch { /* private mode */ } }

export async function ask(question: string, history: ChatMsg[]): Promise<{ answer?: string; error?: string; needPasscode?: boolean }> {
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}api/ask`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-passcode': getPasscode() },
      body: JSON.stringify({ question, history, facts: factPack() }),
    })
    const j = await res.json().catch(() => ({}))
    if (res.status === 401) return { error: j.error ?? 'Wrong passcode.', needPasscode: true }
    if (!res.ok) return { error: j.error ?? `Server error ${res.status}.` }
    return { answer: j.answer }
  } catch {
    return { error: 'Could not reach the server.' }
  }
}
