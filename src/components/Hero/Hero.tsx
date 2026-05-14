import { motion } from "framer-motion";
import { ScrambleText } from "../ui/ScrambleText";
import { MagneticButton } from "../ui/MagneticButton";
import { WireframeCore } from "./WireframeCore";
import { ArrowUpRight, ArrowRight } from "lucide-react";
import "./hero.css";

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.7, delay: 0.1 + i * 0.12, ease: [0.22, 1, 0.36, 1] as const },
  }),
};

export function Hero() {
  return (
    <section className="hero" id="top">
      <div className="container hero-inner">
        <div className="hero-left">
          <motion.div className="eyebrow" variants={fadeUp} initial="hidden" animate="visible" custom={0}>
            <span className="mono">ASCENTRY OS · v2.0 · ONLINE</span>
          </motion.div>

          <h1 className="hero-title">
            <motion.span className="hero-title-line" variants={fadeUp} initial="hidden" animate="visible" custom={1}>
              <ScrambleText text="Bring your company" durationMs={1100} />
            </motion.span>
            <motion.span className="hero-title-line" variants={fadeUp} initial="hidden" animate="visible" custom={2}>
              <ScrambleText text="into the era of " durationMs={1300} delayMs={200} />
              <span className="hero-accent">
                <ScrambleText text="AI." durationMs={900} delayMs={1100} />
              </span>
            </motion.span>
          </h1>

          <motion.p className="hero-sub" variants={fadeUp} initial="hidden" animate="visible" custom={3}>
            Fragmented ERPs and data providers, hours lost to Excel wrangling, no real-time view of performance,
            and a creeping sense of falling behind: most companies know they need AI but don't know where to start.
          </motion.p>

          <motion.p className="hero-sub" variants={fadeUp} initial="hidden" animate="visible" custom={4}>
            Ascentry Labs closes that gap. Founded by <strong>Hunter Sandidge</strong> — the engineer behind the
            AI and analytics ecosystem that monitors life support on the International Space Station, father of the
            AI copilot for the xEVAS spacesuit, and smart-factory and digital transformation lead at a Fortune&nbsp;100 —
            Ascentry Labs translates the noise around AI into systems that actually run your operation.
          </motion.p>

          <motion.div className="hero-cta" variants={fadeUp} initial="hidden" animate="visible" custom={5}>
            <MagneticButton href="#consult" className="btn btn-primary">
              Free 30-min Consultation
              <ArrowUpRight size={16} className="arrow" />
            </MagneticButton>
            <MagneticButton href="#services" className="btn btn-ghost" strength={0.25}>
              See how we help
              <ArrowRight size={16} className="arrow" />
            </MagneticButton>
          </motion.div>

          <motion.div className="hero-meta" variants={fadeUp} initial="hidden" animate="visible" custom={6}>
            <div className="hero-meta-item">
              <span className="mono dim">CLIENTS</span>
              <span>NASA · Collins Aerospace · Marquette</span>
            </div>
            <div className="hero-meta-item">
              <span className="mono dim">SECTORS</span>
              <span>Aerospace · Defense · Finance · Education</span>
            </div>
          </motion.div>
        </div>

        <motion.div
          className="hero-right"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1.4, ease: [0.22, 1, 0.36, 1] }}
        >
          <WireframeCore />
        </motion.div>
      </div>

      <motion.div
        className="hero-scroll-hint"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.8, duration: 0.8 }}
      >
        <span className="mono dim">SCROLL</span>
        <span className="hero-scroll-bar" aria-hidden />
      </motion.div>
    </section>
  );
}
