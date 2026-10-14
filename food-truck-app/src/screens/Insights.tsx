import { useEffect, useRef, useState } from 'react'
import { SendHorizontal } from 'lucide-react'
import { ask, getPasscode, setPasscode, type ChatMsg } from '../lib/ask'

import { MARK } from '../components/Brand'

const STARTERS = ['What should I know this week?', 'How did this week go?', 'Which spot should I do more of?', 'Should I raise the birria taco price?', 'Write my weekly summary']

/** **text** becomes bold; nothing else is interpreted. */
function Inline({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return <>{parts.map((p, i) => p.startsWith('**') && p.endsWith('**') ? <strong key={i}>{p.slice(2, -2)}</strong> : p)}</>
}

/** Render a reply as short paragraphs and bullet lists: lines starting "- " or "• " become bullets, blank lines split blocks. */
function Reply({ text }: { text: string }) {
  const blocks: { kind: 'p' | 'ul'; lines: string[] }[] = []
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    if (!line) { continue }
    const bullet = /^([-•*]|\d+[.)])\s+/.test(line)
    const last = blocks[blocks.length - 1]
    if (bullet) {
      const item = line.replace(/^([-•*]|\d+[.)])\s+/, '')
      if (last?.kind === 'ul') last.lines.push(item); else blocks.push({ kind: 'ul', lines: [item] })
    } else {
      blocks.push({ kind: 'p', lines: [line] })
    }
  }
  return (
    <>
      {blocks.map((b, i) => b.kind === 'ul'
        ? <ul key={i}>{b.lines.map((l, j) => <li key={j}><Inline text={l} /></li>)}</ul>
        : <p key={i}><Inline text={b.lines[0]} /></p>)}
    </>
  )
}

export default function Insights() {
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
    <div className="screen ai-screen">
      <header className="top"><h1>Eventini AI</h1><button className="linkish" onClick={() => { setMsgs([]); setErr(null) }}>New chat</button></header>

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
        {msgs.length === 0 && (
          <div className="welcome">
            <span className="ai-avatar big"><img src={MARK} alt="" className="mark" /></span>
            <b>Ask me anything about the truck.</b>
          </div>
        )}
        {msgs.length === 0 && (
          <div className="starters">
            {STARTERS.map((s) => <button key={s} className="starter" onClick={() => send(s)}>{s}</button>)}
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.role === 'assistant' && <span className="ai-avatar"><img src={MARK} alt="" className="mark" /></span>}
            <div className={`bubble ${m.role}`}>{m.role === 'assistant' ? <Reply text={m.content} /> : m.content}</div>
          </div>
        ))}
        {busy && <div className="msg assistant"><span className="ai-avatar"><img src={MARK} alt="" className="mark" /></span><div className="bubble assistant typing"><i /><i /><i /></div></div>}
        {err && <div className="bubble error">{err} <button className="linkish" onClick={() => { setErr(null); if (q) send(q) }}>Try again</button></div>}
        <div ref={endRef} />
      </div>

      <div className="askbar-wrap">
      <form className="askbar" onSubmit={(e) => { e.preventDefault(); send(q) }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about sales, spots, prices…" disabled={busy} />
        <button type="submit" aria-label="Send" disabled={busy || !q.trim()}><SendHorizontal size={18} /></button>
      </form>
      </div>
    </div>
  )
}
