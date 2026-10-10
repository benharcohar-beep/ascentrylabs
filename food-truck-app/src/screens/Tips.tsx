import { Card } from '../components/ui'
import { TODAY, shortDate } from '../lib/data'
import { weeklyInsights } from '../lib/insights'
import { stockAlerts } from '../lib/stock'
import { money, pct } from '../lib/data'

export default function Tips() {
  const tips = weeklyInsights()
  const stock = stockAlerts()
  return (
    <>
      <section className="grad warm">
        <header className="top">
          <h1>Tips</h1>
          <span className="tag">Week of {shortDate(TODAY)}</span>
        </header>
        <div className="label">{tips.length + stock.length} things worth knowing this week</div>
      </section>
      {stock.map((s) => (
        <Card key={s.id} className="insight warn">
          <div className="eyebrow">Use it or lose it</div>
          <div className="insight-title">{s.item.name}: {s.unitsNow} sold this week, usually {s.unitsBase}</div>
          <p>Selling {pct(s.drop, false)} less than usual per order. About {s.surplusLabel} of {s.ingredient} a week is going unsold, worth {money(s.wastePerWeek)} in ingredients{s.shelfLifeDays <= 2 ? `, and it keeps ${s.shelfLifeDays} day${s.shelfLifeDays > 1 ? 's' : ''}` : ''}.</p>
          <p className="action">1. {s.prepLine}</p>
          <p>2. {s.dealLine}</p>
          <p>3. {s.freeLine}</p>
          <details>
            <summary>why</summary>
            <p className="muted">Units per 100 orders this week against the previous 8 weeks, so a quiet week or a different venue does not count. Surplus assumes you still prep the old amount.</p>
          </details>
        </Card>
      ))}
      {tips.map((t) => (
        <Card key={t.id} className={`insight ${t.tone}`}>
          <div className="insight-title">{t.title}</div>
          <p>{t.body}</p>
          {t.action && <p className="action">{t.action}</p>}
          <details>
            <summary>why</summary>
            <p className="muted">{t.evidence}</p>
          </details>
        </Card>
      ))}
    </>
  )
}
