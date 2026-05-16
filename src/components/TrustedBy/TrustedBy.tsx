import { motion } from "framer-motion";
import "./trusted.css";

// "Trusted by" strip - a clean horizontal row of client/org names with a
// subtle scan line. Pure text (no logos required) so it works without
// hosting external brand assets, and it's intentionally minimal so it
// reads as proof, not as advertising.

const ORGS = [
  "NASA",
  "Collins Aerospace",
  "United Technologies",
  "Marquette · NMDSI",
  "U.S. Department of Defense",
  "Firefly Aerospace",
  "U.K. Defence",
];

export function TrustedBy() {
  return (
    <motion.section
      className="trusted"
      initial={{ opacity: 0 }}
      whileInView={{ opacity: 1 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.6 }}
      aria-label="Selected clients"
    >
      <div className="container trusted-inner">
        <div className="trusted-lead">
          <span className="trusted-divider" />
          <span className="mono">TRUSTED BY</span>
          <span className="trusted-divider" />
        </div>
        <div className="trusted-row">
          {ORGS.map((o, i) => (
            <span key={o} className="trusted-org" style={{ animationDelay: `${-i * 1.4}s` }}>
              {o}
            </span>
          ))}
        </div>
      </div>
    </motion.section>
  );
}
