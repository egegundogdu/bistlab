import Link from "next/link";
import { notFound } from "next/navigation";

import { DcfCalculator } from "@/components/DcfCalculator";
import { PriceChart } from "@/components/PriceChart";
import { get, type Credit, type Dcf, type Governance, type Merton, type Multiples, type Prices, type Returns } from "@/lib/api";
import { date, num, pct, tone } from "@/lib/format";

const RANGES: Record<string, number> = { "1A": 31, "3A": 92, "1Y": 366, "3Y": 1100 };
const SECTION_NAMES: Record<string, string> = {
  pay_sahipleri: "Pay sahipleri",
  kamuyu_aydinlatma: "Kamuyu aydınlatma",
  menfaat_sahipleri: "Menfaat sahipleri",
  yonetim_kurulu: "Yönetim kurulu",
};

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
  params: Promise<{ kod: string }>;
  searchParams: Promise<{ aralik?: string }>;
}) {
  const { kod } = await params;
  const { aralik } = await searchParams;
  const code = decodeURIComponent(kod).toUpperCase();
  if (!/^[A-Z0-9.]{1,16}$/.test(code)) notFound();
  const range = aralik && aralik in RANGES ? aralik : "1Y";
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
      return <ErrorCard title="API'ye ulaşılamıyor"
        text="Repo kökünde ayrı bir terminalde çalıştırın: uv run uvicorn bistlab.api.main:app --reload" />;
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
            {m && <span className="pill" style={{ minHeight: 24 }}>{m.currency} raporlar</span>}
          </div>
          <p className="note">Son kapanış {date(last.date)}</p>
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
          <span className="mono" style={{ fontSize: 34, fontWeight: 600 }}>{num(last.close)} ₺</span>
          <span className="mono" style={{ fontSize: 16, color: tone(change) }}>{pct(change, 2)}</span>
        </div>
      </section>

      <section className="grid">
        <div className="card span-2">
          <div className="card-head">
            <h2>Fiyat <span className="mono" style={{ color: tone(rangeChange), fontWeight: 400 }}>{pct(rangeChange)}</span></h2>
            <div style={{ display: "flex", gap: 4 }} role="group" aria-label="Zaman aralığı">
              {Object.keys(RANGES).map((r) => (
                <Link key={r} href={`/sirket/${code}?aralik=${r}`} className="pill" aria-current={r === range}>{r}</Link>
              ))}
            </div>
          </div>
          <PriceChart points={points} />
        </div>

        <div className="card">
          <div className="card-head"><h2>Temel göstergeler</h2><span className="tag">SPL Düzey 3 · Değerleme</span></div>
          {m ? (
            <dl className="stats">
              <div className="stat"><dt>Piyasa değeri</dt><dd className="mono">{num(m.market_cap_try_bn, 1)} mr ₺</dd></div>
              <div className="stat"><dt>F/K</dt><dd className="mono">{num(m.pe, 1)}</dd></div>
              <div className="stat"><dt>PD/DD</dt><dd className="mono">{num(m.pb, 2)}</dd></div>
              <div className="stat"><dt>FD/FAVÖK</dt><dd className="mono">{num(m.ev_ebitda, 1)}</dd></div>
              <div className="stat"><dt>FCF getirisi</dt><dd className="mono">{pct(m.fcf_yield)}</dd></div>
              <div className="stat"><dt>Medyan F/K (8 şirket)</dt><dd className="mono">{num(multiples?.median.pe ?? null, 1)}</dd></div>
            </dl>
          ) : <p className="note">Finansal tablo yok (endeks ya da kapsam dışı).</p>}
          <p className="note">Son yıllık finansallar (son 12 ay değil), raporlama para biriminde; boş = zarar ya da negatif payda.</p>
        </div>
      </section>

      <section className="grid">
        {dcf ? (
          <DcfCalculator initial={dcf} />
        ) : (
          <div className="card">
            <div className="card-head"><h2>DCF hesaplayıcı</h2><span className="tag">SPL Düzey 3 · Değerleme</span></div>
            <p className="note">
              Bu şirket için varsayım dosyası yok (assumptions/{code}.toml). Şimdilik THYAO ve ASELS hazır.
            </p>
          </div>
        )}
        <div className="card">
          <div className="card-head"><h2>Kredi riski</h2><span className="tag">Kredi Derecelendirme</span></div>
          {latestCredit ? (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                <span className="mono" style={{ fontSize: 40, fontWeight: 600, color: "#8FB8FF" }}>{latestCredit.rating}</span>
                <span className="pill" style={{ borderRadius: 999 }}>Altman bölgesi: {latestCredit.zone}</span>
              </div>
              <dl className="stats" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
                <div><dt className="tag">Altman Z&apos;&apos;</dt><dd className="mono" style={{ margin: "4px 0 0" }}>{num(latestCredit.z)}</dd></div>
                <div><dt className="tag">Faiz karşılama</dt><dd className="mono" style={{ margin: "4px 0 0" }}>{latestCredit.coverage === null ? "∞" : num(latestCredit.coverage)}</dd></div>
                <div><dt className="tag">Temerrüde uzaklık</dt><dd className="mono" style={{ margin: "4px 0 0" }}>{mt ? `${num(mt.distance_to_default)} σ` : "–"}</dd></div>
              </dl>
              <table>
                <thead><tr><th>Dönem</th><th>Z&apos;&apos;</th><th>Karşılama</th><th>Not</th></tr></thead>
                <tbody className="mono">
                  {creditRows.map((r) => (
                    <tr key={r.period}><td>{r.period.slice(0, 4)}</td><td>{num(r.z)}</td><td>{r.coverage === null ? "∞" : num(r.coverage)}</td><td>{r.rating}</td></tr>
                  ))}
                </tbody>
              </table>
              <p className="note">Sentetik not (Damodaran, faiz karşılama) ve Merton DD; kredi notu değildir.</p>
            </>
          ) : <p className="note">Kredi verisi yok.</p>}
        </div>

        <div className="card">
          <div className="card-head"><h2>Kurumsal yönetim</h2><span className="tag">KY Derecelendirme</span></div>
          {gov ? (
            <>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <span className="mono" style={{ fontSize: 40, fontWeight: 600 }}>{num(gov.total, 1)}</span>
                <span className="tag">/ 10</span>
              </div>
              {Object.entries(gov.sections).map(([name, score]) => (
                <div key={name} style={{ display: "grid", gap: 4 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                    <span>{SECTION_NAMES[name] ?? name}</span><span className="mono">{num(score, 1)}</span>
                  </div>
                  <div className="bar"><div style={{ width: `${Math.min(score * 10, 100)}%` }} /></div>
                </div>
              ))}
              <p className="note">KAP KYBF beyanına dayalı; SPK ağırlıkları %25/%25/%15/%35.</p>
            </>
          ) : <p className="note">Bu şirket için KAP kurumsal yönetim formu yüklenmemiş.</p>}
        </div>

        <div className="card">
          <div className="card-head"><h2>Reel getiri</h2><span className="tag">TÜFE ve USD</span></div>
          {real && market ? (
            <>
              <table>
                <thead><tr><th></th><th>Nominal</th><th>Reel TL</th><th>USD</th></tr></thead>
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
                {date(real.start)} → {date(real.end)}. Dönemde TÜFE {pct(returns?.cpi_change ?? null, 0)}, USD/TRY{" "}
                {pct(returns?.usd_change ?? null, 0)}. Yıllık reel: {pct(real.real_annual)}.
              </p>
            </>
          ) : <p className="note">Reel getiri hesaplanamadı.</p>}
        </div>
      </section>
    </>
  );
}
