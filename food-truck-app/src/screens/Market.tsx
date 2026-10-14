import { useState } from 'react'
import { Card } from '../components/ui'
import { Skeleton } from '../components/states'
import { useFirstLoad } from '../lib/sync'
import { data, money, rivalById } from '../lib/data'

export default function Market() {
  const rows = data.benchmarks
    .filter((b) => b.hero_price !== null && b.n_trucks >= 3)
    .sort((a, b) => (a.hero_vs_median ?? 0) - (b.hero_vs_median ?? 0))
  const [open, setOpen] = useState<string | null>(null)
  const loading = useFirstLoad('market')
  // Items other trucks sell that this truck does not. Needs at least 2 trucks so it is a real gap, not one truck's quirk.
  const missing = data.benchmarks.filter((b) => b.hero_price === null && b.n_trucks >= 2).sort((a, b) => b.n_trucks - a.n_trucks)

  // Market average = the plain mean of the other trucks' prices for the item.
  const avg = (item: string) => {
    const ps = data.marketPrices.filter((p) => p.item === item).map((p) => p.price)
    return ps.length ? ps.reduce((a, b) => a + b, 0) / ps.length : 0
  }

  return (
    <div className="screen">
      <header className="top">
        <h1>Market</h1>
        <span />
      </header>

      {loading ? <Skeleton hero={false} rows={8} /> : <>
      <Card className="rows">
        <div className="price-head">
          <span>Item</span><span>You</span><span>Market</span><span>Diff</span>
        </div>
        {rows.map((b) => {
          const you = b.hero_price!
          const a = avg(b.standard_item)
          const gap = a ? you / a - 1 : 0
          const gp = Math.round(gap * 100) // direction follows the rounded figure, so a shown 0% is always grey
          const dir = gp > 0 ? 'up' : gp < 0 ? 'down' : 'flat'
          const isOpen = open === b.standard_item
          const prices = data.marketPrices.filter((p) => p.item === b.standard_item).sort((x, y) => x.price - y.price)
          return (
            <div key={b.standard_item} className={`price-row ${isOpen ? 'open' : ''}`} onClick={() => setOpen(isOpen ? null : b.standard_item)}>
              <div className="price-main">
                <span className="price-name">{b.item_label}</span>
                <span className="price-you">{money(you, { cents: true })}</span>
                <span className="price-avg">{money(a, { cents: true })}</span>
                <span className={`price-diff ${dir}`}>{dir === 'down' ? '▼ ' : dir === 'up' ? '▲ ' : ''}{Math.abs(gp)}%</span>
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

      <section className="block">
        <div className="row"><h2>Not on your menu</h2></div>
        <p className="sub" style={{ margin: '0 0 4px' }}>What other trucks sell that you don't. Tap one to see who sells it.</p>
        <Card className="rows">
          <div className="price-head gaps">
            <span>Item</span><span>Trucks</span><span>Market</span><span>Range</span>
          </div>
          {missing.map((b) => {
            const isOpen = open === b.standard_item
            const prices = data.marketPrices.filter((p) => p.item === b.standard_item).sort((x, y) => x.price - y.price)
            const a = avg(b.standard_item)
            return (
              <div key={b.standard_item} className={`price-row ${isOpen ? 'open' : ''}`} onClick={() => setOpen(isOpen ? null : b.standard_item)}>
                <div className="price-main gaps">
                  <span className="price-name">{b.item_label}</span>
                  <span className="price-avg">{b.n_trucks} of {data.rivals.length}</span>
                  <span className="price-you">{money(a, { cents: true })}</span>
                  <span className="price-range">{money(b.min, { cents: true })} to {money(b.max, { cents: true })}</span>
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
      </section>
      </>}
    </div>
  )
}
