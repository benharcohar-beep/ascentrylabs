import { Link } from 'react-router-dom'

// Logo slot: drop Eventini's SVG/PNG at public/eventini-logo.svg and set HAS_LOGO
// to true. Until then the wordmark is plain text. Tapping it opens the AI tab.
const HAS_LOGO = false

export function Brand() {
  return (
    <Link to="/insights" className="brand-btn" aria-label="Eventini AI">
      {HAS_LOGO ? <img src={`${import.meta.env.BASE_URL}eventini-logo.svg`} alt="Eventini" height="20" /> : <span className="wordmark">Eventini</span>}
      <span className="brand-sep">AI</span>
    </Link>
  )
}
