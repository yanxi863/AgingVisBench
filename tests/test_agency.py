from __future__ import annotations

import pandas as pd

from process.recode_rq2_development_oriented_agency import classify_action


def test_generic_reading_is_development_oriented():
    result = classify_action("reading a book")
    assert result["Agency_Orientation"] == "achievement_growth"
    assert result["Development_Oriented_Agency"] == 1


def test_reading_while_cooking_uses_specific_maintenance_rule():
    result = classify_action("reading a recipe while cooking")
    assert result["Agency_Orientation"] == "maintenance"
    assert result["Development_Oriented_Agency"] == 0
    assert result["Coding_Rule"].startswith("maintenance_reading:")


def test_social_participation_has_priority():
    result = classify_action("reading to children")
    assert result["Agency_Orientation"] == "social_participation"


def test_unknown_requires_review():
    result = classify_action("")
    assert result["Agency_Orientation"] == "unclear"
    assert pd.isna(result["Development_Oriented_Agency"])
    assert result["Review_Needed"] == 1
