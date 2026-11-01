# Main Figure Validation Report

Validation scope: the five planned main figures for *From Commit Granularity to Query Amortization: Native Maintenance in Apache Iceberg and Delta Lake*.

The validation is read-only with respect to historical data and locked analyses. Figure scripts read stored run-level summaries, coefficients, confidence intervals, and break-even results; they do not fit models or run statistical tests.

## Summary

| Figure | Status | Primary validation result |
|---|---|---|
| Figure 1 | PASS | Lifecycle, format versions, timing boundaries, independent unit, and n-1 alignment are documented without causal cross-format framing. |
| Figure 2 | PASS | All 72 canonical runs and 24 grouped cells are represented; commits, active files, and mean file size use validated units. |
| Figure 3 | PASS | All 72 run-level points and locked model coefficients are used; retained footprint and model limitations are explicit. |
| Figure 4 | PASS | Four locked primary coefficients and 95% intervals are reproduced, including the validated Iceberg-Q3 near-zero post estimate. |
| Figure 5 | PASS | All 48 primary break-even cells are shown with logarithmic color normalization and format-specific maintenance boundaries. |

## Figure 1

**Status: PASS**

- Lifecycle and timing definitions traced to Sections 3-4 and Amendment v1.2.
- PNG is 6141 x 3450 px; SVG contains vector primitives and no embedded raster image.
- Visual inspection confirmed readable workflow arrows, nonoverlapping timing spans, and explicit separation of the two campaigns.

## Figure 2

**Status: PASS**

- 72 canonical runs and 24 format/SF/MOPT cells verified; active-files-per-commit ratio is 12 for every run.
- PNG is 7093 x 4316 px; SVG contains vector primitives and no embedded raster image.
- Visual inspection confirmed that title, scale-factor legend, panel titles, units, markers, and footer do not overlap.

## Figure 3

**Status: PASS**

- 72 run-level points, 20 locked primary coefficients, and four locked elasticities verified; eta values are 1.8738768658 and 1.7396602142.
- Quadratic-byte overlay intentionally omitted on log axes because the stored Iceberg model has six nonpositive fitted values.
- PNG is 9267 x 4743 px; SVG contains vector primitives and no embedded raster image.
- Visual inspection confirmed log-scale axes, readable SF encodings, eta labels, and explicit original-scale model-fit caveat.

## Figure 4

**Status: PASS**

- Four locked primary rows and 40,000 stored bootstrap draws verified; Iceberg Q3 post coefficient and percentile-fallback interval match the validation report.
- PNG is 5445 x 3009 px; SVG contains vector primitives and no embedded raster image.
- Visual inspection confirmed that campaign labels, confidence intervals, zero reference, and near-zero annotation are legible and distinct.

## Figure 5

**Status: PASS**

- All 48 primary cells are present and ESTIMABLE; the exact range is 6.5662133282 to 634.2970479705 comparable query executions.
- PNG is 6908 x 4458 px; SVG contains vector primitives and no embedded raster image.
- Visual inspection confirmed readable cell annotations, a shared logarithmic color scale, correct temporal units, and the separate primary maintenance boundaries.

## Cross-Figure Checks

- Apache Iceberg is labeled `1.4.2` and Delta Lake `3.2.0` throughout; no generated SVG contains the superseded Iceberg `1.6.1` label.
- SF is encoded by both color and marker/line style; figures remain distinguishable when color is unavailable.
- Format rows or groups are explicitly described as temporally separate campaigns, not causally controlled direct comparisons.
- SVG files contain editable vector primitives and no embedded raster image.
- PNG files are rendered at 600 dpi with dimensions above 3,000 x 2,500 pixels.
- Output hashes are recorded in `figure_output_manifest.csv`; source hashes are recorded in `figure_source_manifest.csv` and repeated in `figure_captions.md`.

## Known Interpretive Boundaries

- Figure 3 reports retained historical metadata footprint, not active metadata or query-planning work.
- The quadratic byte model is summarized through stored original-scale RMSE rather than drawn on logarithmic axes because the Iceberg fit includes nonpositive fitted values.
- Figure 4 visualizes beta coefficients and intervals; the neutralization ratio and its interval remain tabular results and are not inferred from plot geometry.
- Figure 5 is a temporal amortization under comparable future-query conditions, not an economic cost model.

**Final decision: PASS for all five figures.**
