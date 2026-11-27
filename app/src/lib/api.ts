// bistlab API istemcisi (sunucu tarafında çalışır).
const API = process.env.BISTLAB_API_URL ?? "http://127.0.0.1:8000";

export async function get<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${API}${path}`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export type Security = { ticker: string; last_date: string; last_close: number };
export type Securities = { results: Security[] };
export type Prices = { ticker: string; points: { date: string; close: number }[] };

export type Multiples = {
  results: {
    ticker: string;
    currency: string;
    market_cap_try_bn: number | null;
    pe: number | null;
    pb: number | null;
    ev_ebitda: number | null;
    fcf_yield: number | null;
  }[];
  median: Record<string, number | null>;
};

export type Credit = {
  results: {
    ticker: string;
    currency: string;
    rows: {
      period: string;
      z: number | null;
      zone: string;
      coverage: number | null;
      rating: string;
      spread: number;
    }[];
  }[];
};

export type Merton = {
  results: {
    ticker: string;
    distance_to_default: number;
    default_probability: number;
    asset_vol: number;
    equity_vol: number;
  }[];
};

export type Governance = {
  results: { ticker: string; sections: Record<string, number>; total: number }[];
};

export type Returns = {
  cpi_change: number | null;
  usd_change: number | null;
  results: {
    ticker: string;
    start: string;
    end: string;
    nominal: number;
    real: number;
    usd: number;
    real_annual: number | null;
  }[];
};

export type Dcf = {
  ticker: string;
  currency: string;
  raw_beta: number;
  beta: number;
  beta_note: string;
  cost_of_equity: number;
  model_wacc: number;
  model_terminal_growth: number;
  wacc: number;
  terminal_growth: number;
  base_fcf: number;
  lease_adjusted: boolean;
  growth: number[];
  enterprise_value: number;
  net_debt: number;
  equity_value: number;
  terminal_share: number;
  per_share_try: number;
  price_try: number;
  upside: number;
  implied_growth: number | null;
  sensitivity_rates: number[];
  sensitivity_growths: number[];
  sensitivity: number[][];
};

export type Greeks = { delta: number; gamma: number; vega: number; theta: number; rho: number };

export type OptionReport = {
  option: string;
  spot: number;
  strike: number;
  years: number;
  rate: number;
  continuous_rate: number;
  vol: number;
  black_scholes: number;
  greeks: Greeks;
  binomial_european: number;
  binomial_american: number;
  monte_carlo: number;
  monte_carlo_std_error: number;
  put_call_parity_gap: number;
};

export type ImpliedVol = { implied_vol: number; price: number; option: string };

export type Hedge = {
  tickers: string[];
  index: string;
  value: number;
  spot: number;
  days: number;
  futures_price: number;
  basis_pct: number;
  implied_rate: number;
  hedge_ratio: number;
  notional: number;
  contracts: number | null;
  unhedged_vol: number;
  hedged_vol: number;
  risk_reduction: number;
};

export type PriceQuality = {
  summary: Record<string, number>;
  provisional: number;
  series: {
    ticker: string;
    market: string;
    first: string;
    last: string;
    bars: number;
    coverage: number;
    missing: number;
    stale: number;
    jumps: number;
    suspicious: number;
    flat_run: number;
    provisional: boolean;
    status: string;
  }[];
};
