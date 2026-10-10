import { Card, Meter, Pills, Spark } from '../components/ui'
import { addDays, data, itemTotals, money, pct, rangeWindow, type RangeKey } from '../lib/data'

function weeklySeries(itemId: string, to: string, weeks = 12): number[] {
  const out: number[] = []
  for (let i = weeks - 1; i >= 0; i--) {
    const end = addDays(to, -7 * i), start = addDays(end, -6)
    let v = 0
    for (const r of data.itemDays) if (r.item_id === itemId && r.date >= start && r.date <= end) v += r.revenue
    out.push(v)
  }
  return out
}

export default function Menu({ range, setRange }: { range: RangeKey; setRange: (k: RangeKey) => void }) {
  const w = rangeWindow(range)
  const items = itemTotals(w.from, w.to)
  const max = items[0]?.revenue ?? 1
  const total = items.reduce((a, i) => a + i.revenue, 0)
  const cogs = items.reduce((a, i) => a + i.cogs, 0)

  return (
    <>
      <section className="grad sage">
        <header className="top">
          <h1>Menu</h1>
          <Pills value={range} onChange={setRange} />
        </header>
        {total > 0 ? (
          <>
            <div className="label">You keep, after ingredients</div>
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
                  <Spark values={weeklySeries(i.item.id, w.to)} />
                  <span className={`chip ${thin ? 'warn' : 'good'}`}>keeps {pct(i.margin, false)}</span>
                  <span className="muted">cost {money(i.item.cost, { cents: true })}</span>
                </div>
              </li>
            )
          })}
        </ul>
      </Card>
    </>
  )
}
