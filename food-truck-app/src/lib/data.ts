// Single entry point for the app's data. Today it reads the bundled fake
// JSON; when Eventini's POS feed is wired in, this is the one file to change.
import raw from '../data/data.json'

export type Day = {
  date: string
  trading: boolean
  location_id: string | null
  event: string | null
  temp_f: number
  rain: boolean
  condition: string
  hours?: number
  paid_staff?: number
  orders?: number
  gross_sales?: number
  tips?: number
  tax_collected?: number
  processing_fees?: number
  location_fee?: number
  cogs?: number
  labour?: number
  net_after_fees?: number
  contribution?: number
  gross_per_hour?: number
  net_per_hour?: number
  avg_order?: number
}
export type Location = {
  id: string; name: string; type: string; neighbourhood: string
  lat: number; lon: number; flatFee: number; pctFee: number
}
export type MenuItem = {
  id: string; name: string; category: string; standardItem: string; price: number; cost: number
  keyIngredient: string; keyIngredientQty: number; keyIngredientUnit: string; shelfLifeDays: number
}
export type Benchmark = {
  standard_item: string; item_label: string; n_trucks: number
  min: number; p25: number; median: number; p75: number; max: number
  hero_price: number | null; hero_vs_median: number | null
}
export type Hourly = { location_id: string; hour: number; orders: number; gross_sales: number; days: number }
export type ItemDay = { date: string; item_id: string; qty: number; revenue: number; cogs: number }
export type MarketPrice = { truckId: string; item: string; price: number; seen: string; source: string }
export type Rival = { id: string; name: string; concept: string; tier: string; neighbourhood: string }
export type Monthly = {
  month: string; trading_days: number; orders: number; truck_sales: number; catering_sales: number
  total_sales: number; tips_collected: number; cogs: number; labour: number; fees: number
  fixed_costs: number; operating_profit: number; food_cost_pct: number; labour_pct: number
}

type Data = {
  meta: { generated: string; start: string; end: string; fake: boolean; planted_stories: string[] }
  truck: { name: string; owner: string; concept: string; pos: string }
  locations: Location[]
  menu: MenuItem[]
  standardItems: { id: string; label: string }[]
  rivals: Rival[]
  marketPrices: MarketPrice[]
  benchmarks: Benchmark[]
  days: Day[]
  hourly: Hourly[]
  itemDays: ItemDay[]
  monthly: Monthly[]
}

export const data = raw as unknown as Data

export const locationById = new Map(data.locations.map((l) => [l.id, l]))
export const menuById = new Map(data.menu.map((m) => [m.id, m]))
export const rivalById = new Map(data.rivals.map((r) => [r.id, r]))

export function addDays(iso: string, n: number): string {
  const d = new Date(iso + 'T00:00:00Z')
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

// "Today" is the last Sunday in the dataset, so "this week" is a full Monday
// to Sunday week and every range ends on a clean boundary.
export const TODAY = (() => {
  let d = data.meta.end
  while (new Date(d + 'T00:00:00Z').getUTCDay() !== 0) d = addDays(d, -1)
  return d
})()

export type RangeKey = '1W' | '1M' | '3M' | '1Y'
export const RANGES: { key: RangeKey; days: number; label: string }[] = [
  { key: '1W', days: 7, label: 'week' },
  { key: '1M', days: 30, label: 'month' },
  { key: '3M', days: 91, label: '3 months' },
  { key: '1Y', days: 365, label: 'year' },
]

/** Days inside [from, to] inclusive, in date order. */
export function daysBetween(from: string, to: string): Day[] {
  return data.days.filter((d) => d.date >= from && d.date <= to)
}

export function rangeWindow(key: RangeKey, end = TODAY): { from: string; to: string; prevFrom: string; prevTo: string } {
  const n = RANGES.find((r) => r.key === key)!.days
  const from = addDays(end, -(n - 1))
  return { from, to: end, prevFrom: addDays(from, -n), prevTo: addDays(from, -1) }
}

export type Totals = { gross: number; orders: number; tips: number; net: number; tradingDays: number; hours: number }

export function totals(days: Day[]): Totals {
  const t: Totals = { gross: 0, orders: 0, tips: 0, net: 0, tradingDays: 0, hours: 0 }
  for (const d of days) {
    if (!d.trading) continue
    t.gross += d.gross_sales ?? 0
    t.orders += d.orders ?? 0
    t.tips += d.tips ?? 0
    t.net += d.net_after_fees ?? 0
    t.hours += d.hours ?? 0
    t.tradingDays += 1
  }
  return t
}

export function pctChange(now: number, before: number): number | null {
  if (!before) return null
  return now / before - 1
}

export type Metric = 'sales' | 'orders' | 'avg' | 'tips'
export const METRIC_LABEL: Record<Metric, string> = { sales: 'Sales', orders: 'Orders', avg: 'Average order', tips: 'Tips' }

export function metricOf(t: Totals, m: Metric): number {
  if (m === 'sales') return t.gross
  if (m === 'orders') return t.orders
  if (m === 'tips') return t.tips
  return t.orders ? t.gross / t.orders : 0
}

export function formatMetric(v: number, m: Metric): string {
  if (m === 'orders') return v.toLocaleString()
  if (m === 'avg') return money(v, { cents: true })
  return money(v)
}

/** Bars for the home chart: daily for 1W/1M, weekly for 3M, monthly for 1Y. */
export function buckets(key: RangeKey, from: string, to: string, metric: Metric = 'sales'): { label: string; value: number; sub?: string }[] {
  const days = daysBetween(from, to)
  if (key === '1W' || key === '1M') {
    return days.map((d) => ({
      label: key === '1W' ? weekday(d.date) : d.date.slice(8),
      value: metricOf(totals([d]), metric),
      sub: d.trading ? locationById.get(d.location_id!)?.name : 'Day off',
    }))
  }
  const out: { label: string; value: number; sub?: string }[] = []
  if (key === '3M') {
    for (let i = 0; i < days.length; i += 7) {
      const chunk = days.slice(i, i + 7)
      out.push({ label: shortDate(chunk[0].date), value: metricOf(totals(chunk), metric), sub: `w/c ${shortDate(chunk[0].date)}` })
    }
    return out
  }
  const byMonth = new Map<string, Day[]>()
  for (const d of days) {
    const k = d.date.slice(0, 7)
    byMonth.set(k, [...(byMonth.get(k) ?? []), d])
  }
  for (const [k, ds] of byMonth) out.push({ label: monthName(k), value: metricOf(totals(ds), metric), sub: monthName(k, true) })
  return out
}

/** The last n whole weeks of a metric, oldest first, for sparklines. */
export function weeklyHistory(metric: Metric, n = 8, end = TODAY): number[] {
  const out: number[] = []
  for (let i = n - 1; i >= 0; i--) {
    const to = addDays(end, -7 * i), from = addDays(to, -6)
    out.push(metricOf(totals(daysBetween(from, to)), metric))
  }
  return out
}

export function itemTotals(from: string, to: string) {
  const acc = new Map<string, { qty: number; revenue: number; cogs: number }>()
  for (const r of data.itemDays) {
    if (r.date < from || r.date > to) continue
    const a = acc.get(r.item_id) ?? { qty: 0, revenue: 0, cogs: 0 }
    a.qty += r.qty; a.revenue += r.revenue; a.cogs += r.cogs
    acc.set(r.item_id, a)
  }
  return [...acc.entries()]
    .map(([id, a]) => ({ item: menuById.get(id)!, ...a, margin: a.revenue ? 1 - a.cogs / a.revenue : 0 }))
    .sort((a, b) => b.revenue - a.revenue)
}

export type SpotStat = {
  loc: Location; days: number; hours: number; gross: number; net: number; fees: number; tips: number; orders: number
  grossPerHour: number; netPerHour: number
}

export function spotStats(from: string, to: string): SpotStat[] {
  const acc = new Map<string, SpotStat>()
  for (const d of daysBetween(from, to)) {
    if (!d.trading || !d.location_id) continue
    const loc = locationById.get(d.location_id)!
    const s = acc.get(loc.id) ?? { loc, days: 0, hours: 0, gross: 0, net: 0, fees: 0, tips: 0, orders: 0, grossPerHour: 0, netPerHour: 0 }
    s.days += 1; s.hours += d.hours ?? 0; s.gross += d.gross_sales ?? 0; s.net += d.net_after_fees ?? 0
    s.fees += (d.location_fee ?? 0) + (d.processing_fees ?? 0); s.tips += d.tips ?? 0; s.orders += d.orders ?? 0
    acc.set(loc.id, s)
  }
  return [...acc.values()]
    .map((s) => ({ ...s, grossPerHour: s.hours ? s.gross / s.hours : 0, netPerHour: s.hours ? s.net / s.hours : 0 }))
    .sort((a, b) => b.netPerHour - a.netPerHour)
}

export function hourlyFor(locationId: string) {
  return data.hourly.filter((h) => h.location_id === locationId).sort((a, b) => a.hour - b.hour)
}

// ---- formatting -----------------------------------------------------------

export function money(n: number, opts: { compact?: boolean; cents?: boolean } = {}): string {
  const { compact = false, cents = false } = opts
  if (compact && Math.abs(n) >= 10000) return `$${(n / 1000).toFixed(n >= 100000 ? 0 : 1)}k`
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: cents ? 2 : 0, maximumFractionDigits: cents ? 2 : 0 })
}
export function pct(n: number, signed = true): string {
  const v = Math.round(n * 100)
  return `${signed && v > 0 ? '+' : ''}${v}%`
}
export function weekday(iso: string): string {
  return ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][new Date(iso + 'T00:00:00Z').getUTCDay()]
}
export function shortDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00Z')
  return `${d.getUTCDate()} ${['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][d.getUTCMonth()]}`
}
export function monthName(ym: string, long = false): string {
  const m = Number(ym.slice(5, 7)) - 1
  const names = long
    ? ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    : ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
  return long ? `${names[m]} ${ym.slice(0, 4)}` : names[m]
}
export function hourLabel(h: number): string {
  if (h === 12) return '12pm'
  return h < 12 ? `${h}am` : `${h - 12}pm`
}
