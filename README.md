# Chapter 8 reproducibility package

This package provides the canonical data and executable analysis materials behind
the article *From Commit Granularity to Query Amortization: Native Maintenance in
Apache Iceberg and Delta Lake*.

## Contents

- `canonical_manifest/`: the 72-run canonical manifest.
- `run_level_exports/`: ingestion (72 rows), query (432 format/run/phase/query
  rows), and maintenance (72 rows) summaries.
- `raw_exports/`: complete Iceberg and Delta ingestion, query, and maintenance
  table exports dated 2026-10-24, plus Delta phase-reconstruction quality data.
- `analysis/specification/`: locked statistical specification v1.0, machine-readable
  YAML, and its recorded hash.
- `analysis/scripts/`: executable publication analyses. The locked bootstrap seed is
  20261025, as specified in the scripts and specification.
- `analysis/results/`: final versioned result tables, diagnostics, reports, and run
  manifests used for the reported findings.
- `figures/python/` and `figures/R/`: figure-generation source code and figure-specific
  source data/provenance.
- `audit/`: data-integrity, deviation, reconciliation, and validation reports.
- `SHA256SUMS.csv`: file-level integrity manifest for this package.

## Validation performed during packaging

- canonical manifest rows: 72
- ingestion run-summary rows: 72
- query run-summary rows: 432
- maintenance run-summary rows: 72

The raw exports and historical result files are copied without modification. No
experiment was rerun and no statistical model was re-estimated during packaging.

## Companion source archive

The freshly downloaded consumer and measurement code is distributed separately as
`raas_lakehouse_code_live_20261101.zip`. A second preserved export,
`raas_lakehouse_code_preserved_snapshot_20261024.zip`, is retained for comparison.
Both archives contain provenance notes explaining the difference between later
configuration state and the historical runtime versions used for the canonical
campaigns.
