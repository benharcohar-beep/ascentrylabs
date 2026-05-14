export type Category = { id: string; label: string; color: string };
export type Project = {
  cat: string;
  code: string;
  title: string;
  client: string;
  desc: string;
  metrics: [string, string][];
  tags: string[];
  featured?: boolean;
};

export const CATEGORIES: Category[] = [
  { id: "dt", label: "Digital Transformation", color: "#7fd1d3" },
  { id: "ml", label: "Modeling", color: "#5b9dd9" },
  { id: "ag", label: "Agentic Systems", color: "#ffc000" },
  { id: "ed", label: "Education", color: "#a8bbbf" },
];

export const PROJECTS: Project[] = [
  {
    cat: "ag",
    code: "AG.01",
    title: "Asteria Spacesuit AI Copilot",
    client: "NASA · xEVAS Next-Generation Spacesuit",
    desc: "Led the technical development of an agentic AI copilot designed for next-generation spacesuits, enabling astronauts to access real-time telemetry, execute mission procedures, and retrieve domain knowledge through a natural language interface. The system was architected to operate in low-compute, resource-constrained environments, supporting autonomous decision-making during extravehicular activities.",
    metrics: [["Domain", "Space Exploration"], ["Core technology", "Edge AI"], ["Objective", "Earth-independence"]],
    tags: ["Multi-Agent", "Embedded AI", "Voice Interface"],
    featured: true,
  },
  {
    cat: "ml",
    code: "ML.01",
    title: "Leto™ Life Support Intelligence",
    client: "NASA · International Space Station",
    desc: "Led the technical design and full development of an AI-driven analytics platform for monitoring the Environmental Control and Life Support System (ECLSS) aboard the International Space Station. The system provided continuous health monitoring, anomaly detection, and predictive failure insight across multiple life-support subsystems, directly supporting astronaut safety and mission continuity.",
    metrics: [["Domain", "Space Exploration"], ["Modeling", "AutoML"], ["Impact", "Safer Astronauts"]],
    tags: ["Anomaly Detection", "Predictive Maintenance", "AutoML"],
    featured: true,
  },
  {
    cat: "ml",
    code: "ML.02",
    title: "Adaptive Thermal Control for EVA Systems",
    client: "NASA · xEVAS Spacesuit Program",
    desc: "Developed a machine learning–driven control system to automatically regulate the liquid cooling and ventilation garment to be worn by astronauts during extravehicular activities. The system used a digital twin of astronaut physiology to predict thermal state and dynamically adjust cooling flow rates, reducing reliance on manual intervention and improving consumable efficiency.",
    metrics: [["Domain", "Space Exploration"], ["Modeling", "Supervised ML"], ["Impact", "Safer Astronauts"]],
    tags: ["Digital Twin", "Time-Series", "Control Systems"],
  },
  {
    cat: "ml",
    code: "ML.03",
    title: "Advanced Analytics & Algorithm Development",
    client: "U.S./U.K. Defense · NASA Artemis",
    desc: "Led and contributed to a range of advanced data science and algorithm development efforts for confidential defense and space applications. Work focused on algorithm development, statistical analysis, and building analytical and simulation-based systems to support mission-critical decision-making in complex, data-constrained environments.",
    metrics: [["Domain", "Space & Defense"], ["Modeling", "Multiple"], ["Impact", "Confidential"]],
    tags: ["Machine Learning", "Simulation", "Statistical Diagnostics"],
  },
  {
    cat: "ml",
    code: "ML.04",
    title: "Mirari Digital Twin & Simulation Engine",
    client: "CitizenDS · Internal Product",
    desc: "Designed and prototyped a system for building digital twins from first principles, enabling users to define relationships, equations, and distributions to generate fully simulated datasets and system behavior. The platform translated structured logic into executable simulations, producing both synthetic data and system-level insights.",
    metrics: [["Domain", "Multiple"], ["Modeling", "Monte Carlo"], ["Impact", "Enhanced ML"]],
    tags: ["Digital Twin", "Stochastic Modeling", "Sensitivity Analysis"],
  },
  {
    cat: "ml",
    code: "ML.05",
    title: "Independent Research in ML & Statistical Modeling",
    client: "Independent · Doctoral Dissertation Proposal",
    desc: "Conducted independent research focused on developing machine learning and statistical methods for complex, high-dimensional, and non-stationary data environments. The work centers on improving detection, interpretation, and simulation of system behavior where traditional parametric assumptions fail.",
    metrics: [["Domain", "Multiple"], ["Modeling", "Multiple"], ["Impact", "Novel Algorithms"]],
    tags: ["Anomaly Detection", "Time-Series", "Prediction"],
  },
  {
    cat: "ag",
    code: "AG.02",
    title: "CitizenDS™ Guided Analytics",
    client: "CitizenDS · Production",
    desc: "Designed and developed a desktop-based analytics platform that enables users to explore, analyze, and understand data through a fully guided, no-code experience. Combines automated exploratory data analysis with agentic talk-to-your-data capabilities, allowing users to generate insights, visualizations, and explanations through either structured workflows or natural language interaction.",
    metrics: [["Domain", "Enterprise"], ["Core technology", "Talk-To-Your-Data"], ["Objective", "Time-To-First-Insight"]],
    tags: ["Business Intelligence", "Auto-EDA", "Data Visualization"],
  },
  {
    cat: "ag",
    code: "AG.03",
    title: "Numbra Agentic Excel Modeling",
    client: "Straylight",
    desc: "Designed and built an agentic Excel add-in enabling users to interact with complex spreadsheets through natural language. The system translated user intent into structured actions, allowing full creation, modification, and analysis of financial models, including fully automated discounted cash flow and equity modeling.",
    metrics: [["Domain", "Enterprise"], ["Core technology", "Graph Reasoning"], ["Objective", "Automated Modeling"]],
    tags: ["Agentic AI", "Spreadsheet Intelligence", "Excel Add-In"],
  },
  {
    cat: "ag",
    code: "AG.04",
    title: "Agentic RAG Platform",
    client: "Straylight",
    desc: "Designed and built an agentic retrieval-augmented generation platform enabling users to create private, self-contained AI knowledge systems. The platform allowed organizations to ingest proprietary data, query it through natural language, and receive responses with verifiable source citations, all within a fully controlled, locally deployable environment.",
    metrics: [["Domain", "Enterprise"], ["Core technology", "Knowledge Retrieval"], ["Objective", "Traceable Insights"]],
    tags: ["Personal Assistant", "Public/Local LLM", "Citation-Driven"],
  },
  {
    cat: "ag",
    code: "AG.05",
    title: "Synfata Agentic Synthetic Data Engine",
    client: "CitizenDS · Internal Product",
    desc: "Designed and built an agentic synthetic data generation system capable of producing high-fidelity datasets that preserve realistic distributions and relationships. The platform allows users to describe a dataset in natural language and generates structured data that behaves like real-world data under analysis.",
    metrics: [["Domain", "Enterprise"], ["Core technology", "Copula Modeling"], ["Objective", "Synthetic Training Data"]],
    tags: ["Synthetic Data", "Agentic Tools", "Statistics"],
  },
  {
    cat: "dt",
    code: "DT.01",
    title: "Single Source Platform",
    client: "United Technologies Aerospace Systems",
    desc: "Led the design and deployment of an enterprise-wide data and analytics platform across four U.S. manufacturing sites supporting a multi-billion-dollar portfolio. The initiative unified fragmented data systems into a single operational layer, enabling real-time reporting, forecasting, and cross-functional decision-making at scale.",
    metrics: [["Reports run", "35,000+"], ["SG&A reduction", "> 15%"], ["Manual processes cut", "> 85%"]],
    tags: ["Data Lake", "ETL", "Forecasting"],
  },
  {
    cat: "dt",
    code: "DT.02",
    title: "FactrEye Smart Factory Platform",
    client: "Collins Aerospace",
    desc: "Designed and deployed a real-time operational intelligence platform for a smart factory environment, providing end-to-end visibility into production flow, constraints, and performance drivers. The system tracked thousands of active assemblies and enabled production, quality, and planning teams to monitor, diagnose, and correct issues as they occurred.",
    metrics: [["On-time delivery", "+ 40%"], ["Plant locations", "4"], ["Assemblies daily", "Thousands"]],
    tags: ["Andon", "Real-Time", "Data Visualization"],
  },
  {
    cat: "dt",
    code: "DT.03",
    title: "Enterprise Process Automation & Standardization",
    client: "United Technologies Aerospace Systems",
    desc: "Led a multi-year initiative to standardize, optimize, and automate core business processes across all functional departments within a multi-billion-dollar portfolio. The effort combined deep process re-engineering with targeted automation, transforming how analysts operated day-to-day and shifting capacity from manual work to higher-value analysis.",
    metrics: [["Departments", "8"], ["Tools built", "Hundreds"], ["Hours saved", "Tens of Thousands"]],
    tags: ["Process Mapping", "VBA Automation", "SAP ERP"],
  },
  {
    cat: "dt",
    code: "DT.04",
    title: "Rapid Pricing Platform",
    client: "United Technologies Aerospace Systems",
    desc: "Designed and deployed an enterprise pricing platform to transform the government RFP response process, replacing a fragmented, manual estimation workflow with a real-time, integrated system. Enabled rapid generation, consolidation, and analysis of pricing inputs across hundreds of contributors, significantly accelerating bid development and improving decision quality under tight deadlines.",
    metrics: [["Time to first price", "−60%"], ["Savings", "Millions"], ["Human error", "> 85% ↓"]],
    tags: ["Pricing", "Workflow Automation", "Scenario Analysis"],
  },
  {
    cat: "ed",
    code: "ED.01",
    title: "Fintech: Applied AI & BI Program",
    client: "Marquette University · NMDSI",
    desc: "Designed and led a top-tier applied AI and FinTech program focused on translating data, analytics, and machine learning into real-world decision-making. In parallel, co-directed a multi-university data science initiative, aligning academic programs with industry needs and advancing applied AI education at scale.",
    metrics: [["Placement", "98%"], ["Satisfaction", "97%"], ["Students impacted", "Hundreds"]],
    tags: ["Curriculum Design", "Leadership", "Industry Bridge"],
  },
];
