import { Starfield } from "./Starfield";
import "./background.css";

export function Background() {
  return (
    <div className="bg-root" aria-hidden>
      <div className="bg-base" />
      <div className="bg-nebula nebula-a" />
      <div className="bg-nebula nebula-b" />
      <div className="bg-nebula nebula-c" />
      <Starfield />
      <div className="bg-grid" />
      <div className="bg-vignette" />
      <div className="bg-scanline" />
    </div>
  );
}
