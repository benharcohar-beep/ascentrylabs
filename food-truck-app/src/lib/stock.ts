// Level 1 stock rule: slow sellers found from sales alone, no stock input.
// Compares each item's rate per 100 orders this week with the prior 8 weeks,
// so a quiet week or a different venue does not trigger it on its own.
import { TODAY, addDays, data, daysBetween, menuById, money, pct, totals, type MenuItem } from './data'

export type StockAlert = {
  id: string
  item: MenuItem
  unitsNow: number
  unitsBase: number        // typical weekly units over the baseline
  drop: number             // 0.75 = selling 75% less than usual, per 100 orders
  ingredient: string
  shelfLifeDays: number
  prepCut: number          // suggested cut to prep, as a share
  surplusQty: number       // ingredient units a week going unsold
  surplusLabel: string
  wastePerWeek: number     // $ of ingredients a week at risk
  prepLine: string
  dealLine: string
  freeLine: string
}

const UNIT_LABEL: Record<string, (q: number) => string> = {
  oz: (q) => (q >= 16 ? `${(q / 16).toFixed(q >= 80 ? 0 : 1)} lb` : `${Math.round(q)} oz`),
  each: (q) => `${Math.round(q)}`,
  portion: (q) => `${Math.round(q)} portions`,
  cup: (q) => `${Math.round(q)} cups`,
}

const INGREDIENT_NAME: Record<string, string> = {
  veg_mix: 'roasted veg', churro: 'churros', pork_pastor: 'al pastor pork', beef_asada: 'carne asada', pork_carnitas: 'carnitas',
  chicken: 'chicken', beef_birria: 'birria beef', cheese: 'cheese', corn_cob: 'corn', agua_base: 'agua fresca base',
  crema_guac: 'guacamole', chips: 'chips', bread_torta: 'torta rolls', soda: 'soda', water_btl: 'water',
}

function units(itemId: string, from: string, to: string): number {
  let n = 0
  for (const r of data.itemDays) if (r.item_id === itemId && r.date >= from && r.date <= to) n += r.qty
  return n
}

export function stockAlerts(): StockAlert[] {
  const to = TODAY
  const from = addDays(to, -6)
  const baseTo = addDays(from, -1)
  const baseFrom = addDays(baseTo, -55) // 8 weeks
  const ordersNow = totals(daysBetween(from, to)).orders
  const ordersBase = totals(daysBetween(baseFrom, baseTo)).orders
  if (!ordersNow || !ordersBase) return []

  const out: StockAlert[] = []
  for (const item of data.menu) {
    if (item.category === 'Drinks') continue
    const now = units(item.id, from, to)
    const base = units(item.id, baseFrom, baseTo)
    const rateNow = (now / ordersNow) * 100
    const rateBase = (base / ordersBase) * 100
    if (rateBase < 2) continue // never sold much; not a stock problem
    const drop = 1 - rateNow / rateBase
    if (drop < 0.4) continue

    const weeklyBase = base / 8
    const qty = item.keyIngredientQty
    const surplusQty = Math.max(0, (weeklyBase - now) * qty)
    const label = UNIT_LABEL[item.keyIngredientUnit] ?? ((q: number) => `${Math.round(q)}`)
    const ingredient = INGREDIENT_NAME[item.keyIngredient] ?? item.keyIngredient
    const prepCut = Math.min(0.9, Math.round(drop * 10) / 10)
    const wastePerWeek = (weeklyBase - now) * item.cost

    // A "2 for" price that still covers ingredients with room to spare.
    const floor = item.cost * 2 * 1.6
    let deal = Math.round((item.price * 2 * 0.7) * 2) / 2
    if (deal < floor) deal = Math.ceil(floor * 2) / 2
    const dealLine = `Run ${item.name.toLowerCase()} 2 for ${money(deal, { cents: true })} on your next busy day (still ${pct(1 - (item.cost * 2) / deal, false)} margin).`
    const freeLine = `Or add one free with any plate: costs you ${money(item.cost, { cents: true })} each, against throwing it away.`
    const prepLine = `Prep about ${pct(prepCut, false)} less ${ingredient}: roughly ${label(weeklyBase * qty)} a week was the old level, ${label(Math.max(0, weeklyBase * qty * (1 - prepCut)))} fits what sells now.`

    out.push({
      id: `stock-${item.id}`, item, unitsNow: now, unitsBase: Math.round(weeklyBase), drop, ingredient,
      shelfLifeDays: item.shelfLifeDays, prepCut, surplusQty, surplusLabel: label(surplusQty), wastePerWeek, prepLine, dealLine, freeLine,
    })
  }
  return out.sort((a, b) => b.wastePerWeek - a.wastePerWeek)
}

export const menuItem = (id: string) => menuById.get(id)
