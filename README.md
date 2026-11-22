# bistlab

[![CI](https://github.com/egegundogdu/bistlab/actions/workflows/ci.yml/badge.svg)](https://github.com/egegundogdu/bistlab/actions/workflows/ci.yml)

Borsa İstanbul şirketleri için açık kaynak analiz platformu: değerleme, portföy riski, türev fiyatlama, kredi riski, kurumsal yönetim skoru ve bilgi sistemleri uyum denetimi.

Her modül, SPK lisanslama sınavlarının (SPL Düzey 3, Türev Araçlar, Kredi Derecelendirme, Kurumsal Yönetim Derecelendirme, Bilgi Sistemleri Bağımsız Denetim) bir konusunu çalışan, test edilmiş bir yazılıma dönüştürür.

## Modüller

| Modül | Kapsam | Durum |
| --- | --- | --- |
| `valuation` | Rasyo analizi, DCF, çarpan analizi | Geliştiriliyor |
| `portfolio` | Markowitz optimizasyonu, VaR/CVaR, backtest | Planlandı |
| `derivatives` | Black-Scholes, binom, Monte Carlo, Greeks | Planlandı |
| `credit` | Altman Z'', Merton modeli, temerrüt olasılığı | Planlandı |
| `governance` | KAP raporlarından kurumsal yönetim skoru | Planlandı |
| `audit` | SPK BS tebliğine göre uyum kontrolleri | Planlandı |

## Mimari

```
Veri kaynakları (KAP, fiyat, TEFAS, TCMB EVDS)
        ↓
ETL → PostgreSQL
        ↓
bistlab çekirdek kütüphane (modüller)
        ↓
FastAPI → Web arayüzü (Next.js)
```

## Kurulum

Gereksinimler: Python 3.12, [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/egegundogdu/bistlab.git
cd bistlab
uv sync --dev
uv run pre-commit install
```

## Geliştirme

```bash
uv run pytest          # testler
uv run ruff check .    # kod stili
uv run mypy            # tip kontrolü
```

## Uyarı

Bu proje eğitim ve portföy amaçlıdır. Üretilen hiçbir çıktı yatırım tavsiyesi değildir.

## Lisans

MIT