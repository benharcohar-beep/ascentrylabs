import { useEffect } from "react";
import { PageHeader } from "./PageHeader";
import { Portfolio } from "../components/Portfolio/Portfolio";
import { ConsultCta } from "./ConsultCta";

export function PortfolioPage() {
  useEffect(() => {
    document.title = "Portfolio · Ascentry Labs";
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, []);
  return (
    <>
      <PageHeader
        eyebrow="03 - Portfolio"
        title="Selected work."
        sub="Spanning modeling, agentic systems, digital transformation, and education. Each project shipped under real conditions with real consequences. Click any card for the full case study."
      />
      <Portfolio />
      <ConsultCta />
    </>
  );
}
