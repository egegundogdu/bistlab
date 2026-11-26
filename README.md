# bistlab

[![CI](https://github.com/egegundogdu/bistlab/actions/workflows/ci.yml/badge.svg)](https://github.com/egegundogdu/bistlab/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Lisans](https://img.shields.io/badge/lisans-MIT-green)

**Borsa İstanbul için açık kaynaklı analiz ve risk laboratuvarı.** Değerleme, portföy riski, türev fiyatlama, kredi riski, kurumsal yönetim, fon analizi ve kendi bilgi sistemlerinin denetimi; her modül bir SPK lisans alanına karşılık geliyor.

> *English summary: an open-source analytics and risk lab for Borsa Istanbul. Seven modules — valuation, portfolio risk, derivatives, credit risk, corporate governance scoring, fund look-through and an IT self-audit — each mapped to a Turkish Capital Markets Board (SPK) licence area. Python 3.12, PostgreSQL, strict typing, 130+ tests, CI-gated main branch.*

> ⚠️ **Yatırım tavsiyesi değildir.** Tüm çıktılar eğitim ve yöntem gösterimi amaçlıdır; al/sat önerisi içermez.

## Modüller

| # | Modül | Paket | Ne yapıyor | SPK lisans alanı |
| --- | --- | --- | --- | --- |
| 1 | Değerleme | `bistlab.valuation` | Rasyolar, DCF (CAPM, WACC, Gordon), beta, ters DCF, çarpanlar | SPL Düzey 3 |
| 2 | Portföy ve risk | `bistlab.portfolio` | Getiri/oynaklık, VaR, CVaR, maks. düşüş, Markowitz, yürüyen pencereli backtest | SPL Düzey 3 |
| 3 | Türev araçlar | `bistlab.derivatives` | Black-Scholes-Merton, Greeks, ima edilen volatilite, binom, Monte Carlo, vadeli ve hedge | Türev Araçlar |
| 4 | Kredi riski | `bistlab.credit` | Altman Z'' (gelişmekte olan piyasa), sentetik not (Damodaran), Merton/KMV temerrüde uzaklık | Kredi Derecelendirme |
| 5 | Kurumsal yönetim | `bistlab.governance` | KAP Kurumsal Yönetim Bilgi Formu'ndan 21 göstergeli karne, SPK ağırlıkları | Kurumsal Yönetim Derecelendirme |
| 6 | BS öz denetimi | `bistlab.audit` | Projenin kendi altyapısına 16 otomatik kontrol (VII-128.10 alanları), kanıtlı rapor | Bilgi Sistemleri Bağımsız Denetim |
| 7 | Fon röntgeni | `bistlab.funds` | TEFAS fiyatları, KAP portföy raporu ayrıştırma, içeriden dağılım, getiri farkı, fon çakışması | SPL Düzey 3 |

## Öne çıkan bulgular

Ayrıntılar ve uyarılar modül notlarında; hepsi geçmiş veriye dayanır.

- **Aynı tema, farklı risk:** iki "enerji" fonundan biri (IKP) portföyünün %63'ünü döviz cinsi varlıklarda tutuyor ve BIST 100 betası 0,16; diğeri (KVT) saf BIST, betası 0,58. Ortak varlık oranı yalnızca %5,7.
- **Üç kredi ölçümü, tek şirket:** faiz karşılamaya göre AA olan bir havayolu, Merton modeline göre örneklemin en riskli ikinci şirketi; çünkü kiralama dahil borç yükü piyasa değerini aşıyor.
- **TL faiz şoku sentetik notları çarpıtıyor:** TL raporlayan şirketlerin faiz karşılaması 2023 sonrası sert düştü; USD raporlayan şirket sabit kaldı.
- **Kendi projemi denetledim:** ilk denetim 11/15. Bulgular giderildi, ardından doğrulama turunda "uygun" görünen bir kontrolün aslında işlemediği ortaya çıktı (tasarım etkinliği ≠ işleyiş etkinliği). Raporlar [`docs/audit/`](docs/audit/) altında.

## Mimari

```
Veri kaynakları                      PostgreSQL 17                 Analiz modülleri
─────────────────                    ─────────────                 ─────────────────
yfinance (fiyat, finansal tablo) ─┐                                valuation  portfolio
TCMB EVDS3 (kur, TÜFE)           ─┼─► securities, prices ──────►   derivatives  credit
TEFAS (fon fiyatları)            ─┤   financial_items, macro       governance  funds
KAP (portföy raporu, KY formu)   ─┘   funds, fund_holdings         audit (öz denetim)
```

- `src/bistlab/` — paketler; her modül `python -m bistlab.<modül>.<dosya>` ile çalışan bir komut satırı arayüzüne sahip.
- `src/bistlab/common.py` ve `data/db.py` — paylaşılan yardımcılar ve veri modeli (SQLAlchemy 2).
- `assumptions/` — DCF varsayım dosyaları (TOML).
- `scripts/` — yedekleme ve veritabanı göç (migration) betikleri.
- `docs/audit/` — öz denetim raporları.

## Kurulum

Gereksinimler: Python 3.12, [uv](https://docs.astral.sh/uv/), Docker.

```bash
git clone https://github.com/egegundogdu/bistlab.git
cd bistlab
cp .env.example .env          # DATABASE_URL, POSTGRES_PASSWORD, EVDS_API_KEY değerlerini doldur
docker compose up -d          # PostgreSQL
uv sync --dev
uv run pytest -q
```

EVDS anahtarı TCMB EVDS3 sitesinden ücretsiz alınır. `.env` git'e girmez.

## Kullanım örnekleri

```bash
# Veri
uv run python -m bistlab.data.prices THYAO ASELS XU100 --start 2023-01-01
uv run python -m bistlab.data.financials THYAO ASELS

# 1 · Değerleme ve 2 · Portföy
uv run python -m bistlab.valuation.multiples THYAO ASELS
uv run python -m bistlab.portfolio.optimize THYAO ASELS BIMAS --max-weight 0.35

# 3 · Türevler
uv run python -m bistlab.derivatives.black_scholes --ticker THYAO --days 90

# 4 · Kredi riski
uv run python -m bistlab.credit.scores THYAO EREGL
uv run python -m bistlab.credit.merton THYAO EREGL BIMAS

# 5 · Kurumsal yönetim (KAP > şirket > Kurumsal Yönetim > EXCEL)
uv run python -m bistlab.governance.scorecard data/kap/*_kybf.xls --detail

# 6 · Öz denetim
uv run python -m bistlab.audit.selfcheck

# 7 · Fon röntgeni
uv run python -m bistlab.funds.tefas IKP --start 2023-01-01
uv run python -m bistlab.funds.kap_report data/kap/IKP_2026.10.pdf --period 2026-10
uv run python -m bistlab.funds.xray IKP --compare KVT
```

Tüm seçenekler için her komuta `--help` ekleyin.

## Kalite ve süreç

- **Testler:** pytest, 130+ test; saf hesaplama fonksiyonları veritabanından bağımsız test edilir.
- **Statik kontrol:** ruff (lint + format), mypy `--strict`.
- **CI:** her PR'da GitHub Actions; `main` dalı korumalı — CI geçmeden birleştirme yok.
- **Denetim izi:** fiyat kayıtlarında kaynak ve çekilme zamanı (`source`, `fetched_at`).
- **Yedekleme:** `scripts/backup.sh` (pg_dump); geri yükleme testi yapıldı.

## Veri kalitesi, reel görünüm ve operasyon

| Araç | Ne yapar | Komut |
| --- | --- | --- |
| Fiyat kalitesi | Her seride eksik gün (BIST: XU100 takvimi; yabancı: iş günü boşluğu), bayatlık, şüpheli sıçrama (bölünme oranı, geri dönen tek gün), donuk fiyat, geçici son gün | `python -m bistlab.quality.prices --issues --detail SOL.MC` |
| Reel / USD görünüm | Nominal, reel (TÜFE) ve USD getiri; TMS 29 FCF'sini bugünkü satın alma gücüne taşıyarak FCF getirisi | `python -m bistlab.real.view THYAO ASELS` |
| Günlük yedek | launchd ile her gün 21:00 yedek, son 14 yedek saklanır; Docker kapalıysa kaydedilir, 7 gün atlanırsa öz denetimde YD-02 bulgu verir | `./scripts/install_backup_agent.sh 21` |
| HTTP API (salt okunur) | `/health`, `/quality/prices`, `/real/returns`, `/real/fcf`, `/stress/macro`, `/credit/scores`, `/credit/merton`, `/valuation/multiples`, `/governance/scores`; JSON, OpenAPI belgesi `/docs` | `uv run uvicorn bistlab.api.main:app --reload` |

Öne çıkan bulgular:

- **2023-01 → 2026-11:** XU100 nominal +%88, reel −%49, USD −%30. İncelenen 8 hisseden yalnız ASELS, TUPRS ve BIMAS reel olarak pozitif.
- **Ücretsiz veri tuzakları:** Yahoo bir ters bölünmenin düzeltmesini 8 gün erken uyguladı (SOL.MC ×5), işlemi durdurulan hissede son fiyatı 308 işlem günü tekrarladı (sahte sıfır oynaklık), arife yarım günlerini bazı hisselerde atladı. 81 seride: 65 iyi, 16 dikkat, 0 sorunlu.

## Bilinen sınırlamalar

- **FCF getirisi:** Yahoo'da kira ödemeleri ayrı satır değil; TFRS 16 ile finansmana geçtiği için kiralık filo kullanan havayollarında (PGSUS, THYAO) FCF şişik görünür. PGSUS 2025: %43, borç/kira geri ödemesi düşülünce ~%22.
- **Zaman uyumsuzluğu:** FCF ve kârlar son yıl sonu (TMS 29, o tarihin satın alma gücü), piyasa değeri bugünün fiyatı. Yıl sonu lirası bugünkünden değerli olduğu için düzeltme FCF getirisini *artırır* (Ara 2025 → Eki 2026 katsayı 1,28; FROTO %30 → %38,5). Yüksek FCF getirileri bu uyumsuzluktan kaynaklanmıyor. `python -m bistlab.real.view` iki değeri yan yana gösterir.
- **Kredi skorları:** faaliyet kârı Yahoo'nun EBIT'i yerine esas faaliyet kârından alınır (EBIT, TMS 29 parasal kaybını içerir; ASELS 2022 karşılaması 0,55 değil 5,64).
- Fiyat ve finansal tablo verisi yfinance'tan gelir; resmî kaynak değildir. Son işlem gününün verisi kaynak tarafından geri çekilebilir.
- 2023'ten itibaren TMS 29 (enflasyon muhasebesi) bazı oranları ve tarihsel karşılaştırmaları etkiler.
- Merton modeli normal dağılım varsayar; mutlak temerrüt olasılıkları gerçekçi değildir, sıralama için kullanılmalıdır. Damodaran not tablosu ABD faiz ortamına göre kalibre edilmiştir.
- Kurumsal yönetim karnesi şirket beyanına dayanır; resmî derecelendirme notu değildir.
- Fon getiri farkı tek bir aylık raporla hesaplanır; yönetici katkısı hakkında sonuç için çok sayıda ay gerekir.
- KAP rapor ayrıştırıcısı iki portföy şirketinin formatıyla test edildi.

## Yol haritası

Veri kalitesi paneli · reel/USD katmanı · makro stres testi · KAP bildirim olay çalışması · FastAPI · Next.js arayüz · kaynaklarını gösteren yapay zekâ asistanı.

## Lisans

MIT. Yatırım tavsiyesi değildir.
