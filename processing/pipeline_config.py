from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: Optional[Path]) -> Dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("读取 YAML 配置需要安装 pyyaml。") from exc
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"配置文件必须是 YAML mapping: {path}")
    return data


def _get(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if str(v).strip()]
    s = str(value).strip()
    if not s:
        return []
    return [part.strip() for part in s.split(",") if part.strip()]


@dataclass
class PipelineConfig:
    project_root: Path = PROJECT_ROOT
    image_root: Path = PROJECT_ROOT / "data" / "images"
    generated_data_root: Path = PROJECT_ROOT / "outputs"
    analysis_output_root: Path = PROJECT_ROOT / "outputs" / "analysis"
    result_root: Path = PROJECT_ROOT / "outputs" / "results"
    yolo_weights: Path = PROJECT_ROOT / "models" / "yolov8s.pt"
    python_executable: str = sys.executable
    max_images: Optional[int] = None
    resume: bool = True
    skip_existing: bool = True
    api_enabled: bool = False
    api_key_env: str = "DASHSCOPE_API_KEY"
    base_url_env: str = "DASHSCOPE_BASE_URL"
    model_env: str = "DASHSCOPE_MODEL"
    models_include: List[str] = field(default_factory=list)
    models_exclude: List[str] = field(default_factory=list)
    stage_flags: Dict[str, bool] = field(default_factory=dict)

    @classmethod
    def load(cls, config_path: Optional[str | Path] = None) -> "PipelineConfig":
        path = Path(config_path).expanduser() if config_path else None
        if path and not path.is_absolute():
            path = PROJECT_ROOT / path
        data = _load_yaml(path)

        def resolve_path(value: Any, default: Path) -> Path:
            if value is None or str(value).strip() == "":
                return default
            p = Path(str(value)).expanduser()
            return p if p.is_absolute() else PROJECT_ROOT / p

        max_images_value = _get(data, "runtime", "max_images", default=None)
        max_images = int(max_images_value) if max_images_value not in (None, "") else None
        python_executable = (
            os.getenv("PIPELINE_PYTHON")
            or str(_get(data, "runtime", "python_executable", default="") or "").strip()
            or sys.executable
        )

        return cls(
            project_root=PROJECT_ROOT,
            image_root=resolve_path(_get(data, "paths", "image_root"), PROJECT_ROOT / "data" / "images"),
            generated_data_root=resolve_path(_get(data, "paths", "generated_data_root"), PROJECT_ROOT / "outputs"),
            analysis_output_root=resolve_path(_get(data, "paths", "analysis_output_root"), PROJECT_ROOT / "outputs" / "analysis"),
            result_root=resolve_path(_get(data, "paths", "result_root"), PROJECT_ROOT / "outputs" / "results"),
            yolo_weights=resolve_path(_get(data, "vision", "yolo_weights"), PROJECT_ROOT / "models" / "yolov8s.pt"),
            python_executable=python_executable,
            max_images=max_images,
            resume=_as_bool(_get(data, "runtime", "resume", default=True), default=True),
            skip_existing=_as_bool(_get(data, "runtime", "skip_existing", default=True), default=True),
            api_enabled=_as_bool(_get(data, "api", "enabled", default=False), default=False),
            api_key_env=str(_get(data, "api", "api_key_env", default="DASHSCOPE_API_KEY")),
            base_url_env=str(_get(data, "api", "base_url_env", default="DASHSCOPE_BASE_URL")),
            model_env=str(_get(data, "api", "model_env", default="DASHSCOPE_MODEL")),
            models_include=_as_list(_get(data, "models", "include")),
            models_exclude=_as_list(_get(data, "models", "exclude")),
            stage_flags=dict(_get(data, "stages", default={}) or {}),
        )

    @property
    def clean_data_root(self) -> Path:
        return self.generated_data_root / "clean_data"

    def latest_rq2_output(self) -> Optional[Path]:
        if not self.generated_data_root.exists():
            return None
        candidates = [p for p in self.generated_data_root.glob("rq2_pipeline_*") if p.is_dir()]
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.stat().st_mtime)

    def selected_models(self, available: List[str]) -> List[str]:
        include = set(self.models_include)
        exclude = set(self.models_exclude)
        models = [m for m in available if not include or m in include]
        return [m for m in models if m not in exclude]

    def api_environment_status(self) -> Dict[str, bool]:
        return {
            self.api_key_env: bool(os.getenv(self.api_key_env, "").strip()),
            self.base_url_env: bool(os.getenv(self.base_url_env, "").strip()),
            self.model_env: bool(os.getenv(self.model_env, "").strip()),
        }

    def redacted_summary(self) -> Dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "image_root": str(self.image_root),
            "generated_data_root": str(self.generated_data_root),
            "analysis_output_root": str(self.analysis_output_root),
            "result_root": str(self.result_root),
            "yolo_weights": str(self.yolo_weights),
            "python_executable": self.python_executable,
            "max_images": self.max_images,
            "resume": self.resume,
            "skip_existing": self.skip_existing,
            "api_enabled": self.api_enabled,
            "api_environment_present": self.api_environment_status(),
            "models_include": self.models_include,
            "models_exclude": self.models_exclude,
            "stage_flags": self.stage_flags,
        }
