import { useEffect, useState } from "react";
import { Background } from "./components/Background/Background";
import { Cursor } from "./components/Cursor/Cursor";
import { Nav } from "./components/Nav/Nav";
import { Hero } from "./components/Hero/Hero";
import { Services } from "./components/Services/Services";
import { Portfolio } from "./components/Portfolio/Portfolio";
import { About } from "./components/About/About";
import { Testimonials } from "./components/Testimonials/Testimonials";
import { Consult } from "./components/Consult/Consult";
import { Footer } from "./components/Footer/Footer";
import { CommandPalette } from "./components/CommandPalette/CommandPalette";

export default function App() {
  const [paletteOpen, setPaletteOpen] = useState(false);

  // Cmd+K / Ctrl+K opens the palette globally
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      <Background />
      <Cursor />
      <div className="app-content">
        <Nav onOpenPalette={() => setPaletteOpen(true)} />
        <main>
          <Hero />
          <Services />
          <Portfolio />
          <About />
          <Testimonials />
          <Consult />
        </main>
        <Footer />
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </>
  );
}
