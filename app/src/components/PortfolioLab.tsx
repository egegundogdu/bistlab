"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type CSSProperties } from "react";

import type { FrontierPoint, PortfolioRisk } from "@/lib/api";
import { num, pct } from "@/lib/format";

const API = process.env.NEXT_PUBLIC_BISTLAB_API_URL ?? "http://127.0.0.1:8000";
const ERROR_COLOR = "#E5735A";
const BLUE = "#4C9AFF";
const GREEN = "#4CAF7A";
const AMBER = "#E0A84A";
const ACTIVE = "#2B4A75";

/** İşaretsiz oran (σ, faiz, VaR); getiri ve Sharpe için işaretli pct/num kullanılır. */
const rate = (v: number, digits = 1): string => pct(v, digits).replace("+", "");

const selectStyle: CSSProperties = {
  height: 36,
  padding: "0 10px",
  borderRadius: 8,
  border: "1px solid var(--border-strong)",
  background: "var(--surface)",
  color: "var(--text)",
  font: "inherit",
};

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="stat">
      <dt>{label}</dt>
      <dd className="mono">{value}</dd>
      {hint ? (
        <dd className="note" style={{ margin: 0, fontSize: 13, fontWeight: 400 }}>
          {hint}
        </dd>
      ) : null}
    </div>
  );
}

/* ---------------------------------------------------------------- etkin sınır */

function Frontier({ d }: { d: PortfolioRisk }) {
  const W = 640;
  const H = 340;
  const L = 52;
  const R = 16;
  const T = 16;
  const B = 40;
  const special: { p: FrontierPoint; label: string; color: string }[] = [
    { p: d.current, label: "Senin portföyün", color: BLUE },
    { p: d.min_variance, label: "Min varyans", color: GREEN },
    { p: d.max_sharpe, label: "Maks Sharpe", color: AMBER },
  ];
  const xs = [...d.frontier.map((p) => p.volatility), ...d.asset_volatility, d.current.volatility];
  const ys = [
    ...d.frontier.map((p) => p.expected_return),
    ...d.asset_return,
    d.current.expected_return,
    d.risk_free,
  ];
  const x0 = Math.max(0, Math.min(...xs) * 0.9);
  const x1 = Math.max(...xs) * 1.05;
  const y0 = Math.min(...ys) - 0.05;
  const y1 = Math.max(...ys) + 0.05;
  const sx = (v: number) => L + ((v - x0) / (x1 - x0)) * (W - L - R);
  const sy = (v: number) => H - B - ((v - y0) / (y1 - y0)) * (H - T - B);
  const ticks = (a: number, b: number) => [0, 1, 2, 3, 4].map((i) => a + ((b - a) * i) / 4);
  const line = d.frontier.map((p) => `${sx(p.volatility)},${sy(p.expected_return)}`).join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", color: "var(--text)" }}>
      {ticks(y0, y1).map((v) => (
        <g key={`y${v}`}>
          <line x1={L} x2={W - R} y1={sy(v)} y2={sy(v)} stroke="currentColor" opacity={0.08} />
          <text x={L - 6} y={sy(v) + 4} fontSize={11} textAnchor="end" fill="currentColor" opacity={0.6}>
            {rate(v, 0)}
          </text>
        </g>
      ))}
      {ticks(x0, x1).map((v) => (
        <text
          key={`x${v}`}
          x={sx(v)}
          y={H - B + 18}
          fontSize={11}
          textAnchor="middle"
          fill="currentColor"
          opacity={0.6}
        >
          {rate(v, 0)}
        </text>
      ))}
      <text x={(L + W - R) / 2} y={H - 6} fontSize={11} textAnchor="middle" fill="currentColor" opacity={0.6}>
        Oynaklık (σ, yıllık)
      </text>
      <text
        x={14}
        y={(T + H - B) / 2}
        fontSize={11}
        textAnchor="middle"
        fill="currentColor"
        opacity={0.6}
        transform={`rotate(-90 14 ${(T + H - B) / 2})`}
      >
        Beklenen getiri (μ)
      </text>

      <line
        x1={L}
        x2={W - R}
        y1={sy(d.risk_free)}
        y2={sy(d.risk_free)}
        stroke={ERROR_COLOR}
        strokeDasharray="4 4"
        opacity={0.7}
      />
      <text x={W - R - 4} y={sy(d.risk_free) - 6} fontSize={11} textAnchor="end" fill={ERROR_COLOR}>
        risksiz faiz {rate(d.risk_free, 0)}
      </text>

      <polyline points={line} fill="none" stroke={BLUE} strokeWidth={2} opacity={0.5} />

      {d.tickers.map((t, i) => {
        const x = sx(d.asset_volatility[i] ?? 0);
        const y = sy(d.asset_return[i] ?? 0);
        return (
          <g key={t}>
            <circle cx={x} cy={y} r={3.5} fill="currentColor" opacity={0.45} />
            <text x={x + 6} y={y + 4} fontSize={10} fill="currentColor" opacity={0.6}>
              {t}
            </text>
          </g>
        );
      })}

      {special.map((s) => (
        <circle
          key={s.label}
          cx={sx(s.p.volatility)}
          cy={sy(s.p.expected_return)}
          r={6}
          fill={s.color}
          stroke="var(--surface)"
          strokeWidth={2}
        >
          <title>{`${s.label}: μ ${rate(s.p.expected_return)} · σ ${rate(s.p.volatility)} · Sharpe ${num(s.p.sharpe, 2)}`}</title>
        </circle>
      ))}
    </svg>
  );
}

/* ---------------------------------------------------------- korelasyon ısı haritası */

function Heatmap({ d }: { d: PortfolioRisk }) {
  const cell: CSSProperties = { padding: "6px 4px", textAlign: "center", fontSize: 12 };
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            <th style={cell} />
            {d.tickers.map((t) => (
              <th key={t} className="note" style={{ ...cell, fontWeight: 500 }}>
                {t.slice(0, 4)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {d.tickers.map((t, i) => (
            <tr key={t}>
              <th className="note" style={{ ...cell, textAlign: "left", fontWeight: 500 }}>
                {t}
              </th>
              {d.tickers.map((u, j) => {
                const c = d.correlation[i]?.[j] ?? 0;
                const bg =
                  i === j
                    ? "transparent"
                    : c >= 0
                      ? `rgba(229, 115, 90, ${(c * 0.85).toFixed(2)})`
                      : `rgba(76, 154, 255, ${(-c * 0.85).toFixed(2)})`;
                return (
                  <td key={u} className="mono" style={{ ...cell, background: bg }} title={`${t}–${u}`}>
                    {i === j ? "·" : num(c, 2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ----------------------------------------------------------------- ana bileşen */

export function PortfolioLab({ initial }: { initial: PortfolioRisk }) {
  const tickers = initial.tickers;
  const [raw, setRaw] = useState<number[]>(() => tickers.map(() => 50));
  const [maxWeight, setMaxWeight] = useState(1);
  const [years, setYears] = useState(2);
  const [riskFree, setRiskFree] = useState(0.4);
  const [d, setD] = useState<PortfolioRisk>(initial);
  const [error, setError] = useState<string | null>(null);
  const first = useRef(true);

  const params = new URLSearchParams();
  for (const t of tickers) params.append("tickers", t);
  for (const w of raw) params.append("weights", String(w));
  params.set("years", String(years));
  params.set("risk_free", String(riskFree));
  params.set("max_weight", String(maxWeight));
  const path = `/portfolio/risk?${params.toString()}`;

  useEffect(() => {
    if (first.current) {
      first.current = false; // ilk durum sunucudan geldi (eşit ağırlık, varsayılanlar)
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const response = await fetch(`${API}${path}`, { signal: controller.signal });
        if (!response.ok) {
          const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
          setError(
            typeof body?.detail === "string" ? body.detail : `API hatası (${response.status})`,
          );
          return;
        }
        setD((await response.json()) as PortfolioRisk);
        setError(null);
      } catch (e) {
        if ((e as Error).name !== "AbortError") setError("API'ye ulaşılamıyor.");
      }
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [path]);

  const total = raw.reduce((a, b) => a + b, 0);
  const apply = (weights: number[]) => setRaw(weights.map((w) => Math.round(w * 100)));
  const setOne = (i: number, v: number) => setRaw(raw.map((w, j) => (j === i ? v : w)));
  const capOk = maxWeight * tickers.length >= 1;

  return (
    <div className="grid">
      {/* --- Ağırlıklar --------------------------------------------------- */}
      <section className="card span-2">
        <div className="card-head">
          <h2>Ağırlıklar</h2>
          <span className="tag">SPL Düzey 3 · Portföy yönetimi</span>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
          <button
            type="button"
            className="pill"
            style={{ cursor: "pointer" }}
            onClick={() => setRaw(tickers.map(() => 50))}
          >
            Eşit ağırlık
          </button>
          <button
            type="button"
            className="pill"
            style={{ cursor: "pointer", background: ACTIVE }}
            onClick={() => apply(d.min_variance.weights)}
          >
            Min varyansı uygula
          </button>
          <button
            type="button"
            className="pill"
            style={{ cursor: "pointer", background: ACTIVE }}
            onClick={() => apply(d.max_sharpe.weights)}
          >
            Maks Sharpe&apos;ı uygula
          </button>
          <label style={{ display: "flex", alignItems: "center", gap: 6, marginLeft: "auto" }}>
            <span className="note">Üst sınır</span>
            <select
              value={maxWeight}
              onChange={(e) => setMaxWeight(Number(e.target.value))}
              style={selectStyle}
            >
              {[1, 0.5, 0.4, 0.25, 0.15].map((v) => (
                <option key={v} value={v}>
                  {v === 1 ? "yok" : rate(v, 0)}
                </option>
              ))}
            </select>
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span className="note">Dönem</span>
            <select value={years} onChange={(e) => setYears(Number(e.target.value))} style={selectStyle}>
              {[1, 2, 3].map((v) => (
                <option key={v} value={v}>
                  {v} yıl
                </option>
              ))}
            </select>
          </label>
        </div>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr className="note" style={{ fontSize: 13 }}>
              <th style={{ textAlign: "left", fontWeight: 500, padding: "4px 0" }}>Hisse</th>
              <th style={{ fontWeight: 500 }} />
              <th style={{ textAlign: "right", fontWeight: 500 }}>Seninki</th>
              <th style={{ textAlign: "right", fontWeight: 500, color: GREEN }}>Min var.</th>
              <th style={{ textAlign: "right", fontWeight: 500, color: AMBER }}>Maks Sh.</th>
              <th style={{ textAlign: "right", fontWeight: 500 }}>μ / σ</th>
            </tr>
          </thead>
          <tbody>
            {tickers.map((t, i) => {
              const w = raw[i] ?? 0;
              return (
                <tr key={t}>
                  <td style={{ padding: "6px 12px 6px 0", whiteSpace: "nowrap" }}>
                    <Link href={`/sirket/${t}`} className="mono" style={{ color: "var(--text)" }}>
                      {t}
                    </Link>
                  </td>
                  <td style={{ width: "40%" }}>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      step={1}
                      value={w}
                      onChange={(e) => setOne(i, Number(e.target.value))}
                      aria-label={`${t} ağırlığı`}
                      style={{ width: "100%" }}
                    />
                  </td>
                  <td className="mono" style={{ textAlign: "right" }}>
                    {total > 0 ? rate(w / total, 0) : "—"}
                  </td>
                  <td className="mono" style={{ textAlign: "right", color: GREEN }}>
                    {rate(d.min_variance.weights[i] ?? 0, 0)}
                  </td>
                  <td className="mono" style={{ textAlign: "right", color: AMBER }}>
                    {rate(d.max_sharpe.weights[i] ?? 0, 0)}
                  </td>
                  <td className="mono note" style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    {pct(d.asset_return[i] ?? 0, 0)} / {rate(d.asset_volatility[i] ?? 0, 0)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!capOk ? (
          <p className="note" style={{ color: ERROR_COLOR }}>
            {tickers.length} hisse × {rate(maxWeight, 0)} &lt; %100: ağırlıklar 1&apos;e tamamlanamaz.
          </p>
        ) : null}
        {error ? (
          <p className="note" style={{ color: ERROR_COLOR }}>
            {error}
          </p>
        ) : null}
      </section>

      {/* --- Risk ---------------------------------------------------------- */}
      <section className="card">
        <div className="card-head">
          <h2>Gerçekleşen risk</h2>
          <span className="tag">
            {d.start} → {d.end}
          </span>
        </div>
        <dl className="stats">
          <Stat label="Yıllık getiri" value={pct(d.annual_return, 1)} hint="Nominal TL" />
          <Stat label="Oynaklık (σ)" value={rate(d.volatility, 1)} hint="Yıllık" />
          <Stat
            label="Sharpe"
            value={num(d.sharpe, 2)}
            hint={`Risksiz ${rate(d.risk_free, 0)}'a göre`}
          />
          <Stat label="Maks. düşüş" value={pct(d.max_drawdown, 1)} hint="Zirveden dibe" />
          <Stat
            label={`VaR %${num(d.level * 100, 0)}`}
            value={rate(d.var_historical, 2)}
            hint={`Günlük, tarihsel · normal ${rate(d.var_parametric, 2)}`}
          />
          <Stat label="CVaR" value={rate(d.cvar, 2)} hint="VaR'ı aşan günlerin ort. kaybı" />
        </dl>
        <div style={{ display: "grid", gap: 6, marginTop: 12 }}>
          <label style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Risksiz faiz</span>
            <span className="mono">{rate(riskFree, 2)}</span>
          </label>
          <input
            type="range"
            min={0}
            max={0.6}
            step={0.0025}
            value={riskFree}
            onChange={(e) => setRiskFree(Number(e.target.value))}
            aria-label="Risksiz faiz"
            style={{ width: "100%" }}
          />
        </div>
        <p className="note">
          {d.sharpe < 0
            ? "Getiri risksiz TL faizinin altında: bu dönemde hisse riski taşımak, mevduata göre ödüllendirilmedi."
            : "Getiri risksiz faizin üstünde: alınan risk ödüllendirildi."}{" "}
          VaR, CVaR {d.observations} günlük getiriden. Hedge için{" "}
          <Link href="/opsiyon" style={{ color: "var(--text)" }}>
            Opsiyon → Vadeli ile hedge
          </Link>
          .
        </p>
      </section>

      {/* --- Etkin sınır ----------------------------------------------------- */}
      <section className="card span-2">
        <div className="card-head">
          <h2>Etkin sınır</h2>
          <span className="tag">Markowitz · açığa satış yok</span>
        </div>
        <Frontier d={d} />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 16, fontSize: 13 }} className="note">
          <span>
            <span style={{ color: BLUE }}>●</span> Senin portföyün: μ {rate(d.current.expected_return)} ·
            σ {rate(d.current.volatility)} · Sharpe {num(d.current.sharpe, 2)}
          </span>
          <span>
            <span style={{ color: GREEN }}>●</span> Min varyans: σ {rate(d.min_variance.volatility)}
          </span>
          <span>
            <span style={{ color: AMBER }}>●</span> Maks Sharpe: {num(d.max_sharpe.sharpe, 2)}
          </span>
        </div>
        <p className="note">
          μ = günlük aritmetik ortalama × 252 (gerçekleşen yıllık getiriden farklı tanım). Maks Sharpe
          portföyü geçmişin kazananlarına yığılır — üst sınır koymadan bak, sonra %40 ile karşılaştır.
          Bu, Markowitz&apos;in &quot;hata maksimize edici&quot; ünü: tahmin hatası en çok ağırlık
          verilen hissede büyür.
        </p>
      </section>

      {/* --- Korelasyon -------------------------------------------------------- */}
      <section className="card">
        <div className="card-head">
          <h2>Korelasyon</h2>
          <span className="tag">Günlük getiriler</span>
        </div>
        <Heatmap d={d} />
        <p className="note">
          Kırmızı birlikte, mavi ters hareket. Hisseler aynı makro faktöre (TL, faiz) bağlıysa
          çeşitlendirme sınırlı kalır: min varyans σ {rate(d.min_variance.volatility)}, eşit ağırlık σ{" "}
          {rate(d.volatility)}.
        </p>
      </section>
    </div>
  );
}
