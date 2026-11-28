-- Existing rows keep fetched_at NULL (the real fetch time is unknown);
-- new and updated rows get an automatic timestamp.
ALTER TABLE prices ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'yfinance';
ALTER TABLE prices ADD COLUMN IF NOT EXISTS fetched_at TIMESTAMPTZ;
ALTER TABLE prices ALTER COLUMN fetched_at SET DEFAULT now();
