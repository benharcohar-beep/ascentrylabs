export type Service = {
  cat: string;
  title: string;
  desc: string;
  bullets: string[];
  duration: string;
  color: string;
  icon: "compass" | "map" | "users" | "code" | "graduation" | "mic";
};

export const SERVICES: Service[] = [
  {
    cat: "ASSESSMENT",
    title: "AI Readiness Assessment",
    desc: "Rapid evaluation of your current data, tools, and processes. We identify where AI and ML can (and cannot) create value.",
    bullets: ["Stakeholder interviews", "Opportunity discovery and roadmap", "Prioritized next steps"],
    duration: "2–4 weeks",
    color: "#7fd1d3",
    icon: "compass",
  },
  {
    cat: "STRATEGY",
    title: "Digital Strategy & Transformation",
    desc: "Deep dive into operations, data flows, and decision processes. Defines architecture for data and a structured roadmap for execution.",
    bullets: ["Process mapping", "Architecture design", "Execution roadmap"],
    duration: "4–10 weeks",
    color: "#ffc000",
    icon: "map",
  },
  {
    cat: "ADVISORY",
    title: "AI & Digital Transformation Retainer",
    desc: "Ongoing strategic partnership as you implement and scale. Helps avoid costly missteps and keeps efforts aligned to outcomes.",
    bullets: ["Assessments, strategy, and development", "Active partner or interim officer", "Use as needed"],
    duration: "Monthly retainer",
    color: "#5b9dd9",
    icon: "users",
  },
  {
    cat: "BUILD",
    title: "Custom Development",
    desc: "When the right tool doesn't exist off the shelf, we build it. Bespoke software, AI systems, and automation that are designed around your problem.",
    bullets: ["You own the IP", "Built to solve your problem", "Production-grade handoff"],
    duration: "Project-based",
    color: "#c47ad9",
    icon: "code",
  },
  {
    cat: "EDUCATION",
    title: "Executive AI Education",
    desc: "Private sessions for leadership teams. Clarifies what AI is, what it isn't, and where it fits in your business. University-grade content with no hype or jargon, just relevant content.",
    bullets: ["Half-day intensives", "Full-day deep dives", "Specific topics upon request"],
    duration: "Half-day to full-day",
    color: "#a8bbbf",
    icon: "graduation",
  },
  {
    cat: "SPEAKING",
    title: "Keynote Speaking",
    desc: "Talks on AI, data, and decision systems. Tailored to executive, industry, or technical audiences. Practical application over hype.",
    bullets: ["Conference keynotes", "Private corporate events", "Executive briefings"],
    duration: "45–90 min",
    color: "#3aa39f",
    icon: "mic",
  },
];
