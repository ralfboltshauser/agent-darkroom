"""Lab-grade validation that highlight recovery actually reduces clipped
pixel count on the clipped-gradient fixture (issue #79).

The colorchecker24 and grayscale-ramp fixtures don't have blown
highlights, so the existing lab-grade isolation suite can only assert
"highlight recovery dampens bright patches" via grayscale-ramp luma —
which works as a direction-of-change proxy but doesn't actually test
the recovery operation. The clipped-gradient fixture has a 60% pure-
white band on the bottom half by design; this test counts the clipped
pixels there before and after applying ``highlights_clip_threshold``
at 0.85 (the strong-recovery equivalent) and asserts the count drops.

Phase 4 / RFC-021: ``highlights_recovery_strong`` was retired and
replaced by the parameterized ``highlights_clip_threshold`` entry. The
test exercises the parameterized form at ``clip_threshold=0.85``.

Per RFC-019 / ADR-067 fixture-integrity rules: the test stays in
direction-of-change territory (just asserts clip-count direction +
minimum delta), not a Delta-E reference test, since the clipped
fixture isn't anchored in the published reference data.
"""

from __future__ import annotations

import dataclasses
import os
import sys
from pathlib import Path

import pytest
from PIL import Image

from chemigram.core.pipeline import render
from chemigram.core.vocab import VocabularyIndex, load_packs
from chemigram.core.xmp import Xmp, parse_xmp, write_xmp

_TESTS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_TESTS_ROOT.parent))

_REPO = Path(__file__).resolve().parents[2]
_BASELINE_TEMPLATE = _REPO / "src/chemigram/core/_baseline_v1.xmp"
_CLIPPED = _REPO / "tests/fixtures/reference-targets/clipped_gradient_synthetic.png"

# The clipped fixture is 600x400. Its bottom-left 60% (rows 200..399,
# cols 0..359) is pinned at 255,255,255 in the source. After render,
# the same proportional region in the output contains the clipped band.
# We count pixels at or above the threshold within that region.
_CLIP_THRESHOLD = 250  # 8-bit; matches conftest.highlight_clip_pct convention


def _resolve_configdir() -> Path:
    raw = os.environ.get("CHEMIGRAM_DT_CONFIGDIR")
    if raw:
        path = Path(raw).expanduser()
        if path.exists():
            return path
    fallback = Path.home() / "chemigram-phase0" / "dt-config"
    if fallback.exists():
        return fallback
    pytest.skip("CHEMIGRAM_DT_CONFIGDIR not set and ~/chemigram-phase0/dt-config absent")


def _empty_baseline() -> Xmp:
    template = parse_xmp(_BASELINE_TEMPLATE)
    return dataclasses.replace(template, history=())


def _clipped_pixel_count(image_path: Path, threshold: int = _CLIP_THRESHOLD) -> int:
    """Count pixels in the bottom-left 60% region with all RGB channels
    at or above ``threshold``.

    Region: rows H/2..H, cols 0..0.6*W (the clipped band in the source).
    """
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    band = img.crop((0, h // 2, int(w * 0.6), h))
    n = 0
    for r, g, b in band.getdata():
        if r >= threshold and g >= threshold and b >= threshold:
            n += 1
    return n


@pytest.fixture(scope="module")
def configdir() -> Path:
    return _resolve_configdir()


@pytest.fixture(scope="module")
def vocab() -> VocabularyIndex:
    return load_packs(["expressive-baseline"])


# (clip_threshold, min_reduction_pct) — empirical min thresholds. Aggressive
# recovery at 0.85 drops more pixels; mild recovery at 0.95 still measurable
# but with a smaller floor. The display-referred fixture limits how much
# clipping the module can actually unrecover; thresholds are deliberately
# conservative to stay robust to render-size variation while still detecting
# "module silently no-ops" regressions.
_CLIP_DIRECTION_CASES: tuple[tuple[float, float], ...] = (
    (0.85, 5.0),
    (0.95, 1.0),
)


@pytest.mark.parametrize(
    "clip_threshold, min_reduction_pct",
    _CLIP_DIRECTION_CASES,
    ids=[f"clip_{c[0]}" for c in _CLIP_DIRECTION_CASES],
)
def test_highlights_clip_threshold_reduces_clipped_pixels_on_clipped_fixture(
    clip_threshold: float,
    min_reduction_pct: float,
    vocab: VocabularyIndex,
    configdir: Path,
    tmp_path_factory: pytest.TempPathFactory,
    darktable_binary: str,
) -> None:
    """Render the clipped fixture twice — empty baseline vs through
    ``highlights_clip_threshold`` at the parametrized clip value — and
    assert the clipped-pixel count in the white band drops by at least
    the floor for that value.

    Strengthens #143 / option C: prior coverage exercised only the
    aggressive 0.85 value, leaving milder 0.95 in PARAMETERIZED_EFFECTS
    with render-completes-only. This pair verifies the recovery module
    is directionally engaged across the parametric range.
    """
    _ = darktable_binary
    from chemigram.core.helpers import apply_entry

    out_dir = tmp_path_factory.mktemp(f"clipped_recovery_{clip_threshold}")
    baseline_xmp = _empty_baseline()

    # Baseline render
    base_xmp_path = out_dir / "baseline.xmp"
    base_out = out_dir / "baseline.jpg"
    write_xmp(baseline_xmp, base_xmp_path)
    base_result = render(
        raw_path=_CLIPPED,
        xmp_path=base_xmp_path,
        output_path=base_out,
        width=400,
        height=400,
        high_quality=False,
        configdir=configdir,
    )
    if not base_result.success:
        pytest.fail(f"baseline render failed: {base_result.error_message}")

    # Recovery render via parameterized apply path (RFC-021)
    entry = vocab.lookup_by_name("highlights_clip_threshold")
    if entry is None:
        pytest.fail("highlights_clip_threshold not found in expressive-baseline pack")
    recovery_xmp = apply_entry(
        baseline_xmp, entry, parameter_values={"clip_threshold": clip_threshold}
    )
    recovery_xmp_path = out_dir / "recovery.xmp"
    recovery_out = out_dir / "recovery.jpg"
    write_xmp(recovery_xmp, recovery_xmp_path)
    recovery_result = render(
        raw_path=_CLIPPED,
        xmp_path=recovery_xmp_path,
        output_path=recovery_out,
        width=400,
        height=400,
        high_quality=False,
        configdir=configdir,
    )
    if not recovery_result.success:
        pytest.fail(f"recovery render failed: {recovery_result.error_message}")

    base_clipped = _clipped_pixel_count(base_out)
    recovery_clipped = _clipped_pixel_count(recovery_out)

    if base_clipped == 0:
        pytest.fail(
            f"baseline render has 0 clipped pixels in the band — fixture "
            f"may not have rendered with the expected clipped region "
            f"({base_out})"
        )

    reduction_pct = (base_clipped - recovery_clipped) / base_clipped * 100
    if reduction_pct < min_reduction_pct:
        pytest.fail(
            f"highlights_clip_threshold at {clip_threshold} reduced clipped "
            f"pixels by only {reduction_pct:.2f}% (baseline {base_clipped} -> "
            f"recovery {recovery_clipped}); expected >= {min_reduction_pct}% "
            f"reduction. The clipped fixture is sRGB display-referred so "
            f"recovery is limited, but a reduction below the floor suggests "
            f"the module isn't engaging at this value."
        )
