import Link from "next/link";
import { notFound } from "next/navigation";

import { DcfCalculator } from "@/components/DcfCalculator";
import { PriceChart } from "@/components/PriceChart";
import { get, type Credit, type Dcf, type Governance, type Merton, type Multiples, type Prices, type Returns } from "@/lib/api";
import { date, num, pct, tone } from "@/lib/format";

const RANGES: Record<string, number> = { "1M": 31, "3M": 92, "1Y": 366, "3Y": 1100 };

function since(range: string): string {
  const days = RANGES[range] ?? RANGES["1Y"];
  return new Date(Date.now() - days * 86_400_000).toISOString().slice(0, 10);
}

function ErrorCard({ title, text }: { title: string; text: string }) {
  return (
    <div className="card error">
      <h2>{title}</h2>
      <p style={{ margin: 0 }}>{text}</p>
    </div>
  );
}

export default async function Company({
  params,
  searchParams,
}: {
  params: Promise<{ ticker: string }>;
  searchParams: Promise<{ range?: string }>;
}) {
  const { ticker } = await params;
  const { range: rangeParam } = await searchParams;
  const code = decodeURIComponent(ticker).toUpperCase();
  if (!/^[A-Z0-9.]{1,16}$/.test(code)) notFound();
  const range = rangeParam && rangeParam in RANGES ? rangeParam : "1Y";
  const q = `tickers=${encodeURIComponent(code)}`;

  const [prices, multiples, credit, merton, governance, returns, dcf] = await Promise.all([
    get<Prices>(`/prices/${encodeURIComponent(code)}?since=${since(range)}`),
    get<Multiples>(`/valuation/multiples?${q}`),
    get<Credit>(`/credit/scores?${q}`),
    get<Merton>(`/credit/merton?${q}`),
    get<Governance>("/governance/scores"),
    get<Returns>(`/real/returns?${q}`),
    get<Dcf>(`/valuation/dcf/${encodeURIComponent(code)}`),
  ]);

  if (prices === null) {
    const health = await get<{ database: boolean }>("/health");
    if (health === null) {
      return <ErrorCard title="API unreachable"
        text="Run this in a separate terminal at the repo root: uv run uvicorn bistlab.api.main:app --reload" />;
    }
    notFound();
  }

  const points = prices.points;
  const last = points[points.length - 1];
  const prev = points[points.length - 2];
  const change = prev ? last.close / prev.close - 1 : null;
  const rangeChange = points.length > 1 ? last.close / points[0].close - 1 : null;
  const m = multiples?.results[0];
  const creditRows = credit?.results[0]?.rows ?? [];
  const latestCredit = creditRows[creditRows.length - 1];
  const mt = merton?.results[0];
  const gov = governance?.results.find((g) => g.ticker === code);
  const real = returns?.results.find((r) => r.ticker === code);
  const market = returns?.results.find((r) => r.ticker === "XU100");

  return (
    <>
      <section style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 16 }}>
        <div style={{ display: "grid", gap: 6 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h1 style={{ margin: 0, fontSize: 30, fontWeight: 700, letterSpacing: "-0.02em" }}>{code}</h1>
            {m && <span className="pill" style={{ minHeight: 24 }}>Reports in {m.currency}</span>}
          </div>
          <p className="note">Last close {date(last.date)}</p>
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
          <span className="mono" style={{ fontSize: 34, fontWeight: 600 }}>{num(last.close)} ₺</span>
          <span className="mono" style={{ fontSize: 16, color: tone(change) }}>{pct(change, 2)}</span>
        </div>
      </section>

      <section className="grid">
        <div className="card span-2">
          <div className="card-head">
            <h2>Price <span className="mono" style={{ color: tone(rangeChange), fontWeight: 400 }}>{pct(rangeChange)}</span></h2>
            <div style={{ display: "flex", gap: 4 }} role="group" aria-label="Time range">
              {Object.keys(RANGES).map((r) => (
                <Link key={r} href={`/company/${code}?range=${r}`} className="pill" aria-current={r === range}>{r}</Link>
              ))}
            </div>
          </div>
          <PriceChart points={points} />
        </div>

        <div className="card">
          <div className="card-head"><h2>Key metrics</h2><span className="tag">Equity Investments</span></div>
          {m ? (
            <dl className="stats">
              <div className="stat"><dt>Market cap</dt><dd className="mono">{num(m.market_cap_try_bn, 1)} bn ₺</dd></div>
              <div className="stat"><dt>P/E</dt><dd className="mono">{num(m.pe, 1)}</dd></div>
              <div className="stat"><dt>P/B</dt><dd className="mono">{num(m.pb, 2)}</dd></div>
              <div className="stat"><dt>EV/EBITDA</dt><dd className="mono">{num(m.ev_ebitda, 1)}</dd></div>
              <div className="stat"><dt>FCF yield</dt><dd className="mono">{pct(m.fcf_yield)}</dd></div>
              <div className="stat"><dt>Peer median P/E</dt><dd className="mono">{num(multiples?.median.pe ?? null, 1)}</dd></div>
            </dl>
          ) : <p className="note">No financial statements (index or not covered).</p>}
          <p className="note">Last annual financials (not trailing twelve months), in the reporting currency; blank = loss or negative denominator.</p>
        </div>
      </section>

      <section className="grid">
        {dcf ? (
          <DcfCalculator initial={dcf} />
        ) : (
          <div className="card">
            <div className="card-head"><h2>DCF calculator</h2><span className="tag">Equity Investments</span></div>
            <p className="note">
              No assumption file for this company (assumptions/{code}.toml). THYAO and ASELS are available for now.
            </p>
          </div>
        )}
        <div className="card">
          <div className="card-head"><h2>Credit risk</h2><span className="tag">Fixed Income — Credit</span></div>
          {latestCredit ? (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                <span className="mono" style={{ fontSize: 40, fontWeight: 600, color: "#8FB8FF" }}>{latestCredit.rating}</span>
                <span className="pill" style={{ borderRadius: 999 }}>Altman zone: {latestCredit.zone}</span>
              </div>
              <dl className="stats" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
                <div><dt className="tag">Altman Z&apos;&apos;</dt><dd className="mono" style={{ margin: "4px 0 0" }}>{num(latestCredit.z)}</dd></div>
                <div><dt className="tag">Interest coverage</dt><dd className="mono" style={{ margin: "4px 0 0" }}>{latestCredit.coverage === null ? "∞" : num(latestCredit.coverage)}</dd></div>
                <div><dt className="tag">Distance to default</dt><dd className="mono" style={{ margin: "4px 0 0" }}>{mt ? `${num(mt.distance_to_default)} σ` : "–"}</dd></div>
              </dl>
              <table>
                <thead><tr><th>Year</th><th>Z&apos;&apos;</th><th>Coverage</th><th>Rating</th></tr></thead>
                <tbody className="mono">
                  {creditRows.map((r) => (
                    <tr key={r.period}><td>{r.period.slice(0, 4)}</td><td>{num(r.z)}</td><td>{r.coverage === null ? "∞" : num(r.coverage)}</td><td>{r.rating}</td></tr>
                  ))}
                </tbody>
              </table>
              <p className="note">Synthetic rating (Damodaran, interest coverage) and Merton distance to default; not a credit rating.</p>
            </>
          ) : <p className="note">No credit data.</p>}
        </div>

        <div className="card">
          <div className="card-head"><h2>Corporate governance</h2><span className="tag">Corporate Issuers</span></div>
          {gov ? (
            <>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <span className="mono" style={{ fontSize: 40, fontWeight: 600 }}>{num(gov.total, 1)}</span>
                <span className="tag">/ 10</span>
              </div>
              {Object.entries(gov.sections).map(([name, score]) => (
                <div key={name} style={{ display: "grid", gap: 4 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                    <span>{name}</span><span className="mono">{num(score, 1)}</span>
                  </div>
                  <div className="bar"><div style={{ width: `${Math.min(score * 10, 100)}%` }} /></div>
                </div>
              ))}
              <p className="note">Based on the company&apos;s KAP governance disclosure; regulator weights 25% / 25% / 15% / 35%.</p>
            </>
          ) : <p className="note">No KAP governance form loaded for this company.</p>}
        </div>

        <div className="card">
          <div className="card-head"><h2>Real returns</h2><span className="tag">CPI and USD</span></div>
          {real && market ? (
            <>
              <table>
                <thead><tr><th></th><th>Nominal</th><th>Real TRY</th><th>USD</th></tr></thead>
                <tbody className="mono">
                  {[real, market].map((r) => (
                    <tr key={r.ticker}>
                      <td>{r.ticker}</td>
                      <td style={{ color: tone(r.nominal) }}>{pct(r.nominal, 0)}</td>
                      <td style={{ color: tone(r.real) }}>{pct(r.real, 0)}</td>
                      <td style={{ color: tone(r.usd) }}>{pct(r.usd, 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="note">
                {date(real.start)} → {date(real.end)}. CPI over the period {pct(returns?.cpi_change ?? null, 0)}, USD/TRY{" "}
                {pct(returns?.usd_change ?? null, 0)}. Annualised real: {pct(real.real_annual)}.
              </p>
            </>
          ) : <p className="note">Real returns could not be computed.</p>}
        </div>
      </section>
    </>
  );
}
