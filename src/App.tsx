import { useEffect, useState } from "react";
import { Background } from "./components/Background/Background";
import { Cursor } from "./components/Cursor/Cursor";
import { Nav } from "./components/Nav/Nav";
import { Hero } from "./components/Hero/Hero";
import { StatusBar } from "./components/StatusBar/StatusBar";
import { Services } from "./components/Services/Services";
import { Portfolio } from "./components/Portfolio/Portfolio";
import { About } from "./components/About/About";
import { Testimonials } from "./components/Testimonials/Testimonials";
import { Consult } from "./components/Consult/Consult";
import { Footer } from "./components/Footer/Footer";
import { CommandPalette } from "./components/CommandPalette/CommandPalette";
import { BootSequence } from "./components/BootSequence/BootSequence";
import { AskAscentry } from "./components/AskAscentry/AskAscentry";
import { ServiceFinder } from "./components/ServiceFinder/ServiceFinder";

export default function App() {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [finderOpen, setFinderOpen] = useState(false);
  // Smooth scrolling is handled by CSS `html { scroll-behavior: smooth }`
  // in app.css — no JS library needed. Lenis was overshooting wheel
  // input which felt out of control.

  // Cmd+K toggles the palette globally
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

  // Allow other components (Services CTA, Ask Ascentry chip) to open the
  // ServiceFinder via a custom event without prop-drilling state down.
  useEffect(() => {
    const onOpen = () => setFinderOpen(true);
    window.addEventListener("ascentry:open-finder", onOpen);
    return () => window.removeEventListener("ascentry:open-finder", onOpen);
  }, []);

  return (
    <>
      <BootSequence />
      <Background />
      <Cursor />
      <div className="app-content">
        <Nav onOpenPalette={() => setPaletteOpen(true)} />
        <main>
          <Hero />
          <StatusBar />
          <Services />
          <Portfolio />
          <About />
          <Testimonials />
          <Consult />
        </main>
        <Footer />
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <AskAscentry />
      <ServiceFinder open={finderOpen} onClose={() => setFinderOpen(false)} />
    </>
  );
}
