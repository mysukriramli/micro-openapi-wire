# ⚡ Micro-OpenAPI Wire

An autonomous, zero-maintenance token-reduction infrastructure running entirely on GitHub Actions. It pulls multi-megabyte OpenAPI specifications from major platforms, parses their Abstract Syntax Tree (AST), strips out verbose human prose and redundant types, and emits compact function-calling definitions optimized for LLMs.

## Token Reduction Metrics
- **Average Token Savings**: 85% – 95%
- **Input Overhead**: Shrinks 30,000+ token Swagger specs down to under 1,500 tokens.

## Machine Feeds
- [`v1/index.json`](public/v1/index.json) (Catalog & reduction stats)
- [`llms.txt`](public/llms.txt) (Token-efficient LLM digest)
- `schemas.parquet` (Columnar database snapshot)

## Architecture
- **Ingestion**: Raw upstream JSON/YAML OpenAPI definitions
- **Transformation Engine**: Python AST Pruner + DuckDB
- **Ledger**: Git-native append-only JSONL committed to `/data/history`
- **Delivery**: GitHub Pages (Fastly Edge CDN)
