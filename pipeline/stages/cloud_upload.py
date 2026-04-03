"""Cloud upload stage — uploads pipeline outputs to configured cloud storage."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from pipeline.base import BaseStage, StageResult, StageStatus
from pipeline.cache import CacheManager
from pipeline.config import ConfigLoader

_DEFAULT_RETRY_DELAYS = [60, 120, 240, 480, 600]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_upload_cmd(tool: str, src: str, dest: str) -> list[str]:
    """Return the upload command for the configured cloud tool."""
    if tool == "rclone":
        return ["rclone", "copy", src, dest]
    if tool == "aws":
        return ["aws", "s3", "sync", src, dest]
    if tool == "gsutil":
        return ["gsutil", "-m", "rsync", "-r", src, dest]
    raise ValueError(f"Unsupported cloud tool '{tool}'. Use rclone, aws, or gsutil.")


class CloudUploadStage(BaseStage):
    """Upload outputs and figures to cloud storage with retry back-off."""

    @property
    def name(self) -> str:
        return "cloud_upload"

    def _should_skip(self, config: ConfigLoader, cache: CacheManager) -> bool:
        return False  # Always attempt upload.

    def _run(self, config: ConfigLoader) -> StageResult:
        start = time.monotonic()
        tool = config.get("cloud.tool", "rclone")
        destination = config.get("cloud.destination", "")
        max_retries = int(config.get("cloud.max_retries", 5))
        retry_delays = _DEFAULT_RETRY_DELAYS[:max_retries]

        if not destination:
            return StageResult(
                stage=self.name,
                status=StageStatus.FAILED,
                elapsed_seconds=time.monotonic() - start,
                message="cloud.destination is not configured in pipeline_config.yaml",
            )

        outputs_dir = config.resolve_path("outputs_dir")
        figures_dir = config.resolve_path("figures_dir")
        upload_pairs = [
            (str(outputs_dir), destination),
            (str(figures_dir), f"{destination}/figures"),
        ]

        for src, dest in upload_pairs:
            cmd = _build_upload_cmd(tool, src, dest)
            for attempt, delay in enumerate(retry_delays, start=1):
                try:
                    self.run_subprocess(cmd)
                    break
                except Exception as exc:  # noqa: BLE001
                    if attempt == len(retry_delays):
                        return StageResult(
                            stage=self.name,
                            status=StageStatus.FAILED,
                            elapsed_seconds=time.monotonic() - start,
                            message=(
                                f"Upload of '{src}' failed after {attempt} retries: {exc}"
                            ),
                        )
                    time.sleep(delay)

        # Write upload manifest.
        manifest: dict[str, str] = {}
        for directory in (outputs_dir, figures_dir):
            for p in directory.rglob("*"):
                if p.is_file():
                    manifest[str(p)] = _sha256(p)

        manifest_path = outputs_dir / "upload_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        return StageResult(
            stage=self.name,
            status=StageStatus.COMPLETED,
            elapsed_seconds=time.monotonic() - start,
            artifacts=[str(manifest_path)],
        )
