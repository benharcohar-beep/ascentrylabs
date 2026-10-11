import { Card, Meter, Pills } from '../components/ui'
import { itemTotals, money, pct, rangeWindow, type RangeKey } from '../lib/data'

export default function Menu({ range, setRange }: { range: RangeKey; setRange: (k: RangeKey) => void }) {
  const w = rangeWindow(range)
  const items = itemTotals(w.from, w.to)
  const max = items[0]?.revenue ?? 1
  const total = items.reduce((a, i) => a + i.revenue, 0)
  const cogs = items.reduce((a, i) => a + i.cogs, 0)

  return (
    <>
      <section className="block-hero marigold page">
        <header className="top">
          <h1>Menu</h1>
          <Pills value={range} onChange={setRange} />
        </header>
        {total > 0 ? (
          <>
            <div className="label">Profit after ingredients</div>
            <div className="big">{pct(1 - cogs / total, false)} <small>of {money(total)}</small></div>
          </>
        ) : (
          <div className="label">Nothing sold in this range</div>
        )}
      </section>

      <Card>
        <ul className="list">
          {items.map((i) => {
            const thin = i.margin < 0.6
            return (
              <li key={i.item.id}>
                <div className="list-main">
                  <span className="name">{i.item.name} <small className="muted">{money(i.item.price, { cents: true })}</small></span>
                  <span className="val">{money(i.revenue)}</span>
                </div>
                <div className="list-sub">
                  <Meter value={i.revenue} max={max} />
                  <span>{i.qty.toLocaleString()} sold</span>
                </div>
                <div className="list-foot">
                  <span className={`chip ${thin ? 'warn' : 'good'}`}>{pct(i.margin, false)} profit</span>
                  <span className="muted">costs {money(i.item.cost, { cents: true })} to make</span>
                </div>
              </li>
            )
          })}
        </ul>
      </Card>
    </>
  )
}
