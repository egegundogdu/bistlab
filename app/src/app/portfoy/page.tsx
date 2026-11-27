import { PortfolioLab } from "@/components/PortfolioLab";
import { get, type PortfolioRisk } from "@/lib/api";

export const metadata = { title: "Portföy · bistlab" };

export default async function PortfolioPage() {
  const initial = await get<PortfolioRisk>("/portfolio/risk");

  return (
    <div className="container" style={{ padding: "32px 32px 48px" }}>
      <header style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0 }}>Portföy</h1>
        <p className="note" style={{ maxWidth: 760 }}>
          8 şirketten bir portföy kur: gerçekleşen risk (oynaklık, maks. düşüş, VaR, CVaR), risksiz
          TL faizine göre Sharpe, hisselerin birbirine ne kadar bağlı hareket ettiği ve Markowitz etkin
          sınırında nerede durduğun. Optimizasyon geçmiş getirilerle yapılır; sonuçlar geleceğin
          tahmini değil, geçmişin aynasıdır.
        </p>
      </header>
      {initial === null ? (
        <div className="card error">API&apos;ye ulaşılamıyor; uvicorn çalışıyor mu?</div>
      ) : (
        <PortfolioLab initial={initial} />
      )}
    </div>
  );
}
