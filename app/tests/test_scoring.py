"""Pruebas unitarias del cálculo oficial RIASEC."""

from __future__ import annotations

import pytest

from app.services.riasec_service import (
    RiasecScoringError,
    build_result_payload,
    calculate_scores,
    determine_profiles,
    rank_scores,
)

RIASEC_CODES = ("R", "I", "A", "S", "E", "C")


def _responses(raw_by_area: dict[str, int]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    item_index = 1
    for area in RIASEC_CODES:
        for position in range(10):
            rows.append(
                {
                    "item_id": f"{area}-{position + 1}",
                    "item": {"area": area, "item_index": item_index},
                    "response_raw": raw_by_area[area],
                }
            )
            item_index += 1
    return rows


def test_scores_transform_raw_1_5_to_dimension_range_0_40():
    responses = _responses(
        {"R": 5, "I": 4, "A": 3, "S": 2, "E": 1, "C": 5}
    )

    assert calculate_scores(responses) == {
        "R": 40,
        "I": 30,
        "A": 20,
        "S": 10,
        "E": 0,
        "C": 40,
    }


def test_ranking_is_descending_but_does_not_break_ties_psychometrically():
    scores = {"R": 35, "I": 35, "A": 28, "S": 20, "E": 15, "C": 10}

    ranking = rank_scores(scores)
    profiles = determine_profiles(scores)

    assert [entry.code for entry in ranking[:2]] == ["R", "I"]
    assert ranking[0].score == ranking[1].score == 35
    assert profiles["tie_top1"] is True
    assert profiles["top1_candidates"] == ["R", "I"]
    assert profiles["holland_code"] is None


def test_holland_code_exists_only_when_top_three_positions_are_unique():
    unique = {"R": 38, "I": 34, "A": 29, "S": 20, "E": 15, "C": 10}
    tied_third = {"R": 38, "I": 34, "A": 29, "S": 29, "E": 15, "C": 10}

    assert determine_profiles(unique)["holland_code"] == "RIA"
    assert determine_profiles(tied_third)["holland_code"] is None


def test_complete_payload_keeps_scoring_in_backend():
    responses = _responses(
        {"R": 5, "I": 4, "A": 3, "S": 2, "E": 1, "C": 1}
    )

    payload = build_result_payload(responses)

    assert payload["scores"]["R"] == 40
    assert payload["holland_code"] == "RIA"
    assert payload["scoring_version"]


def test_scoring_rejects_duplicate_or_incomplete_items():
    responses = _responses({code: 3 for code in RIASEC_CODES})
    responses[1]["item_id"] = responses[0]["item_id"]

    with pytest.raises(RiasecScoringError):
        calculate_scores(responses)

    with pytest.raises(RiasecScoringError):
        calculate_scores(_responses({code: 3 for code in RIASEC_CODES})[:-1])
