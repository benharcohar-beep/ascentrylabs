import { useEffect } from "react";
import { motion } from "framer-motion";
import { PageHeader } from "./PageHeader";
import { ConsultCta } from "./ConsultCta";
import { Compass, PenTool, Cpu, Activity, ArrowRight } from "lucide-react";
import "./process.css";

type Phase = {
  num: string;
  name: string;
  duration: string;
  desc: string;
  deliverables: string[];
  Icon: typeof Compass;
  color: string;
};

const PHASES: Phase[] = [
  {
    num: "01",
    name: "Discover",
    duration: "2 weeks",
    desc: "We sit down with the people doing the work. Map the current state of your data, tools, and decisions before recommending a single change.",
    deliverables: [
      "Stakeholder interviews across leadership and operators",
      "Current-state audit of data + systems + workflows",
      "Prioritized opportunity map (impact × feasibility)",
    ],
    Icon: Compass,
    color: "#7fd1d3",
  },
  {
    num: "02",
    name: "Design",
    duration: "2–6 weeks",
    desc: "We translate the opportunity into a concrete plan — architecture, sequence, owners, success metrics. Nothing gets built until we both agree on the shape of the end state.",
    deliverables: [
      "Reference architecture for data + AI systems",
      "Phased execution roadmap with realistic timelines",
      "Success metrics that an executive can defend",
    ],
    Icon: PenTool,
    color: "#ffc000",
  },
  {
    num: "03",
    name: "Build",
    duration: "6–12 weeks per phase",
    desc: "We ship in production-realistic environments from day one. Iterative releases, real users in the loop, no \"big reveal\" surprises at the end.",
    deliverables: [
      "Working systems deployed against real data",
      "Documentation, runbooks, and trained operators",
      "Production-grade handoff — you own the IP",
    ],
    Icon: Cpu,
    color: "#5b9dd9",
  },
  {
    num: "04",
    name: "Run",
    duration: "Ongoing",
    desc: "Most engagements continue as a retainer once systems are live — for course correction, scale-up, and continuous improvement. No lock-in: end the retainer any month with a 30-day notice.",
    deliverables: [
      "Monthly strategic reviews with leadership",
      "Hands-on support for the operators using the system",
      "Roadmap updates as the business evolves",
    ],
    Icon: Activity,
    color: "#c47ad9",
  },
];

export function ProcessPage() {
  useEffect(() => {
    document.title = "How We Work · Ascentry Labs";
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, []);

  return (
    <>
      <PageHeader
        eyebrow="07 — How We Work"
        title="From ambiguity to systems that ship."
        sub="Four phases. The first two are about figuring out what's actually worth building. The next two are about building it and making it stick."
        rightLabel="[ P.01 — P.04 ]"
      />

      <section className="section process">
        <div className="container">
          <div className="process-flow">
            <div className="process-spine" aria-hidden />
            {PHASES.map((p, i) => (
              <motion.div
                key={p.num}
                className="process-phase"
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-80px" }}
                transition={{ duration: 0.55, delay: i * 0.08, ease: [0.22, 1, 0.36, 1] }}
                style={{ ["--phase-color" as string]: p.color }}
              >
                <div className="process-node" aria-hidden>
                  <span className="process-node-dot" />
                  <span className="process-node-ring" />
                </div>

                <div className="process-card glass">
                  <div className="process-card-corners" aria-hidden>
                    <span /><span /><span /><span />
                  </div>

                  <header className="process-card-head">
                    <div className="process-card-icon">
                      <p.Icon size={32} strokeWidth={1.3} />
                    </div>
                    <div className="process-card-meta">
                      <span className="mono process-num">PHASE {p.num}</span>
                      <span className="mono process-duration">{p.duration}</span>
                    </div>
                  </header>

                  <h2 className="process-name">{p.name}</h2>
                  <p className="process-desc">{p.desc}</p>

                  <div className="process-deliverables">
                    <div className="mono dim process-deliverables-label">WHAT YOU GET</div>
                    <ul>
                      {p.deliverables.map((d) => (
                        <li key={d}>
                          <ArrowRight size={12} className="process-deliverable-arrow" />
                          <span>{d}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <ConsultCta />
    </>
  );
}
