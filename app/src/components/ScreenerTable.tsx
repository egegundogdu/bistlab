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
const QUALITY_ORDER = ["İyi", "Dikkat", "Sorunlu"];
const QUALITY_COLOR: Record<string, string> = {
  İyi: "#4CAF7A",
  Dikkat: "#E0A84A",
  Sorunlu: "#E5735A",
};

function ratingRank(rating: string | null): number {
  const i = rating ? RATINGS.indexOf(rating) : -1;
  return i === -1 ? Number.POSITIVE_INFINITY : i;
}

const INVESTMENT_GRADE = ratingRank("BBB-");
const dash = "—";
const n = (v: number | null, digits = 1) => (v === null ? dash : num(v, digits));
const shortDate = (iso: string | null) => (iso ? `${iso.slice(8, 10)}.${iso.slice(5, 7)}` : dash);

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
    group: "Değerleme",
    label: "PD (mr ₺)",
    title: "Piyasa değeri, milyar TL",
    value: (r) => r.mcap,
    render: (r) => n(r.mcap, 0),
  },
  { id: "pe", group: "Değerleme", label: "F/K", value: (r) => r.pe, render: (r) => n(r.pe), median: "pe" },
  { id: "pb", group: "Değerleme", label: "PD/DD", value: (r) => r.pb, render: (r) => n(r.pb, 2), median: "pb" },
  {
    id: "evEbitda",
    group: "Değerleme",
    label: "FD/FAVÖK",
    value: (r) => r.evEbitda,
    render: (r) => n(r.evEbitda),
    median: "ev_ebitda",
  },
  {
    id: "fcfYield",
    group: "Değerleme",
    label: "FCF get.",
    value: (r) => r.fcfYield,
    render: (r) => (r.fcfYield === null ? dash : pct(r.fcfYield, 1)),
    median: "fcf_yield",
  },
  {
    id: "rating",
    group: "Kredi",
    label: "Not",
    title: "Sentetik not (Damodaran, faiz karşılama) — kredi notu değildir",
    value: (r) => (r.rating ? ratingRank(r.rating) : null),
    render: (r) => r.rating ?? dash,
  },
  { id: "z", group: "Kredi", label: "Z''", title: "Altman Z''", value: (r) => r.z, render: (r) => n(r.z, 2) },
  {
    id: "coverage",
    group: "Kredi",
    label: "Faiz karş.",
    value: (r) => r.coverage,
    render: (r) => n(r.coverage, 2),
  },
  {
    id: "dd",
    group: "Kredi",
    label: "Merton DD",
    title:
      "Temerrüde uzaklık (σ). Risk-nötr 1 yıllık temerrüt olasılığı 8 şirketin hepsinde <%0,01 — ayırt edici bilgi DD'de.",
    value: (r) => r.dd,
    render: (r) => n(r.dd, 2),
  },
  {
    id: "governance",
    group: "KY",
    label: "Skor",
    title: "Kurumsal yönetim: KAP KYBF beyanına dayalı, 10 üzerinden",
    value: (r) => r.governance,
    render: (r) => n(r.governance),
  },
  {
    id: "lastDate",
    group: "Veri",
    label: "Son",
    title: "Son fiyat tarihi",
    value: (r) => r.lastDate,
    render: (r) => shortDate(r.lastDate),
  },
  {
    id: "quality",
    group: "Veri",
    label: "Kalite",
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
    if (va === null) return 1; // boşlar her zaman sonda
    if (vb === null) return -1;
    const cmp =
      typeof va === "number" && typeof vb === "number"
        ? va - vb
        : String(va).localeCompare(String(vb), "tr");
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

  // 2×2: F/K medyanın altı/üstü × yatırım yapılabilir (BBB− ve üstü) / spekülatif
  const medPe = median.pe ?? null;
  const rated = rows.filter((r) => r.pe !== null && medPe !== null && r.rating);
  const cheap = (r: ScreenerRow) => (r.pe as number) < (medPe as number);
  const strong = (r: ScreenerRow) => ratingRank(r.rating) <= INVESTMENT_GRADE;

  return (
    <div className="grid">
      <section className="card" style={{ gridColumn: "1 / -1" }}>
        <div className="card-head">
          <h2>8 şirket, 4 mercek</h2>
          <span className="tag">Değerleme · Kredi · KY · Veri</span>
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
                <th style={{ ...cell, textAlign: "left" }}>{head("ticker", "Kod")}</th>
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
                    <Link href={`/sirket/${r.ticker}`} className="mono" style={{ color: "var(--text)" }}>
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
                          ? `Son kredi dönemi ${r.period}`
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
                  Medyan
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
          Çarpanlar son yıllık finansallardan, raporlama para biriminde. Kredi sütunları{" "}
          {latestPeriod || "son"} dönemi; * işaretli notlar daha eski döneme ait (üzerine gel). Sentetik
          not ve Merton kredi notu değildir. KY skoru yalnızca KYBF&apos;si indirilmiş şirketlerde var.
          Kalite hücresinin üzerine gel: ayrıntı.
        </p>
      </section>

      <section className="card" style={{ gridColumn: "1 / -1" }}>
        <div className="card-head">
          <h2>Kesişimler: F/K × kredi</h2>
          <span className="tag">Kural tabanlı · sinyal değil</span>
        </div>
        <dl className="stats">
          <Quadrant
            title="Ucuz ve sağlam"
            rows={rated.filter((r) => cheap(r) && strong(r))}
            hint="Düşük çarpan, yatırım yapılabilir not: ya fırsat ya da piyasanın gördüğü başka bir risk (ters DCF'ye bak)."
          />
          <Quadrant
            title="Ucuz ama zayıf"
            rows={rated.filter((r) => cheap(r) && !strong(r))}
            hint="Düşük çarpan, spekülatif not: ucuzluk büyük ihtimalle kredi riskinin fiyatı."
          />
          <Quadrant
            title="Pahalı ve sağlam"
            rows={rated.filter((r) => !cheap(r) && strong(r))}
            hint="Yüksek çarpan, sağlam bilanço: piyasa kalite ya da büyüme primi ödüyor."
          />
          <Quadrant
            title="Pahalı ve zayıf"
            rows={rated.filter((r) => !cheap(r) && !strong(r))}
            hint="Yüksek çarpan, spekülatif not: kâr geçici düşmüş olabilir ya da model sınırı (BIMAS: kira faizi karşılamayı düşürür)."
          />
        </dl>
        <p className="note" style={{ marginBottom: 0 }}>
          Eşikler: F/K medyanı ({n(medPe)}) ve yatırım yapılabilir not sınırı BBB−. Sentetik not faiz
          karşılamadan türetilir; kira yükü yüksek perakendecilerde (TFRS 16) notu olduğundan düşük
          gösterebilir.
        </p>
      </section>
    </div>
  );
}
