import { useState } from 'react'

// Logo slot: drop Eventini's SVG/PNG at public/eventini-logo.svg and set HAS_LOGO
// to true. Until then the wordmark is plain text.
const HAS_LOGO = false

export function Brand() {
  const [about, setAbout] = useState(false)
  return (
    <>
      <button className="brand-btn" onClick={() => setAbout(true)} aria-label="About this concept">
        {HAS_LOGO ? <img src={`${import.meta.env.BASE_URL}eventini-logo.svg`} alt="Eventini" height="20" /> : <span className="wordmark">eventini</span>}
        <span className="brand-sep">AI</span>
        <span className="concept-tag">Concept</span>
      </button>
      {about && (
        <div className="sheet-back" onClick={() => setAbout(false)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <h2>About this concept</h2>
            <p>Eventini AI is a concept for an owner-facing insights app on top of the Eventini POS, built by Ben Harcourt-Harrison. It is not an Eventini product and Eventini has not endorsed it.</p>
            <p>Everything shown is sample data for a made-up Milwaukee taqueria. The Eventini name and wordmark belong to Eventini.</p>
            <button className="btn" onClick={() => setAbout(false)}>Close</button>
          </div>
        </div>
      )}
    </>
  )
}
