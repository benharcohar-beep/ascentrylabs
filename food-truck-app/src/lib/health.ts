// One overall rating for the top of Home, built from three checks an owner
// can see and argue with. Each check scores -1, 0 or +1; the sum sets the
// badge. Nothing here is a model: change a threshold and the rating moves.
import { data, daysBetween, pct, pctChange, rangeWindow, totals } from './data'

export type Check = { label: string; detail: string; score: -1 | 0 | 1 }
export type Health = { rating: 'Good' | 'Steady' | 'Needs attention'; tone: 'good' | 'info' | 'warn'; summary: string; checks: Check[] }

export function health(): Health {
  const checks: Check[] = []

  // 1. Momentum: this week against last week.
  const w = rangeWindow('1W')
  const now = totals(daysBetween(w.from, w.to))
  const prev = totals(daysBetween(w.prevFrom, w.prevTo))
  const ch = pctChange(now.gross, prev.gross)
  if (ch === null) checks.push({ label: 'Sales trend', detail: 'Not enough history yet.', score: 0 })
  else if (ch >= 0.05) checks.push({ label: 'Sales trend', detail: `Up ${pct(ch, false)} on last week.`, score: 1 })
  else if (ch <= -0.1) checks.push({ label: 'Sales trend', detail: `Down ${pct(Math.abs(ch), false)} on last week.`, score: -1 })
  else checks.push({ label: 'Sales trend', detail: `About level with last week (${pct(ch)}).`, score: 0 })

  // 2. What you keep: sales minus food, staff and fees over the last 4 weeks.
  const m = { from: addWeeks(w.to, -4), to: w.to }
  const ds = daysBetween(m.from, m.to).filter((d) => d.trading)
  const gross = ds.reduce((a, d) => a + (d.gross_sales ?? 0), 0)
  const kept = ds.reduce((a, d) => a + (d.contribution ?? 0), 0)
  const keep = gross ? kept / gross : 0
  if (!gross) checks.push({ label: 'What you keep', detail: 'No sales in the last 4 weeks.', score: -1 })
  else if (keep >= 0.25) checks.push({ label: 'What you keep', detail: `${pct(keep, false)} of sales left after food, staff and fees.`, score: 1 })
  else if (keep >= 0.12) checks.push({ label: 'What you keep', detail: `${pct(keep, false)} of sales left after food, staff and fees. Healthy is 25% or more.`, score: 0 })
  else checks.push({ label: 'What you keep', detail: `Only ${pct(keep, false)} of sales left after food, staff and fees.`, score: -1 })

  // 3. Pricing against the market.
  const priced = data.benchmarks.filter((b) => b.hero_price !== null && b.n_trucks >= 3)
  const under = priced.filter((b) => (b.hero_vs_median ?? 0) <= -0.1).length
  if (under === 0) checks.push({ label: 'Pricing', detail: 'No item is more than 10% under the market middle.', score: 1 })
  else if (under <= 2) checks.push({ label: 'Pricing', detail: `${under} item${under > 1 ? 's' : ''} more than 10% under the market middle.`, score: 0 })
  else checks.push({ label: 'Pricing', detail: `${under} items more than 10% under the market middle.`, score: -1 })

  const total = checks.reduce((a, c) => a + c.score, 0)
  const weak = checks.filter((c) => c.score < 0)
  if (total >= 2) return { rating: 'Good', tone: 'good', summary: 'Sales, margin and pricing all look healthy.', checks }
  if (total <= -1 || weak.length >= 2)
    return { rating: 'Needs attention', tone: 'warn', summary: `${weak.map((c) => c.label.toLowerCase()).join(' and ')} need${weak.length === 1 ? 's' : ''} a look.`, checks }
  return { rating: 'Steady', tone: 'info', summary: weak.length ? `Fine overall, but ${weak[0].label.toLowerCase()} needs a look.` : 'Nothing urgent. One or two things could be better.', checks }
}

function addWeeks(iso: string, n: number): string {
  const d = new Date(iso + 'T00:00:00Z')
  d.setUTCDate(d.getUTCDate() + n * 7 + 1)
  return d.toISOString().slice(0, 10)
}
