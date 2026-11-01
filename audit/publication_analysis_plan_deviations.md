# Analysis Plan Reconstruction and Deviation Audit

Audit date: 2026-10-25

## 1. Documents located

| Document | File timestamp | SHA-256 | Evidential role |
|---|---|---|---|
| `concept_v5.1_additions.docx` | 2026-07-28 12:54:44 | `534AD3EB22BCD52894542F6C6AD6021C8433804A29A1E4D00F75F4A549A47B25` | Most specific v5.1 methods proposal |
| `concept_v5_2_additions.docx` | 2026-07-28 13:34:15 | `25C9ADAB173D7207309813E145AF02673059ABE8C514972D83D5970697649D4F` | Post-inspection amendments; explicitly references inspection of SF500 data |
| `convept_v5.docx` | 2026-09-07 18:10:26 | `EC8568C6286296E3D9F748A926751622A66D63DE698A2BE5187F5AF2CAE16E8B` | Later consolidated v5-style concept, created after experiments had begun |
| `paper structure.docx` | 2026-10-25 18:18:12 | `F8A6CE116C9FFB836CE6E8D64DB97873E562637656A15C79A12AFFF996767CD4` | Retrospective publication structure after exploratory analyses |

No separately archived final plan, cryptographic freeze record, registered protocol, or timestamped pre-analysis repository snapshot was found. The v5.1 document contains a proposed freeze clause, but there is no evidence that the specified freeze, hash, and archive occurred before analysis. The work must therefore be described as a documented evolving analysis plan with retrospective validation, not as preregistered confirmatory analysis.

## 2. Reconstructed v5.1 specification

The most specific v5.1 proposal defined:

- RQ1: residual data-file count prediction;
- RQ2: output footprint;
- RQ3: pre-maintenance query performance;
- RQ4a: metadata footprint per GiB;
- RQ4b: metadata growth exponent and constant;
- RQ5: structural mediation;
- RQ6: maintenance neutralization and temporal break-even.

Its common model was:

`log2(Y) = beta0 + betaM log2(rows/micro-batch) + betaS log2(SF) + betaF format + betaMF log2(rows/micro-batch) * format + epsilon`

It proposed run-level inference, a BCa bootstrap with 10,000 run-level resamples stratified by cell, and an archived random seed. It also proposed:

- `neutralization = 1 - abs(beta_post) / abs(beta_pre)`;
- `break-even queries = Tier-A maintenance time / (pre median - post median)`;
- physical ingestion run as the independent unit;
- three warmups and three measured query repetitions;
- technical query repetitions aggregated to one run-level statistic;
- an endpoint hierarchy with a formal multiplicity rule to be fixed before final analysis.

## 3. Deviation matrix

| Topic | Original specification | Actual work completed to date | Deviation and reason | Scientific consequence / required action |
|---|---|---|---|---|
| Plan freeze | Freeze, hash, and archive plan/scripts before final analysis | Multiple dated drafts exist; no evidenced pre-analysis freeze | Freeze clause was proposed but not demonstrably executed | Do not claim preregistration. Freeze the final execution plan now and label analyses exploratory or retrospectively specified as appropriate. |
| Research questions | RQ1-RQ6 centered on files, footprint, queries, metadata, mediation, neutralization | Additional EventLog validation, temporal micro-batch analysis, and measurement-feasibility work were added | Scope evolved in response to discovered measurement limitations | Clearly distinguish original questions, post-data amendments, and new exploratory questions. |
| Primary model | Full log2 model with MOPT, SF, format, and MOPT-by-format interaction | Metadata work compared linear, quadratic, and power models separately by format; temporal work used within-run trends and grouped summaries | Model family was adapted to the measurement question and collinearity structure | The final inferential model must be fixed prospectively; exploratory model selection cannot be presented as confirmatory. |
| Elasticities | Interpret log2 coefficients as scaling elasticities | Some power-model exponents were explored for retained metadata footprint | Only a subset of planned elasticities has been investigated | Do not generalize metadata exponents to all endpoints. Run only the frozen final models in the final stage. |
| BCa bootstrap | 10,000 run-level resamples stratified by cell, seed archived | Not applied in the validated exploratory reports | Final inferential stage not yet executed | Specify seed, resampling strata, confidence level, and handling of three-run cells before execution. |
| Query repetition aggregation | Run-level median of three measured repetitions | Current publication synthesis uses arithmetic mean as the primary run-level summary | Analysis convention changed after the proposal | Choose mean or median before final analysis. If mean is retained, report the change and provide median sensitivity analysis. |
| Descriptive summaries | Run-level units with technical repetitions aggregated | Exploratory reports use arithmetic means with SD/CV and retain all valid observations | Compatible at run level but not identical to the proposed median convention | Keep run as inferential unit; never treat query repetitions or batches as independent replications. |
| Neutralization | Compute beta_pre, beta_post, and `1 - abs(beta_post)/abs(beta_pre)` | No final validated beta neutralization result computed | Planned final analysis remains outstanding | Preserve as a planned derived endpoint only after its base models and uncertainty method are frozen. |
| Metadata growth law | Estimate exponent/constant and examine growth law | Linear, quadratic, and power fits completed; retained-footprint definition validated; no universal law claimed | Exploratory model comparison completed without the proposed BCa inferential layer | Use as exploratory quantitative characterization. Do not call the observed quadratic-compatible pattern a universal law. |
| Temporal query break-even | Maintenance time divided by per-query pre/post saving | No final validated break-even result; only descriptive or hypothetical treatment in older material | Required assumptions and uncertainty propagation not finalized | Do not report a final break-even until query aggregation, failed/negative savings, maintenance boundary, and interval method are fixed. |
| MOPT* | Derive a conditional optimal threshold from competing objectives | No final MOPT* computed | Planned synthesis endpoint remains outstanding | Any future MOPT* must be framed as conditional on the tested grid and declared utility rule, not as a universal optimum. |
| Multiplicity | Endpoint hierarchy; exact correction to be set before final analysis | No final correction rule found and no formal correction applied in exploratory reports | The promised rule was never frozen | Define families, primary endpoints, and correction procedure before inferential testing. |
| H5 mediator | Original plan expected file-scan metrics | v5.2 replaced unavailable `input_files`/`input_bytes` mediation with `num_tasks` after SF500 inspection | Explicit post-data measurement adaptation | Label this analysis exploratory and avoid implying that `num_tasks` is equivalent to scanned files or bytes. |
| n-1 alignment | Initially not fully specified | v5.2 documented the terminal missing metrics row and current audit validates it in every run | Measurement behavior discovered during campaign | Use observed batches only for latency/resources; use independently validated state for commit and final-row counts. |
| Delta phase timing | Historical collector split treated last stage as write boundary | EventLog work showed Delta internal post-write stages; corrected phases stored separately | Original timing boundary was invalid for Delta | Use `delta_eventlog_phase_v1` outputs for Delta write/post-write analyses; retain original columns only as historical measurements. |
| Iceberg phase timing | Collector exposed write and `metadata_commit_duration_ms` | Missing Iceberg EventLogs prevent equivalent reconstruction; commit metric is not an isolated commit duration | Cross-format phase equivalence cannot be established | Use full batch/append wall time for format-neutral comparisons; avoid direct pure-commit comparisons. |
| Query planning | Proposed query-performance comparison | Delta EventLogs complete; Iceberg query EventLogs absent; total planning unavailable in a format-neutral way | Planned decomposition cannot be symmetrically executed | Use `query_wall_time_ms` as the primary format-neutral outcome; treat Delta-only phase diagnostics as secondary. |
| `cache_mode` | Controlled comparable query conditions implied | Five Iceberg runs labeled `none`; all others `warm_cache` | Condition labeling is not homogeneous | Freeze primary exclusion/modeling rule and report a sensitivity analysis. |
| Temporal micro-batch performance | Not a central v5.1 endpoint | Full within-run exploratory analysis completed | New question introduced after data collection | Report as exploratory; state that Delta modulo-10 periodicity is an association, not isolated checkpoint cost. |

## 4. Items that must be frozen before final analysis

1. Exact primary endpoint list and hierarchy.
2. Exact model formula for every primary endpoint, including transformations and interaction terms.
3. Definition of the independent unit and aggregation from batches/query repetitions to runs.
4. Mean-versus-median rule for the three measured query repetitions.
5. `cache_mode=none` primary and sensitivity handling.
6. BCa implementation, 10,000-resample design, random seed, and confidence level.
7. Multiplicity families and correction method.
8. Rules for zero, negative, or undefined neutralization and break-even denominators.
9. Delta reconstructed-phase eligibility and treatment of unreconstructable batches.
10. Explicitly unavailable cross-format phase metrics due to missing Iceberg EventLogs.

## 5. Interpretation status

The completed analyses are scientifically useful and reproducible as exploratory and measurement-validation work. They do not constitute execution of a demonstrably preregistered v5.1 plan. A final plan can still be frozen before the remaining inferential calculations, but this is a prospective lock of the final analysis stage, not retroactive preregistration.
