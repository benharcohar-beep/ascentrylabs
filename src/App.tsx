import { useEffect, useState } from "react";
import { Routes, Route, useLocation } from "react-router-dom";
import { Background } from "./components/Background/Background";
import { Cursor } from "./components/Cursor/Cursor";
import { Nav } from "./components/Nav/Nav";
import { Footer } from "./components/Footer/Footer";
import { CommandPalette } from "./components/CommandPalette/CommandPalette";
import { BootSequence } from "./components/BootSequence/BootSequence";
import { AskAscentry } from "./components/AskAscentry/AskAscentry";
import { ServiceFinder } from "./components/ServiceFinder/ServiceFinder";
import { PageTransition } from "./components/PageTransition/PageTransition";
import { ErrorBoundary } from "./components/ErrorBoundary/ErrorBoundary";
import { HomePage } from "./pages/HomePage";
import { ServicesPage } from "./pages/ServicesPage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { AboutPage } from "./pages/AboutPage";
import { TestimonialsPage } from "./pages/TestimonialsPage";
import { ProcessPage } from "./pages/ProcessPage";
import { CalculatorPage } from "./pages/CalculatorPage";
import { CaseStudyPage } from "./pages/CaseStudyPage";

export default function App() {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [finderOpen, setFinderOpen] = useState(false);
  const location = useLocation();
  const isHome = location.pathname === "/";

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

  // Other components open the ServiceFinder via a custom event
  useEffect(() => {
    const onOpen = () => setFinderOpen(true);
    window.addEventListener("ascentry:open-finder", onOpen);
    return () => window.removeEventListener("ascentry:open-finder", onOpen);
  }, []);

  // Scroll restoration: any in-page hash navigation should bring the
  // section into view smoothly. Without this, navigation between routes
  // sometimes preserves the scroll position from the previous page.
  useEffect(() => {
    if (location.hash) {
      const el = document.querySelector(location.hash);
      if (el) {
        setTimeout(() => el.scrollIntoView({ behavior: "smooth", block: "start" }), 120);
        return;
      }
    }
  }, [location]);

  return (
    <>
      <BootSequence />
      <Background />
      <Cursor />
      <div className="app-content">
        <Nav showSectionLinks={!isHome} />
        <main>
          {/* key={location.pathname} forces React to remount the wrapper on
              route changes, retriggering the CSS fade-in keyframe.
              The inner ErrorBoundary catches per-page render errors so the
              nav + footer + factory background stay alive while the user
              picks another route. */}
          <div key={location.pathname} className="page-transition">
            <ErrorBoundary scope="page">
              <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/services" element={<ServicesPage />} />
                <Route path="/portfolio" element={<PortfolioPage />} />
                <Route path="/portfolio/:slug" element={<CaseStudyPage />} />
                <Route path="/about" element={<AboutPage />} />
                <Route path="/testimonials" element={<TestimonialsPage />} />
                <Route path="/process" element={<ProcessPage />} />
                <Route path="/calculator" element={<CalculatorPage />} />
                <Route path="*" element={<HomePage />} />
              </Routes>
            </ErrorBoundary>
          </div>
        </main>
        <Footer />
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <AskAscentry />
      <ServiceFinder open={finderOpen} onClose={() => setFinderOpen(false)} />
      <PageTransition />
    </>
  );
}
