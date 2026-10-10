import { useState } from 'react'
import { Card, RangeBar } from '../components/ui'
import { data, money, pct, rivalById } from '../lib/data'

export default function Market() {
  const rows = data.benchmarks
    .filter((b) => b.hero_price !== null && b.n_trucks >= 3)
    .sort((a, b) => (a.hero_vs_median ?? 0) - (b.hero_vs_median ?? 0))
  const [open, setOpen] = useState<string | null>(null)
  const below = rows.filter((r) => (r.hero_vs_median ?? 0) < -0.03).length
  const trucks = new Set(data.marketPrices.map((p) => p.truckId)).size

  return (
    <>
      <section className="grad blue">
        <header className="top">
          <h1>Market</h1>
        </header>
        <div className="label">Items priced under {trucks} other Milwaukee trucks</div>
        <div className="big">{below} <small>of {rows.length}</small></div>
      </section>

      {rows.map((b) => {
        const you = b.hero_price!
        const gap = b.hero_vs_median ?? 0
        const isOpen = open === b.standard_item
        const prices = data.marketPrices.filter((p) => p.item === b.standard_item).sort((a, c) => a.price - c.price)
        return (
          <Card key={b.standard_item} className="mkt" onClick={() => setOpen(isOpen ? null : b.standard_item)}>
            <div className="row">
              <div className="name">{b.item_label}</div>
              <div className={`chip ${gap < -0.03 ? 'warn' : gap > 0.03 ? 'info' : 'good'}`}>{pct(gap)} vs middle</div>
            </div>
            <RangeBar min={b.min} max={b.max} median={b.median} you={you} />
            <div className="range-labels">
              <span>{money(b.min, { cents: true })}</span>
              <span className="you">you {money(you, { cents: true })}</span>
              <span>{money(b.max, { cents: true })}</span>
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
                <li className="muted small">Middle {money(b.median, { cents: true })} from {b.n_trucks} trucks. Sources: menu photos, Instagram, websites and pooled POS data.</li>
              </ul>
            )}
          </Card>
        )
      })}
    </>
  )
}
