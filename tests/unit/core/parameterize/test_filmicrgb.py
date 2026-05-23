"""Round-trip and patching tests for the filmicrgb Path C decoder.

Closes #97. Filmic v6 ships parallel to sigmoid as the modern darktable
tone-mapping module. The 116-byte struct has 18 floats + 11 4-byte
int-shaped fields (enums/gbool/int). 8 magnitude axes parameterized;
mode/enum fields preserved verbatim.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest

from chemigram.core.parameterize.filmicrgb import (
    _AXIS_FIELD_INDICES,
    _AXIS_OFFSETS,
    _STRUCT_FORMAT,
    _STRUCT_SIZE,
    SUPPORTED_MODVERSION,
    decode,
    encode,
    patch,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SHIPPED_DTSTYLE = (
    _REPO_ROOT / "vocabulary/packs/expressive-baseline/layers/L3/filmicrgb/filmic.dtstyle"
)


def _read_op_params(dtstyle_path: Path) -> str:
    text = dtstyle_path.read_text()
    m = re.search(r"<op_params>(.+?)</op_params>", text, re.DOTALL)
    assert m, f"no op_params in {dtstyle_path}"
    return m.group(1).strip()


def test_supported_modversion_is_six() -> None:
    assert SUPPORTED_MODVERSION == 6


def test_struct_format_matches_size() -> None:
    assert struct.calcsize(_STRUCT_FORMAT) == _STRUCT_SIZE
    assert _STRUCT_SIZE == 116


def test_axis_count_is_8() -> None:
    """8 magnitude axes parameterized; 21 other fields preserved."""
    assert len(_AXIS_FIELD_INDICES) == 8


def test_axis_offsets_match_field_indices() -> None:
    for name, idx in _AXIS_FIELD_INDICES.items():
        assert _AXIS_OFFSETS[name] == idx * 4


def test_round_trip_on_shipped_dtstyle() -> None:
    op_params = _read_op_params(_SHIPPED_DTSTYLE)
    assert encode(decode(op_params)) == op_params


def test_decode_extracts_darktable_defaults() -> None:
    """Shipped filmic.dtstyle uses darktable's documented v6 defaults."""
    fields = decode(_read_op_params(_SHIPPED_DTSTYLE))
    assert fields[0] == pytest.approx(18.45, abs=1e-3)  # grey_point_source
    assert fields[1] == pytest.approx(-8.0, abs=1e-5)  # black_point_source
    assert fields[2] == pytest.approx(4.0, abs=1e-5)  # white_point_source
    assert fields[12] == pytest.approx(4.0, abs=1e-5)  # output_power
    assert fields[14] == pytest.approx(1.0, abs=1e-5)  # contrast
    assert fields[15] == pytest.approx(0.0, abs=1e-5)  # saturation
    # Enum/gboolean/int defaults
    assert fields[18] == 3  # preserve_color = POWER_NORM
    assert fields[19] == 4  # version = COLORSCIENCE_V5
    assert fields[20] == 1  # auto_hardness TRUE
    assert fields[21] == 0  # custom_grey FALSE
    assert fields[27] == 2  # spline_version = V3


@pytest.mark.parametrize("axis", list(_AXIS_FIELD_INDICES.keys()))
def test_patch_sets_one_axis_only(axis: str) -> None:
    """Patching one axis preserves the other 28 fields."""
    src = _read_op_params(_SHIPPED_DTSTYLE)
    src_fields = decode(src)
    test_value = 2.5 if axis == "output_power" else 0.5
    out = patch(src, **{axis: test_value})
    fields = decode(out)
    target_idx = _AXIS_FIELD_INDICES[axis]
    assert fields[target_idx] == pytest.approx(test_value, abs=1e-5)
    for i in range(len(src_fields)):
        if i == target_idx:
            continue
        assert fields[i] == src_fields[i], f"field {i} changed unexpectedly"


def test_patch_all_8_axes_simultaneously() -> None:
    src = _read_op_params(_SHIPPED_DTSTYLE)
    values = {
        "grey_point_source": 20.0,
        "black_point_source": -7.0,
        "white_point_source": 5.0,
        "output_power": 2.5,
        "latitude": 25.0,
        "contrast": 1.5,
        "saturation": 10.0,
        "balance": -10.0,
    }
    out = patch(src, **values)
    fields = decode(out)
    for axis, expected in values.items():
        assert fields[_AXIS_FIELD_INDICES[axis]] == pytest.approx(expected, abs=1e-5)


def test_patch_with_no_args_is_identity() -> None:
    src = _read_op_params(_SHIPPED_DTSTYLE)
    assert patch(src) == src


def test_patch_preserves_mode_enums_and_gbools() -> None:
    """The 11 mode/enum/gboolean fields (indices 18..28) must survive every patch."""
    src = _read_op_params(_SHIPPED_DTSTYLE)
    src_fields = decode(src)
    out = patch(src, contrast=1.5, saturation=20.0, output_power=2.0)
    fields = decode(out)
    for mode_idx in range(18, 29):
        assert fields[mode_idx] == src_fields[mode_idx], (
            f"mode/enum field {mode_idx} should be preserved"
        )


def test_patch_preserves_reconstruction_floats() -> None:
    """reconstruct_threshold/feather/bloom_vs_details/grey_vs_color/structure_vs_texture
    (indices 3..7) preserved across patches."""
    src = _read_op_params(_SHIPPED_DTSTYLE)
    src_fields = decode(src)
    out = patch(src, grey_point_source=20.0, contrast=2.0)
    fields = decode(out)
    for idx in range(3, 8):
        assert fields[idx] == src_fields[idx]


def test_patch_unknown_kwarg_raises() -> None:
    src = _read_op_params(_SHIPPED_DTSTYLE)
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        patch(src, contras=1.5)  # typo
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        patch(src, contrast=1.5, preserve_color=2)  # mode field, not axis


def test_decode_rejects_short_blob() -> None:
    with pytest.raises(ValueError, match="expected 116 bytes"):
        decode("00" * 8)


def test_decode_rejects_wrong_size_blob() -> None:
    with pytest.raises(ValueError, match="modversion"):
        decode("00" * 100)


# Camera-aware auto-tune (#135 / RFC-039)


def test_patch_with_raw_path_substitutes_auto_points(tmp_path: Path) -> None:
    """When raw_path is supplied and no explicit black/white point
    overrides, the patch reads the raw's histogram and substitutes
    black_point_source / white_point_source. Other axes are preserved.
    Mocked exif reader keeps the test fast and deterministic."""
    import struct as _struct
    from unittest.mock import patch as mock_patch

    # Build a baseline op_params with defaults
    fields = [0.0] * 18 + [0] * 11
    fields[0] = 18.45  # grey_point_source
    fields[1] = -8.0  # black_point_source (default)
    fields[2] = 4.0  # white_point_source (default)
    fields[12] = 4.0  # output_power
    fields[14] = 1.0  # contrast
    src = _struct.pack("<18f11i", *fields).hex()

    raw_path = tmp_path / "fake.arw"
    raw_path.write_bytes(b"x")

    with mock_patch(
        "chemigram.core.exif.read_filmic_auto_points",
        return_value=(-5.21, 1.62),
    ):
        out = patch(src, raw_path=raw_path)

    out_fields = decode(out)
    # black and white points are now the auto-tuned values
    assert out_fields[1] == pytest.approx(-5.21, abs=0.01)
    assert out_fields[2] == pytest.approx(1.62, abs=0.01)
    # Other axes preserved
    assert out_fields[0] == pytest.approx(18.45, abs=0.01)
    assert out_fields[12] == pytest.approx(4.0, abs=0.01)


def test_patch_with_explicit_points_skips_auto_tune(tmp_path: Path) -> None:
    """Explicit black/white_point_source overrides bypass auto-tune
    (photographer opting into scene-specific tone points)."""
    import struct as _struct
    from unittest.mock import patch as mock_patch

    fields = [0.0] * 18 + [0] * 11
    fields[1] = -8.0
    fields[2] = 4.0
    src = _struct.pack("<18f11i", *fields).hex()

    raw_path = tmp_path / "fake.arw"
    raw_path.write_bytes(b"x")

    with mock_patch(
        "chemigram.core.exif.read_filmic_auto_points",
        return_value=(-5.21, 1.62),
    ):
        out = patch(src, raw_path=raw_path, black_point_source=-10.0, white_point_source=5.0)

    out_fields = decode(out)
    # Explicit overrides win
    assert out_fields[1] == pytest.approx(-10.0, abs=0.01)
    assert out_fields[2] == pytest.approx(5.0, abs=0.01)


def test_patch_with_unreadable_raw_falls_back(tmp_path: Path) -> None:
    """If rawpy can't read the raw, auto-tune silently skips and
    source values are preserved."""
    import struct as _struct

    fields = [0.0] * 18 + [0] * 11
    fields[1] = -8.0
    fields[2] = 4.0
    src = _struct.pack("<18f11i", *fields).hex()

    bad_raw = tmp_path / "junk.arw"
    bad_raw.write_bytes(b"not a raw file")
    out = patch(src, raw_path=bad_raw)
    out_fields = decode(out)
    assert out_fields[1] == pytest.approx(-8.0, abs=0.01)
    assert out_fields[2] == pytest.approx(4.0, abs=0.01)


def test_patch_with_landscape_fixture_real_histogram() -> None:
    """End-to-end test against the bundled landscape ARW (skipped if
    fixture absent). Real rawpy call; expected values from the raw's
    actual histogram percentiles."""
    raw_path = Path(__file__).resolve().parents[4] / "tests/fixtures/raws/landscape.ARW"
    if not raw_path.exists():
        pytest.skip("landscape fixture not available (git lfs pull?)")
    import struct as _struct

    fields = [0.0] * 18 + [0] * 11
    fields[1] = -8.0  # source default
    fields[2] = 4.0  # source default
    src = _struct.pack("<18f11i", *fields).hex()

    out = patch(src, raw_path=raw_path)
    out_fields = decode(out)
    # Sony landscape: black_ev ~-5 to -6, white_ev ~+1 to +2
    assert -7.0 < out_fields[1] < -4.0
    assert 0.5 < out_fields[2] < 3.0
