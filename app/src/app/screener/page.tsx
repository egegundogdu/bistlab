import { ScreenerTable, type ScreenerRow } from "@/components/ScreenerTable";
import {
  get,
  type Credit,
  type Governance,
  type Merton,
  type Multiples,
  type PriceQuality,
} from "@/lib/api";

export const metadata = { title: "Screener · bistlab" };

export default async function ScreenerPage() {
  const [multiples, credit, merton, governance, quality] = await Promise.all([
    get<Multiples>("/valuation/multiples"),
    get<Credit>("/credit/scores"),
    get<Merton>("/credit/merton"),
    get<Governance>("/governance/scores"),
    get<PriceQuality>("/quality/prices"),
  ]);

  const rows: ScreenerRow[] = (multiples?.results ?? []).map((m) => {
    const c = credit?.results.find((x) => x.ticker === m.ticker);
    const last = c && c.rows.length > 0 ? c.rows[c.rows.length - 1] : undefined;
    const d = merton?.results.find((x) => x.ticker === m.ticker);
    const g = governance?.results.find((x) => x.ticker === m.ticker);
    const q = quality?.series.find((x) => x.ticker === m.ticker);
    return {
      ticker: m.ticker,
      currency: m.currency,
      mcap: m.market_cap_try_bn,
      pe: m.pe,
      pb: m.pb,
      evEbitda: m.ev_ebitda,
      fcfYield: m.fcf_yield,
      period: last?.period ?? null,
      rating: last?.rating ?? null,
      z: last?.z ?? null,
      coverage: last?.coverage ?? null,
      dd: d?.distance_to_default ?? null,
      pd: d?.default_probability ?? null,
      governance: g?.total ?? null,
      lastDate: q?.last ?? null,
      quality: q?.status ?? null,
      qualityNote: q
        ? `${q.bars} days · missing ${q.missing} · jumps ${q.jumps} · flat run ${q.flat_run}` +
          (q.provisional ? " · last bar provisional" : "")
        : null,
    };
  });

  return (
    <div className="container" style={{ padding: "32px 32px 48px" }}>
      <header style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0 }}>Screener</h1>
        <p className="note" style={{ maxWidth: 760 }}>
          The company page looks deep at one stock; here eight companies sit side by side. With
          valuation, credit, governance and data quality on one row, the real question shows: is the
          cheap-looking stock actually cheap, or is risk being priced in? Click a column header to sort.
        </p>
      </header>
      {rows.length === 0 ? (
        <div className="card error">API unreachable — is uvicorn running?</div>
      ) : (
        <ScreenerTable rows={rows} median={multiples?.median ?? {}} />
      )}
    </div>
  );
}
