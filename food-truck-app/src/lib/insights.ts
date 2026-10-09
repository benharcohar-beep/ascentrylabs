// Rule-based insights. No model, no API: every card is a plain calculation
// over the data, so the owner can check each claim against the numbers.
import {
  TODAY, addDays, daysBetween, data, itemTotals, locationById, money, pct, pctChange, rangeWindow, spotStats, totals,
  weekday,
} from './data'

export type Insight = {
  id: string
  tone: 'good' | 'warn' | 'info'
  title: string
  body: string
  evidence: string
  action?: string
}

export function weeklyInsights(): Insight[] {
  const out: Insight[] = []
  const w = rangeWindow('1W')
  const now = totals(daysBetween(w.from, w.to))
  const prev = totals(daysBetween(w.prevFrom, w.prevTo))

  // 1. Week on week
  const ch = pctChange(now.gross, prev.gross)
  if (ch !== null) {
    const best = daysBetween(w.from, w.to).filter((d) => d.trading).sort((a, b) => (b.gross_sales ?? 0) - (a.gross_sales ?? 0))[0]
    out.push({
      id: 'wow', tone: ch >= 0 ? 'good' : 'warn',
      title: `Sales ${ch >= 0 ? 'up' : 'down'} ${pct(Math.abs(ch), false)} on last week`,
      body: best
        ? `${money(now.gross)} this week against ${money(prev.gross)} last week. Best day was ${weekday(best.date)} at ${locationById.get(best.location_id!)?.name} (${money(best.gross_sales ?? 0)}).`
        : `${money(now.gross)} this week against ${money(prev.gross)} last week.`,
      evidence: `${now.tradingDays} trading days vs ${prev.tradingDays}; ${now.orders} orders vs ${prev.orders}.`,
    })
  }

  // 2. Fees eating a spot (last 12 months, so winter venues count)
  const q = rangeWindow('3M')
  const yr = rangeWindow('1Y')
  const spots = spotStats(yr.from, yr.to).filter((s) => s.days >= 3)
  const regular = spots.filter((s) => s.loc.type !== 'festival' && s.loc.type !== 'market')
  const noFee = regular.filter((s) => s.loc.pctFee === 0 && s.loc.flatFee === 0).sort((a, b) => b.netPerHour - a.netPerHour)[0]
  const feeHeavy = regular
    .filter((s) => s.fees / s.gross > 0.15 && noFee && s.netPerHour < noFee.netPerHour && s.grossPerHour > noFee.grossPerHour)
    .sort((a, b) => b.grossPerHour - a.grossPerHour)[0]
  if (feeHeavy && noFee) {
    out.push({
      id: 'fees', tone: 'warn',
      title: `${feeHeavy.loc.name} looks busy but earns less than ${noFee.loc.name}`,
      body: `It takes ${money(feeHeavy.grossPerHour)} an hour at the till, more than any no-fee spot. After the ${pct(feeHeavy.loc.pctFee, false)} cut and ${money(feeHeavy.loc.flatFee)} pitch fee you keep ${money(feeHeavy.netPerHour)} an hour. ${noFee.loc.name} has no fee and nets ${money(noFee.netPerHour)}.`,
      evidence: `Last 12 months: ${feeHeavy.days} days there, ${money(feeHeavy.fees)} in fees on ${money(feeHeavy.gross)} of sales.`,
      action: 'Worth asking for a lower cut, or trading there only on the biggest game nights.',
    })
  }

  // 3. Best regular slot by net per hour
  const bestNet = regular.filter((s) => s.days >= 8)[0]
  if (bestNet) {
    out.push({
      id: 'best-slot', tone: 'good',
      title: `${bestNet.loc.name} is your best regular slot`,
      body: `${money(bestNet.netPerHour)} an hour after fees over the last 12 months, from ${bestNet.days} visits.`,
      evidence: `Ranked on net sales per trading hour; festivals, markets and spots with fewer than 8 visits excluded.`,
      action: 'If there is a free weekday, this is where to put it.',
    })
  }

  // 4. Underpriced items vs market
  const under = data.benchmarks
    .filter((b) => b.hero_vs_median !== null && b.hero_vs_median <= -0.08 && b.n_trucks >= 4)
    .sort((a, b) => (a.hero_vs_median ?? 0) - (b.hero_vs_median ?? 0))
  if (under.length) {
    const top = under[0]
    const items = itemTotals(q.from, q.to)
    const sold = items.filter((i) => i.item.standardItem === top.standard_item).reduce((a, i) => a + i.qty, 0)
    const gap = (top.median - (top.hero_price ?? 0))
    out.push({
      id: 'price', tone: 'info',
      title: `Your ${top.item_label.toLowerCase().replace(/,.*$/, '')} is ${pct(Math.abs(top.hero_vs_median ?? 0), false)} under the Milwaukee median`,
      body: `You charge ${money(top.hero_price ?? 0, { cents: true })}; ${top.n_trucks} other Mexican trucks charge between ${money(top.min, { cents: true })} and ${money(top.max, { cents: true })}, median ${money(top.median, { cents: true })}.`,
      evidence: `You sold ${sold.toLocaleString()} in the last 3 months. Each $0.25 would have been about ${money(sold * 0.25)}.`,
      action: `A move to ${money(Math.floor(top.median * 4) / 4, { cents: true })} keeps you at or below the median (worth about ${money(sold * gap)} a quarter).`,
    })
  }

  // 5. Thin-margin item
  const items = itemTotals(q.from, q.to).filter((i) => i.qty > 50 && i.item.category !== 'Drinks')
  const thin = items.filter((i) => i.margin < 0.6).sort((a, b) => a.margin - b.margin)[0]
  const fat = items.filter((i) => i.item.category === thin?.item.category && i.item.id !== thin?.item.id).sort((a, b) => b.margin - a.margin)[0]
  if (thin) {
    out.push({
      id: 'margin', tone: 'warn',
      title: `${thin.item.name} keeps only ${pct(thin.margin, false)} of its price`,
      body: `Ingredients cost ${money(thin.item.cost, { cents: true })} of a ${money(thin.item.price, { cents: true })} sale.${fat ? ` ${fat.item.name} keeps ${pct(fat.margin, false)}.` : ''}`,
      evidence: `Based on your recipe costs and ${thin.qty.toLocaleString()} sold in the last 3 months.`,
      action: 'Check the portion on the dearest ingredient, or move the price up with the market gap above.',
    })
  }

  // 6. Rain
  const ds = daysBetween(yr.from, yr.to).filter((d) => d.trading && d.date >= '2026-05-01' && d.date <= '2026-09-30')
  const rain = ds.filter((d) => d.rain), dry = ds.filter((d) => !d.rain)
  if (rain.length >= 5 && dry.length >= 5) {
    const r = totals(rain).gross / rain.length, dr = totals(dry).gross / dry.length
    out.push({
      id: 'rain', tone: 'info',
      title: `A wet day costs you about ${pct(1 - r / dr, false)} of sales`,
      body: `Summer rain days averaged ${money(r)} against ${money(dr)} on dry days.`,
      evidence: `${rain.length} rain days and ${dry.length} dry days, May to September.`,
      action: 'Check the forecast before prepping for a street or market day; breweries hold up better.',
    })
  }

  // 7. Tips by venue
  const byType = new Map<string, { tips: number; gross: number }>()
  for (const s of spotStats(yr.from, yr.to)) {
    const t = byType.get(s.loc.type) ?? { tips: 0, gross: 0 }
    t.tips += s.tips; t.gross += s.gross
    byType.set(s.loc.type, t)
  }
  const rates = [...byType.entries()].map(([k, v]) => ({ type: k, rate: v.tips / v.gross })).sort((a, b) => b.rate - a.rate)
  if (rates.length >= 2) {
    const hi = rates[0], lo = rates[rates.length - 1]
    out.push({
      id: 'tips', tone: 'info',
      title: `Tips run ${pct(hi.rate, false)} at ${typeLabel(hi.type)} and ${pct(lo.rate, false)} at ${typeLabel(lo.type)}`,
      body: `Over the year that is ${money(totals(daysBetween(yr.from, yr.to)).tips)} in tips, most of it from card and tap.`,
      evidence: 'Tips as a share of sales by venue type, last 12 months.',
    })
  }

  return out
}

export function typeLabel(t: string): string {
  return { brewery: 'breweries', street: 'street pitches', food_park: 'the food park', event: 'games', festival: 'festivals',
    office: 'office lunches', hospital: 'the hospital', market: 'farmers markets', campus: 'campus' }[t] ?? t
}

export const lastUpdated = addDays(TODAY, 0)
