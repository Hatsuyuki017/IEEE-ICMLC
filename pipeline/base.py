"""Base classes and data models for pipeline stages."""

from __future__ import annotations

import subprocess
import time
from abc import ABC, abstractmethod
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from pipeline.cache import CacheManager
    from pipeline.config import ConfigLoader


class StageStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    stage: str
    status: StageStatus
    elapsed_seconds: float
    message: str = ""
    artifacts: list[str] = field(default_factory=list)


def _run_in_subprocess(fn: Callable, *args, **kwargs):
    """Trampoline executed inside a worker process."""
    return fn(*args, **kwargs)


class BaseStage(ABC):
    """Abstract base for all pipeline stages."""

    #: Hard wall-clock deadline per stage.  ``None`` means "use the value
    #: from ``config.timeout_seconds``".  Set a concrete integer on a
    #: subclass (or instance) to override the global config value.
    TIMEOUT_SECONDS: int | None = None  # resolved at runtime from config

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable stage identifier."""

    @abstractmethod
    def _run(self, config: "ConfigLoader") -> StageResult:
        """Execute the stage logic and return a result.

        This method is invoked inside a worker process to honour the
        timeout budget.
        """

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(
        self,
        config: "ConfigLoader",
        cache: "CacheManager",
        force: bool = False,
    ) -> StageResult:
        """Run the stage, honouring cache skip and timeout logic."""
        timeout = (
            self.TIMEOUT_SECONDS
            if self.TIMEOUT_SECONDS is not None
            else config.timeout_seconds
        )

        if not force and self._should_skip(config, cache):
            return StageResult(
                stage=self.name,
                status=StageStatus.SKIPPED,
                elapsed_seconds=0.0,
                message="Inputs unchanged; stage skipped (use --force to override).",
            )

        start = time.monotonic()
        try:
            with ProcessPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._run, config)
                result: StageResult = future.result(timeout=timeout)
        except FuturesTimeout:
            elapsed = time.monotonic() - start
            return StageResult(
                stage=self.name,
                status=StageStatus.TIMEOUT,
                elapsed_seconds=elapsed,
                message=f"Stage exceeded {timeout}s timeout and was terminated.",
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = time.monotonic() - start
            return StageResult(
                stage=self.name,
                status=StageStatus.FAILED,
                elapsed_seconds=elapsed,
                message=str(exc),
            )

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _should_skip(self, config: "ConfigLoader", cache: "CacheManager") -> bool:
        """Return ``True`` if the stage can be safely skipped."""
        return False

    @staticmethod
    def run_subprocess(
        cmd: list[str],
        *,
        capture_output: bool = False,
        timeout: Optional[int] = None,
    ) -> subprocess.CompletedProcess:
        """Run *cmd* as a subprocess, streaming output to the terminal."""
        return subprocess.run(
            cmd,
            check=True,
            capture_output=capture_output,
            timeout=timeout,
            text=True,
        )
