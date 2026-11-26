"use client";

import { useEffect, useRef, useState } from "react";

import type { Dcf } from "@/lib/api";
import { num, pct, tone } from "@/lib/format";

const API = process.env.NEXT_PUBLIC_BISTLAB_API_URL ?? "http://127.0.0.1:8000";

function bn(value: number, currency: string): string {
  return `${num(value / 1e9, 1)} mr ${currency === "TRY" ? "₺" : currency}`;
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
      setError("WACC, uzun vadeli büyümeden en az 0,5 puan yüksek olmalı.");
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const url = `${API}/valuation/dcf/${initial.ticker}?wacc=${wacc}&terminal_growth=${growth}`;
        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) {
          const body = (await response.json().catch(() => null)) as { detail?: string } | null;
          setError(body?.detail ?? `API hatası (${response.status})`);
          return;
        }
        setResult((await response.json()) as Dcf);
        setError(null);
      } catch (e) {
        if ((e as Error).name !== "AbortError") setError("API'ye ulaşılamıyor.");
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
        <h2>DCF hesaplayıcı</h2>
        <span className="tag">SPL Düzey 3 · Değerleme</span>
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
          <span>Uzun vadeli büyüme (nominal)</span>
          <span className="mono" style={{ color: "var(--text)" }}>{pct(growth, 2).replace("+", "")}</span>
        </label>
        <input id="growth" type="range" min={growthMin} max={growthMax} step={step} value={growth}
          onChange={(e) => setGrowth(Number(e.target.value))} style={{ accentColor: "#4C9AFF", width: "100%" }} />
      </div>

      <div style={{ borderTop: "1px solid var(--border)", paddingTop: 14, display: "grid", gap: 6 }}>
        <span className="tag">Hisse başı içsel değer</span>
        {error ? (
          <span style={{ color: "var(--down)", fontSize: 13 }}>{error}</span>
        ) : (
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
            <span className="mono" style={{ fontSize: 30, fontWeight: 600 }}>{num(result.per_share_try)} ₺</span>
            <span className="mono" style={{ fontSize: 15, color: tone(result.upside) }}>
              {pct(result.upside)} fiyata göre
            </span>
          </div>
        )}
        <span className="tag">
          Fiyat {num(result.price_try)} ₺ · Baz FCF {bn(result.base_fcf, result.currency)}
          {result.lease_adjusted ? " (kira düzeltmeli)" : ""} · Net borç {bn(result.net_debt, result.currency)} · Uç
          değerin payı {pct(result.terminal_share, 0).replace("+", "")}
        </span>
        <span className="tag">
          Model: WACC {pct(result.model_wacc).replace("+", "")} (beta {num(result.beta)}, {result.beta_note}), büyüme{" "}
          {pct(result.model_terminal_growth).replace("+", "")}
          {changed && (
            <>
              {" · "}
              <button type="button" onClick={reset} className="pill" style={{ minHeight: 24, background: "transparent", cursor: "pointer" }}>
                Modele dön
              </button>
            </>
          )}
        </span>
      </div>

      <div style={{ borderTop: "1px solid var(--border)", paddingTop: 12, display: "grid", gap: 8 }}>
        <span className="tag">
          Ters DCF: bugünkü fiyat 5 yıl boyunca yıllık{" "}
          <span className="mono" style={{ color: "var(--text)" }}>
            {result.implied_growth === null ? "–" : pct(result.implied_growth).replace("+", "")}
          </span>{" "}
          FCF büyümesi fiyatlıyor ({result.currency}). Varsayım: {result.growth.map((g) => pct(g, 0).replace("+", "")).join(", ")}.
        </span>
        <div style={{ overflowX: "auto" }}>
          <table aria-label="Duyarlılık tablosu, TL / hisse">
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
