export type Testimonial = {
  quote: string;
  name: string;
  role: string;
  org: string;
  accent: "gold" | "cyan" | "blue";
};

export const TESTIMONIALS: Testimonial[] = [
  {
    quote: "Sandidge is the perfect blend of innovation and practical implementation. Taking lessons learned from subject matter experts, his approach fuses operational experience with thoughtful algorithm development. The results are products which infuse large sets of data into actionable results, whether implemented by the user or within the operational architecture.",
    name: "D. Olivas, PhD",
    role: "Astronaut (Ret.)",
    org: "NASA",
    accent: "gold",
  },
  {
    quote: "Hunter was my employee for years. He led one of the most transformative changes to our company by assessing each and every department, understanding their processes, and building a centralized data lake and a digital platform that automated over 170 processes. Under his initiative, I feel like we advanced 20 years into the future.",
    name: "K. Plesic",
    role: "Director of Finance",
    org: "Collins Aerospace",
    accent: "cyan",
  },
  {
    quote: "Hunter supported my portfolios for years where he led digital transformation efforts, bringing a rare ability to quickly diagnose process breakdowns and align them with the underlying data and system architecture. He consistently translated complex, ambiguous problems into practical solutions.",
    name: "Anonymous on request",
    role: "C-Suite Leader",
    org: "Aerospace",
    accent: "blue",
  },
  {
    quote: "Hunter brings a unique combination of deep technical expertise and a genuine understanding of how businesses operate and create value. His background in both finance and data science is a rare combination that supercharges value creation.",
    name: "Anonymous on request",
    role: "Senior Director, Accounting",
    org: "Private Equity",
    accent: "gold",
  },
  {
    quote: "Hunter is my go-to for understanding how to turn buzzwords into results. His teams have built me tools that support daily decision makers. He understands what data is critical to operators and delivers it with clarity.",
    name: "J. Spruce",
    role: "Owner",
    org: "Spruce Consulting Group",
    accent: "cyan",
  },
  {
    quote: "Hunter was [at Marquette] consistently rated as our top professor for connecting AI to real business decisions, explaining risks, and helping people see how AI can be used responsibly and effectively. He's a real-life Tony Stark who can educate and explain to people at all levels of technical understanding.",
    name: "J. Wall, PhD",
    role: "Professor",
    org: "Redlands University",
    accent: "blue",
  },
  {
    quote: "Having worked closely with Hunter on the Asteria and Leto programs, I've seen firsthand his ability to transform complex algorithmic concepts into deployed, real-world solutions. He is a tenacious developer who pioneers advanced AI techniques long before they become industry buzzwords. If you have a high-stakes technical challenge and need a partner who prioritizes action over analysis paralysis, I cannot recommend Hunter and Ascentry Labs highly enough.",
    name: "Anonymous on request",
    role: "Technology Discipline Chief",
    org: "Aerospace",
    accent: "gold",
  },
];
