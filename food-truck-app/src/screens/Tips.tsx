import { Card } from '../components/ui'
import { TODAY, shortDate } from '../lib/data'
import { weeklyInsights } from '../lib/insights'

export default function Tips() {
  const tips = weeklyInsights()
  return (
    <>
      <header className="top">
        <h1>Tips</h1>
      </header>
      <p className="lede">Week of {shortDate(TODAY)}. Each one is worked out from your own numbers; tap "why" to see the sums behind it.</p>
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
      <p className="foot">No AI involved: these are fixed rules over the data, so every claim can be checked.</p>
    </>
  )
}
