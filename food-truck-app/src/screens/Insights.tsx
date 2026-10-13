import { useEffect, useRef, useState } from 'react'
import { SendHorizontal } from 'lucide-react'
import { TODAY, money, shortDate } from '../lib/data'
import { weeklyInsights, type Insight } from '../lib/insights'
import { stockAlerts } from '../lib/stock'
import { ask, getPasscode, setPasscode, type ChatMsg } from '../lib/ask'

const ORDER: Insight['section'][] = ['Sales', 'Spots', 'Menu', 'Market', 'Weather', 'Tips']
const STARTERS = ['How did this week go?', 'Which spot should I do more of?', 'Should I raise the birria taco price?', 'Write my weekly summary']

export default function Insights() {
  const tips = weeklyInsights().filter((t) => t.id !== 'wow')
  const stock = stockAlerts()
  const sections = ORDER.map((s) => ({ name: s, items: tips.filter((t) => t.section === s) })).filter((s) => s.items.length)

  const [msgs, setMsgs] = useState<ChatMsg[]>([])
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [needPass, setNeedPass] = useState(false)
  const [pass, setPass] = useState(getPasscode())
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => { if (msgs.length || busy) endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, busy])

  async function send(text: string) {
    const question = text.trim()
    if (!question || busy) return
    setErr(null); setQ('')
    const next = [...msgs, { role: 'user' as const, content: question }]
    setMsgs(next); setBusy(true)
    const r = await ask(question, msgs)
    setBusy(false)
    if (r.needPasscode) { setNeedPass(true); setMsgs(msgs); setQ(question); return }
    if (r.error) { setErr(r.error); setMsgs(msgs); setQ(question); return }
    setMsgs([...next, { role: 'assistant', content: r.answer ?? '' }])
  }

  return (
    <>
      <section className="block-hero lilac page">
        <header className="top"><h1>Eventini AI</h1></header>
        <div className="label">Week of {shortDate(TODAY)}. Ask anything; answers come from your own numbers.</div>
      </section>

      {needPass && (
        <div className="card passbox">
          <b>Passcode</b>
          <p className="sub">This demo needs a passcode to use the AI.</p>
          <div className="row">
            <input value={pass} onChange={(e) => setPass(e.target.value)} placeholder="passcode" />
            <button className="btn" onClick={() => { setPasscode(pass); setNeedPass(false); if (q) send(q) }}>Save</button>
          </div>
        </div>
      )}

      <div className="chat">
        {/* The AI's opening message: this week's findings */}
        <div className="bubble assistant opener">
          <p className="opener-lead">{tips.length + stock.length} things worth knowing this week.</p>
          {stock.length > 0 && (
            <div className="sec">
              <h3>Stock</h3>
              {stock.map((s) => (
                <details key={s.id} className="irow">
                  <summary>
                    <span className="fig">{money(s.wastePerWeek)}<em>a week in the bin</em></span>
                    <span className="txt"><b>{s.item.name} has stopped selling</b><span>{s.unitsNow} this week against about {s.unitsBase} a week before. About {s.surplusLabel} of {s.ingredient} a week is going in the bin.</span></span>
                  </summary>
                  <div className="irow-body">
                    <p><b>First:</b> {s.prepLine}</p>
                    <p><b>This week:</b> {s.dealLine}</p>
                    <p><b>Or:</b> {s.freeLine}</p>
                  </div>
                </details>
              ))}
            </div>
          )}
          {sections.map((sec) => (
            <div className="sec" key={sec.name}>
              <h3>{sec.name}</h3>
              {sec.items.map((t) => (
                <details key={t.id} className="irow">
                  <summary>
                    <span className={`fig ${t.tone}`}>{t.figure}<em>{t.figureNote}</em></span>
                    <span className="txt"><b>{t.title}</b><span>{t.body}</span></span>
                  </summary>
                  <div className="irow-body">
                    {t.action && <p>{t.action}</p>}
                    <p className="muted">How: {t.evidence}</p>
                  </div>
                </details>
              ))}
            </div>
          ))}
        </div>

        {msgs.length === 0 && (
          <div className="starters">
            {STARTERS.map((s) => <button key={s} className="starter" onClick={() => send(s)}>{s}</button>)}
          </div>
        )}
        {msgs.map((m, i) => <div key={i} className={`bubble ${m.role}`}>{m.content}</div>)}
        {busy && <div className="bubble assistant thinking">…</div>}
        {err && <div className="bubble error">{err}</div>}
        <div ref={endRef} />
      </div>

      <form className="askbar" onSubmit={(e) => { e.preventDefault(); send(q) }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about sales, spots, prices…" disabled={busy} />
        <button type="submit" aria-label="Send" disabled={busy || !q.trim()}><SendHorizontal size={18} /></button>
      </form>
    </>
  )
}
