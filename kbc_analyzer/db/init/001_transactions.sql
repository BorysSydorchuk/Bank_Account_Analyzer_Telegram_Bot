-- Runs automatically on first container boot (mounted into
-- /docker-entrypoint-initdb.d/ — only fires against an empty data directory).

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      TEXT NOT NULL,
    -- Enable Banking's own transaction reference (entry_reference). This is the natural
    -- key used to detect duplicates on repeated syncs — scoped per account_id since the
    -- same reference could in principle repeat across different accounts.
    external_id     TEXT NOT NULL,
    booking_date    DATE,
    amount          DECIMAL(10,2) NOT NULL,
    currency        TEXT DEFAULT 'EUR',
    description     TEXT,
    category        TEXT,
    subcategory     TEXT,
    raw_data        JSONB,
    fetched_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (account_id, external_id)
);