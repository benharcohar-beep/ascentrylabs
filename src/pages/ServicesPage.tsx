import { useEffect } from "react";
import { PageHeader } from "./PageHeader";
import { Services } from "../components/Services/Services";
import { ConsultCta } from "./ConsultCta";

export function ServicesPage() {
  useEffect(() => {
    document.title = "Services · Ascentry Labs";
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, []);
  return (
    <>
      <PageHeader
        eyebrow="02 - Services"
        title="Six ways we work together."
        sub="From a single readiness sprint to a long-term technical partner. Pick a starting point - we shape the engagement to fit."
        rightLabel="[ S.01 - S.06 ]"
      />
      <Services />
      <ConsultCta />
    </>
  );
}
