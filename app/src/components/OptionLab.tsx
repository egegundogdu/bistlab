"use client";

import { useEffect, useState, type CSSProperties, type ReactNode } from "react";

import type { Hedge, ImpliedVol, OptionReport } from "@/lib/api";
import { num, pct } from "@/lib/format";

const API = process.env.NEXT_PUBLIC_BISTLAB_API_URL ?? "http://127.0.0.1:8000";
const ERROR_COLOR = "#E5735A";
const ACTIVE = "#2B4A75";

/** Unsigned rate (σ, interest rate, basis): pct's +/− sign is meaningless here. */
const p = (value: number, digits = 1): string => pct(value, digits).replace("+", "");

export type Choice = { ticker: string; close: number };

/** Debounced (250 ms) GET; aborts the previous request when the path changes. */
function useApi<T>(path: string | null): { data: T | null; error: string | null } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (path === null) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const response = await fetch(`${API}${path}`, { signal: controller.signal });
        if (!response.ok) {
          const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
          setError(
            typeof body?.detail === "string" ? body.detail : `API error (${response.status})`,
          );
          return;
        }
        setData((await response.json()) as T);
        setError(null);
      } catch (e) {
        if ((e as Error).name !== "AbortError") setError("API unreachable.");
      }
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [path]);

  return { data, error };
}

function qs(params: Record<string, string | number>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) search.set(key, String(value));
  return search.toString();
}

const inputStyle: CSSProperties = {
  height: 40,
  padding: "0 14px",
  borderRadius: 8,
  border: "1px solid var(--border-strong)",
  background: "var(--surface)",
  color: "var(--text)",
  font: "inherit",
};

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label style={{ display: "grid", gap: 6 }}>
      <span>{label}</span>
      {children}
    </label>
  );
}

function Slider(props: {
  label: string;
  display: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
}) {
  return (
    <label style={{ display: "grid", gap: 6 }}>
      <span style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
        <span>{props.label}</span>
        <span className="mono">{props.display}</span>
      </span>
      <input
        type="range"
        min={props.min}
        max={props.max}
        step={props.step}
        value={props.value}
        onChange={(e) => props.onChange(Number(e.target.value))}
        style={{ width: "100%" }}
      />
    </label>
  );
}

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

function ErrorLine({ message }: { message: string | null }) {
  return message ? (
    <p className="note" style={{ color: ERROR_COLOR }}>
      {message}
    </p>
  ) : null;
}

const GREEKS: {
  key: keyof OptionReport["greeks"];
  label: string;
  digits: number;
  hint: string;
}[] = [
  {
    key: "delta",
    label: "Delta Δ",
    digits: 3,
    hint: "Approximate change in the option price when the underlying rises by ₺1; the share count held in a delta hedge.",
  },
  {
    key: "gamma",
    label: "Gamma Γ",
    digits: 4,
    hint: "Sensitivity of delta to the underlying; tells you how often the hedge must be rebalanced.",
  },
  {
    key: "vega",
    label: "Vega ν",
    digits: 3,
    hint: "Sensitivity to volatility; more uncertainty makes both calls and puts more valuable.",
  },
  {
    key: "theta",
    label: "Theta Θ",
    digits: 3,
    hint: "Value lost as time passes (time decay).",
  },
  {
    key: "rho",
    label: "Rho ρ",
    digits: 3,
    hint: "Sensitivity to interest rates; far from negligible when TRY rates are high.",
  },
];

export function OptionLab({ choices }: { choices: Choice[] }) {
  const first = choices.find((c) => c.ticker === "THYAO") ?? choices[0];
  const [ticker, setTicker] = useState(first.ticker);
  const [spot, setSpot] = useState(first.close);
  const [moneyness, setMoneyness] = useState(1);
  const [days, setDays] = useState(30);
  const [vol, setVol] = useState(0.35);
  const [rate, setRate] = useState(0.4);
  const [option, setOption] = useState<"call" | "put">("call");
  const [market, setMarket] = useState("");
  const [hedgeTickers, setHedgeTickers] = useState("THYAO, ASELS");
  const [hedgeValue, setHedgeValue] = useState(1_000_000);
  const [hedgeDays, setHedgeDays] = useState(60);
  const [multiplier, setMultiplier] = useState("");

  const strike = Math.round(spot * moneyness * 100) / 100;

  const report = useApi<OptionReport>(
    `/derivatives/option?${qs({ spot, strike, days, rate, vol, type: option })}`,
  );

  const marketPrice = Number(market.replace(",", "."));
  const implied = useApi<ImpliedVol>(
    marketPrice > 0
      ? `/derivatives/implied-vol?${qs({ price: marketPrice, spot, strike, days, rate, type: option })}`
      : null,
  );

  const hedgeQuery = new URLSearchParams();
  for (const t of hedgeTickers.split(/[\s,]+/).filter(Boolean)) {
    hedgeQuery.append("tickers", t.toUpperCase());
  }
  hedgeQuery.set("value", String(hedgeValue));
  hedgeQuery.set("days", String(hedgeDays));
  hedgeQuery.set("rate", String(rate));
  if (Number(multiplier.replace(",", ".")) > 0) {
    hedgeQuery.set("multiplier", multiplier.replace(",", "."));
  }
  const hedge = useApi<Hedge>(
    hedgeValue > 0 ? `/derivatives/futures-hedge?${hedgeQuery.toString()}` : null,
  );

  const r = report.data;
  const h = hedge.data;
  const ci = r ? 1.96 * r.monte_carlo_std_error : 0;
  const early = r ? r.binomial_american - r.binomial_european : 0;
  const intrinsic = option === "call" ? Math.max(spot - strike, 0) : Math.max(strike - spot, 0);
  const timeValue = r ? r.black_scholes - intrinsic : 0;

  return (
    <div className="grid">
      {/* --- Contract ------------------------------------------------------ */}
      <section className="card">
        <div className="card-head">
          <h2>Contract</h2>
          <span className="tag">Derivatives</span>
        </div>
        <div style={{ display: "grid", gap: 16 }}>
          <Field label="Underlying">
            <select
              value={ticker}
              onChange={(e) => {
                const c = choices.find((x) => x.ticker === e.target.value);
                if (c) {
                  setTicker(c.ticker);
                  setSpot(c.close);
                }
              }}
              style={inputStyle}
            >
              {choices.map((c) => (
                <option key={c.ticker} value={c.ticker}>
                  {c.ticker} · {num(c.close)}
                </option>
              ))}
            </select>
          </Field>
          <div style={{ display: "flex", gap: 8 }}>
            {(["call", "put"] as const).map((v) => (
              <button
                key={v}
                type="button"
                className="pill"
                aria-pressed={option === v}
                onClick={() => setOption(v)}
                style={{ cursor: "pointer", background: option === v ? ACTIVE : "transparent" }}
              >
                {v === "call" ? "Call" : "Put"}
              </button>
            ))}
          </div>
          <Slider
            label="Strike"
            display={`${num(strike)} ₺ · K/S ${num(moneyness, 2)}`}
            value={moneyness}
            min={0.7}
            max={1.3}
            step={0.01}
            onChange={setMoneyness}
          />
          <Slider
            label="Maturity"
            display={`${days} days`}
            value={days}
            min={1}
            max={365}
            step={1}
            onChange={setDays}
          />
          <Slider
            label="Volatility (σ, annual)"
            display={p(vol, 0)}
            value={vol}
            min={0.05}
            max={1.5}
            step={0.01}
            onChange={setVol}
          />
          <Slider
            label="Interest rate (annual effective)"
            display={p(rate, 2)}
            value={rate}
            min={0}
            max={0.8}
            step={0.0025}
            onChange={setRate}
          />
          <p className="note" style={{ margin: 0 }}>
            The underlying price is the last close ({num(spot)} ₺). The effective rate is converted to
            continuous compounding in the model{r ? ` (${p(r.continuous_rate, 2)})` : ""}.
          </p>
        </div>
      </section>

      {/* --- Three methods ------------------------------------------------- */}
      <section className="card span-2">
        <div className="card-head">
          <h2>Three methods, one price</h2>
          <span className="tag">
            {ticker} · {option} · {days} days
          </span>
        </div>
        <ErrorLine message={report.error} />
        {r ? (
          <>
            <dl className="stats">
              <Stat label="Black-Scholes" value={`${num(r.black_scholes)} ₺`} hint="Closed form" />
              <Stat
                label="Binomial (European)"
                value={`${num(r.binomial_european)} ₺`}
                hint="Tree; converges to BS as steps increase"
              />
              <Stat
                label="Binomial (American)"
                value={`${num(r.binomial_american)} ₺`}
                hint="With the right to exercise early"
              />
              <Stat
                label="Monte Carlo"
                value={`${num(r.monte_carlo)} ₺`}
                hint={`95% interval ±${num(ci)} ₺`}
              />
            </dl>
            <p className="note">
              BS − binomial gap {num(r.black_scholes - r.binomial_european, 4)} ₺; Monte Carlo puts BS{" "}
              {Math.abs(r.monte_carlo - r.black_scholes) <= ci
                ? "inside its 95% confidence interval"
                : "outside its 95% confidence interval"}
              . Put-call parity gap: {num(r.put_call_parity_gap, 6)}.
            </p>
            <p className="note">
              Early-exercise premium (American − European): <span className="mono">{num(early, 4)} ₺</span>
              {option === "call"
                ? " — for a call on a non-dividend stock early exercise is never optimal, so this should be zero."
                : " — for a put, high rates make receiving the strike early valuable."}
            </p>
            <p className="note">
              Intrinsic value {num(intrinsic)} ₺ · time value {num(timeValue)} ₺
              {timeValue < 0
                ? " — negative time value on a European put: the cost of having to wait to exercise when rates are high."
                : "."}
            </p>
          </>
        ) : !report.error ? (
          <p className="note">Calculating…</p>
        ) : null}
      </section>

      {/* --- Greeks -------------------------------------------------------- */}
      <section className="card">
        <div className="card-head">
          <h2>Greeks</h2>
          <span className="tag">Black-Scholes</span>
        </div>
        {r ? (
          <dl style={{ display: "grid", gap: 14, margin: 0 }}>
            {GREEKS.map((g) => (
              <div key={g.key}>
                <dt style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                  <span>{g.label}</span>
                  <span className="mono">{num(r.greeks[g.key], g.digits)}</span>
                </dt>
                <dd className="note" style={{ margin: 0 }}>
                  {g.hint}
                </dd>
              </div>
            ))}
          </dl>
        ) : null}
      </section>

      {/* --- Implied volatility -------------------------------------------- */}
      <section className="card">
        <div className="card-head">
          <h2>Implied volatility</h2>
          <span className="tag">What is the market pricing in?</span>
        </div>
        <div style={{ display: "grid", gap: 16 }}>
          <Field label="Market price (₺)">
            <input
              inputMode="decimal"
              value={market}
              onChange={(e) => setMarket(e.target.value)}
              placeholder={r ? `e.g. ${num(r.black_scholes * 1.1)}` : "e.g. 12.50"}
              style={inputStyle}
            />
          </Field>
          <ErrorLine message={marketPrice > 0 ? implied.error : null} />
          {marketPrice > 0 && implied.data ? (
            <>
              <dl className="stats">
                <Stat label="Implied σ" value={p(implied.data.implied_vol, 1)} />
                <Stat label="Slider σ" value={p(vol, 1)} />
              </dl>
              <p className="note" style={{ margin: 0 }}>
                This price implies {implied.data.implied_vol > vol ? "higher" : "lower"} volatility than
                the slider assumption. It is the option counterpart of a reverse DCF: solving for the
                assumption from the price.
              </p>
            </>
          ) : (
            <p className="note" style={{ margin: 0 }}>
              Enter a price: σ is solved for with the same underlying, strike, maturity and rate.
            </p>
          )}
        </div>
      </section>

      {/* --- Futures hedge ------------------------------------------------- */}
      <section className="card">
        <div className="card-head">
          <h2>Hedge with index futures</h2>
          <span className="tag">XU030 · VIOP</span>
        </div>
        <div style={{ display: "grid", gap: 16 }}>
          <Field label="Stocks in the portfolio">
            <input
              value={hedgeTickers}
              onChange={(e) => setHedgeTickers(e.target.value)}
              style={inputStyle}
            />
          </Field>
          <Field label="Portfolio value (₺)">
            <input
              type="number"
              min={1}
              step={100000}
              value={hedgeValue}
              onChange={(e) => setHedgeValue(Number(e.target.value) || 0)}
              style={inputStyle}
            />
          </Field>
          <Slider
            label="Maturity"
            display={`${hedgeDays} days`}
            value={hedgeDays}
            min={1}
            max={365}
            step={1}
            onChange={setHedgeDays}
          />
          <Field label="Contract multiplier (optional)">
            <input
              inputMode="decimal"
              value={multiplier}
              onChange={(e) => setMultiplier(e.target.value)}
              placeholder="e.g. 10"
              style={inputStyle}
            />
          </Field>
          <ErrorLine message={hedge.error} />
          {h ? (
            <>
              <dl className="stats">
                <Stat
                  label="Futures price"
                  value={num(h.futures_price)}
                  hint={`Basis ${p(h.basis_pct, 2)}`}
                />
                <Stat label="Hedge ratio (β)" value={num(h.hedge_ratio, 2)} />
                <Stat
                  label="Notional to sell"
                  value={`${num(h.notional / 1e6, 2)} m ₺`}
                  hint={
                    h.contracts !== null
                      ? `${num(h.contracts, 1)} contracts`
                      : "Enter a multiplier for the contract count"
                  }
                />
                <Stat
                  label="Risk reduction"
                  value={p(h.risk_reduction, 0)}
                  hint={`σ ${p(h.unhedged_vol, 1)} → ${p(h.hedged_vol, 1)}`}
                />
              </dl>
              <p className="note" style={{ margin: 0 }}>
                The hedge ratio is estimated from past returns and may not hold in the future. The
                futures price comes from cost of carry (rate {p(rate, 1)}), not an actual exchange
                quote.
              </p>
            </>
          ) : null}
        </div>
      </section>
    </div>
  );
}
