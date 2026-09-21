from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True,
    )


def test_main_help_and_status():
    assert "strict dry-run" in run("processing/run_full_audit_pipeline.py", "--help").stdout
    status = run(
        "processing/run_full_audit_pipeline.py", "--stage", "status",
        "--config", "examples/pipeline.synthetic.yml",
    ).stdout
    assert "snapshot_available" in status
    assert "synthetic_model" in status


def test_direct_rq2_dry_run_is_zero_write(tmp_path):
    image = tmp_path / "images" / "synthetic" / "60yo_Test_Woman" / "placeholder.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"not-decoded-in-dry-run")
    output = tmp_path / "must-not-exist"
    result = run(
        "processing/run_rq2_full_pipeline.py",
        "--image-root", str(tmp_path / "images"),
        "--output-root", str(output),
        "--models", "synthetic",
        "--max-images", "1",
        "--skip-api",
        "--dry-run",
    )
    assert "no directories, manifests, API calls, or result files were created" in result.stdout
    assert not output.exists()


def test_urban_rural_skip_api_is_zero_write(tmp_path):
    output = tmp_path / "must-not-exist"
    result = run(
        "processing/audit_urban_rural_scene.py",
        "--source-data", str(tmp_path / "missing-source"),
        "--output-data", str(output),
        "--skip-api",
    )
    assert "no files were written" in result.stdout
    assert not output.exists()
