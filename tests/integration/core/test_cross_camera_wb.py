"""Cross-body integration test for the RFC-039 raw-aware apply path (#142).

The RFC-039 mechanism reads the raw's EXIF WB coefficients at apply time
and uses them as the substitution base for the parametric temperature
primitive. The architectural claim is "directionally-correct on any
camera body" — not just on the Sony fixtures the rest of the suite uses.

This test verifies the claim across 3 manufacturers:

- Sony DSC-RX10M4 (the primary ``landscape.ARW`` fixture)
- Canon EOS R6 (``cross_camera_canon.CR3``)
- Nikon D70 (``cross_camera_nikon.NEF``)

For each fixture we (a) probe the camera's daylight WB via the chemigram
EXIF reader, (b) apply the parametric ``temperature`` primitive with
``kelvin_delta=+1500`` (warm shift), and (c) assert that the resulting
op_params reflect the camera's WB scaled by ~+15% on R and ~-15% on B.

The three bodies have meaningfully different daylight coefficients:

- Sony:   (2.391, 1.0, 1.711)
- Canon:  (1.810, 1.0, 1.628)
- Nikon:  (2.168, 1.0, 1.516)

Identical patch inputs → three distinct op_params. That's the
cross-camera portability property in one assertion.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemigram.core.exif import read_camera_daylight_wb
from chemigram.core.parameterize.temperature import (
    _BLUE_FIELD_INDEX,
    _RED_FIELD_INDEX,
    decode,
    patch,
)
from tests._lfs import skip_if_lfs_pointer

_REPO = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO / "tests" / "fixtures" / "raws"

# (body_label, fixture_filename, expected_daylight_wb_approx).
# Expected values come from a one-time rawpy probe; the test asserts they
# remain stable (catches a libraw / rawpy upgrade that changes EXIF
# interpretation).
_BODIES: tuple[tuple[str, str, tuple[float, float, float]], ...] = (
    ("sony_rx10m4", "landscape.ARW", (2.391, 1.000, 1.711)),
    ("canon_eos_r6", "cross_camera_canon.CR3", (1.810, 1.000, 1.628)),
    ("nikon_d70", "cross_camera_nikon.NEF", (2.168, 1.000, 1.516)),
)

# Identity (1.0, 1.0, 1.0) op_params — source coefficients are ignored
# when raw_path is supplied; the camera's WB substitutes in.
_IDENTITY_OP_PARAMS = "0000803f0000803f0000803f0000807f02000000"

# +1500K shift target: roughly +15% on R, -15% on B, relative to the
# camera's daylight. The temperature module's parametric apply uses a
# linear kelvin → coefficient approximation; the 1.15 / 0.85 factors
# match the production code in src/chemigram/core/parameterize/temperature.py.
_KELVIN_DELTA = 1500.0
_R_FACTOR = 1.15
_B_FACTOR = 0.85


def _require_fixture(name: str) -> Path:
    path = _FIXTURES / name
    if not path.exists():
        pytest.skip(f"fixture {name} not available (git lfs pull?)")
    skip_if_lfs_pointer(path)
    return path


@pytest.mark.parametrize("body_label, fixture, expected_wb", _BODIES, ids=[b[0] for b in _BODIES])
def test_daylight_wb_probe_per_body(
    body_label: str, fixture: str, expected_wb: tuple[float, float, float]
) -> None:
    """The EXIF reader returns a plausible, body-specific daylight WB
    triplet. Catches a regression in :func:`read_camera_daylight_wb` or
    a libraw upgrade that changes coefficient interpretation."""
    path = _require_fixture(fixture)
    r, g, b = read_camera_daylight_wb(path)
    assert r == pytest.approx(expected_wb[0], abs=0.05), body_label
    assert g == pytest.approx(expected_wb[1], abs=0.05), body_label
    assert b == pytest.approx(expected_wb[2], abs=0.05), body_label


@pytest.mark.parametrize("body_label, fixture, expected_wb", _BODIES, ids=[b[0] for b in _BODIES])
def test_warm_shift_anchors_on_camera_wb_per_body(
    body_label: str, fixture: str, expected_wb: tuple[float, float, float]
) -> None:
    """+1500K applied via ``patch(raw_path=...)`` produces a warm shift
    anchored on the CAMERA'S WB, not on the source coefficients. The
    output's R coefficient ≈ camera_R * 1.15; B ≈ camera_B * 0.85.

    This is the load-bearing cross-camera assertion of RFC-039 — the
    parametric primitive's behavior on a Canon body is correct relative
    to that body, not Sony-correct masquerading as camera-portable.
    """
    path = _require_fixture(fixture)
    out = patch(_IDENTITY_OP_PARAMS, kelvin_delta=_KELVIN_DELTA, raw_path=path)
    assert out is not None, f"patch returned None at +1500K for {body_label}"
    fields = decode(out)
    assert fields[_RED_FIELD_INDEX] == pytest.approx(expected_wb[0] * _R_FACTOR, abs=0.05), (
        f"R coefficient on {body_label} doesn't anchor to camera WB"
    )
    assert fields[_BLUE_FIELD_INDEX] == pytest.approx(expected_wb[2] * _B_FACTOR, abs=0.05), (
        f"B coefficient on {body_label} doesn't anchor to camera WB"
    )


def test_three_bodies_produce_three_distinct_op_params() -> None:
    """The architectural claim in one shot: the same logical operation
    (warm by +1500K) produces three distinct op_params strings across
    three different camera bodies, because the substitution is
    body-specific. If two bodies produced identical op_params, the
    RFC-039 mechanism would be broken (or two bodies have identical
    daylight WB, which is unlikely)."""
    op_params_by_body: dict[str, str] = {}
    for body_label, fixture, _ in _BODIES:
        path = _require_fixture(fixture)
        out = patch(_IDENTITY_OP_PARAMS, kelvin_delta=_KELVIN_DELTA, raw_path=path)
        assert out is not None
        op_params_by_body[body_label] = out

    distinct = set(op_params_by_body.values())
    assert len(distinct) == len(op_params_by_body), (
        "RFC-039 cross-camera portability broken: at least two bodies "
        f"produced identical op_params from the same +1500K delta. "
        f"op_params per body: {op_params_by_body}"
    )
