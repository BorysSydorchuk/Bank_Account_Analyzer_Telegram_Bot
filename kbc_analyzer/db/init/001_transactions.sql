-- Runs automatically on first container boot (mounted into
-- /docker-entrypoint-initdb.d/ — only fires against an empty data directory).

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      TEXT NOT NULL,
    booking_date    DATE,
    amount          DECIMAL(10,2) NOT NULL,
    currency        TEXT DEFAULT 'EUR',
    description     TEXT,
    category        TEXT,
    subcategory     TEXT,
    raw_data        JSONB,
    fetched_at      TIMESTAMPTZ DEFAULT NOW()
);