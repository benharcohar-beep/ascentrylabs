import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { money, type SpotStat } from '../lib/data'
import { token, useTheme } from '../lib/theme'

// Milwaukee map of the spots. Tiles are slightly desaturated in CSS so the dots stand out. Dot size = what the spot makes per hour after
// fees; amber = the venue takes over 12%; the selected spot is coral.
export function SpotMap({ spots, sel, onSelect }: { spots: SpotStat[]; sel: string | null; onSelect: (id: string | null) => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const layerRef = useRef<L.LayerGroup | null>(null)
  const [theme] = useTheme()

  useEffect(() => {
    if (!ref.current || mapRef.current) return
    const map = L.map(ref.current, { zoomControl: false, attributionControl: true, scrollWheelZoom: false })
    // OpenStreetMap's own tiles: free, no key. Fine for a demo's traffic.
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(map)
    L.control.zoom({ position: 'bottomright' }).addTo(map)
    map.setView([43.035, -87.93], 11)
    mapRef.current = map
    layerRef.current = L.layerGroup().addTo(map)
    return () => { map.remove(); mapRef.current = null }
  }, [])

  useEffect(() => {
    const map = mapRef.current, layer = layerRef.current
    if (!map || !layer) return
    layer.clearLayers()
    const max = Math.max(1, ...spots.map((s) => s.netPerHour))
    const ink = token('--ink') || '#111111', accent = token('--accent') || '#6fb3b0', warn = token('--warn') || '#e0a233', ring = token('--card') || '#fff'
    for (const s of spots) {
      const fee = s.gross ? s.fees / s.gross : 0
      const on = s.loc.id === sel
      const r = 4 + 9 * Math.sqrt(s.netPerHour / max)
      const m = L.circleMarker([s.loc.lat, s.loc.lon], {
        radius: on ? r + 3 : r,
        color: ring, weight: 2,
        fillColor: on ? accent : fee > 0.12 ? warn : ink,
        fillOpacity: 0.92,
      })
      m.bindTooltip(`${s.loc.name.replace(/ \(.*\)/, '')}: ${money(s.netPerHour)}/hr`, { direction: 'top', offset: [0, -r], opacity: 0.95 })
      m.on('click', () => onSelect(on ? null : s.loc.id))
      m.addTo(layer)
    }
    if (spots.length) {
      const b = L.latLngBounds(spots.map((s) => [s.loc.lat, s.loc.lon] as [number, number]))
      map.fitBounds(b.pad(0.25), { maxZoom: 13 })
    }
  }, [spots, sel, onSelect, theme])

  return <div ref={ref} className="spotmap" />
}
