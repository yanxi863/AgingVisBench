from __future__ import annotations

import math

from processing.run_rq2_full_pipeline import (
    build_age_group,
    normalize_age,
    normalize_binary,
    parse_group_parts,
    safe_parse_json,
)
from processing.audit_urban_rural_scene import normalize_scene_value


def test_group_and_age_helpers():
    assert parse_group_parts("60yo_China_Woman") == ("60yo", "China", "Woman")
    assert normalize_age("75yo") == 75
    assert build_age_group(75) == "70s"
    assert math.isnan(normalize_age("unknown"))


def test_semantic_json_normalization():
    result = safe_parse_json('```json\n{"action_type":"reading; writing","agency_level":"routine_active","scene_type":"house","space_type":"inside","objects":["book"],"modern_object_presence":1,"traditional_cultural_marker_presence":0,"medical_object_count":"0","environment_type":"indoor"}\n```')
    assert result["action_type"] == ["reading", "writing"]
    assert result["agency_level"] == "active"
    assert result["scene_type"] == "home"
    assert result["medical_object_count"] == 0


def test_binary_and_urban_rural_unknown_preservation():
    assert normalize_binary(True) == 1
    assert normalize_binary("no") == 0
    assert normalize_binary("unknown") is None
    assert normalize_scene_value("village") == "rural"
    assert normalize_scene_value("unclear") == "unknown_or_mixed"
