import { OptionLab, type Choice } from "@/components/OptionLab";
import { get, type Securities } from "@/lib/api";

export const metadata = { title: "Options · bistlab" };

export default async function OptionPage() {
  const securities = await get<Securities>("/securities");
  const choices: Choice[] = (securities?.results ?? [])
    .filter((s) => s.last_close > 0)
    .map((s) => ({ ticker: s.ticker, close: s.last_close }))
    .sort((a, b) => a.ticker.localeCompare(b.ticker));

  return (
    <div className="container" style={{ padding: "32px 32px 48px" }}>
      <header style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0 }}>Options lab</h1>
        <p className="note" style={{ maxWidth: 760 }}>
          The same option priced three ways: the Black-Scholes closed form, a binomial tree and Monte
          Carlo. Where the methods converge tells you about the model; where they diverge (early
          exercise) tells you about the contract. Then in reverse: solving for volatility from a
          market price, and cutting portfolio risk with index futures.
        </p>
      </header>
      {choices.length === 0 ? (
        <div className="card error">API unreachable — is uvicorn running?</div>
      ) : (
        <OptionLab choices={choices} />
      )}
    </div>
  );
}
