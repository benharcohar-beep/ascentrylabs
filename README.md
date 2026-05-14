# Ascentry Labs

Marketing site for [Ascentry Labs](https://ascentrylabs.com) — an AI &amp; digital transformation consultancy.

A futuristic redesign with a parallax starfield background, drifting nebulas, floating tilt cards, magnetic buttons, a custom reticle cursor, glyph-scramble headlines, a rotating wireframe core in the hero, and a Cmd+K command palette.

## Stack

- **Vite + React 19 + TypeScript** — fast dev, strict types
- **Three.js + @react-three/fiber + drei** — wireframe core in the hero
- **Framer Motion** — entrance animations and AnimatePresence transitions
- **Lucide** — icons
- **Plain CSS with custom properties** — no UI framework, full design control

## Run locally

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # type-check + production bundle
npm run preview  # serve the built bundle
```

## Project layout

```
src/
  App.tsx                       # Root, wires everything + Cmd+K hotkey
  main.tsx                      # Entry, mounts <App />
  styles/
    globals.css                 # Design tokens, reset, typography, .btn, .glass
    app.css                     # Layout shell
  data/                         # Services, projects, testimonials, nav
  components/
    Background/                 # Starfield (canvas2D) + nebula + grid + vignette
    Cursor/                     # Custom reticle cursor (pointer:fine only)
    Nav/                        # Top navigation with Cmd+K trigger
    Hero/                       # Hero copy + WireframeCore (R3F) + ScrambleText
    Services/                   # Six service cards in a tilt grid
    Portfolio/                  # Filterable project grid
    About/                      # Stats + experience timeline
    Testimonials/               # Horizontal scroll-snap carousel
    Consult/                    # Contact form
    Footer/                     # Brand + links + status
    CommandPalette/             # Cmd+K palette with grouped commands
    ui/
      MagneticButton.tsx        # Pull-toward-cursor wrapper
      TiltCard.tsx              # 3D rotateX/rotateY on hover with glare
      ScrambleText.tsx          # Glyph-decode text reveal
```

## Deployment

The site is wired for **Vercel** — it auto-detects Vite, runs `npm run build`, and serves `dist/`. Push to `main` and a deploy fires.

## Notes

- The contact form opens the user's mail client with a prefilled draft. Wire it to Web3Forms / Formspree / Resend by replacing the `onSubmit` handler in `src/components/Consult/Consult.tsx`.
- `prefers-reduced-motion` is respected — animations and the starfield drop to a static state for users who request it.
- The Three.js bundle is large (~1.2MB pre-gzip). Consider code-splitting `WireframeCore` with `React.lazy` if first-paint becomes a concern.
