import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { PageHeader } from "./PageHeader";
import { ConsultCta } from "./ConsultCta";
import { Users, Clock, DollarSign, Bot, ArrowUpRight } from "lucide-react";
import "./calculator.css";

// Quick ROI estimator. Reads as a "what could this be worth" napkin
// math, not a binding quote. All assumptions are surfaced underneath
// the result so an executive can sanity-check the inputs.

function fmtUSD(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)}M`;
  if (n >= 1_000) return `$${Math.round(n / 1_000)}K`;
  return `$${Math.round(n)}`;
}
function fmtHours(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${Math.round(n / 1_000)}K`;
  return Math.round(n).toLocaleString();
}

type Inputs = {
  teamSize: number;          // people
  manualHours: number;       // hours per person per week
  hourlyCost: number;        // fully-loaded $/hr per person
  automationPct: number;     // 0..100 - % of manual hours that can be automated
};

const DEFAULTS: Inputs = {
  teamSize: 25,
  manualHours: 12,
  hourlyCost: 95,
  automationPct: 55,
};

export function CalculatorPage() {
  const [inputs, setInputs] = useState<Inputs>(DEFAULTS);

  useEffect(() => {
    document.title = "ROI Calculator · Ascentry Labs";
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, []);

  const set = <K extends keyof Inputs>(k: K) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = Number(e.target.value);
    setInputs((prev) => ({ ...prev, [k]: v }));
  };

  const result = useMemo(() => {
    const weeks = 52;
    const hoursReclaimedYr = inputs.teamSize * inputs.manualHours * (inputs.automationPct / 100) * weeks;
    const dollarsYr = hoursReclaimedYr * inputs.hourlyCost;
    const fiveYr = dollarsYr * 5;
    // Typical engagement: assessment + a build phase, ballpark $150-400K for the mid case.
    // Scale loosely with team size for realism.
    const engagementCost = Math.min(400_000, Math.max(80_000, 30_000 + inputs.teamSize * 6_000));
    const paybackMonths = dollarsYr > 0 ? Math.max(0.3, (engagementCost / dollarsYr) * 12) : 0;
    return { hoursReclaimedYr, dollarsYr, fiveYr, engagementCost, paybackMonths };
  }, [inputs]);

  return (
    <>
      <PageHeader
        eyebrow="08 - Math"
        title="What could AI be worth to your team?"
        sub="Napkin-math estimator. Pull the sliders to your reality - we'll show you the order of magnitude. The honest number lives in a real discovery conversation."
        rightLabel="[ ROI.01 ]"
      />

      <section className="section calculator">
        <div className="container">
          <div className="calc-grid">
            {/* ── Inputs ───────────────────────────────────────── */}
            <div className="calc-inputs glass">
              <div className="calc-corners" aria-hidden>
                <span /><span /><span /><span />
              </div>
              <header className="calc-section-head">
                <span className="mono dim">INPUTS</span>
                <h2>Your numbers</h2>
              </header>

              <div className="calc-field">
                <label className="calc-label">
                  <Users size={14} className="calc-label-icon" />
                  Team size
                  <span className="calc-value mono">{inputs.teamSize} people</span>
                </label>
                <input
                  type="range"
                  min={1}
                  max={500}
                  step={1}
                  value={inputs.teamSize}
                  onChange={set("teamSize")}
                />
              </div>

              <div className="calc-field">
                <label className="calc-label">
                  <Clock size={14} className="calc-label-icon" />
                  Manual-process hours per person per week
                  <span className="calc-value mono">{inputs.manualHours} hrs</span>
                </label>
                <input
                  type="range"
                  min={1}
                  max={40}
                  step={1}
                  value={inputs.manualHours}
                  onChange={set("manualHours")}
                />
              </div>

              <div className="calc-field">
                <label className="calc-label">
                  <DollarSign size={14} className="calc-label-icon" />
                  Fully-loaded hourly cost per person
                  <span className="calc-value mono">${inputs.hourlyCost}/hr</span>
                </label>
                <input
                  type="range"
                  min={25}
                  max={400}
                  step={5}
                  value={inputs.hourlyCost}
                  onChange={set("hourlyCost")}
                />
              </div>

              <div className="calc-field">
                <label className="calc-label">
                  <Bot size={14} className="calc-label-icon" />
                  Realistic automation rate
                  <span className="calc-value mono">{inputs.automationPct}%</span>
                </label>
                <input
                  type="range"
                  min={10}
                  max={90}
                  step={1}
                  value={inputs.automationPct}
                  onChange={set("automationPct")}
                />
              </div>

              <button className="calc-reset" onClick={() => setInputs(DEFAULTS)}>
                Reset to defaults
              </button>
            </div>

            {/* ── Outputs ──────────────────────────────────────── */}
            <div className="calc-results">
              <motion.div
                className="calc-stat calc-stat-primary glass"
                key={`stat-1-${result.dollarsYr}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
              >
                <div className="mono dim">ANNUAL DOLLAR SAVINGS</div>
                <div className="calc-stat-num" style={{ color: "var(--accent)" }}>
                  {fmtUSD(result.dollarsYr)}
                </div>
                <div className="calc-stat-foot dim">per year</div>
              </motion.div>

              <div className="calc-stats-row">
                <motion.div
                  className="calc-stat glass"
                  key={`stat-2-${result.hoursReclaimedYr}`}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25, delay: 0.05 }}
                >
                  <div className="mono dim">HOURS RECLAIMED</div>
                  <div className="calc-stat-num" style={{ color: "var(--gold)" }}>
                    {fmtHours(result.hoursReclaimedYr)}
                  </div>
                  <div className="calc-stat-foot dim">per year</div>
                </motion.div>

                <motion.div
                  className="calc-stat glass"
                  key={`stat-3-${result.fiveYr}`}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25, delay: 0.1 }}
                >
                  <div className="mono dim">5-YEAR SAVINGS</div>
                  <div className="calc-stat-num" style={{ color: "var(--blue)" }}>
                    {fmtUSD(result.fiveYr)}
                  </div>
                  <div className="calc-stat-foot dim">linear, undiscounted</div>
                </motion.div>
              </div>

              <div className="calc-payback">
                <div className="calc-payback-row">
                  <span className="mono dim">Typical engagement range</span>
                  <span className="calc-payback-v">{fmtUSD(result.engagementCost)}</span>
                </div>
                <div className="calc-payback-row">
                  <span className="mono dim">Estimated payback period</span>
                  <span className="calc-payback-v">
                    {result.paybackMonths < 1
                      ? "< 1 month"
                      : result.paybackMonths < 12
                        ? `${result.paybackMonths.toFixed(1)} months`
                        : `${(result.paybackMonths / 12).toFixed(1)} years`}
                  </span>
                </div>
              </div>

              <Link to="/#consult" className="btn btn-primary btn-fx calc-cta">
                <span className="btn-bracket">[</span>
                Validate these numbers with us
                <span className="btn-bracket">]</span>
                <ArrowUpRight size={14} className="arrow" />
              </Link>
            </div>
          </div>

          <footer className="calc-notes">
            <span className="mono dim">ASSUMPTIONS</span>
            <ul>
              <li>52-week year, no holiday discount.</li>
              <li>"Automation rate" is the share of those weekly manual hours an AI/automation engagement can realistically displace. 40–70% is typical for well-scoped projects.</li>
              <li>"Fully-loaded hourly cost" should include benefits, overhead, and tooling - not just salary.</li>
              <li>5-year figure is linear, not NPV-discounted - pad downward by ~10–15% for a more conservative view.</li>
              <li>Engagement range scales loosely with team size; real quotes happen after a discovery call.</li>
            </ul>
          </footer>
        </div>
      </section>

      <ConsultCta />
    </>
  );
}
