import { useEffect } from "react";
import { PageHeader } from "./PageHeader";
import { About } from "../components/About/About";
import { ConsultCta } from "./ConsultCta";

export function AboutPage() {
  useEffect(() => {
    document.title = "About · Ascentry Labs";
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, []);
  return (
    <>
      <PageHeader
        eyebrow="04 — About"
        title="A part of the AI landscape most people never see."
        sub="Ascentry Labs is led by Hunter Sandidge — a builder who has spent his career operating where the stakes are highest: spacesuits, factories, and balance sheets. We bring that same discipline to every engagement."
        rightLabel="[ A.01 ]"
      />
      <About />
      <ConsultCta />
    </>
  );
}
