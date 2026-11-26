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
