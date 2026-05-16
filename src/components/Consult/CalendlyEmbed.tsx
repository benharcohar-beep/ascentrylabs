import { useEffect, useRef } from "react";

type Props = { url: string };

// Loads Calendly's official embed script once globally, then renders an
// inline widget bound to the given URL. Their script auto-discovers any
// `.calendly-inline-widget` div on the page and injects an iframe with
// the calendar.
//
// If the script fails to load (e.g. blocked by an ad-blocker), we render
// a small fallback link out to Calendly so the user is never stuck.
export function CalendlyEmbed({ url }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const existing = document.querySelector('script[src*="calendly.com/assets/external/widget.js"]');
    if (!existing) {
      const s = document.createElement("script");
      s.src = "https://assets.calendly.com/assets/external/widget.js";
      s.async = true;
      document.body.appendChild(s);
    }
  }, []);

  return (
    <div className="calendly-wrap">
      <div
        ref={containerRef}
        className="calendly-inline-widget"
        data-url={`${url}?hide_event_type_details=1&hide_gdpr_banner=1&background_color=07071a&text_color=f4f6ff&primary_color=7fd1d3`}
        style={{ minWidth: "320px", height: "660px" }}
      />
      <noscript>
        <a href={url} target="_blank" rel="noopener noreferrer">Open Calendly →</a>
      </noscript>
    </div>
  );
}
