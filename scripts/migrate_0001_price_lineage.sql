-- Mevcut satırlarda fetched_at NULL kalır (gerçek çekilme zamanı bilinmiyor);
-- yeni ve güncellenen satırlar otomatik zaman damgası alır.
ALTER TABLE prices ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'yfinance';
ALTER TABLE prices ADD COLUMN IF NOT EXISTS fetched_at TIMESTAMPTZ;
ALTER TABLE prices ALTER COLUMN fetched_at SET DEFAULT now();
