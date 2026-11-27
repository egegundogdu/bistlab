import { ScreenerTable, type ScreenerRow } from "@/components/ScreenerTable";
import {
  get,
  type Credit,
  type Governance,
  type Merton,
  type Multiples,
  type PriceQuality,
} from "@/lib/api";

export const metadata = { title: "Tarayıcı · bistlab" };

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
        ? `${q.bars} gün · eksik ${q.missing} · sıçrama ${q.jumps} · donuk seri ${q.flat_run}` +
          (q.provisional ? " · son bar geçici" : "")
        : null,
    };
  });

  return (
    <div className="container" style={{ padding: "32px 32px 48px" }}>
      <header style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0 }}>Tarayıcı</h1>
        <p className="note" style={{ maxWidth: 760 }}>
          Şirket sayfası tek hisseye derin bakar; burada 8 şirket yan yana. Değerleme, kredi, kurumsal
          yönetim ve veri kalitesi aynı satırda olunca asıl soru görünür: ucuz görünen şirket
          gerçekten ucuz mu, yoksa riski mi fiyatlanmış? Sütun başlığına tıklayarak sırala.
        </p>
      </header>
      {rows.length === 0 ? (
        <div className="card error">API&apos;ye ulaşılamıyor; uvicorn çalışıyor mu?</div>
      ) : (
        <ScreenerTable rows={rows} median={multiples?.median ?? {}} />
      )}
    </div>
  );
}
