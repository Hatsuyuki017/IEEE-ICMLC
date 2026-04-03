#!/usr/bin/env python3
"""
run_pipeline.py — GBM Research Automation Pipeline Orchestrator

Orchestrates all research stages (S1-S9) for the IEEE-ICMLC paper submission:
  S1-S5  autoresearch skill   (literature survey, hypothesis formation)
  S6     model training       (GBM benchmark, CPTAC → TCGA evaluation)
  S7-S8  academic-plotting    (publication figures)
  S9     ml-paper-writing     (LaTeX sections) + humanizer (text refinement)
  post   cloud sync           (upload outputs to remote target)

Usage:
  python run_pipeline.py [--config pipeline_config.yaml] [--resume] [--dry-run]
"""

import argparse
import json
import logging
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required: pip install pyyaml")


class _UTCFormatter(logging.Formatter):
    converter = time.gmtime


_handler = logging.StreamHandler()
_handler.setFormatter(_UTCFormatter("%(asctime)s  %(levelname)-8s  %(message)s", "%Y-%m-%dT%H:%M:%SZ"))
logging.basicConfig(level=logging.INFO, handlers=[_handler])
log = logging.getLogger(__name__)

MAX_STDERR_CHARS = 2000

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REQUIRED_CONFIG_KEYS = [
    "pipeline.max_runtime_minutes",
    "data.cptac_path",
    "data.tcga_path",
    "data.scrna_path",
    "data.ref_folder",
    "data.output_dir",
]


def load_config(path: str) -> dict[str, Any]:
    """Load and validate pipeline_config.yaml."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with config_path.open() as fh:
        cfg = yaml.safe_load(fh)
    # Validate required nested keys
    missing = []
    for dotted in REQUIRED_CONFIG_KEYS:
        parts = dotted.split(".")
        node = cfg
        for part in parts:
            if not isinstance(node, dict) or part not in node:
                missing.append(dotted)
                break
            node = node[part]
    if missing:
        raise KeyError(f"Missing required config keys: {missing}")
    return cfg


# ---------------------------------------------------------------------------
# Input-file verification
# ---------------------------------------------------------------------------

def verify_input_files(cfg: dict[str, Any]) -> None:
    """Raise FileNotFoundError listing every missing data input path."""
    data = cfg.get("data", {})
    paths_to_check = [
        data.get("cptac_path", ""),
        data.get("tcga_path", ""),
        data.get("scrna_path", ""),
        data.get("ref_folder", ""),
    ]
    missing = [p for p in paths_to_check if p and not Path(p).exists()]
    if missing:
        raise FileNotFoundError(
            "The following required input files/directories are missing:\n"
            + "\n".join(f"  {p}" for p in missing)
        )
    log.info("All required input files verified.")


# ---------------------------------------------------------------------------
# Sync manifest
# ---------------------------------------------------------------------------

def _manifest_path(cfg: dict[str, Any]) -> Path:
    output_dir = Path(cfg["data"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / "sync_manifest.json"


def update_manifest(entry: dict[str, Any], cfg: dict[str, Any]) -> None:
    """Append a JSON entry to results/sync_manifest.json."""
    manifest = _manifest_path(cfg)
    entries: list[dict[str, Any]] = []
    if manifest.exists():
        with manifest.open() as fh:
            try:
                entries = json.load(fh)
            except json.JSONDecodeError:
                entries = []
    entries.append(entry)
    with manifest.open("w") as fh:
        json.dump(entries, fh, indent=2)


# ---------------------------------------------------------------------------
# Stage runner
# ---------------------------------------------------------------------------

def run_stage(
    name: str,
    cmd: list[str],
    timeout_minutes: int,
    cfg: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run a pipeline stage as a subprocess with a wall-clock timeout.

    Returns a dict with keys: stage, status, elapsed, outputs, error.
    """
    timeout_seconds = timeout_minutes * 60
    log.info("[%s] Starting (timeout=%d min): %s", name, timeout_minutes, " ".join(cmd))
    start = time.monotonic()
    result: dict[str, Any] = {
        "stage": name,
        "status": "ok",
        "elapsed": 0.0,
        "outputs": [],
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if dry_run:
        log.info("[%s] DRY-RUN — skipping execution.", name)
        result["status"] = "dry-run"
        update_manifest(result, cfg)
        return result

    try:
        proc = subprocess.run(
            cmd,
            timeout=timeout_seconds,
            capture_output=True,
            text=True,
        )
        elapsed = time.monotonic() - start
        result["elapsed"] = round(elapsed, 2)
        if proc.returncode != 0:
            result["status"] = "error"
            result["error"] = proc.stderr[-MAX_STDERR_CHARS:] if proc.stderr else "(no stderr)"
            log.error("[%s] Failed (rc=%d): %s", name, proc.returncode, result["error"])
        else:
            log.info("[%s] Completed in %.1fs.", name, elapsed)
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        result["status"] = "timeout"
        result["elapsed"] = round(elapsed, 2)
        result["error"] = f"Exceeded {timeout_minutes}-minute timeout."
        log.warning("[%s] TIMEOUT after %.1fs.", name, elapsed)
    except FileNotFoundError as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        log.error("[%s] Command not found: %s", name, exc)

    update_manifest(result, cfg)
    return result


# ---------------------------------------------------------------------------
# Stage definitions
# ---------------------------------------------------------------------------

def stage_autoresearch(cfg: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    """S1-S5: Literature survey and hypothesis formation via autoresearch skill."""
    skills = cfg.get("skills", {})
    tmpl = skills.get(
        "autoresearch_cmd",
        "autoresearch --tasks {tasks} --output-dir {output_dir} --ref-folder {ref_folder}",
    )
    cmd_str = tmpl.format(
        tasks="S1 S2 S3 S4 S5",
        output_dir=cfg["data"]["output_dir"],
        ref_folder=cfg["data"]["ref_folder"],
    )
    cmd = shlex.split(cmd_str)
    return run_stage("autoresearch", cmd, cfg["pipeline"]["max_runtime_minutes"], cfg, dry_run)


def stage_model_training(cfg: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    """S6: Train and evaluate GBM benchmark models."""
    cmd = [
        sys.executable, "-m", "gbm_benchmark",
        "--cptac", cfg["data"]["cptac_path"],
        "--tcga", cfg["data"]["tcga_path"],
        "--scrna", cfg["data"]["scrna_path"],
        "--output-dir", cfg["data"]["output_dir"],
    ]
    return run_stage("model_training", cmd, cfg["pipeline"]["max_runtime_minutes"], cfg, dry_run)


def stage_plotting(cfg: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    """S7-S8: Generate publication figures via academic-plotting skill."""
    skills = cfg.get("skills", {})
    tmpl = skills.get("plotting_cmd", "academic-plotting --config pipeline_config.yaml")
    cmd = shlex.split(tmpl)
    return run_stage("academic_plotting", cmd, cfg["pipeline"]["max_runtime_minutes"], cfg, dry_run)


def stage_paper_writing(cfg: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    """S9: Write LaTeX paper sections via ml-paper-writing skill."""
    skills = cfg.get("skills", {})
    tmpl = skills.get(
        "paper_writing_cmd",
        "ml-paper-writing --template main.tex --sections-dir sections/ --output-dir sections/",
    )
    cmd = shlex.split(tmpl)
    result = run_stage("paper_writing", cmd, cfg["pipeline"]["max_runtime_minutes"], cfg, dry_run)

    if result["status"] in ("ok", "dry-run"):
        # Apply humanizer to each generated .tex section
        humanizer_tmpl = skills.get("humanizer_cmd", "humanizer --input {input_file} --output {input_file}")
        sections_dir = Path("sections")
        tex_files = list(sections_dir.glob("*.tex")) if sections_dir.exists() else []
        for tex_file in tex_files:
            h_cmd = shlex.split(humanizer_tmpl.format(input_file=str(tex_file)))
            h_result = run_stage(
                f"humanizer:{tex_file.name}",
                h_cmd,
                cfg["pipeline"]["max_runtime_minutes"],
                cfg,
                dry_run,
            )
            if h_result["status"] not in ("ok", "dry-run"):
                log.warning("Humanizer failed for %s; continuing.", tex_file)

    return result


def stage_latex_compile(cfg: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    """Compile main.tex → main.pdf using pdflatex + bibtex."""
    if dry_run:
        return run_stage("latex_compile", ["pdflatex", "main.tex"], 0, cfg, dry_run=True)
    if not Path("main.tex").exists():
        log.warning("main.tex not found; skipping LaTeX compilation.")
        return {"stage": "latex_compile", "status": "skipped", "outputs": [], "error": None}
    cmds = [
        ["pdflatex", "-interaction=nonstopmode", "main.tex"],
        ["bibtex", "main"],
        ["pdflatex", "-interaction=nonstopmode", "main.tex"],
        ["pdflatex", "-interaction=nonstopmode", "main.tex"],
    ]
    result: dict[str, Any] = {}
    for cmd in cmds:
        result = run_stage("latex_compile", cmd, 10, cfg, dry_run)
        if result["status"] == "error":
            break
    if Path("main.pdf").exists():
        result["outputs"] = ["main.pdf"]
        log.info("LaTeX compiled successfully: main.pdf")
    else:
        log.warning("main.pdf not produced after compilation.")
    return result


# ---------------------------------------------------------------------------
# Cloud sync
# ---------------------------------------------------------------------------

def cloud_sync(cfg: dict[str, Any]) -> None:
    """Upload all manifest outputs to the configured cloud target."""
    cloud_cfg = cfg.get("cloud", {})
    if not cloud_cfg.get("enabled", False):
        log.info("Cloud sync disabled (cloud.enabled: false).")
        return

    remote_target = cloud_cfg.get("remote_target", "")
    if not remote_target:
        log.warning("Cloud sync enabled but cloud.remote_target is empty; skipping.")
        return

    manifest = _manifest_path(cfg)
    if not manifest.exists():
        log.warning("No sync_manifest.json found; nothing to upload.")
        return

    with manifest.open() as fh:
        entries = json.load(fh)

    retry_attempts = int(cloud_cfg.get("retry_attempts", 3))
    retry_delay = int(cloud_cfg.get("retry_delay_seconds", 10))

    for entry in entries:
        for output_path in entry.get("outputs", []):
            if not Path(output_path).exists():
                log.warning("Skipping missing file: %s", output_path)
                continue
            for attempt in range(1, retry_attempts + 1):
                try:
                    subprocess.run(
                        ["rsync", "-avz", output_path, remote_target],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    log.info("Uploaded %s (attempt %d).", output_path, attempt)
                    break
                except subprocess.CalledProcessError as exc:
                    log.warning("Upload failed (attempt %d/%d): %s", attempt, retry_attempts, exc.stderr)
                    if attempt < retry_attempts:
                        time.sleep(retry_delay)
                    else:
                        log.error("All upload attempts exhausted for: %s", output_path)


# ---------------------------------------------------------------------------
# Resume helper
# ---------------------------------------------------------------------------

def _completed_stages(cfg: dict[str, Any]) -> set[str]:
    """Return the set of stage names already in sync_manifest.json with status ok."""
    manifest = _manifest_path(cfg)
    if not manifest.exists():
        return set()
    try:
        with manifest.open() as fh:
            entries = json.load(fh)
        return {e["stage"] for e in entries if e.get("status") in ("ok", "dry-run")}
    except (json.JSONDecodeError, KeyError):
        return set()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="GBM Research Automation Pipeline Orchestrator"
    )
    parser.add_argument(
        "--config",
        default="pipeline_config.yaml",
        help="Path to pipeline configuration YAML (default: pipeline_config.yaml)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip stages whose outputs already appear in sync_manifest.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and input files without executing any stages",
    )
    args = parser.parse_args()

    # 1. Load configuration
    try:
        cfg = load_config(args.config)
    except (FileNotFoundError, KeyError) as exc:
        log.error("Configuration error: %s", exc)
        return 1

    # 2. Verify input files (skip in dry-run mode when data may not exist)
    if not args.dry_run:
        try:
            verify_input_files(cfg)
        except FileNotFoundError as exc:
            log.error("Input file error:\n%s", exc)
            return 1

    # 3. Determine which stages to run
    resume = args.resume or cfg.get("pipeline", {}).get("resume", False)
    done = _completed_stages(cfg) if resume else set()
    dry_run = args.dry_run

    stages = [
        ("autoresearch", stage_autoresearch),
        ("model_training", stage_model_training),
        ("academic_plotting", stage_plotting),
        ("paper_writing", stage_paper_writing),
        ("latex_compile", stage_latex_compile),
    ]

    for stage_name, stage_fn in stages:
        if stage_name in done:
            log.info("[%s] Already completed; skipping (--resume).", stage_name)
            continue
        result = stage_fn(cfg, dry_run)
        status = result.get("status", "unknown")
        if status == "error":
            log.error("[%s] Stage failed; continuing with remaining stages.", stage_name)

    # 4. Cloud sync
    cloud_sync(cfg)

    # 5. Mark pipeline complete
    completion_entry: dict[str, Any] = {
        "stage": "pipeline",
        "status": "done",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "outputs": [],
        "error": None,
    }
    update_manifest(completion_entry, cfg)
    log.info("Pipeline complete. Manifest: %s", _manifest_path(cfg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
