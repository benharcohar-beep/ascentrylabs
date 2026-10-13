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

export type Cash = {
  asOf: string
  balance: number        // what is in the account
  taxOwed: number        // sales tax collected but not yet paid over
  available: number      // balance less tax owed
  opening: number
  lastRemittance: { date: string; amount: number } | null
  nextRemittance: { date: string; amount: number } | null
  trend: number[]        // balance at the end of each of the last 8 weeks
}

/** Cash on hand on a date: opening balance rolled forward from every day since the start. */
export function cashAt(asOf = TODAY): Cash {
  const opening = data.meta.opening_cash ?? 0
  const remitDay = data.meta.tax_remit_day ?? 20
  const months = new Set<string>()
  for (const d of data.days) months.add(d.date.slice(0, 7))
  const firstMonth = [...months].sort()[0]

  // Fixed bills by day, as in statement()
  const fixedByMonth = new Map<string, number>()
  for (const f of data.fixedCosts) fixedByMonth.set(f.month, (fixedByMonth.get(f.month) ?? 0) + f.amount)
  const dim = (ym: string) => daysInMonth(ym)

  // Sales tax collected per month, remitted on remitDay of the following month
  const taxByMonth = new Map<string, number>()
  for (const d of data.days) if (d.trading) taxByMonth.set(d.date.slice(0, 7), (taxByMonth.get(d.date.slice(0, 7)) ?? 0) + (d.tax_collected ?? 0))
  const remitDate = (ym: string) => {
    const y = Number(ym.slice(0, 4)), m = Number(ym.slice(5, 7))
    const ny = m === 12 ? y + 1 : y, nm = m === 12 ? 1 : m + 1
    return `${ny}-${String(nm).padStart(2, '0')}-${String(remitDay).padStart(2, '0')}`
  }
  const cateringByDate = new Map<string, { rev: number; cost: number }>()
  for (const c of data.catering) {
    const x = cateringByDate.get(c.date) ?? { rev: 0, cost: 0 }
    x.rev += c.revenue; x.cost += c.food_cost + c.staff_cost
    cateringByDate.set(c.date, x)
  }

  let bal = opening
  let taxOwed = 0
  let lastRemit: Cash['lastRemittance'] = null
  const weekly: number[] = []
  const weekEnds = new Set<string>()
  for (let i = 7; i >= 0; i--) weekEnds.add(addDays(asOf, -7 * i))

  for (const d of data.days) {
    if (d.date > asOf) break
    const ym = d.date.slice(0, 7)
    if (d.trading) {
      bal += (d.gross_sales ?? 0) + (d.tax_collected ?? 0) - (d.cogs ?? 0) - (d.labour ?? 0) - (d.processing_fees ?? 0) - (d.location_fee ?? 0)
      taxOwed += d.tax_collected ?? 0
    }
    const c = cateringByDate.get(d.date)
    if (c) bal += c.rev - c.cost
    bal -= (fixedByMonth.get(ym) ?? 0) / dim(ym)
    // remit last month's tax on remitDay (skip the first month, nothing owed yet)
    if (Number(d.date.slice(8)) === remitDay) {
      const prev = ym === firstMonth ? null : prevMonth(ym)
      const owed = prev ? taxByMonth.get(prev) ?? 0 : 0
      if (owed > 0) { bal -= owed; taxOwed -= owed; lastRemit = { date: d.date, amount: owed } }
    }
    if (weekEnds.has(d.date)) weekly.push(bal)
  }
  const curMonth = asOf.slice(0, 7)
  const nextDate = remitDate(prevMonth(curMonth)) > asOf ? remitDate(prevMonth(curMonth)) : remitDate(curMonth)
  const nextAmt = nextDate === remitDate(prevMonth(curMonth)) ? taxByMonth.get(prevMonth(curMonth)) ?? 0 : taxByMonth.get(curMonth) ?? 0
  return { asOf, balance: bal, taxOwed: Math.max(0, taxOwed), available: bal - Math.max(0, taxOwed), opening,
    lastRemittance: lastRemit, nextRemittance: nextAmt > 0 ? { date: nextDate, amount: nextAmt } : null, trend: weekly }
}

function prevMonth(ym: string): string {
  const y = Number(ym.slice(0, 4)), m = Number(ym.slice(5, 7))
  return m === 1 ? `${y - 1}-12` : `${y}-${String(m - 1).padStart(2, '0')}`
}
