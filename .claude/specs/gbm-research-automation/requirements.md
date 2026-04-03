# Requirements: GBM Research Automation Pipeline

## Introduction

This document defines the requirements for an automated research pipeline for the IEEE-ICMLC 2026 paper titled *"A Cross-Scale Fusion Transformer Integrating Single-Cell Marker Programs for Glioblastoma Prognostic Modeling"*. The pipeline automates literature survey, model training, data visualization, and paper writing tasks, using a suite of AI skills (`autoresearch`, `academic-plotting`, `ml-paper-writing`, `humanizer`) with a maximum runtime of 90 minutes per process.

---

## 1. Literature Survey and Hypothesis Formation (S1–S5)

**User Story**: As a researcher, I want the pipeline to autonomously survey relevant literature and form research hypotheses, so that I can ensure comprehensive background coverage without manual searching.

**Acceptance Criteria**:

1.1. WHEN the pipeline starts, the system SHALL invoke the `autoresearch` skill for tasks S1–S5 (literature review, hypothesis formation, related-work analysis, gap identification, and contribution framing).

1.2. IF the `autoresearch` skill does not complete within 90 minutes, the system SHALL log a timeout error and continue with the next task.

1.3. WHERE literature sources are identified, the system SHALL store them in `references.bib` using BibTeX format.

1.4. WHILE the literature survey is running, the system SHALL write intermediate results to the configured `output_dir` so progress is not lost if interrupted.

1.5. WHEN the survey is complete, the system SHALL produce a structured summary that is stored as `sections/introduction.tex`.

---

## 2. Model Training and Evaluation (S6)

**User Story**: As a researcher, I want the pipeline to train and evaluate multiple survival models using the curated GBM dataset, so that I can obtain reproducible benchmark results without manual intervention.

**Acceptance Criteria**:

2.1. WHEN training is triggered, the system SHALL load cohort data from the paths specified in `pipeline_config.yaml` under `data.cptac_path` and `data.tcga_path`.

2.2. IF any required input file is missing at pipeline startup, the system SHALL raise a `FileNotFoundError` listing each missing path before exiting.

2.3. WHERE GPU resources are available, the system SHALL use CUDA for deep model training; otherwise it SHALL fall back to CPU.

2.4. WHILE training runs, the system SHALL enforce a 90-minute per-process timeout as configured in `pipeline_config.yaml` under `pipeline.max_runtime_minutes`.

2.5. WHEN evaluation finishes, the system SHALL write AUC, C-index, and Kaplan–Meier results to `results/metrics.json`.

---

## 3. Data Visualization (S7–S8)

**User Story**: As a researcher, I want publication-quality figures generated automatically, so that I can include them in the paper without manual formatting.

**Acceptance Criteria**:

3.1. WHEN visualization tasks S7–S8 are started, the system SHALL invoke the `academic-plotting` skill strictly according to the figure specifications in `pipeline_config.yaml` under `figures`.

3.2. IF a figure already exists in `figures/` and `pipeline.overwrite_figures` is `false`, the system SHALL skip regeneration and log a notice.

3.3. WHERE figures are generated, the system SHALL save them in both `.pdf` and `.png` formats at 300 DPI or higher.

3.4. WHEN all figures are complete, the system SHALL update `sections/results.tex` with the correct figure file references.

---

## 4. Paper Writing (S9)

**User Story**: As a researcher, I want the paper sections to be written and refined automatically, so that I can meet the submission deadline even while travelling.

**Acceptance Criteria**:

4.1. WHEN task S9 starts, the system SHALL invoke the `ml-paper-writing` skill to populate or update the LaTeX template sections (abstract, introduction, methods, results, discussion, conclusion) in the `sections/` directory.

4.2. AFTER the `ml-paper-writing` skill completes, the system SHALL invoke the `humanizer` skill on the generated text to reduce AI-detectable writing patterns.

4.3. IF the compiled PDF (`main.pdf`) already exists and all sections are unchanged, the system SHALL skip LaTeX compilation and log a notice.

4.4. WHERE the paper references figures, the system SHALL verify that each referenced file exists in `figures/` before finalizing.

4.5. WHEN the paper compilation is successful, the system SHALL record the output path in the cloud sync manifest at `results/sync_manifest.json`.

---

## 5. Cloud Synchronization

**User Story**: As a researcher who needs to be away from my computer, I want all pipeline outputs automatically synchronized to the cloud, so that I can access results from any location.

**Acceptance Criteria**:

5.1. WHEN any pipeline stage completes, the system SHALL append the output file paths and timestamps to `results/sync_manifest.json`.

5.2. IF cloud sync is enabled (`cloud.enabled: true` in `pipeline_config.yaml`), the system SHALL upload all entries in `sync_manifest.json` to the configured remote target.

5.3. WHERE a cloud upload fails, the system SHALL retry up to `cloud.retry_attempts` times with `cloud.retry_delay_seconds` between attempts.

5.4. WHILE the pipeline is running, results SHALL remain accessible on the local filesystem even if cloud sync is unavailable.

5.5. WHEN the entire pipeline completes successfully, the system SHALL set `status: "done"` in `results/sync_manifest.json`.
