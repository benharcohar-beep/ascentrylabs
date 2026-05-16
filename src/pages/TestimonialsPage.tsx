import { useEffect } from "react";
import { PageHeader } from "./PageHeader";
import { Testimonials } from "../components/Testimonials/Testimonials";
import { ConsultCta } from "./ConsultCta";

export function TestimonialsPage() {
  useEffect(() => {
    document.title = "Testimonials · Ascentry Labs";
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, []);
  return (
    <>
      <PageHeader
        eyebrow="05 — Signal"
        title="Words from people I've worked with."
        sub="From astronauts to enterprise execs to professors. Same throughline: turning ambiguity into systems that ship."
      />
      <Testimonials />
      <ConsultCta />
    </>
  );
}
