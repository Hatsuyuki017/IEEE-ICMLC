#!/usr/bin/env python3
"""GBM Research Automation Pipeline — entry point.

Usage
-----
    python run_pipeline.py [options]

Options
-------
    --config <path>         Path to config file (default: pipeline_config.yaml)
    --force                 Ignore cache; re-run all stages
    --stages <s1,s2,...>    Comma-separated list of stages to run
                            Choices: model_tuning, visualization, paper_writing,
                                     humanizer, cloud_upload
    --help                  Show this help message and exit

Examples
--------
    # Run the full pipeline:
    python run_pipeline.py

    # Re-run everything from scratch:
    python run_pipeline.py --force

    # Run only visualization and paper writing:
    python run_pipeline.py --stages visualization,paper_writing

    # Use a custom config file:
    python run_pipeline.py --config /path/to/my_config.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_pipeline.py",
        description="GBM research automation pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--config",
        default="pipeline_config.yaml",
        metavar="PATH",
        help="Path to pipeline_config.yaml (default: %(default)s)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cached results and re-run all stages.",
    )
    parser.add_argument(
        "--stages",
        default=None,
        metavar="STAGES",
        help=(
            "Comma-separated list of stages to run "
            "(default: all stages in order)."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # Resolve config path relative to the script's directory.
    script_dir = Path(__file__).resolve().parent
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = script_dir / config_path

    # Import here so that import errors are reported after argument parsing.
    from pipeline.config import ConfigLoader, ConfigError
    from pipeline.orchestrator import PipelineOrchestrator

    try:
        config = ConfigLoader(config_path)
        config.validate()
    except FileNotFoundError:
        print(f"ERROR: Configuration file not found: {config_path}", file=sys.stderr)
        return 1
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    stages = [s.strip() for s in args.stages.split(",")] if args.stages else None

    try:
        orchestrator = PipelineOrchestrator(config, force=args.force)
        return orchestrator.run(stages=stages)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
