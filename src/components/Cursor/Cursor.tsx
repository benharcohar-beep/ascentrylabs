import { useEffect, useRef, useState } from "react";
import "./cursor.css";

export function Cursor() {
  const dotRef = useRef<HTMLDivElement>(null);
  const ringRef = useRef<HTMLDivElement>(null);
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    // Skip on touch / no fine pointer
    const fine = window.matchMedia("(pointer: fine)").matches;
    if (!fine) return;
    setEnabled(true);
    document.body.classList.add("has-custom-cursor");

    let mx = window.innerWidth / 2;
    let my = window.innerHeight / 2;
    let rx = mx;
    let ry = my;
    let raf = 0;

    const onMove = (e: MouseEvent) => {
      mx = e.clientX;
      my = e.clientY;
    };
    const onOver = (e: MouseEvent) => {
      const t = e.target as HTMLElement | null;
      if (!t) return;
      const interactive = t.closest("a, button, [role='button'], input, textarea, [data-cursor='hover']");
      if (ringRef.current) {
        ringRef.current.classList.toggle("is-hover", !!interactive);
      }
    };
    const onDown = () => {
      ringRef.current?.classList.add("is-down");
    };
    const onUp = () => {
      ringRef.current?.classList.remove("is-down");
    };

    function tick() {
      // Smooth lerp toward target
      rx += (mx - rx) * 0.18;
      ry += (my - ry) * 0.18;

      if (dotRef.current) {
        dotRef.current.style.transform = `translate3d(${mx}px, ${my}px, 0) translate(-50%, -50%)`;
      }
      if (ringRef.current) {
        ringRef.current.style.transform = `translate3d(${rx}px, ${ry}px, 0) translate(-50%, -50%)`;
      }
      raf = requestAnimationFrame(tick);
    }

    // Hide the cursor when the mouse genuinely leaves the document, not
    // when window focus is lost - Chrome doesn't reliably fire `focus`
    // when you switch back from DevTools, which previously left the
    // cursor permanently invisible.
    const onLeaveDoc = (e: MouseEvent) => {
      // mouseleave on document fires when the cursor exits the window
      if (!e.relatedTarget) {
        if (dotRef.current) dotRef.current.style.opacity = "0";
        if (ringRef.current) ringRef.current.style.opacity = "0";
      }
    };
    const onEnterDoc = () => {
      if (dotRef.current) dotRef.current.style.opacity = "1";
      if (ringRef.current) ringRef.current.style.opacity = "1";
    };

    window.addEventListener("mousemove", onMove, { passive: true });
    document.addEventListener("mouseover", onOver, { passive: true });
    window.addEventListener("mousedown", onDown);
    window.addEventListener("mouseup", onUp);
    document.addEventListener("mouseleave", onLeaveDoc);
    document.addEventListener("mouseenter", onEnterDoc);
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseover", onOver);
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("mouseup", onUp);
      document.removeEventListener("mouseleave", onLeaveDoc);
      document.removeEventListener("mouseenter", onEnterDoc);
      document.body.classList.remove("has-custom-cursor");
    };
  }, []);

  if (!enabled) return null;

  return (
    <>
      <div ref={dotRef} className="cursor-dot" aria-hidden />
      <div ref={ringRef} className="cursor-ring" aria-hidden>
        <span className="cursor-tick t" />
        <span className="cursor-tick r" />
        <span className="cursor-tick b" />
        <span className="cursor-tick l" />
      </div>
    </>
  );
}
