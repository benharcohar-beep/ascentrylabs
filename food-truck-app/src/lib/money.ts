// The accountant's view: a plain statement for any period.
// Sales less food, staff and fees is profit from trading; less the fixed
// bills (pro-rated by the day) is what is actually the owner's.
import { TODAY, addDays, data, daysBetween, rangeWindow, type RangeKey } from './data'

export type Statement = {
  from: string; to: string; days: number; tradingDays: number
  truckSales: number; catering: number; sales: number
  food: number; staff: number; fees: number; tradingProfit: number
  fixed: number; fixedLines: { name: string; amount: number }[]
  profit: number
  tax: number; tips: number
}

function daysInMonth(ym: string): number {
  const y = Number(ym.slice(0, 4)), m = Number(ym.slice(5, 7))
  return new Date(Date.UTC(y, m, 0)).getUTCDate()
}

export function statement(from: string, to: string): Statement {
  const ds = daysBetween(from, to)
  const s: Statement = { from, to, days: ds.length, tradingDays: 0, truckSales: 0, catering: 0, sales: 0, food: 0, staff: 0, fees: 0,
    tradingProfit: 0, fixed: 0, fixedLines: [], profit: 0, tax: 0, tips: 0 }
  for (const d of ds) {
    if (!d.trading) continue
    s.tradingDays += 1
    s.truckSales += d.gross_sales ?? 0
    s.food += d.cogs ?? 0
    s.staff += d.labour ?? 0
    s.fees += (d.processing_fees ?? 0) + (d.location_fee ?? 0)
    s.tax += d.tax_collected ?? 0
    s.tips += d.tips ?? 0
  }
  for (const c of data.catering) {
    if (c.date < from || c.date > to) continue
    s.catering += c.revenue
    s.food += c.food_cost
    s.staff += c.staff_cost
  }
  // Fixed bills: each day carries its month's bills divided by the days in that month.
  const byName = new Map<string, number>()
  for (const d of ds) {
    const ym = d.date.slice(0, 7)
    const dim = daysInMonth(ym)
    for (const f of data.fixedCosts) if (f.month === ym) byName.set(f.cost, (byName.get(f.cost) ?? 0) + f.amount / dim)
  }
  s.fixedLines = [...byName.entries()].map(([name, amount]) => ({ name, amount })).sort((a, b) => b.amount - a.amount)
  s.fixed = s.fixedLines.reduce((a, l) => a + l.amount, 0)
  s.sales = s.truckSales + s.catering
  s.tradingProfit = s.sales - s.food - s.staff - s.fees
  s.profit = s.tradingProfit - s.fixed
  return s
}

export function statementFor(range: RangeKey, end = TODAY): { now: Statement; prev: Statement } {
  const w = rangeWindow(range, end)
  return { now: statement(w.from, w.to), prev: statement(w.prevFrom, w.prevTo) }
}

/** Calendar months in the data, newest first, from the Monthly_PnL tab. */
export function months() {
  return [...data.monthly].reverse()
}

export const weekStart = (end = TODAY) => addDays(end, -6)
