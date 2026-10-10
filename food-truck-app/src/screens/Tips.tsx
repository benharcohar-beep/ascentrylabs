import { Card } from '../components/ui'
import { TODAY, shortDate } from '../lib/data'
import { weeklyInsights } from '../lib/insights'

export default function Tips() {
  const tips = weeklyInsights()
  return (
    <>
      <header className="top">
        <h1>Tips</h1>
        <span className="tag">Week of {shortDate(TODAY)}</span>
      </header>
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
