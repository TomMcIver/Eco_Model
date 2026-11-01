# Data sources (first vertical slice)

Verified 2026-10-29 against the official Stats NZ information-release pages and
their "Download data" files. The same mapping lives in code:
`src/eco_model/data/statsnz_catalog.py` (`STATSNZ_SERIES`).

Licence: Stats NZ content is CC BY 4.0 ("CC BY 4.0 Stats NZ" on every snapshot).
Attribution: "Source: Stats NZ and licensed by Stats NZ for re-use under the
Creative Commons Attribution 4.0 International licence."

## Series mapping

| contracts id | Stats NZ series ref | Definition (as labelled in the file) | Units | SA | Release / file |
| --- | --- | --- | --- | --- | --- |
| `gdp_real_sa_chain_volume` | `SNEQ.SG01RSC00B01` | Group "Series, GDP(P), Chain volume, Seasonally adjusted, Total"; title "Gross Domestic Product - production measure" | NZ$ millions (UNITS=Dollars, MAGNITUDE=6), chain-volume | Seasonally adjusted | *Gross domestic product: <quarter>* release, main CSV `gross-domestic-product-<month>-<year>-quarter.csv` (older releases: zipped CSV tables) |
| `cpi_all_groups_index` | `CPIQ.SE9A` | Group "CPI All Groups for New Zealand", title "All groups" | Index, June 2017 quarter = 1000 (2017.06 value is exactly 1000 in the file) | Not seasonally adjusted (as published) | *Consumers price index: <quarter>* release, `...-index-numbers.csv` (2018-2021 releases: zipped CSV tables) |
| `hlfs_unemployment_rate_sa` | `HLFQ.S1F3S` | Group "Labour Force Status by Sex: Seasonally Adjusted", "Unemployment Rate", total both sexes (Table 1 of the HLFS workbook lists S1F1S males / S1F3S total) | Percent | Seasonally adjusted | *Labour market statistics: <quarter>* release, zipped CSV `labour-market-statistics-<month>-<year>-quarter.zip`, member `hlfs-*-csv.csv` |

Cross-check (June 2026 GDP release): `SNEQ.SG01RSC01B01PC` (q/q % change of the
same series) = 0.2 for 2026Q2; 71805 / 71628 - 1 = 0.25 %.

## Release URLs and publication times

Release page: `https://www.stats.govt.nz/information-releases/<prefix>-<month>-<year>-quarter/`
with prefixes `gross-domestic-product`, `consumers-price-index`,
`labour-market-statistics`. Every page embeds `"PublicationDate":"YYYY-MM-DD 10:45:00"`
(NZ local). This 10:45 NZ release time was verified on every ingested page,
converted with `Pacific/Auckland` (DST-aware) to UTC, and stored in the
`release_calendar` table together with the page URL.

Archived release pages exist from the March 2017 quarter (GDP), June 2017 (CPI,
HLFS) onwards; earlier pages 404. Each archived file is ingested as its own vintage.

## Vintage / publication-time rules

1. Observation `published_at` = release `PublicationDate`, **unless** the file's
   HTTP `Last-Modified` is more than 1 hour after it. Then the file was
   replaced after release (e.g. `...-corrected.csv`) and its values are stamped
   with `Last-Modified` instead (fail-closed: the original as-released bytes are
   not available). The reason is recorded in each snapshot's `notes`
   (`vintage_basis`).
2. All historical quarters inside one release file carry that file's
   publication time — that is the honest vintage. A single current release
   therefore supports only the PSEUDO_OOS (revised-data) track. The archive of
   per-release files gives genuine first-release vs later vintages from 2017.
3. `release_calendar` holds the official release time of each reference
   quarter's first publication (from the page, independent of file
   replacement). Use `DuckDBObservationStore.latest_period_released()` to decide
   which quarter was available at a past origin. `assumed_publication_lag_days`
   (GDP 80, CPI 21, HLFS 37 days; ESTIMATED) is only a fallback.
4. Raw files are kept unchanged at `data/raw/<provider>_<dataset>/<sha256>.<ext>`;
   release pages are kept too (`statsnz_<dataset>-release-page`). Response
   headers (ETag, Last-Modified, Content-Type, Content-Length, Date) are in
   snapshot `notes`; cookies are not stored.
5. Each observation also stores `release_published_at` (the official time of
   the release its file belongs to). Among values available at a time, the
   newest release wins (`latest`, `as_of`), so a replaced old-release file can
   never override a newer release. `first_release` takes the value from the
   earliest release held, even if that release's file was later replaced
   (check snapshot `notes.vintage_basis`).

## Ingestion run 2026-10-29 (`python -m eco_model.data.ingest`)

| Series | Releases ingested (vintages) | Latest-vintage range | Latest value | Calendar rows |
| --- | --- | --- | --- | --- |
| GDP `SNEQ.SG01RSC00B01` | 38 (2017Q1 .. 2026Q2 releases) | 1987Q2 .. 2026Q2, no gaps | 71,805 (2026Q2, NZ$m) | 38 |
| CPI `CPIQ.SE9A` | 35 (2018Q1 .. 2026Q3 releases) | 1914Q2 .. 2026Q3, no gaps | 1368 (2026Q3) | 38 (2017Q2 .. 2026Q3) |
| HLFS `HLFQ.S1F3S` | 36 (2017Q3 .. 2026Q2 releases) | 1986Q1 .. 2026Q2, no gaps | 5.6 % (2026Q2) | 37 (2017Q2 .. 2026Q2) |

Releases without usable values (release dates still in `release_calendar`):

- CPI June, September, December 2017 quarters: pages offer only `.xls`/PDF or a
  visualisation CSV (no `CPIQ.SE9A`); `.xls` is not parsed (no xlrd dependency).
- HLFS June 2017 quarter: the page's CSV link serves the June 2018 quarter file
  (latest period 2018Q2); rejected as a mislinked file (fail-closed).
- March 2017 quarter CPI and HLFS release pages return 404.

Vintages stamped at file Last-Modified instead of the release time (file
replaced after release; release quarter shown):

- GDP: 2017Q1, 2017Q2, 2018Q4 (same day, 16:29 NZDT), 2020Q2 (`-corrected`),
  2021Q2 (`-corrected-27-9-2021`).
- HLFS: 2017Q3, 2018Q2 (`-updated-2-august-2018`), 2021Q2 (`-corrected`),
  2024Q4 .. 2025Q3 (all re-uploaded 2026-03-11), 2025Q4 and 2026Q1
  (`-revised`, re-uploaded with the June 2026 quarter release).
- CPI: none.

Size: ~1.2 GB of raw files under `data/raw/` (git-ignored); DuckDB ~7 MB.

## Known source quirk: zero as "not collected"

Stats NZ CPI files carry `0` in `Data_value` for early-history quarters that were not collected (e.g. CPI all groups, 1914Q3-1925Q2 for most quarters). The store keeps these rows as published; `eco_model.transforms` treats non-positive index/level values as missing so no zero ever enters a growth or inflation calculation.
