import { Link } from 'react-router-dom'

// Eventini's mark (public/eventini-mark.png, black on transparent; inverted in dark mode). Tapping it opens the AI tab.
export const MARK = `${import.meta.env.BASE_URL}eventini-mark.png`

export function Brand() {
  return (
    <Link to="/insights" className="brand-btn" aria-label="Eventini AI">
      <img src={MARK} alt="" className="mark" width={18} height={18} />
      <span className="wordmark">Eventini</span>
      <span className="brand-sep">AI</span>
    </Link>
  )
}
