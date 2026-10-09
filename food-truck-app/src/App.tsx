import './app.css'

export default function App() {
  return (
    <main className="shell">
      <header className="top">
        <span className="brand">Truckboard</span>
        <span className="tag">Preview</span>
      </header>

      <section className="card hero">
        <div className="label">This week</div>
        <div className="big">$4,860</div>
        <div className="delta">+12% vs last week</div>
      </section>

      <section className="tiles">
        <div className="card tile"><div className="num">312</div><div className="label">orders</div></div>
        <div className="card tile"><div className="num">$15.60</div><div className="label">avg order</div></div>
        <div className="card tile"><div className="num">$412</div><div className="label">tips</div></div>
      </section>

      <p className="note">
        Placeholder shell. Screens, charts and data are coming next; this page exists so the
        deployment pipeline can be set up first.
      </p>

      <nav className="nav">
        {['Home', 'Spots', 'Menu', 'Market', 'Tips'].map((n, i) => (
          <span key={n} className={i === 0 ? 'on' : ''}>{n}</span>
        ))}
      </nav>
    </main>
  )
}
