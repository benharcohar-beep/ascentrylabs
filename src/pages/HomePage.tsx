import { useEffect } from "react";
import { Hero } from "../components/Hero/Hero";
import { TrustedBy } from "../components/TrustedBy/TrustedBy";
import { StatusBar } from "../components/StatusBar/StatusBar";
import { Consult } from "../components/Consult/Consult";

export function HomePage() {
  useEffect(() => {
    document.title = "Ascentry Labs · AI & Digital Transformation";
  }, []);
  return (
    <>
      <Hero />
      <TrustedBy />
      <StatusBar />
      <Consult />
    </>
  );
}
