import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import "./pagehead.css";

type Props = {
  eyebrow: string;
  title: string;
  sub?: string;
  rightLabel?: string;
};

// Shared page header for the inner routes. Picks up where the home page
// section-heads left off — but with a back-to-home affordance and a
// consistent visual rhythm at the top of each page.
export function PageHeader({ eyebrow, title, sub, rightLabel }: Props) {
  return (
    <header className="pagehead">
      <div className="container">
        <Link to="/" className="pagehead-back">
          <ArrowLeft size={14} />
          <span className="mono">BACK TO HOME</span>
        </Link>
        <div className="pagehead-row">
          <div className="pagehead-main">
            <div className="eyebrow">{eyebrow}</div>
            <h1 className="pagehead-title">{title}</h1>
            {sub && <p className="pagehead-sub">{sub}</p>}
          </div>
          {rightLabel && (
            <div className="pagehead-right mono dim">{rightLabel}</div>
          )}
        </div>
      </div>
    </header>
  );
}
