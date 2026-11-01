# Main Figure Captions and Provenance

## Figure 1

Experimental lifecycle and measurement boundaries. TPC-DS store_sales records were read from Kafka by Spark Structured Streaming under a maximum-offsets-per-trigger (MOPT) upper bound and written to a format-specific transactional sink. Pre-maintenance queries were followed by native maintenance and the same post-maintenance queries. Iceberg 1.4.2 and Delta Lake 3.2.0 were evaluated in temporally separate campaigns. The physical ingestion run was the independent statistical unit; query repetitions were technical repeats. The stored ingestion metrics followed the known n-1 alignment, with the terminal commit reconciled separately.

**Validated sources**

| Source | SHA-256 |
|---|---|
| `manuscript_section_03_experimental_design_v1.3.md` | `65ca03793c7f1c845683e77d5cdefa22c32473f1e0444610800dc74dbae48e0a` |
| `manuscript_section_04_measurement_and_statistical_methodology_v1.4.md` | `cd24f77472e98d48e8d6c9d2e0dc70bc03607190561494626da5b47e356a9daa` |
| `publication_data_integrity_amendment_v1.2.md` | `d856b905134d7ec9d37918d658267e1a82abf052787624c12e292cc6618667c8` |

## Figure 2

Micro-batch granularity and ingestion-created physical state. Panels show completed ingestion commits, active Parquet files before maintenance, and mean active file size for Apache Iceberg 1.4.2 (a-c) and Delta Lake 3.2.0 (d-f). Points are arithmetic means across three independent physical runs and error bars show run-level standard deviations. Under the validated writer configuration, every completed commit produced 12 active files. Format rows represent temporally separate experimental campaigns and are not presented as a causally controlled cross-format comparison.

**Validated sources**

| Source | SHA-256 |
|---|---|
| `publication_canonical_run_manifest.csv` | `afaf04a6231035a1df4397a73d2f1cf45cf3271dbca18b001eb41f0b1f6830e2` |
| `lakehouse_publication_synthesis_artifacts/publication_maintenance_group_summary.csv` | `a7c82cf5ee21122883397f54cd4074438eff0c199adbf59e918e8378c77e3f23` |
| `publication_metadata_growth_final_analysis_v1_0_2_sealed/metadata_growth_run_level.csv` | `1c0fc837382555c0bda20d85f7c84b5dc6b6ad4428d78540243f2cb2d9e788ef` |

## Figure 3

Retained metadata scaling within the observed commit ranges. Each point is one canonical physical run. Dashed curves are scale-factor-specific predictions from the stored SF-fixed-effects power-model coefficients; no model was re-estimated for this figure. The validated retained-metadata-byte elasticities are eta=1.874 for Iceberg and eta=1.740 for Delta. Stored original-scale quadratic models achieved lower byte RMSE than the power models, but are not overlaid on the logarithmic axes because the Iceberg model produced nonpositive fitted values in part of the low-commit range. Retained footprint includes historical objects and must not be interpreted as active metadata or query-planning cost.

**Validated sources**

| Source | SHA-256 |
|---|---|
| `publication_metadata_growth_final_analysis_v1_0_2_sealed/metadata_growth_run_level.csv` | `1c0fc837382555c0bda20d85f7c84b5dc6b6ad4428d78540243f2cb2d9e788ef` |
| `publication_metadata_growth_final_analysis_v1_0_2_sealed/metadata_growth_primary_elasticities.csv` | `5d142f7eb531e3b7174cf1509f66ca9b0ed85aa27582d9525f942044068869cc` |
| `publication_metadata_growth_final_analysis_v1_0_2_sealed/metadata_growth_primary_coefficients.csv` | `6b17fadf756b717d8d2b1815ae17fbaa0176a825a8d40d72f4fbee5890c080e6` |
| `publication_metadata_growth_final_analysis_v1_0_2_sealed/metadata_growth_secondary_model_comparison.csv` | `80be06c7eaae870f144c8f036bdfb438178701bda5e64ab676021b47f299f5cc` |

## Figure 4

MOPT elasticity of query wall time before and after native maintenance. Points are the locked SF-adjusted run-level coefficients for Q2 and Q3; horizontal bars are the locked 95% confidence intervals. The near-zero Iceberg Q3 post-maintenance point is beta_post=-0.00008 rather than an exact zero. All four primary combinations showed a statistically supported reduction in absolute MOPT elasticity under the prespecified paired run-level analysis. Iceberg and Delta estimates arise from temporally separate campaigns.

**Validated sources**

| Source | SHA-256 |
|---|---|
| `publication_final_neutralization_analysis_v1_0/primary_neutralization_results.csv` | `0364c6507c4a2439d875f2acf82f2de905e0330e3c5b157fb4a162cad24bfa50` |
| `publication_final_neutralization_analysis_v1_0/primary_bootstrap_estimates.csv` | `ee3a0ceb698b5865d3d67a629b85d25b4f6646c7f67340fe14b19f371d7dacb8` |
| `publication_neutralization_validation.md` | `d41446587376dbe30c62b3f50c0da84211457b7ca4fbe07648dacd55cac09557` |

## Figure 5

Temporal query break-even after native maintenance for the 48 primary format-by-query-by-SF-by-MOPT cells. Values are the estimated numbers of comparable future query executions required to amortize the measured maintenance wall time through positive query-time savings; color uses a logarithmic scale. The primary Iceberg boundary includes rewrite_data_files, whereas the Delta boundary is OPTIMIZE. Iceberg's additional rewrite_manifests sensitivity is reported in the Supplementary Material. This is a temporal, not monetary, amortization and assumes repeated queries under comparable execution conditions.

**Validated sources**

| Source | SHA-256 |
|---|---|
| `publication_query_break_even_analysis_v1_0_sealed/query_break_even_cell_results.csv` | `898c93bc3e90ee82e8dc64f00d327c18f4c1886ad9adbf6a53ff7bdf11cbbc8c` |
| `publication_query_break_even_analysis_v1_0_sealed/publication_query_break_even_results.md` | `07070e6341e28803cbc836c326d29d00285e2e932fd3c71e6eea61755367edeb` |
| `publication_query_break_even_analysis_v1_0_sealed/analysis_run_manifest.json` | `1346b8075fd465b3f339167bb9bbaed8de28513a2f6d582e122d62f0818ec0df` |
