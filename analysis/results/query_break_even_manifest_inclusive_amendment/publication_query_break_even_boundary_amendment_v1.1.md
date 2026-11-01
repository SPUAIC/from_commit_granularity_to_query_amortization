# Temporal Query Break-Even Boundary Amendment v1.1

## Decision

The locked v1.0 specification defined Iceberg `rewrite_data_files` as the primary temporal-amortization numerator and the full `rewrite_data_files + rewrite_manifests` sequence as a sensitivity. For the manuscript, v1.1 changes the primary Iceberg boundary to the complete native maintenance sequence actually executed after each ingestion run. The data-file rewrite alone becomes the Iceberg sensitivity. Delta `OPTIMIZE` remains unchanged.

This is a documented post-specification amendment. It is conservative for Iceberg because it increases, never decreases, the maintenance numerator. No raw data, query saving, bootstrap draw, confidence interval, or Delta estimate was changed or recomputed.

Across the canonical Iceberg runs, `rewrite_manifests` added a median 6.8% of `rewrite_data_files` duration and a maximum 36.4%.

## Amended primary results

| Format | Query | Range | Minimum cell, estimate [95% CI] | Maximum cell, estimate [95% CI] |
|---|---|---:|---|---|
| Iceberg | Q2 | 9.8-216.9 | SF500/160k: 9.8 [9.4, 10.1] | SF50/2.56m: 216.9 [198.5, 227.2] |
| Iceberg | Q3 | 6.7-215.7 | SF500/160k: 6.7 [6.5, 7.1] | SF50/2.56m: 215.7 [184.9, 241.6] |
| Delta | Q2 | 47.5-634.3 | SF100/160k: 47.5 [45.2, 49.7] | SF50/2.56m: 634.3 [511.1, 747.4] |
| Delta | Q3 | 25.5-451.4 | SF100/160k: 25.5 [24.8, 26.8] | SF50/2.56m: 451.4 [403.9, 524.5] |

The amended Iceberg B11 Q2 example is 46.3 comparable executions with a 95% BCa interval of [20.0, 92.4].

## Reproducibility

The amended Iceberg primary rows are byte-for-byte numerical copies of the full-sequence sensitivity rows produced by the validated v1.0 pipeline. Their 10,000 paired bootstrap draws used seed `20261025`; therefore, the reported interval endpoints are the pipeline outputs rather than values reconstructed from rounded manuscript tables.

The v1.0 analysis directory remains unchanged. The v1.1 CSV files retain the original role in `analysis_role_v1_0` and record the new role in `analysis_role`.
