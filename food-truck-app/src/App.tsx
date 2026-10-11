import { useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Nav } from './components/ui'
import type { RangeKey } from './lib/data'
import Home from './screens/Home'
import Market from './screens/Market'
import Menu from './screens/Menu'
import Spots from './screens/Spots'
import Tips from './screens/Tips'
import History from './screens/History'
import './app.css'

export default function App() {
  // One shared time range across Home, Spots and Menu.
  const [range, setRange] = useState<RangeKey>('1W')
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <main className="shell">
        <Routes>
          <Route path="/" element={<Home range={range} setRange={setRange} />} />
          <Route path="/spots" element={<Spots range={range} setRange={setRange} />} />
          <Route path="/menu" element={<Menu range={range} setRange={setRange} />} />
          <Route path="/market" element={<Market />} />
          <Route path="/tips" element={<Tips />} />
          <Route path="/history/:metric" element={<History />} />
        </Routes>
        <Nav />
      </main>
    </BrowserRouter>
  )
}
