"""Smoke tests for scripts/audit_visual_proofs.py.

The audit script encodes direction-of-effect heuristics per subtype. If
those heuristics silently break (e.g., a refactor swaps a sign, or a
subtype name moves and the dispatch stops matching), the audit's report
goes silently green and stops catching regressions in the visual-proof
gallery. These tests fail when that happens.

Each test exercises one verdict branch with a synthetic delta dict +
fake entry — no rendering, no filesystem. Fast, deterministic.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO / "scripts" / "audit_visual_proofs.py"


@pytest.fixture(scope="module")
def audit() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_audit", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Register before exec_module so dataclass field-type resolution
    # (with PEP 563 stringified annotations) can find the module.
    sys.modules["_audit"] = mod
    spec.loader.exec_module(mod)
    return mod


@dataclass
class _FakeEntry:
    name: str
    subtype: str | None
    layer: str = "L3"


def _delta(**overrides: float) -> dict[str, float]:
    """Build a delta dict; unspecified channels default to 0."""
    base = {
        "mean_r": 0.0,
        "mean_g": 0.0,
        "mean_b": 0.0,
        "mean_luma": 0.0,
        "std_luma": 0.0,
        "mean_chroma": 0.0,
        "clip_hi": 0.0,
        "clip_lo": 0.0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Sigmoid direction-of-effect
# ---------------------------------------------------------------------------


def test_sigmoid_lift_with_luma_up_is_ok(audit: ModuleType) -> None:
    entry = _FakeEntry("look_blacks_lifted_subject", "sigmoid")
    v = audit._verdict_chart(entry, _delta(mean_luma=4.0, std_luma=-1.0))
    assert v.status == "ok"


def test_sigmoid_lift_with_luma_down_fails(audit: ModuleType) -> None:
    entry = _FakeEntry("shadows_lift", "sigmoid")
    v = audit._verdict_chart(entry, _delta(mean_luma=-4.0, std_luma=-1.0))
    assert v.status == "fail"
    assert "lift moved luma down" in v.note


def test_sigmoid_crush_with_luma_down_is_ok(audit: ModuleType) -> None:
    entry = _FakeEntry("shadows_crushed", "sigmoid")
    v = audit._verdict_chart(entry, _delta(mean_luma=-4.0, std_luma=1.0))
    assert v.status == "ok"


def test_sigmoid_crush_with_luma_up_fails(audit: ModuleType) -> None:
    entry = _FakeEntry("shadows_crushed", "sigmoid")
    v = audit._verdict_chart(entry, _delta(mean_luma=4.0, std_luma=1.0))
    assert v.status == "fail"


# ---------------------------------------------------------------------------
# Vignette darkening direction
# ---------------------------------------------------------------------------


def test_vignette_darkens_is_ok(audit: ModuleType) -> None:
    entry = _FakeEntry("vignette", "vignette")
    v = audit._verdict_chart(entry, _delta(mean_luma=-3.0))
    assert v.status == "ok"


def test_vignette_brightens_fails(audit: ModuleType) -> None:
    entry = _FakeEntry("vignette", "vignette")
    v = audit._verdict_chart(entry, _delta(mean_luma=3.0))
    assert v.status == "fail"
    assert "vignette brightened" in v.note


# ---------------------------------------------------------------------------
# Grain adds noise
# ---------------------------------------------------------------------------


def test_grain_adds_noise_is_ok(audit: ModuleType) -> None:
    entry = _FakeEntry("look_70s_film", "grain")
    v = audit._verdict_chart(entry, _delta(std_luma=8.0))
    assert v.status == "ok"


def test_grain_with_no_noise_fails(audit: ModuleType) -> None:
    entry = _FakeEntry("grain_heavy", "grain")
    v = audit._verdict_chart(entry, _delta(std_luma=0.1, mean_luma=2.0))
    assert v.status == "fail"
    assert "grain didn't add noise" in v.note


# ---------------------------------------------------------------------------
# Universal clip checks
# ---------------------------------------------------------------------------


def test_blown_highlights_fail(audit: ModuleType) -> None:
    entry = _FakeEntry("foo_bar", "exposure")
    v = audit._verdict_chart(entry, _delta(mean_luma=20.0, clip_hi=0.5))
    assert v.status == "fail"
    assert "blown" in v.note


def test_blown_highlights_allowed_for_open_entries(audit: ModuleType) -> None:
    entry = _FakeEntry("whites_open", "sigmoid")
    v = audit._verdict_chart(entry, _delta(mean_luma=20.0, clip_hi=0.5))
    # Whites-open is *allowed* to push some clip_hi — not flagged.
    assert v.status != "fail"


def test_crushed_shadows_fail(audit: ModuleType) -> None:
    entry = _FakeEntry("foo_bar", "exposure")
    v = audit._verdict_chart(entry, _delta(mean_luma=-20.0, clip_lo=0.5))
    assert v.status == "fail"
    assert "crushed" in v.note


# ---------------------------------------------------------------------------
# Near-baseline + expected-near-baseline exceptions
# ---------------------------------------------------------------------------


def test_near_baseline_warns_by_default(audit: ModuleType) -> None:
    entry = _FakeEntry("look_landscape_neutral", "look")
    v = audit._verdict_chart(entry, _delta())
    assert v.status == "warn"


def test_known_chart_unfair_entry_skips_to_ok(audit: ModuleType) -> None:
    # blacks_lifted is in _EXPECTED_NEAR_BASELINE_NAMES — chart isn't the
    # verifying fixture (see tests/e2e/_lab_grade_deltas.py SKIP_REASONS).
    entry = _FakeEntry("blacks_lifted", "sigmoid")
    v = audit._verdict_chart(entry, _delta(mean_luma=-4.0))
    assert v.status == "ok"
    assert "chart isn't the verifying fixture" in v.note


def test_expected_near_baseline_subtype_skips_to_ok(audit: ModuleType) -> None:
    # highlights subtype handler returns ok unconditionally — recovery
    # only matters where input has clipping, and the chart has none.
    entry = _FakeEntry("highlights_clip_threshold", "highlights")
    v = audit._verdict_chart(entry, _delta())
    assert v.status == "ok"


# ---------------------------------------------------------------------------
# Real-raw heuristics
# ---------------------------------------------------------------------------


def test_real_raw_near_baseline_warns(audit: ModuleType) -> None:
    entry = _FakeEntry("transform", "ashift")
    v = audit._verdict_real_raw(entry, _delta())
    assert v.status == "warn"


def test_real_raw_blown_highlights_fail(audit: ModuleType) -> None:
    entry = _FakeEntry("look_random", "look")
    v = audit._verdict_real_raw(entry, _delta(mean_luma=20.0, clip_hi=0.5))
    assert v.status == "fail"


# ---------------------------------------------------------------------------
# End-to-end smoke — script runs against on-disk gallery with exit 0
# ---------------------------------------------------------------------------


def test_audit_runs_end_to_end(audit: ModuleType, tmp_path: Path) -> None:
    """Run the actual audit on the current visual-proofs gallery. Asserts
    the script wires up, finds entries, and produces a report. Doesn't
    assert specific contents — those evolve with the vocabulary."""
    json_path = tmp_path / "report.json"
    rc = audit.main(["--json", str(json_path)])
    assert rc == 0, "audit should exit 0 when no FAILs are present"
    assert json_path.exists()
    import json

    payload = json.loads(json_path.read_text())
    assert payload["total"] > 0
    assert payload["fail"] == 0
    assert isinstance(payload["entries"], list)
