import { PortfolioLab } from "@/components/PortfolioLab";
import { get, type PortfolioRisk } from "@/lib/api";

export const metadata = { title: "Portfolio · bistlab" };

export default async function PortfolioPage() {
  const initial = await get<PortfolioRisk>("/portfolio/risk");

  return (
    <div className="container" style={{ padding: "32px 32px 48px" }}>
      <header style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0 }}>Portfolio</h1>
        <p className="note" style={{ maxWidth: 760 }}>
          Build a portfolio from eight companies: realised risk (volatility, max drawdown, VaR, CVaR),
          Sharpe ratio against the risk-free TRY rate, how closely the stocks move together, and where
          you sit on the Markowitz efficient frontier. Optimisation uses past returns; the results are
          a mirror of the past, not a forecast.
        </p>
      </header>
      {initial === null ? (
        <div className="card error">API unreachable — is uvicorn running?</div>
      ) : (
        <PortfolioLab initial={initial} />
      )}
    </div>
  );
}
