# Choose the initial research data store

Status: closed
Type: grilling
Blocked by: none

## Question

What storage and provenance requirements must the first data pipeline satisfy?

## Resolution

Use DuckDB and Parquet initially. Retain versioned datasets and original source files with retrieval timestamps, publication vintages, revision history, and complete provenance. Historical backtests may only use information available at each simulated forecast date.

