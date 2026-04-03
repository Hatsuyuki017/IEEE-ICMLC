# Requirements Document

## Introduction

This feature implements an automated research pipeline for the GBM (Glioblastoma) prognosis study submitted to IEEE ICMLC 2026. The pipeline orchestrates model tuning, data visualization, paper section writing, and AI-trace removal — running each stage with a 90-minute hard timeout so that it can execute unattended (laptop closed, offline) and upload all artifacts to the cloud for later review.

The skills consumed by the pipeline are:
- **autoresearch** — autonomous literature survey and research orchestration
- **academic-plotting** — publication-quality figure generation
- **ml-paper-writing** — structured scientific writing for ML/bioinformatics papers
- **humanizer** — post-processing to remove detectable AI writing patterns

---

## Requirements

### Requirement 1 — Pipeline Orchestration

**User Story:** As a researcher preparing a conference submission, I want the full analysis-to-paper workflow to run automatically so that I can travel without monitoring my computer.

#### Acceptance Criteria

1. WHEN the user invokes the pipeline runner THEN the system SHALL execute all stages in the correct order: model tuning → data visualization → paper writing → humanization → cloud upload.
2. WHEN any stage exceeds 90 minutes of wall-clock time THEN the system SHALL terminate that stage, log a timeout warning, and continue with the next stage.
3. WHILE the pipeline is running THEN the system SHALL write structured progress logs to `pipeline.log` so the user can review status after reconnecting.
4. IF the computer goes offline during execution THEN the system SHALL continue running in the background and SHALL upload results once connectivity is restored.

---

### Requirement 2 — Model Tuning Stage

**User Story:** As a researcher, I want model hyperparameters and feature sets to be tuned automatically so that I get the best reproducible external-validation scores before the submission deadline.

#### Acceptance Criteria

1. WHEN the model-tuning stage is invoked THEN the system SHALL use the `autoresearch` skill to orchestrate the tuning run.
2. WHEN the tuning stage starts THEN the system SHALL load dataset paths from `pipeline_config.yaml` rather than hard-coded paths.
3. WHEN the tuning stage finishes (or times out) THEN the system SHALL persist tuned model artifacts and a JSON summary of best AUC/C-index scores to `outputs/model_tuning/`.
4. IF a previous tuning run exists in `outputs/model_tuning/` THEN the system SHALL skip re-running and use cached results unless the `--force` flag is passed.

---

### Requirement 3 — Data Visualization Stage

**User Story:** As a researcher, I want publication-quality figures regenerated automatically so that all plots are consistent with the final model results.

#### Acceptance Criteria

1. WHEN the visualization stage is invoked THEN the system SHALL use the `academic-plotting` skill to produce figures.
2. WHEN a figure is generated THEN the system SHALL save both `.pdf` and `.png` versions to the `figures/` directory with the naming convention `fig_<name>.{pdf,png}`.
3. WHEN the visualization stage runs THEN the system SHALL produce at minimum: UMAP plots, Kaplan–Meier curves, ROC curves, ablation bar charts, and volcano plot.
4. IF a figure already exists and source data is unchanged THEN the system SHALL skip regenerating that figure unless the `--force` flag is passed.

---

### Requirement 4 — Paper Writing Stage

**User Story:** As a researcher, I want the LaTeX paper sections populated or updated automatically so that the manuscript reflects the latest results without manual copy-paste.

#### Acceptance Criteria

1. WHEN the paper-writing stage is invoked THEN the system SHALL use the `ml-paper-writing` skill.
2. WHEN the paper-writing stage runs THEN the system SHALL update all section files under `sections/` with content derived from the latest model outputs and figures.
3. WHEN writing numeric results into the paper THEN the system SHALL read values from `outputs/model_tuning/results_summary.json` to avoid hard-coded numbers.
4. IF a section file already contains a `% AUTO-GENERATED` comment block THEN the system SHALL replace only that block and leave surrounding human-written content intact.

---

### Requirement 5 — Humanization Stage

**User Story:** As a researcher, I want AI-generated text in the paper to be rewritten to sound natural so that the manuscript passes AI-detection tools used by the conference.

#### Acceptance Criteria

1. WHEN the humanization stage is invoked THEN the system SHALL use the `humanizer` skill.
2. WHEN the humanizer processes a section file THEN the system SHALL write the humanized version to `outputs/humanized/<section>.tex` and SHALL NOT overwrite the original `sections/` files.
3. WHEN humanization finishes THEN the system SHALL produce a diff report at `outputs/humanized/changes.diff` comparing originals with humanized outputs.
4. IF the humanizer returns an empty or unchanged file THEN the system SHALL log a warning and retain the original content.

---

### Requirement 6 — Cloud Upload Stage

**User Story:** As a researcher traveling without reliable connectivity, I want all pipeline outputs uploaded to cloud storage automatically so that I can access results from any device.

#### Acceptance Criteria

1. WHEN all preceding stages complete (or time out) THEN the system SHALL upload the `outputs/` directory and updated `figures/` directory to the configured cloud destination.
2. WHEN the cloud upload is configured THEN the system SHALL read the target path from `pipeline_config.yaml` under `cloud.destination`.
3. IF the device is offline when the upload stage runs THEN the system SHALL retry with exponential back-off (max 5 retries, cap 10 minutes per retry) until connectivity is restored.
4. WHEN the upload succeeds THEN the system SHALL write a manifest file `outputs/upload_manifest.json` listing all uploaded files with checksums.

---

### Requirement 7 — Configuration

**User Story:** As a researcher, I want a single configuration file to control all pipeline settings so that I don't need to edit source code.

#### Acceptance Criteria

1. WHEN the pipeline starts THEN the system SHALL read all settings from `pipeline_config.yaml` in the repository root.
2. WHERE data paths are specified THEN the system SHALL support both absolute paths and paths relative to the repository root.
3. WHEN a required configuration key is missing THEN the system SHALL raise a descriptive error and exit with a non-zero code before any stage runs.
4. IF the user passes `--config <path>` THEN the system SHALL use the specified file instead of the default `pipeline_config.yaml`.
