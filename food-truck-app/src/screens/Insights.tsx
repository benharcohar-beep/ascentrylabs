import { Card } from '../components/ui'
import { TODAY, money, shortDate } from '../lib/data'
import { weeklyInsights, type Insight } from '../lib/insights'
import { stockAlerts } from '../lib/stock'

const ORDER: Insight['section'][] = ['Sales', 'Spots', 'Menu', 'Market', 'Weather', 'Tips']

export default function Insights() {
  const tips = weeklyInsights()
  const stock = stockAlerts()
  const sections = ORDER.map((s) => ({ name: s, items: tips.filter((t) => t.section === s && t.id !== 'wow') })).filter((s) => s.items.length)

  return (
    <>
      <section className="block-hero pink page">
        <header className="top">
          <h1>Insights</h1>
        </header>
        <div className="label">Week of {shortDate(TODAY)}</div>
        <div className="big">{tips.filter((t) => t.id !== 'wow').length + stock.length}</div>
        <div className="label">insights this week, from your own numbers</div>
      </section>

      {stock.length > 0 && (
        <section className="block">
          <h2>Stock</h2>
          <Card className="rows">
            {stock.map((s) => (
              <details key={s.id} className="irow">
                <summary>
                  <span className="fig">{money(s.wastePerWeek)}<em>a week in the bin</em></span>
                  <span className="txt">
                    <b>{s.item.name} has stopped selling</b>
                    <span>{s.unitsNow} this week against about {s.unitsBase} a week before. About {s.surplusLabel} of {s.ingredient} a week is going in the bin.</span>
                  </span>
                </summary>
                <div className="irow-body">
                  <p><b>First:</b> {s.prepLine}</p>
                  <p><b>This week:</b> {s.dealLine}</p>
                  <p><b>Or:</b> {s.freeLine}</p>
                  <p className="muted">How: units per 100 orders this week against the previous 8 weeks, so a quiet week or a different venue does not count.</p>
                </div>
              </details>
            ))}
          </Card>
        </section>
      )}

      {sections.map((sec) => (
        <section className="block" key={sec.name}>
          <h2>{sec.name}</h2>
          <Card className="rows">
            {sec.items.map((t) => (
              <details key={t.id} className="irow">
                <summary>
                  <span className={`fig ${t.tone}`}>{t.figure}<em>{t.figureNote}</em></span>
                  <span className="txt">
                    <b>{t.title}</b>
                    <span>{t.body}</span>
                  </span>
                </summary>
                <div className="irow-body">
                  {t.action && <p>{t.action}</p>}
                  <p className="muted">How: {t.evidence}</p>
                </div>
              </details>
            ))}
          </Card>
        </section>
      ))}
    </>
  )
}
