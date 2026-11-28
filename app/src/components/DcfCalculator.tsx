"use client";

import { useEffect, useRef, useState } from "react";

import type { Dcf } from "@/lib/api";
import { num, pct, tone } from "@/lib/format";

const API = process.env.NEXT_PUBLIC_BISTLAB_API_URL ?? "http://127.0.0.1:8000";

function bn(value: number, currency: string): string {
  return `${num(value / 1e9, 1)} bn ${currency === "TRY" ? "₺" : currency}`;
}

export function DcfCalculator({ initial }: { initial: Dcf }) {
  const [wacc, setWacc] = useState(initial.model_wacc);
  const [growth, setGrowth] = useState(initial.model_terminal_growth);
  const [result, setResult] = useState<Dcf>(initial);
  const [error, setError] = useState<string | null>(null);
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (wacc - growth < 0.005) {
      setError("WACC must exceed long-term growth by at least 0.5 percentage points.");
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const url = `${API}/valuation/dcf/${initial.ticker}?wacc=${wacc}&terminal_growth=${growth}`;
        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) {
          const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
          setError(typeof body?.detail === "string" ? body.detail : `API error (${response.status})`);
          return;
        }
        setResult((await response.json()) as Dcf);
        setError(null);
      } catch (e) {
        if ((e as Error).name !== "AbortError") setError("API unreachable.");
      }
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [wacc, growth, initial.ticker]);

  const reset = () => {
    setWacc(initial.model_wacc);
    setGrowth(initial.model_terminal_growth);
  };
  const changed = Math.abs(wacc - initial.model_wacc) > 1e-9 || Math.abs(growth - initial.model_terminal_growth) > 1e-9;
  const step = 0.0025;
  const waccMin = Math.max(0.01, initial.model_wacc - 0.06);
  const waccMax = initial.model_wacc + 0.06;
  const growthMin = initial.model_terminal_growth - 0.04;
  const growthMax = initial.model_terminal_growth + 0.04;

  return (
    <div className="card" style={{ borderColor: "#2B4A75" }}>
      <div className="card-head">
        <h2>DCF calculator</h2>
        <span className="tag">Equity Investments</span>
      </div>

      <div style={{ display: "grid", gap: 6 }}>
        <label htmlFor="wacc" style={{ display: "flex", justifyContent: "space-between", color: "var(--muted)", fontSize: 13 }}>
          <span>WACC ({result.currency})</span>
          <span className="mono" style={{ color: "var(--text)" }}>{pct(wacc, 2).replace("+", "")}</span>
        </label>
        <input id="wacc" type="range" min={waccMin} max={waccMax} step={step} value={wacc}
          onChange={(e) => setWacc(Number(e.target.value))} style={{ accentColor: "#4C9AFF", width: "100%" }} />
      </div>
      <div style={{ display: "grid", gap: 6 }}>
        <label htmlFor="growth" style={{ display: "flex", justifyContent: "space-between", color: "var(--muted)", fontSize: 13 }}>
          <span>Long-term growth (nominal)</span>
          <span className="mono" style={{ color: "var(--text)" }}>{pct(growth, 2).replace("+", "")}</span>
        </label>
        <input id="growth" type="range" min={growthMin} max={growthMax} step={step} value={growth}
          onChange={(e) => setGrowth(Number(e.target.value))} style={{ accentColor: "#4C9AFF", width: "100%" }} />
      </div>

      <div style={{ borderTop: "1px solid var(--border)", paddingTop: 14, display: "grid", gap: 6 }}>
        <span className="tag">Intrinsic value per share</span>
        {error ? (
          <span style={{ color: "var(--down)", fontSize: 13 }}>{error}</span>
        ) : (
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
            <span className="mono" style={{ fontSize: 30, fontWeight: 600 }}>{num(result.per_share_try)} ₺</span>
            <span className="mono" style={{ fontSize: 15, color: tone(result.upside) }}>
              {pct(result.upside)} vs price
            </span>
          </div>
        )}
        <span className="tag">
          Price {num(result.price_try)} ₺ · Base FCF {bn(result.base_fcf, result.currency)}
          {result.lease_adjusted ? " (lease-adjusted)" : ""} · Net debt {bn(result.net_debt, result.currency)} · Terminal
          value share {pct(result.terminal_share, 0).replace("+", "")}
        </span>
        <span className="tag">
          Model: WACC {pct(result.model_wacc).replace("+", "")} (beta {num(result.beta)}, {result.beta_note}), growth{" "}
          {pct(result.model_terminal_growth).replace("+", "")}
          {changed && (
            <>
              {" · "}
              <button type="button" onClick={reset} className="pill" style={{ minHeight: 24, background: "transparent", cursor: "pointer" }}>
                Reset to model
              </button>
            </>
          )}
        </span>
      </div>

      <div style={{ borderTop: "1px solid var(--border)", paddingTop: 12, display: "grid", gap: 8 }}>
        <span className="tag">
          Reverse DCF: today&apos;s price implies{" "}
          <span className="mono" style={{ color: "var(--text)" }}>
            {result.implied_growth === null ? "–" : pct(result.implied_growth).replace("+", "")}
          </span>{" "}
          annual FCF growth for 5 years ({result.currency}). Assumed path: {result.growth.map((g) => pct(g, 0).replace("+", "")).join(", ")}.
        </span>
        <div style={{ overflowX: "auto" }}>
          <table aria-label="Sensitivity table, TRY per share">
            <thead>
              <tr>
                <th>WACC \ g</th>
                {result.sensitivity_growths.map((g) => <th key={g}>{pct(g).replace("+", "")}</th>)}
              </tr>
            </thead>
            <tbody className="mono">
              {result.sensitivity.map((row, i) => (
                <tr key={result.sensitivity_rates[i]}>
                  <td>{pct(result.sensitivity_rates[i]).replace("+", "")}</td>
                  {row.map((v, j) => (
                    <td key={j} style={i === 2 && j === 1 ? { color: "#8FB8FF", fontWeight: 600 } : undefined}>{num(v)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
