"use client";

import { useEffect, useState, type CSSProperties, type ReactNode } from "react";

import type { Hedge, ImpliedVol, OptionReport } from "@/lib/api";
import { num, pct } from "@/lib/format";

const API = process.env.NEXT_PUBLIC_BISTLAB_API_URL ?? "http://127.0.0.1:8000";
const ERROR_COLOR = "#E5735A";
const ACTIVE = "#2B4A75";

/** Oran gösterimi (σ, faiz, baz): pct'nin +/− işareti burada anlamsız. */
const p = (value: number, digits = 1): string => pct(value, digits).replace("+", "");

export type Choice = { ticker: string; close: number };

/** Gecikmeli (250 ms) GET; yol değiştikçe önceki isteği iptal eder. */
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
            typeof body?.detail === "string" ? body.detail : `API hatası (${response.status})`,
          );
          return;
        }
        setData((await response.json()) as T);
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
    hint: "Dayanak 1 TL artınca opsiyon fiyatının yaklaşık değişimi; delta hedge'de tutulacak hisse oranı.",
  },
  {
    key: "gamma",
    label: "Gamma Γ",
    digits: 4,
    hint: "Deltanın dayanağa duyarlılığı; hedge'in ne sık yenilenmesi gerektiğini söyler.",
  },
  {
    key: "vega",
    label: "Vega ν",
    digits: 3,
    hint: "Oynaklık duyarlılığı; belirsizlik arttıkça hem alım hem satım değerlenir.",
  },
  {
    key: "theta",
    label: "Theta Θ",
    digits: 3,
    hint: "Zaman geçtikçe değer kaybı (zaman erimesi).",
  },
  {
    key: "rho",
    label: "Rho ρ",
    digits: 3,
    hint: "Faiz duyarlılığı; TL faizleri yüksekken küçümsenecek bir etki değil.",
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
      {/* --- Sözleşme ------------------------------------------------------ */}
      <section className="card">
        <div className="card-head">
          <h2>Sözleşme</h2>
          <span className="tag">Türev Araçlar</span>
        </div>
        <div style={{ display: "grid", gap: 16 }}>
          <Field label="Dayanak">
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
                {v === "call" ? "Alım (call)" : "Satım (put)"}
              </button>
            ))}
          </div>
          <Slider
            label="Kullanım fiyatı"
            display={`${num(strike)} ₺ · K/S ${num(moneyness, 2)}`}
            value={moneyness}
            min={0.7}
            max={1.3}
            step={0.01}
            onChange={setMoneyness}
          />
          <Slider
            label="Vade"
            display={`${days} gün`}
            value={days}
            min={1}
            max={365}
            step={1}
            onChange={setDays}
          />
          <Slider
            label="Oynaklık (σ, yıllık)"
            display={p(vol, 0)}
            value={vol}
            min={0.05}
            max={1.5}
            step={0.01}
            onChange={setVol}
          />
          <Slider
            label="Faiz (yıllık efektif)"
            display={p(rate, 2)}
            value={rate}
            min={0}
            max={0.8}
            step={0.0025}
            onChange={setRate}
          />
          <p className="note" style={{ margin: 0 }}>
            Dayanak fiyatı son kapanış ({num(spot)} ₺). Efektif faiz modelde sürekli bileşiğe
            çevrilir{r ? ` (${p(r.continuous_rate, 2)})` : ""}.
          </p>
        </div>
      </section>

      {/* --- Üç yöntem ----------------------------------------------------- */}
      <section className="card span-2">
        <div className="card-head">
          <h2>Üç yöntem, tek fiyat</h2>
          <span className="tag">
            {ticker} · {option === "call" ? "alım" : "satım"} · {days} gün
          </span>
        </div>
        <ErrorLine message={report.error} />
        {r ? (
          <>
            <dl className="stats">
              <Stat label="Black-Scholes" value={`${num(r.black_scholes)} ₺`} hint="Kapalı form" />
              <Stat
                label="Binom (Avrupa)"
                value={`${num(r.binomial_european)} ₺`}
                hint="Ağaç; adım arttıkça BS'ye yakınsar"
              />
              <Stat
                label="Binom (Amerikan)"
                value={`${num(r.binomial_american)} ₺`}
                hint="Erken kullanım hakkıyla"
              />
              <Stat
                label="Monte Carlo"
                value={`${num(r.monte_carlo)} ₺`}
                hint={`%95 aralık ±${num(ci)} ₺`}
              />
            </dl>
            <p className="note">
              BS − binom farkı {num(r.black_scholes - r.binomial_european, 4)} ₺; Monte Carlo BS&apos;yi{" "}
              {Math.abs(r.monte_carlo - r.black_scholes) <= ci
                ? "%95 güven aralığı içinde"
                : "%95 güven aralığı dışında"}{" "}
              buluyor. Put-call parite farkı: {num(r.put_call_parity_gap, 6)}.
            </p>
            <p className="note">
              Erken kullanım primi (Amerikan − Avrupa): <span className="mono">{num(early, 4)} ₺</span>
              {option === "call"
                ? " — temettüsüz alımda erken kullanmak hiçbir zaman optimal değil, sıfır olmalı."
                : " — satımda yüksek faiz, parayı erken almayı değerli kılar."}
            </p>
            <p className="note">
              İçsel değer {num(intrinsic)} ₺ · zaman değeri {num(timeValue)} ₺
              {timeValue < 0
                ? " — Avrupa satımda negatif zaman değeri: yüksek faizde kullanımı beklemenin maliyeti."
                : "."}
            </p>
          </>
        ) : !report.error ? (
          <p className="note">Hesaplanıyor…</p>
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

      {/* --- Zımni oynaklık ------------------------------------------------ */}
      <section className="card">
        <div className="card-head">
          <h2>Zımni oynaklık</h2>
          <span className="tag">Piyasa ne fiyatlıyor?</span>
        </div>
        <div style={{ display: "grid", gap: 16 }}>
          <Field label="Piyasa fiyatı (₺)">
            <input
              inputMode="decimal"
              value={market}
              onChange={(e) => setMarket(e.target.value)}
              placeholder={r ? `ör. ${num(r.black_scholes * 1.1)}` : "ör. 12,50"}
              style={inputStyle}
            />
          </Field>
          <ErrorLine message={marketPrice > 0 ? implied.error : null} />
          {marketPrice > 0 && implied.data ? (
            <>
              <dl className="stats">
                <Stat label="Zımni σ" value={p(implied.data.implied_vol, 1)} />
                <Stat label="Sürgüdeki σ" value={p(vol, 1)} />
              </dl>
              <p className="note" style={{ margin: 0 }}>
                Bu fiyat, sürgüdeki varsayımdan{" "}
                {implied.data.implied_vol > vol ? "daha yüksek" : "daha düşük"} bir oynaklık
                fiyatlıyor. Ters DCF&apos;nin opsiyondaki karşılığı: fiyattan varsayımı geri çözmek.
              </p>
            </>
          ) : (
            <p className="note" style={{ margin: 0 }}>
              Bir fiyat gir: aynı dayanak, kullanım fiyatı, vade ve faizle σ geri çözülür.
            </p>
          )}
        </div>
      </section>

      {/* --- Vadeli hedge -------------------------------------------------- */}
      <section className="card">
        <div className="card-head">
          <h2>Vadeli ile hedge</h2>
          <span className="tag">XU030 · VİOP</span>
        </div>
        <div style={{ display: "grid", gap: 16 }}>
          <Field label="Portföydeki hisseler">
            <input
              value={hedgeTickers}
              onChange={(e) => setHedgeTickers(e.target.value)}
              style={inputStyle}
            />
          </Field>
          <Field label="Portföy değeri (₺)">
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
            label="Vade"
            display={`${hedgeDays} gün`}
            value={hedgeDays}
            min={1}
            max={365}
            step={1}
            onChange={setHedgeDays}
          />
          <Field label="Kontrat çarpanı (isteğe bağlı)">
            <input
              inputMode="decimal"
              value={multiplier}
              onChange={(e) => setMultiplier(e.target.value)}
              placeholder="ör. 10"
              style={inputStyle}
            />
          </Field>
          <ErrorLine message={hedge.error} />
          {h ? (
            <>
              <dl className="stats">
                <Stat
                  label="Vadeli fiyat"
                  value={num(h.futures_price)}
                  hint={`Baz ${p(h.basis_pct, 2)}`}
                />
                <Stat label="Hedge oranı (β)" value={num(h.hedge_ratio, 2)} />
                <Stat
                  label="Açığa satılacak"
                  value={`${num(h.notional / 1e6, 2)} mn ₺`}
                  hint={
                    h.contracts !== null
                      ? `${num(h.contracts, 1)} kontrat`
                      : "Çarpan girilirse kontrat sayısı"
                  }
                />
                <Stat
                  label="Risk azalması"
                  value={p(h.risk_reduction, 0)}
                  hint={`σ ${p(h.unhedged_vol, 1)} → ${p(h.hedged_vol, 1)}`}
                />
              </dl>
              <p className="note" style={{ margin: 0 }}>
                Hedge oranı geçmiş getirilerden; geleceğe aynen taşınacağının garantisi yok. Vadeli
                fiyat taşıma maliyetinden (faiz {p(rate, 1)}) hesaplanıyor, gerçek VİOP kotasyonu
                değil.
              </p>
            </>
          ) : null}
        </div>
      </section>
    </div>
  );
}
