import Link from "next/link";

import { get, type Securities } from "@/lib/api";

const LINKS = [
  { href: "/company/THYAO", label: "Company" },
  { href: "/options", label: "Options" },
  { href: "/screener", label: "Screener" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/docs", label: "API", external: true },
];

export async function Nav() {
  const securities = await get<Securities>("/securities");
  const api = process.env.BISTLAB_API_URL ?? "http://127.0.0.1:8000";
  return (
    <header style={{ borderBottom: "1px solid var(--border)", background: "var(--surface-2)" }}>
      <nav
        className="container"
        aria-label="Main menu"
        style={{ padding: "14px 32px", display: "flex", flexWrap: "wrap", alignItems: "center", gap: 28 }}
      >
        <Link href="/" style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--text)", textDecoration: "none" }}>
          <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
            <rect x="1" y="1" width="24" height="24" rx="6" fill="none" stroke="#4C9AFF" strokeWidth="1.5" />
            <path d="M6 17 L11 11 L15 14 L20 7" fill="none" stroke="#4C9AFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span style={{ fontWeight: 700, fontSize: 18, letterSpacing: "-0.02em" }}>bistlab</span>
        </Link>
        <div style={{ display: "flex", gap: 4 }}>
          {LINKS.map((link) =>
            link.external ? (
              <a key={link.href} href={`${api}${link.href}`} className="pill" style={{ border: 0 }}>
                {link.label}
              </a>
            ) : (
              <Link key={link.href} href={link.href} className="pill" style={{ border: 0 }}>
                {link.label}
              </Link>
            ),
          )}
        </div>
        <form action="/company" method="get" style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <label htmlFor="ticker" style={{ position: "absolute", left: -9999 }}>
            Search ticker
          </label>
          <input
            id="ticker"
            name="ticker"
            list="tickers"
            placeholder="Search ticker (THYAO, XU100…)"
            autoComplete="off"
            style={{
              width: 240, height: 40, padding: "0 14px", borderRadius: 8, border: "1px solid var(--border-strong)",
              background: "var(--surface)", color: "var(--text)", font: "inherit",
            }}
          />
          <datalist id="tickers">
            {securities?.results.map((s) => <option key={s.ticker} value={s.ticker} />)}
          </datalist>
          <button type="submit" className="pill" style={{ minHeight: 40, background: "transparent", cursor: "pointer" }}>
            Go
          </button>
        </form>
      </nav>
    </header>
  );
}
