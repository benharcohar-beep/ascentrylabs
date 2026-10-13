import { useState } from 'react'
import { Card } from '../components/ui'
import { data, money, pct, rivalById } from '../lib/data'

export default function Market() {
  const rows = data.benchmarks
    .filter((b) => b.hero_price !== null && b.n_trucks >= 3)
    .sort((a, b) => (a.hero_vs_median ?? 0) - (b.hero_vs_median ?? 0))
  const [open, setOpen] = useState<string | null>(null)
  const trucks = new Set(data.marketPrices.map((p) => p.truckId)).size
  const under = rows.filter((r) => (r.hero_vs_median ?? 0) <= -0.1).length

  // Market average = the plain mean of the other trucks' prices for the item.
  const avg = (item: string) => {
    const ps = data.marketPrices.filter((p) => p.item === item).map((p) => p.price)
    return ps.length ? ps.reduce((a, b) => a + b, 0) / ps.length : 0
  }

  return (
    <>
      <section className="block-hero coral page">
        <header className="top">
          <h1>Market</h1>
        </header>
        <div className="label">Your price against the average of {trucks} other Milwaukee trucks</div>
        <div className="big">{under} <small>items well under</small></div>
      </section>

      <Card className="rows">
        <div className="price-head">
          <span>Item</span><span>You</span><span>Market avg</span>
        </div>
        {rows.map((b) => {
          const you = b.hero_price!
          const a = avg(b.standard_item)
          const gap = a ? you / a - 1 : 0
          const isOpen = open === b.standard_item
          const prices = data.marketPrices.filter((p) => p.item === b.standard_item).sort((x, y) => x.price - y.price)
          return (
            <div key={b.standard_item} className={`price-row ${isOpen ? 'open' : ''}`} onClick={() => setOpen(isOpen ? null : b.standard_item)}>
              <div className="price-main">
                <span className="price-name">{b.item_label}<em className={gap < -0.03 ? 'warn' : gap > 0.03 ? 'info' : 'good'}>{gap < -0.03 ? `${pct(Math.abs(gap), false)} cheaper` : gap > 0.03 ? `${pct(gap, false)} dearer` : 'about the same'}</em></span>
                <span className="price-you">{money(you, { cents: true })}</span>
                <span className="price-avg">{money(a, { cents: true })}</span>
              </div>
              {isOpen && (
                <ul className="rivals">
                  {prices.map((p) => (
                    <li key={p.truckId + p.seen}>
                      <span>{rivalById.get(p.truckId)?.name}</span>
                      <span className="muted">{rivalById.get(p.truckId)?.neighbourhood}</span>
                      <span className="num">{money(p.price, { cents: true })}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )
        })}
      </Card>
    </>
  )
}
