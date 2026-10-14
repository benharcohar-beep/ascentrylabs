import { Pills } from '../components/ui'

// A face for each dish so the list is not twenty identical rows.
const FACE: [RegExp, string][] = [[/quesabirria|birria/i, '🥘'], [/taco plate/i, '🍽️'], [/taco/i, '🌮'], [/burrito/i, '🌯'], [/quesadilla/i, '🧀'], [/torta/i, '🥪'], [/elote/i, '🌽'], [/guac/i, '🥑'], [/salsa/i, '🌶️'], [/churro/i, '🍩'], [/agua/i, '🍹'], [/jarritos|soda/i, '🥤'], [/water/i, '💧']]
const face = (n: string) => FACE.find(([re]) => re.test(n))?.[1] ?? '🍴'
import { itemTotals, money, pct, rangeWindow, type RangeKey } from '../lib/data'

export default function Menu({ range, setRange }: { range: RangeKey; setRange: (k: RangeKey) => void }) {
  const w = rangeWindow(range)
  const items = itemTotals(w.from, w.to)
  const total = items.reduce((a, i) => a + i.revenue, 0)
  const cogs = items.reduce((a, i) => a + i.cogs, 0)

  return (
    <div className="screen">
      <header className="top">
        <h1>Menu</h1>
        <Pills value={range} onChange={setRange} />
      </header>

      <section className="hero compact">
        <div className="label">Left after ingredients</div>
        <div className="hero-num">{total > 0 ? pct(1 - cogs / total, false) : '–'}</div>
        <div className="hero-sub"><span>on {money(total)} of sales</span></div>
      </section>

      <ul className="feed flat">
        {items.map((i) => (
          <li key={i.item.id} className="feed-row">
            <span className="feed-ico face">{face(i.item.name)}</span>
            <span className="feed-main">
              <b>{i.item.name}</b>
              <span>{i.qty.toLocaleString()} sold · {money(i.item.price, { cents: true })} · costs {money(i.item.cost, { cents: true })}</span>
            </span>
            <span className="feed-right">
              <span className="feed-amt">{money(i.revenue)}</span>
              <span className={`feed-tag ${i.margin < 0.6 ? 'warn' : 'good'}`}>{pct(i.margin, false)} margin</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
