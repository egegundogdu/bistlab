# bistlab bilgi sistemleri öz denetimi — 2026-11-26

Sonuç: 15 kontrolden 11 uygun, 4 bulgu.

| Kod | Alan | Kontrol | Durum | Kanıt |
| --- | --- | --- | --- | --- |
| BG-01 | Gizli bilgi | .env .gitignore'da | Uygun | .gitignore satırları kontrol edildi |
| BG-02 | Gizli bilgi | .env git'te izlenmiyor | Uygun | git ls-files .env |
| BG-03 | Gizli bilgi | .env hiçbir commit'e girmemiş | Uygun | git log --all -- .env |
| BG-04 | Gizli bilgi | İzlenen dosyalarda anahtar kalıbı yok | Uygun | taranan tüm dosyalar temiz |
| DY-01 | Değişiklik yönetimi | main dalı korumalı (PR + CI zorunlu) | Bulgu (Orta) | gh api .../branches/main/protection |
| DY-02 | Değişiklik yönetimi | main'e giren değişikliklerin ≥%90'ı PR'dan | Uygun | 27 commit, PR oranı %96 |
| DY-03 | Değişiklik yönetimi | CI'da lint, tip ve test adımları | Uygun | ruff, mypy, pytest var |
| DY-04 | Değişiklik yönetimi | pre-commit kancaları tanımlı | Uygun | .pre-commit-config.yaml |
| BY-01 | Bağımlılık yönetimi | Bağımlılık sürümleri kilitli | Uygun | uv.lock |
| VB-01 | Veri bütünlüğü | Sıfır/negatif kapanış fiyatı yok | Uygun | 0 hatalı satır |
| VB-02 | Veri bütünlüğü | Fon ağırlıkları toplamı ≈ %100 | Uygun | 2 rapor; sapan: yok |
| VB-03 | Veri bütünlüğü | Fiyat serileri güncel (≤10 gün) | Uygun | 81 seri; eski: yok |
| DI-01 | Denetim izi | Fiyat kayıtlarında kaynak ve çekilme zamanı | Bulgu (Orta) | prices sütunları: close, date, high, low, open, security_id, volume |
| YD-01 | Yedekleme | Veritabanı yedekleme betiği var | Bulgu (Orta) | scripts/backup* yok |
| ER-01 | Erişim | Veritabanı parolası koda gömülü değil | Bulgu (Düşük) | docker-compose.yml |

Resmî bağımsız denetim değildir; VII-128.10 kontrol alanlarından esinlenen öz değerlendirmedir.
