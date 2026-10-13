import { useState } from 'react'
import { Card } from '../components/ui'
import { data, money, rivalById } from '../lib/data'

export default function Market() {
  const rows = data.benchmarks
    .filter((b) => b.hero_price !== null && b.n_trucks >= 3)
    .sort((a, b) => (a.hero_vs_median ?? 0) - (b.hero_vs_median ?? 0))
  const [open, setOpen] = useState<string | null>(null)

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
      </section>

      <Card className="rows">
        <div className="price-head">
          <span>Item</span><span>You</span><span>Market avg</span><span>Diff</span>
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
                <span className="price-name">{b.item_label}</span>
                <span className="price-you">{money(you, { cents: true })}</span>
                <span className="price-avg">{money(a, { cents: true })}</span>
                <span className={`price-diff ${gap < -0.03 ? 'down' : gap > 0.03 ? 'up' : 'flat'}`}>{gap < -0.03 ? '▼' : gap > 0.03 ? '▲' : ''} {Math.abs(Math.round(gap * 100))}%</span>
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
