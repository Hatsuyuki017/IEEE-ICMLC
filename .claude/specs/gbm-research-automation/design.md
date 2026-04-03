# Design Document: GBM Research Automation Pipeline

## Overview

This document describes the system design for the GBM research automation pipeline. The pipeline orchestrates five skill-based stages (literature survey, model training, visualization, paper writing, cloud sync) using a central Python orchestrator (`run_pipeline.py`) and a YAML configuration file (`pipeline_config.yaml`). Each stage is time-bounded to 90 minutes and writes its outputs to well-defined locations so that any stage can be re-run independently.

---

## Architecture Design

### System Architecture Diagram

```mermaid
graph TD
    A[run_pipeline.py<br/>Orchestrator] -->|reads| B[pipeline_config.yaml]
    A -->|S1-S5| C[autoresearch skill<br/>Literature + Hypothesis]
    A -->|S6| D[Model Training<br/>GBM Benchmark]
    A -->|S7-S8| E[academic-plotting skill<br/>Figure Generation]
    A -->|S9| F[ml-paper-writing skill<br/>LaTeX Sections]
    F -->|post-process| G[humanizer skill<br/>Text Refinement]
    A -->|all stages| H[Cloud Sync<br/>sync_manifest.json]

    C -->|writes| I[sections/introduction.tex<br/>references.bib]
    D -->|writes| J[results/metrics.json]
    E -->|writes| K[figures/*.pdf, *.png]
    F -->|writes| L[sections/*.tex<br/>main.pdf]
    H -->|uploads| M[Remote Cloud Target]
```

### Data Flow Diagram

```mermaid
sequenceDiagram
    participant Orch as run_pipeline.py
    participant Cfg as pipeline_config.yaml
    participant AR as autoresearch
    participant MT as Model Training
    participant AP as academic-plotting
    participant PW as ml-paper-writing + humanizer
    participant CS as Cloud Sync

    Orch->>Cfg: load configuration
    Orch->>Orch: verify_input_files()
    Orch->>AR: run(tasks=S1-S5, timeout=90min)
    AR-->>Orch: sections/introduction.tex, references.bib
    Orch->>MT: run(tasks=S6, timeout=90min)
    MT-->>Orch: results/metrics.json
    Orch->>AP: run(tasks=S7-S8, timeout=90min)
    AP-->>Orch: figures/*.pdf + figures/*.png
    Orch->>PW: run(tasks=S9, timeout=90min)
    PW-->>Orch: sections/*.tex, main.pdf
    Orch->>CS: sync(manifest=results/sync_manifest.json)
    CS-->>Orch: upload confirmation
```

---

## Component Design

### `run_pipeline.py` — Orchestrator

- **Responsibilities**: Parse `pipeline_config.yaml`, verify input files, run each stage in order with a per-stage timeout, update `sync_manifest.json`, trigger cloud sync.
- **Interfaces**:
  - `verify_input_files(config) -> None` — raises `FileNotFoundError` listing missing files
  - `run_stage(name, fn, timeout_minutes) -> dict` — executes `fn()` in a subprocess with timeout; returns `{"status": "ok"|"timeout"|"error", "outputs": [...], "elapsed": float}`
  - `update_manifest(entry: dict) -> None` — appends to `results/sync_manifest.json`
  - `cloud_sync(manifest_path, config) -> None` — uploads files to cloud target with retry logic
- **Dependencies**: `pipeline_config.yaml`, `results/` directory

### `pipeline_config.yaml` — Configuration

- **Responsibilities**: Single source of truth for all paths, timeouts, figure specs, and cloud settings.
- **Key sections**: `pipeline`, `data`, `figures`, `cloud`, `skills`
- **Dependencies**: None (consumed by orchestrator at startup)

### autoresearch Stage (S1–S5)

- **Responsibilities**: Literature survey, related-work retrieval, hypothesis framing, writing `sections/introduction.tex` and populating `references.bib`.
- **Interfaces**: Called via `skills.autoresearch_cmd` from config with `--tasks S1-S5` argument.
- **Dependencies**: Internet access, `data.ref_folder`, output directory

### Model Training Stage (S6)

- **Responsibilities**: Load CPTAC and TCGA cohorts, run classical and deep model benchmark, write `results/metrics.json`.
- **Interfaces**: Standalone Python module; invoked as subprocess.
- **Dependencies**: `data.cptac_path`, `data.tcga_path`, `data.scrna_path`

### academic-plotting Stage (S7–S8)

- **Responsibilities**: Generate all publication figures (UMAP, heatmaps, ROC, Kaplan–Meier, etc.) from metrics and intermediate model outputs.
- **Interfaces**: Called via `skills.plotting_cmd` with `--config pipeline_config.yaml`.
- **Dependencies**: `results/metrics.json`, `figures/` output directory, `matplotlib`, `seaborn`, `scanpy`

### ml-paper-writing + humanizer Stage (S9)

- **Responsibilities**: Populate LaTeX section templates with research content; then apply humanizer post-processing to reduce AI-detectable text patterns.
- **Interfaces**:
  - Called via `skills.paper_writing_cmd`
  - Humanizer called via `skills.humanizer_cmd` on each generated `.tex` file
- **Dependencies**: All prior stages complete, `sections/` templates

### Cloud Sync

- **Responsibilities**: Upload all outputs listed in `results/sync_manifest.json` to the remote target, with retry logic.
- **Interfaces**: `cloud_sync(manifest_path, config)` in orchestrator.
- **Dependencies**: `cloud.enabled`, `cloud.remote_target`, `cloud.retry_attempts`, `cloud.retry_delay_seconds`

---

## Data Model

```python
# Sync Manifest entry (appended to results/sync_manifest.json as JSON Lines)
class ManifestEntry(TypedDict):
    stage: str          # e.g. "autoresearch", "plotting", "paper_writing"
    output_path: str    # relative path from repo root
    timestamp: str      # ISO-8601 UTC
    status: str         # "ok" | "timeout" | "error"

# Stage result returned by run_stage()
class StageResult(TypedDict):
    status: str         # "ok" | "timeout" | "error"
    outputs: list[str]  # list of output file paths produced
    elapsed: float      # wall-clock seconds
    error: str | None   # error message if status != "ok"
```

---

## Business Process

### Process 1: Full Pipeline Run

```mermaid
flowchart TD
    Start([Pipeline Start]) --> LoadCfg[Load pipeline_config.yaml]
    LoadCfg --> Verify{Input files present?}
    Verify -- No --> Abort([Abort with FileNotFoundError])
    Verify -- Yes --> S1_5[Run autoresearch S1-S5<br/>timeout=90min]
    S1_5 --> S6[Run Model Training S6<br/>timeout=90min]
    S6 --> S7_8[Run academic-plotting S7-S8<br/>timeout=90min]
    S7_8 --> S9[Run ml-paper-writing S9<br/>timeout=90min]
    S9 --> Humanize[Run humanizer on .tex files]
    Humanize --> Compile[Compile LaTeX → main.pdf]
    Compile --> Sync[Cloud Sync]
    Sync --> Done([Pipeline Complete])
```

### Process 2: Resume from Failed Stage

```mermaid
flowchart TD
    Start([Pipeline Start with --resume]) --> ReadManifest[Read sync_manifest.json]
    ReadManifest --> FindLast[Find last completed stage]
    FindLast --> SkipDone[Skip completed stages]
    SkipDone --> RunNext[Run next pending stage]
    RunNext --> Continue[Continue until all stages done]
    Continue --> Done([Pipeline Complete])
```

---

## Error Handling Strategy

| Error Type | Handling |
|---|---|
| Missing input file | `verify_input_files()` raises `FileNotFoundError` with list of missing paths; pipeline aborts |
| Stage timeout | Log `TIMEOUT` to manifest, skip stage, continue with remaining stages |
| Stage runtime error | Log `ERROR` + traceback to manifest, skip stage, continue |
| Cloud sync failure | Retry up to `cloud.retry_attempts` times; log warning if all retries exhausted |
| LaTeX compilation error | Log error; `main.pdf` not produced; other outputs still synced |
