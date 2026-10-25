CREATE SEQUENCE IF NOT EXISTS seq_commit_id START 1;

CREATE TABLE IF NOT EXISTS api_schemas (
    api_name VARCHAR PRIMARY KEY,
    source_url VARCHAR,
    original_size_bytes BIGINT,
    minified_size_bytes BIGINT,
    token_reduction_pct DOUBLE,
    minified_json VARCHAR,
    content_hash VARCHAR,
    last_updated_utc VARCHAR
);

CREATE TABLE IF NOT EXISTS ledger (
    commit_id BIGINT PRIMARY KEY,
    timestamp_utc VARCHAR,
    operation VARCHAR,
    api_name VARCHAR,
    endpoint_drift_summary VARCHAR
);
