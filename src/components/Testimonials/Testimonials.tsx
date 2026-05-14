import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { TESTIMONIALS } from "../../data/testimonials";
import { TiltCard } from "../ui/TiltCard";
import { Quote, ChevronLeft, ChevronRight } from "lucide-react";
import "./testimonials.css";

const ACCENT_COLOR = {
  gold: "#ffc000",
  cyan: "#7fd1d3",
  blue: "#5b9dd9",
} as const;

export function Testimonials() {
  const trackRef = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    const onScroll = () => {
      const center = track.scrollLeft + track.clientWidth / 2;
      const cards = Array.from(track.querySelectorAll<HTMLElement>(".tm-card"));
      let nearest = 0;
      let nearestDist = Infinity;
      cards.forEach((el, i) => {
        const ec = el.offsetLeft + el.offsetWidth / 2;
        const d = Math.abs(ec - center);
        if (d < nearestDist) { nearestDist = d; nearest = i; }
      });
      setActive(nearest);
    };
    track.addEventListener("scroll", onScroll, { passive: true });
    return () => track.removeEventListener("scroll", onScroll);
  }, []);

  const scrollBy = (dir: 1 | -1) => {
    const track = trackRef.current;
    if (!track) return;
    const card = track.querySelector<HTMLElement>(".tm-card");
    if (!card) return;
    track.scrollBy({ left: dir * (card.offsetWidth + 24), behavior: "smooth" });
  };

  return (
    <section className="section testimonials" id="testimonials">
      <div className="container">
        <div className="section-head">
          <div>
            <div className="eyebrow">05 — Signal</div>
            <h2 className="section-title">Words from people<br />I've worked with.</h2>
            <p className="section-sub">
              From astronauts to enterprise execs to professors. Same throughline: turning ambiguity into systems
              that ship.
            </p>
          </div>
          <div className="tm-controls">
            <button className="tm-arrow" onClick={() => scrollBy(-1)} aria-label="Previous testimonial">
              <ChevronLeft size={18} />
            </button>
            <span className="mono dim">{String(active + 1).padStart(2, "0")} / {String(TESTIMONIALS.length).padStart(2, "0")}</span>
            <button className="tm-arrow" onClick={() => scrollBy(1)} aria-label="Next testimonial">
              <ChevronRight size={18} />
            </button>
          </div>
        </div>

        <div className="tm-track no-scrollbar" ref={trackRef}>
          {TESTIMONIALS.map((t, i) => (
            <motion.div
              key={i}
              className="tm-card-wrap"
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.55, delay: (i % 3) * 0.08 }}
            >
              <TiltCard
                className="tm-card glass"
                intensity={3}
                style={{ ["--tm-accent" as string]: ACCENT_COLOR[t.accent] }}
              >
                <Quote size={28} className="tm-quote-icon" />
                <p className="tm-quote">{t.quote}</p>
                <footer className="tm-foot">
                  <div className="tm-name">{t.name}</div>
                  <div className="mono tm-meta">
                    {t.role} · {t.org}
                  </div>
                </footer>
              </TiltCard>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
