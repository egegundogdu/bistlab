import { OptionLab, type Choice } from "@/components/OptionLab";
import { get, type Securities } from "@/lib/api";

export const metadata = { title: "Opsiyon · bistlab" };

export default async function OptionPage() {
  const securities = await get<Securities>("/securities");
  const choices: Choice[] = (securities?.results ?? [])
    .filter((s) => s.last_close > 0)
    .map((s) => ({ ticker: s.ticker, close: s.last_close }))
    .sort((a, b) => a.ticker.localeCompare(b.ticker));

  return (
    <div className="container" style={{ padding: "32px 32px 48px" }}>
      <header style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0 }}>Opsiyon laboratuvarı</h1>
        <p className="note" style={{ maxWidth: 760 }}>
          Aynı opsiyonu üç yöntemle fiyatlıyoruz: Black-Scholes kapalı formu, binom ağacı ve Monte
          Carlo. Yöntemlerin aynı yere yakınsaması modelin, ayrıştıkları yer (erken kullanım)
          sözleşmenin kendisi hakkında bilgi verir. Sonra tersine: piyasa fiyatından oynaklığı geri
          çözüyor ve endeks vadelisiyle portföy riskini azaltıyoruz.
        </p>
      </header>
      {choices.length === 0 ? (
        <div className="card error">API&apos;ye ulaşılamıyor; uvicorn çalışıyor mu?</div>
      ) : (
        <OptionLab choices={choices} />
      )}
    </div>
  );
}
