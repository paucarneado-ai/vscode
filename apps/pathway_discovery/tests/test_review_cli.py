"""Tests for review_cli."""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from apps.pathway_discovery.review_cli import (
    cmd_list, cmd_history, cmd_show, cmd_set, _load_report, VALID_STATUSES,
)


def _make_report(review_state: dict, recommendations: list | None = None) -> dict:
    return {
        "report_schema_version": 6,
        "review_queue_state": review_state,
        "recommendations": recommendations or [],
    }


def _write_report(tmpdir: str, data: dict) -> str:
    reports_dir = os.path.join(tmpdir, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    path = os.path.join(reports_dir, "pathway_audit_latest.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return path


# --- list ---

def test_list_shows_active_items(capsys):
    data = _make_report({
        "fp-active": {"operator_status": "unreviewed", "inactive": False, "last_bucket": "watchlist"},
        "fp-resolved": {"operator_status": "resolved", "inactive": False},
        "fp-inactive": {"operator_status": "monitor", "inactive": True},
    })
    cmd_list(data)
    out = capsys.readouterr().out
    assert "fp-active" in out
    assert "fp-resolved" not in out
    assert "fp-inactive" not in out


def test_list_empty(capsys):
    cmd_list(_make_report({}))
    assert "empty" in capsys.readouterr().out.lower()


def test_list_enriches_from_recommendations(capsys):
    data = _make_report(
        {"fp1": {"operator_status": "unreviewed", "inactive": False}},
        [{"stable_fingerprint": "fp1", "why_now": "test reason", "intervention_hint": "do this",
          "review_bucket": "watchlist"}],
    )
    cmd_list(data)
    out = capsys.readouterr().out
    assert "test reason" in out
    assert "do this" in out


# --- history ---

def test_history_shows_reviewed_and_inactive(capsys):
    data = _make_report({
        "fp-keep": {"operator_status": "keep", "inactive": False, "decision_reason": "accepted"},
        "fp-gone": {"operator_status": "monitor", "inactive": True, "last_description": "old finding"},
        "fp-unrev": {"operator_status": "unreviewed", "inactive": False},
    })
    cmd_history(data)
    out = capsys.readouterr().out
    assert "fp-keep" in out
    assert "fp-gone" in out
    assert "fp-unrev" not in out  # unreviewed + active = not history


def test_history_empty(capsys):
    cmd_history(_make_report({}))
    assert "No decision history" in capsys.readouterr().out


# --- show ---

def test_show_displays_entry(capsys):
    data = _make_report({
        "fp-full1234567890": {"operator_status": "monitor", "operator_note": "tracking", "inactive": False},
    })
    cmd_show(data, "fp-full")
    out = capsys.readouterr().out
    assert "fp-full1234567890" in out
    assert "monitor" in out
    assert "tracking" in out


def test_show_invalid_fingerprint():
    data = _make_report({"fp1": {"operator_status": "unreviewed"}})
    with pytest.raises(SystemExit):
        cmd_show(data, "nonexistent")


# --- set ---

def test_set_updates_status():
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_report({"fp-test123": {"operator_status": "unreviewed", "inactive": False}})
        path = _write_report(tmpdir, data)
        cmd_set(data, path, "fp-test", "monitor", note="watching", reason="looks stable")

        with open(path) as f:
            updated = json.load(f)
        entry = updated["review_queue_state"]["fp-test123"]
        assert entry["operator_status"] == "monitor"
        assert entry["operator_note"] == "watching"
        assert entry["decision_reason"] == "looks stable"


def test_set_auto_populates_reviewed_at():
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_report({"fp-new123": {"operator_status": "unreviewed", "inactive": False}})
        path = _write_report(tmpdir, data)
        cmd_set(data, path, "fp-new", "keep")

        with open(path) as f:
            updated = json.load(f)
        entry = updated["review_queue_state"]["fp-new123"]
        assert entry["reviewed_at"] != ""


def test_set_does_not_overwrite_reviewed_at_on_subsequent():
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_report({"fp-x123": {
            "operator_status": "keep", "reviewed_at": "2026-01-01 10:00", "inactive": False,
        }})
        path = _write_report(tmpdir, data)
        cmd_set(data, path, "fp-x", "schedule")

        with open(path) as f:
            updated = json.load(f)
        # reviewed_at should stay as original since it was already set (not unreviewed->X)
        assert updated["review_queue_state"]["fp-x123"]["reviewed_at"] == "2026-01-01 10:00"


def test_set_invalid_status():
    data = _make_report({"fp1": {"operator_status": "unreviewed"}})
    with pytest.raises(SystemExit):
        cmd_set(data, "/dev/null", "fp1", "invalid_status")


def test_set_invalid_fingerprint():
    data = _make_report({"fp1": {"operator_status": "unreviewed"}})
    with pytest.raises(SystemExit):
        cmd_set(data, "/dev/null", "nonexistent", "keep")


def test_set_preserves_other_fields():
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_report({
            "fp-pres123": {
                "operator_status": "unreviewed", "inactive": False,
                "last_bucket": "watchlist", "last_description": "chain a->b",
            }
        })
        path = _write_report(tmpdir, data)
        cmd_set(data, path, "fp-pres", "monitor")

        with open(path) as f:
            updated = json.load(f)
        entry = updated["review_queue_state"]["fp-pres123"]
        assert entry["last_bucket"] == "watchlist"
        assert entry["last_description"] == "chain a->b"


def test_set_preserves_inactive_entries():
    """Setting one item should not destroy other entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_report({
            "fp-a": {"operator_status": "unreviewed", "inactive": False},
            "fp-b": {"operator_status": "resolved", "inactive": True, "decision_reason": "done"},
        })
        path = _write_report(tmpdir, data)
        cmd_set(data, path, "fp-a", "keep")

        with open(path) as f:
            updated = json.load(f)
        assert "fp-b" in updated["review_queue_state"]
        assert updated["review_queue_state"]["fp-b"]["operator_status"] == "resolved"


# --- Integration: resolved item excluded from next audit render ---

def test_resolved_excluded_after_cli_set():
    """After CLI marks item resolved, reporter should exclude it from active queue."""
    from apps.pathway_discovery.reporter import generate_report
    from apps.pathway_discovery.schemas import CandidatePathway, CandidateType, PathwayRecommendation

    rec = PathwayRecommendation(
        recommendation_id="PR-1",
        candidate=CandidatePathway(
            candidate_id="CP-1", candidate_type=CandidateType.LONG_PATH,
            description="chain", stable_fingerprint="fp-cli-test",
        ),
        score=50.0, review_bucket="watchlist",
        in_review_queue=False,  # resolved = not in active queue
        operator_status="resolved",
        decision_reason="addressed in refactor",
        reviewed_at="2026-03-18 12:00",
        inactive=False,
    )
    report = generate_report([rec], [], [], [], [])
    if "## Review Queue" in report:
        queue_section = report.split("## Review Queue")[1].split("##")[0]
        assert "fp-cli-test" not in queue_section

    # But should appear in Decision Log
    assert "## Decision Log" in report
    assert "resolved" in report


# --- _load_report error ---

def test_load_report_missing():
    with pytest.raises(SystemExit):
        _load_report("/nonexistent/path/report.json")
