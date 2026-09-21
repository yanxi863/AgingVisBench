from __future__ import annotations

from processing.pipeline_config import PipelineConfig


def test_public_config_uses_real_environment_names(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-only-value")
    config = PipelineConfig.load("examples/pipeline.synthetic.yml")
    assert config.api_key_env == "DASHSCOPE_API_KEY"
    assert config.base_url_env == "DASHSCOPE_BASE_URL"
    assert config.model_env == "DASHSCOPE_MODEL"
    assert config.image_root == config.project_root / "examples" / "sample_corpus"
    summary = config.redacted_summary()
    assert summary["api_environment_present"]["DASHSCOPE_API_KEY"] is True
    assert "test-only-value" not in str(summary)


def test_selected_models_applies_include_and_exclude():
    config = PipelineConfig(models_include=["a", "b"], models_exclude=["b"])
    assert config.selected_models(["a", "b", "c"]) == ["a"]
