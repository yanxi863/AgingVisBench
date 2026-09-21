from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List

try:
    from pipeline_config import PipelineConfig
except ImportError:  # pragma: no cover - supports module execution from project root
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from pipeline_config import PipelineConfig


STAGE_ORDER = ["rq2", "urban-rural"]


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def command_text(command: Iterable[str]) -> str:
    return " ".join(f'"{part}"' if " " in part else part for part in command)


def run_command(command: List[str], cwd: Path, dry_run: bool) -> None:
    print(f"Command: {command_text(command)}")
    if dry_run:
        print("DRY-RUN: command not executed; no files were written.")
        return
    subprocess.run(command, cwd=str(cwd), check=True)


def latest_rq2_or_default(config: PipelineConfig) -> Path:
    latest = config.latest_rq2_output()
    return latest if latest is not None else config.generated_data_root


def status(config: PipelineConfig) -> dict:
    latest_rq2 = config.latest_rq2_output()
    clean_data = config.clean_data_root
    return {
        "config": config.redacted_summary(),
        "stages": {
            "image_corpus": {
                "status": "available" if config.image_root.is_dir() else "missing",
                "path": rel(config.image_root, config.project_root),
            },
            "rq2": {
                "status": "available" if latest_rq2 else "missing",
                "latest_output": rel(latest_rq2, config.project_root) if latest_rq2 else None,
            },
            "urban_rural": {
                "status": "available" if clean_data.is_dir() else "missing",
                "output": rel(clean_data, config.project_root),
            },
            "published_reports": {
                "status": "snapshot_available" if (config.project_root / "reports").is_dir() else "missing",
                "note": "Aggregate V0.5 snapshot; not regenerated from public synthetic data.",
            },
        },
    }


def run_rq2(config: PipelineConfig, args: argparse.Namespace, dry_run: bool) -> None:
    script = config.project_root / "processing" / "run_rq2_full_pipeline.py"
    max_images = args.max_images if args.max_images is not None else config.max_images
    models = args.models or config.models_include
    command = [
        config.python_executable,
        str(script),
        "--image-root",
        str(config.image_root),
        "--output-root",
        str(config.generated_data_root),
        "--python-executable",
        config.python_executable,
        "--yolo-weights",
        str(config.yolo_weights),
    ]
    if max_images is not None:
        command.extend(["--max-images", str(max_images)])
    if models:
        command.extend(["--models", *models])
    if config.models_exclude:
        command.extend(["--exclude-models", *config.models_exclude])
    if args.skip_api or not config.api_enabled:
        command.append("--skip-api")
    command.append("--execute" if args.execute and not dry_run else "--dry-run")
    run_command(command, config.project_root, dry_run)


def run_urban_rural(config: PipelineConfig, args: argparse.Namespace, dry_run: bool) -> None:
    script = config.project_root / "processing" / "audit_urban_rural_scene.py"
    source_data = Path(args.source_data).expanduser() if args.source_data else latest_rq2_or_default(config)
    if not source_data.is_absolute():
        source_data = config.project_root / source_data
    output_data = Path(args.output_data).expanduser() if args.output_data else config.clean_data_root
    if not output_data.is_absolute():
        output_data = config.project_root / output_data
    models = args.models or config.models_include

    command = [
        config.python_executable,
        str(script),
        "--source-data",
        str(source_data),
        "--output-data",
        str(output_data),
    ]
    if models:
        command.extend(["--models", *models])
    if args.limit is not None:
        command.extend(["--limit", str(args.limit)])
    if args.skip_api or not config.api_enabled:
        command.append("--skip-api")
    if not dry_run:
        command.append("--execute")
    run_command(command, config.project_root, dry_run)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the public AgingVisBench audit stages with status and strict dry-run support."
    )
    parser.add_argument("--stage", choices=["status", *STAGE_ORDER, "all"], default="status")
    parser.add_argument("--config", default=None, help="Pipeline YAML, e.g. config/pipeline.local.yml")
    parser.add_argument("--execute", action="store_true", help="Execute stage commands. Without this flag, no command runs.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned commands without executing or writing files.")
    parser.add_argument("--max-images", type=int, default=None, help="Limit images per model for the RQ2 stage.")
    parser.add_argument("--models", nargs="*", default=None, help="Optional model directory names to include.")
    parser.add_argument("--skip-api", action="store_true", help="Skip semantic API-dependent work.")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows per model for urban/rural audit.")
    parser.add_argument("--source-data", default=None, help="Override the urban/rural source directory.")
    parser.add_argument("--output-data", default=None, help="Override the urban/rural output directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.execute and args.dry_run:
        raise SystemExit("--execute and --dry-run are mutually exclusive.")

    config = PipelineConfig.load(args.config)
    dry_run = args.dry_run or not args.execute

    if args.stage == "status":
        print_json(status(config))
        return

    stages = STAGE_ORDER if args.stage == "all" else [args.stage]
    for stage in stages:
        print(f"\n=== Stage: {stage} ===")
        if stage == "rq2":
            run_rq2(config, args, dry_run)
        elif stage == "urban-rural":
            run_urban_rural(config, args, dry_run)
        else:  # pragma: no cover
            raise ValueError(f"Unknown stage: {stage}")


if __name__ == "__main__":
    main()
