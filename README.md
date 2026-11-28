# bistlab

[![CI](https://github.com/egegundogdu/bistlab/actions/workflows/ci.yml/badge.svg)](https://github.com/egegundogdu/bistlab/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Next.js](https://img.shields.io/badge/Next.js-16-black)
![License](https://img.shields.io/badge/license-MIT-green)

🇹🇷 Türkçe: [README.tr.md](README.tr.md)

**An open-source equity analytics and risk lab, built on a high-inflation emerging market.** Valuation, portfolio risk, derivatives pricing, credit risk, corporate-governance scoring, fund look-through and an IT-controls self-audit — one Python engine, exposed through a typed HTTP API and a Next.js web app, with every number traceable to its data source.

The case study is Borsa Istanbul: 40% policy rates, IAS 29 hyperinflation accounting, a currency that lost most of its value in three years and free data that breaks in instructive ways. The calculation core is market-agnostic; the data layer is a pluggable interface.

> ⚠️ **Not investment advice.** All outputs are for education and methodology demonstration only.

<!-- Screenshot / demo GIF goes here (portfolio page, options lab). Live demo link to follow. -->

## Modules

| # | Module | Package | What it does | CFA curriculum area |
| --- | --- | --- | --- | --- |
| 1 | Valuation | `bistlab.valuation` | Ratios, DCF (CAPM, WACC, Gordon), Blume-adjusted beta, **reverse DCF**, sensitivity grid, peer multiples | Equity Investments |
| 2 | Portfolio & risk | `bistlab.portfolio` | Return/volatility, historical & parametric VaR, CVaR, max drawdown, Markowitz (min-variance, max-Sharpe, efficient frontier), rolling backtest | Portfolio Management |
| 3 | Derivatives | `bistlab.derivatives` | Black-Scholes-Merton, Greeks, implied volatility, binomial (European/American), Monte Carlo, futures pricing and index hedging | Derivatives |
| 4 | Credit risk | `bistlab.credit` | Altman Z'' (emerging markets), synthetic rating from interest coverage (Damodaran), Merton/KMV distance to default | Fixed Income — Credit Analysis |
| 5 | Corporate governance | `bistlab.governance` | 21-indicator scorecard parsed from regulatory governance filings (KAP), regulator weights | Corporate Issuers — Governance / ESG |
| 6 | Fund x-ray | `bistlab.funds` | Fund prices (TEFAS), parsing of monthly holdings reports, look-through exposure, replica return gap, fund overlap | Portfolio Management |
| 7 | IT self-audit | `bistlab.audit` | 19 automated controls over the project's own infrastructure (access, backups, dependencies, data integrity) with evidence-backed reports | Model risk & IT controls |

Supporting layers: **data quality** checks on every price series, a **real / USD view** (CPI-deflated and dollar returns), a **macro stress test** (market and FX betas under shock scenarios).

## Highlights

All based on historical data; caveats are listed under *Known limitations*.

- **What is the market pricing in?** A reverse DCF solves for the cash-flow growth that justifies today's price. For one stock it implies FCF *shrinking* 14.6% a year for five years; for another it implies FCF *doubling* every year (+103%). Not a buy/sell signal — a quantified statement of what the price assumes.
- **Risk was not rewarded.** Over two years (Nov 2024 – Nov 2026), an equal-weight portfolio of eight large caps returned 21.3% a year in TRY with 24.5% volatility — a Sharpe ratio of **−0.77** against a 40% risk-free rate. Six of the eight stocks sit below the risk-free line on the efficient-frontier chart.
- **Markowitz is an error maximiser, shown with real numbers.** Unconstrained max-Sharpe weights put 93% in a single stock on a 2-year window; on a 1-year window the same optimiser puts 65% in a different stock. Min-variance weights, which ignore noisy return estimates, barely move.
- **Option intuition breaks at 40% rates.** An at-the-money call has a delta of 0.63, not 0.5. A deep in-the-money one-year American put is worth exactly its intrinsic value (exercise now), while the European put is worth a third of that — its time value is negative because the forward price sits above the strike.
- **Same theme, different risk.** Two "energy" funds: one holds 63% of its portfolio in foreign-currency assets with an index beta of 0.16; the other is pure domestic equity with a beta of 0.58. Their holdings overlap by only 5.7%.
- **Three credit measures, one company.** An airline rated investment grade (A−) on interest coverage is the second-riskiest name in the sample under Merton, because lease-inclusive debt exceeds its market value.
- **Nominal vs real.** Jan 2023 – Nov 2026: the BIST 100 index rose 88% in lira, fell 49% in real terms and 30% in dollars.
- **Free data fails in instructive ways.** Yahoo applied a reverse split 8 days early, repeated a suspended stock's last price for 308 trading days (fake zero volatility), and its EBIT for Turkish companies includes the IAS 29 monetary loss — which made one defence company look CCC-rated instead of AA. Each case is detected by a check, not by luck.
- **I audited my own project.** The first IT self-audit passed 11 of 15 controls. After remediation, a verification round found a control that looked compliant but did not actually operate (design effectiveness ≠ operating effectiveness). Current run: 19/19. Reports in [`docs/audit/`](docs/audit/).

## Architecture

```
Data sources                          PostgreSQL 17                 Analytics (pure functions)
────────────                          ─────────────                 ──────────────────────────
yfinance (prices, statements)  ─┐                                   valuation   portfolio
CBRT EVDS (FX, CPI)            ─┼─►  securities, prices  ──────►    derivatives credit
TEFAS (fund prices)            ─┤    financial_items, macro         governance  funds
KAP (holdings, governance)     ─┘    funds, fund_holdings           audit · quality · real · stress
                                                                           │
                                         FastAPI (typed, read-only) ◄──────┘
                                                    │
                                         Next.js web app (Company, Options, Screener, Portfolio)
```

- **Pure calculation core.** Every model is a pure function; data access sits behind `Protocol` interfaces. The same function runs from the CLI, the API and the web app, and the API test suite runs without a database.
- `src/bistlab/` — packages; each module has a CLI (`python -m bistlab.<module>.<file>`).
- `src/bistlab/api/` — FastAPI app: schemas, core, services; OpenAPI docs at `/docs`.
- `app/` — Next.js (TypeScript) front end.
- `assumptions/` — DCF assumption files (TOML). `scripts/` — backup and migration scripts. `docs/audit/` — self-audit reports.

## Web app

| Page | What you can do |
| --- | --- |
| Company | Price chart, multiples vs peer median, interactive DCF (WACC and terminal-growth sliders, reverse DCF, 5×3 sensitivity) |
| Options lab | Price one option three ways (BSM, binomial, Monte Carlo), Greeks, early-exercise premium, implied volatility, index-futures hedge |
| Screener | Eight companies side by side across valuation, credit, governance and data quality; P/E × credit-rating quadrant |
| Portfolio | Weight sliders, realised risk (VaR, CVaR, drawdown, Sharpe), efficient frontier with your portfolio, min-variance and max-Sharpe points, correlation heat map |

## HTTP API (read-only)

`/health`, `/securities`, `/prices/{ticker}`, `/quality/prices`, `/real/returns`, `/real/fcf`, `/stress/macro`, `/credit/scores`, `/credit/merton`, `/valuation/multiples`, `/valuation/dcf/{ticker}`, `/governance/scores`, `/derivatives/option`, `/derivatives/implied-vol`, `/derivatives/futures-hedge`, `/funds/{code}/xray`, `/portfolio/risk`. JSON responses, invalid input returns 422, OpenAPI documentation at `/docs`.

## Getting started

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), Docker, Node.js 20+.

```bash
git clone https://github.com/egegundogdu/bistlab.git
cd bistlab
cp .env.example .env          # fill in DATABASE_URL, POSTGRES_PASSWORD, EVDS_API_KEY
docker compose up -d          # PostgreSQL
uv sync --dev
uv run pytest -q

# API and web app (two terminals)
uv run uvicorn bistlab.api.main:app --reload
cd app && npm install && npm run dev   # http://localhost:3000
```

The EVDS key is free from the Central Bank of the Republic of Türkiye. `.env` is git-ignored.

## CLI examples

```bash
# Data
uv run python -m bistlab.data.prices THYAO ASELS XU100 --start 2023-01-01
uv run python -m bistlab.data.financials THYAO ASELS

# 1 · Valuation and 2 · Portfolio
uv run python -m bistlab.valuation.multiples THYAO ASELS
uv run python -m bistlab.portfolio.optimize THYAO ASELS BIMAS --max-weight 0.35

# 3 · Derivatives
uv run python -m bistlab.derivatives.black_scholes --ticker THYAO --days 90

# 4 · Credit risk
uv run python -m bistlab.credit.scores THYAO EREGL
uv run python -m bistlab.credit.merton THYAO EREGL BIMAS

# 5 · Corporate governance (KAP > company > Corporate Governance > Excel)
uv run python -m bistlab.governance.scorecard data/kap/*_kybf.xls --detail

# 6 · Fund x-ray
uv run python -m bistlab.funds.tefas IKP --start 2023-01-01
uv run python -m bistlab.funds.kap_report data/kap/IKP_2026.10.pdf --period 2026-10
uv run python -m bistlab.funds.xray IKP --compare KVT

# 7 · IT self-audit
uv run python -m bistlab.audit.selfcheck

# Data quality and real/USD view
uv run python -m bistlab.quality.prices --issues
uv run python -m bistlab.real.view THYAO ASELS
```

Add `--help` to any command for all options.

## Engineering practices

- **Tests:** pytest, 188 tests; calculation functions and the API are tested without a database (fakes and seeded synthetic prices).
- **Static checks:** ruff (lint + format), mypy `--strict`, TypeScript type checking.
- **CI:** GitHub Actions on every PR (Python and web jobs); `main` is protected — no merge without a green build.
- **Audit trail:** every price row records its source and fetch time (`source`, `fetched_at`).
- **Backups:** daily `pg_dump` via launchd, 14 kept, restore tested automatically; a missed backup becomes an audit finding.

## Known limitations

- **Free-cash-flow yield:** Yahoo does not report lease payments separately; under IFRS 16 they move to financing, so airlines with leased fleets show inflated FCF (one airline: 43% reported, ~22% after debt and lease repayments).
- **Timing mismatch:** cash flows and earnings are from the last fiscal year end (IAS 29, purchasing power at that date) while market value uses today's price. `bistlab.real.view` shows both views side by side.
- **Credit scores** use reported operating profit, not Yahoo's EBIT (which includes the IAS 29 monetary loss).
- **P/E** uses the last annual earnings in the reporting currency; it differs from trailing-twelve-month, TRY-based figures on local data sites, by definition.
- Prices and statements come from yfinance, not an official source; the latest day can be revised.
- Merton assumes normal returns: absolute default probabilities are not realistic and are used for ranking only. Damodaran's rating table is calibrated to US rates.
- The governance scorecard relies on company self-disclosure; it is not an official rating.
- Option and futures prices are theoretical (cost of carry); exchange quotes are not yet ingested.
- Portfolio optimisation is in-sample; out-of-sample testing is on the roadmap.

## Roadmap

English UI and API messages · live demo · second market (S&P 500 and UAE equities) · Sharia-compliance screen · out-of-sample portfolio backtest · event study on regulatory disclosures · AI assistant that cites its sources.

## License

MIT. Not investment advice.
