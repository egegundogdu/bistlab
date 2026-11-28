"use client";

import Link from "next/link";
import { useState, type CSSProperties } from "react";

import { num, pct } from "@/lib/format";

export type ScreenerRow = {
  ticker: string;
  currency: string;
  mcap: number | null;
  pe: number | null;
  pb: number | null;
  evEbitda: number | null;
  fcfYield: number | null;
  period: string | null;
  rating: string | null;
  z: number | null;
  coverage: number | null;
  dd: number | null;
  pd: number | null;
  governance: number | null;
  lastDate: string | null;
  quality: string | null;
  qualityNote: string | null;
};

const RATINGS = [
  "AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-",
  "BB+", "BB", "BB-", "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "D",
];
const QUALITY_ORDER = ["Good", "Warning", "Problem"];
const QUALITY_COLOR: Record<string, string> = {
  Good: "#4CAF7A",
  Warning: "#E0A84A",
  Problem: "#E5735A",
};
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function ratingRank(rating: string | null): number {
  const i = rating ? RATINGS.indexOf(rating) : -1;
  return i === -1 ? Number.POSITIVE_INFINITY : i;
}

const INVESTMENT_GRADE = ratingRank("BBB-");
const dash = "—";
const n = (v: number | null, digits = 1) => (v === null ? dash : num(v, digits));
const shortDate = (iso: string | null) =>
  iso ? `${Number(iso.slice(8, 10))} ${MONTHS[Number(iso.slice(5, 7)) - 1] ?? ""}` : dash;

type Column = {
  id: string;
  group: string;
  label: string;
  title?: string;
  value: (r: ScreenerRow) => number | string | null;
  render: (r: ScreenerRow) => string;
  median?: string;
};

const COLUMNS: Column[] = [
  {
    id: "mcap",
    group: "Valuation",
    label: "Mkt cap",
    title: "Market capitalisation, billion TRY",
    value: (r) => r.mcap,
    render: (r) => n(r.mcap, 0),
  },
  { id: "pe", group: "Valuation", label: "P/E", value: (r) => r.pe, render: (r) => n(r.pe), median: "pe" },
  { id: "pb", group: "Valuation", label: "P/B", value: (r) => r.pb, render: (r) => n(r.pb, 2), median: "pb" },
  {
    id: "evEbitda",
    group: "Valuation",
    label: "EV/EBITDA",
    value: (r) => r.evEbitda,
    render: (r) => n(r.evEbitda),
    median: "ev_ebitda",
  },
  {
    id: "fcfYield",
    group: "Valuation",
    label: "FCF yield",
    value: (r) => r.fcfYield,
    render: (r) => (r.fcfYield === null ? dash : pct(r.fcfYield, 1)),
    median: "fcf_yield",
  },
  {
    id: "rating",
    group: "Credit",
    label: "Rating",
    title: "Synthetic rating (Damodaran, interest coverage) — not a credit rating",
    value: (r) => (r.rating ? ratingRank(r.rating) : null),
    render: (r) => r.rating ?? dash,
  },
  { id: "z", group: "Credit", label: "Z''", title: "Altman Z''", value: (r) => r.z, render: (r) => n(r.z, 2) },
  {
    id: "coverage",
    group: "Credit",
    label: "Int. cover",
    title: "Interest coverage",
    value: (r) => r.coverage,
    render: (r) => n(r.coverage, 2),
  },
  {
    id: "dd",
    group: "Credit",
    label: "Merton DD",
    title:
      "Distance to default (σ). The risk-neutral one-year default probability is below 0.01% for all eight companies — the information is in DD.",
    value: (r) => r.dd,
    render: (r) => n(r.dd, 2),
  },
  {
    id: "governance",
    group: "Gov.",
    label: "Score",
    title: "Corporate governance: based on the KAP disclosure, out of 10",
    value: (r) => r.governance,
    render: (r) => n(r.governance),
  },
  {
    id: "lastDate",
    group: "Data",
    label: "Last",
    title: "Last price date",
    value: (r) => r.lastDate,
    render: (r) => shortDate(r.lastDate),
  },
  {
    id: "quality",
    group: "Data",
    label: "Quality",
    value: (r) => (r.quality ? QUALITY_ORDER.indexOf(r.quality) : null),
    render: (r) => r.quality ?? dash,
  },
];

const cell: CSSProperties = {
  padding: "9px 8px",
  borderBottom: "1px solid var(--border)",
  textAlign: "right",
  whiteSpace: "nowrap",
};

const headButton: CSSProperties = {
  cursor: "pointer",
  border: 0,
  background: "transparent",
  color: "inherit",
  font: "inherit",
  padding: "2px 4px",
};

function groups(): { name: string; span: number }[] {
  const out: { name: string; span: number }[] = [];
  for (const c of COLUMNS) {
    const prev = out[out.length - 1];
    if (prev && prev.name === c.group) prev.span += 1;
    else out.push({ name: c.group, span: 1 });
  }
  return out;
}

function Quadrant({ title, rows, hint }: { title: string; rows: ScreenerRow[]; hint: string }) {
  return (
    <div className="stat">
      <dt>{title}</dt>
      <dd className="mono">{rows.map((r) => r.ticker).join(", ") || dash}</dd>
      <dd className="note" style={{ margin: 0, fontSize: 13, fontWeight: 400 }}>
        {hint}
      </dd>
    </div>
  );
}

export function ScreenerTable({
  rows,
  median,
}: {
  rows: ScreenerRow[];
  median: Record<string, number | null>;
}) {
  const [sortId, setSortId] = useState("ticker");
  const [asc, setAsc] = useState(true);

  const column = COLUMNS.find((c) => c.id === sortId);
  const sorted = [...rows].sort((a, b) => {
    const va = column ? column.value(a) : a.ticker;
    const vb = column ? column.value(b) : b.ticker;
    if (va === null && vb === null) return 0;
    if (va === null) return 1; // empty values always last
    if (vb === null) return -1;
    const cmp =
      typeof va === "number" && typeof vb === "number"
        ? va - vb
        : String(va).localeCompare(String(vb), "en");
    return asc ? cmp : -cmp;
  });

  const sortBy = (id: string) => {
    if (id === sortId) setAsc(!asc);
    else {
      setSortId(id);
      setAsc(true);
    }
  };
  const head = (id: string, label: string) => (
    <button
      type="button"
      onClick={() => sortBy(id)}
      style={{ ...headButton, fontWeight: id === sortId ? 700 : 500 }}
    >
      {label}
      {id === sortId ? (asc ? " ▲" : " ▼") : ""}
    </button>
  );

  const latestPeriod = rows.reduce<string>((m, r) => (r.period && r.period > m ? r.period : m), "");
  const isOld = (r: ScreenerRow) => r.period !== null && r.period < latestPeriod;

  // 2×2: P/E below/above the median × investment grade (BBB− and above) / speculative
  const medPe = median.pe ?? null;
  const rated = rows.filter((r) => r.pe !== null && medPe !== null && r.rating);
  const cheap = (r: ScreenerRow) => (r.pe as number) < (medPe as number);
  const strong = (r: ScreenerRow) => ratingRank(r.rating) <= INVESTMENT_GRADE;

  return (
    <div className="grid">
      <section className="card" style={{ gridColumn: "1 / -1" }}>
        <div className="card-head">
          <h2>{rows.length} companies, 4 lenses</h2>
          <span className="tag">Valuation · Credit · Governance · Data</span>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr>
                <th style={{ ...cell, textAlign: "left" }} />
                {groups().map((g) => (
                  <th
                    key={g.name}
                    colSpan={g.span}
                    className="note"
                    style={{ ...cell, textAlign: "center", fontWeight: 500 }}
                  >
                    {g.name}
                  </th>
                ))}
              </tr>
              <tr>
                <th style={{ ...cell, textAlign: "left" }}>{head("ticker", "Ticker")}</th>
                {COLUMNS.map((c) => (
                  <th key={c.id} style={cell} title={c.title}>
                    {head(c.id, c.label)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={r.ticker}>
                  <td style={{ ...cell, textAlign: "left" }}>
                    <Link href={`/company/${r.ticker}`} className="mono" style={{ color: "var(--text)" }}>
                      {r.ticker}
                    </Link>{" "}
                    <span className="note">{r.currency}</span>
                  </td>
                  {COLUMNS.map((c) => {
                    const old = c.id === "rating" && isOld(r);
                    const title =
                      c.id === "quality"
                        ? (r.qualityNote ?? undefined)
                        : old
                          ? `Last credit period ${r.period}`
                          : undefined;
                    return (
                      <td
                        key={c.id}
                        className="mono"
                        title={title}
                        style={{
                          ...cell,
                          color: c.id === "quality" && r.quality ? QUALITY_COLOR[r.quality] : undefined,
                        }}
                      >
                        {c.render(r)}
                        {old ? "*" : ""}
                      </td>
                    );
                  })}
                </tr>
              ))}
              <tr>
                <td style={{ ...cell, textAlign: "left" }} className="note">
                  Median
                </td>
                {COLUMNS.map((c) => {
                  const m = c.median ? (median[c.median] ?? null) : null;
                  let text = "";
                  if (c.median) {
                    if (c.id === "fcfYield") text = m === null ? dash : pct(m, 1);
                    else text = n(m, c.id === "pb" ? 2 : 1);
                  }
                  return (
                    <td key={c.id} className="mono note" style={cell}>
                      {text}
                    </td>
                  );
                })}
              </tr>
            </tbody>
          </table>
        </div>
        <p className="note">
          Market cap in billion TRY. Multiples from the last annual financials, in the reporting
          currency. Credit columns use the {latestPeriod || "latest"} period; ratings marked * are
          from an earlier period (hover). Synthetic ratings and Merton are not credit ratings.
          Governance scores exist only where the KAP form has been loaded. Hover a quality cell for
          details.
        </p>
      </section>

      <section className="card" style={{ gridColumn: "1 / -1" }}>
        <div className="card-head">
          <h2>Intersections: P/E × credit</h2>
          <span className="tag">Rule-based · not a signal</span>
        </div>
        <dl className="stats">
          <Quadrant
            title="Cheap and solid"
            rows={rated.filter((r) => cheap(r) && strong(r))}
            hint="Low multiple, investment-grade rating: either an opportunity or a risk the market sees elsewhere (check the reverse DCF)."
          />
          <Quadrant
            title="Cheap but weak"
            rows={rated.filter((r) => cheap(r) && !strong(r))}
            hint="Low multiple, speculative rating: the discount is most likely the price of credit risk."
          />
          <Quadrant
            title="Expensive and solid"
            rows={rated.filter((r) => !cheap(r) && strong(r))}
            hint="High multiple, solid balance sheet: the market is paying a quality or growth premium."
          />
          <Quadrant
            title="Expensive and weak"
            rows={rated.filter((r) => !cheap(r) && !strong(r))}
            hint="High multiple, speculative rating: earnings may be temporarily depressed, or it is a model limitation (BIMAS: lease interest lowers coverage)."
          />
        </dl>
        <p className="note" style={{ marginBottom: 0 }}>
          Thresholds: the P/E median ({n(medPe)}) and the investment-grade line at BBB−. The synthetic
          rating is derived from interest coverage; for lease-heavy retailers (IFRS 16) it can
          understate credit quality.
        </p>
      </section>
    </div>
  );
}
