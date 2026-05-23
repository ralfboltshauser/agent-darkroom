"""Round-trip and patching tests for the denoiseprofile Path C decoder.

Closes #96. denoiseprofile mv12 is a 416-byte struct: 8 magnitude floats
+ a[3]/b[3] noise calibration (6 floats) + mode enum + x[6][7]/y[6][7]
wavelet curves (84 floats) + 5 mode flags. 4 magnitude axes parameterized;
the calibration arrays, mode, wavelet curves, and flags are preserved
verbatim through patch().
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest

from chemigram.core.parameterize.denoiseprofile import (
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
    _REPO_ROOT / "vocabulary/packs/expressive-baseline/layers/L3/denoiseprofile/denoise.dtstyle"
)


def _read_op_params(dtstyle_path: Path) -> str:
    text = dtstyle_path.read_text()
    m = re.search(r"<op_params>(.+?)</op_params>", text, re.DOTALL)
    assert m, f"no op_params in {dtstyle_path}"
    return m.group(1).strip()


def test_supported_modversion_is_twelve() -> None:
    assert SUPPORTED_MODVERSION == 12


def test_struct_format_matches_size() -> None:
    assert struct.calcsize(_STRUCT_FORMAT) == _STRUCT_SIZE
    assert _STRUCT_SIZE == 416


def test_axis_count_is_4() -> None:
    """4 magnitude axes; the rest of the 416-byte struct is preserved."""
    assert len(_AXIS_FIELD_INDICES) == 4


def test_axis_offsets_match_field_indices() -> None:
    for name, idx in _AXIS_FIELD_INDICES.items():
        assert _AXIS_OFFSETS[name] == idx * 4


def test_axes_use_denoise_prefix() -> None:
    """All axis names carry the denoise_ prefix to disambiguate from
    same-named axes on other modules (notably dehaze.strength)."""
    for name in _AXIS_FIELD_INDICES:
        assert name.startswith("denoise_"), f"{name!r} should start with 'denoise_'"


def test_round_trip_on_shipped_dtstyle() -> None:
    op_params = _read_op_params(_SHIPPED_DTSTYLE)
    assert encode(decode(op_params)) == op_params


def test_decode_extracts_darktable_defaults() -> None:
    """Shipped denoise.dtstyle uses darktable's documented v12 defaults."""
    fields = decode(_read_op_params(_SHIPPED_DTSTYLE))
    # 8 magnitude floats
    assert fields[0] == pytest.approx(1.0, abs=1e-5)  # radius
    assert fields[1] == pytest.approx(7.0, abs=1e-5)  # nbhood
    assert fields[2] == pytest.approx(1.0, abs=1e-5)  # strength
    assert fields[3] == pytest.approx(1.0, abs=1e-5)  # shadows
    assert fields[5] == pytest.approx(0.0, abs=1e-5)  # scattering
    # Calibration zeros (auto-populated at apply time when known)
    for i in range(8, 14):
        assert fields[i] == pytest.approx(0.0, abs=1e-5)
    # Mode = NLMEANS (0) — see decoder docstring "Mode choice — NLMEANS (not WAVELETS)".
    # WAVELETS mode would need an empirically-captured wavelet-curve baseline.
    assert fields[14] == 0
    # Mode flags TRUE
    for i in range(99, 102):
        assert fields[i] == 1


@pytest.mark.parametrize("axis", list(_AXIS_FIELD_INDICES.keys()))
def test_patch_sets_one_axis_only(axis: str) -> None:
    """Patching one axis preserves the other 103 fields."""
    src = _read_op_params(_SHIPPED_DTSTYLE)
    src_fields = decode(src)
    test_value = 2.5
    out = patch(src, **{axis: test_value})
    fields = decode(out)
    target_idx = _AXIS_FIELD_INDICES[axis]
    assert fields[target_idx] == pytest.approx(test_value, abs=1e-5)
    for i in range(len(src_fields)):
        if i == target_idx:
            continue
        assert fields[i] == src_fields[i], f"field {i} changed unexpectedly"


def test_patch_all_4_axes_simultaneously() -> None:
    src = _read_op_params(_SHIPPED_DTSTYLE)
    values = {
        "denoise_strength": 5.0,
        "denoise_shadows": 1.4,
        "denoise_radius": 2.0,
        "denoise_scattering": 1.5,
    }
    out = patch(src, **values)
    fields = decode(out)
    for axis, expected in values.items():
        assert fields[_AXIS_FIELD_INDICES[axis]] == pytest.approx(expected, abs=1e-5)


def test_patch_with_no_args_is_identity() -> None:
    src = _read_op_params(_SHIPPED_DTSTYLE)
    assert patch(src) == src


def test_patch_preserves_calibration_and_mode() -> None:
    """a[3]/b[3] noise calibration (indices 8..13), mode (14), and the
    5 trailing mode flags (indices 99..103) must survive every patch."""
    src = _read_op_params(_SHIPPED_DTSTYLE)
    src_fields = decode(src)
    out = patch(src, denoise_strength=10.0, denoise_shadows=1.5)
    fields = decode(out)
    # Calibration arrays preserved
    for i in range(8, 14):
        assert fields[i] == src_fields[i]
    # Mode preserved
    assert fields[14] == src_fields[14]
    # Mode flags preserved
    for i in range(99, 104):
        assert fields[i] == src_fields[i]


def test_patch_preserves_wavelet_curves() -> None:
    """The x[6][7] (indices 15..56) and y[6][7] (indices 57..98) wavelet
    curves must survive every patch — the parameterized strength axes
    don't touch the curves; this is the load-bearing invariant for the
    constructed-baseline ship (#96 closing notes)."""
    src = _read_op_params(_SHIPPED_DTSTYLE)
    src_fields = decode(src)
    out = patch(src, denoise_strength=20.0, denoise_radius=5.0)
    fields = decode(out)
    for i in range(15, 99):  # x[][] + y[][]
        assert fields[i] == src_fields[i], f"curve field {i} should be preserved"


def test_patch_unknown_kwarg_raises() -> None:
    src = _read_op_params(_SHIPPED_DTSTYLE)
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        patch(src, strength=2.0)  # missing the denoise_ prefix
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        patch(src, denoise_strength=2.0, mode=0)  # mode is not parameterized


def test_decode_rejects_short_blob() -> None:
    with pytest.raises(ValueError, match="expected 416 bytes"):
        decode("00" * 8)


def test_decode_rejects_wrong_size_blob() -> None:
    with pytest.raises(ValueError, match="modversion"):
        decode("00" * 200)


# Camera-aware ISO scaling (#134 / RFC-039)


def test_patch_with_raw_path_scales_strength_above_reference_iso(tmp_path: Path) -> None:
    """At ISO above the reference threshold, the patch auto-scales
    denoise_strength upward (log2 scaling). Construct a fake EXIF
    via a mocked exifread reader since the bundled fixtures are
    ISO 100 (below reference)."""
    import struct as _struct
    from unittest.mock import patch as mock_patch

    # Build a baseline op_params with strength=1.0 (the default).
    # 8 mag floats + 6 calib floats + 1 mode int + 84 curve floats + 5 ints
    fields = [0.0] * 8 + [0.0] * 6 + [0] + [0.0] * 84 + [0] * 5
    fields[2] = 1.0  # denoise_strength index per _AXIS_FIELD_INDICES
    src = _struct.pack("<8f6fi42f42f3iii", *fields).hex()

    raw_path = tmp_path / "fake.arw"
    raw_path.write_bytes(b"not actually a raw")

    # Mock read_camera_iso to return ISO 800 (3 stops above reference 200).
    # Expected scaling: log2(800/200) = 2, so 2**2 = 4x.
    with mock_patch("chemigram.core.exif.read_camera_iso", return_value=800):
        out = patch(src, raw_path=raw_path)

    out_fields = decode(out)
    assert out_fields[2] == pytest.approx(4.0, abs=0.01)


def test_patch_with_raw_path_below_reference_iso_is_noop(tmp_path: Path) -> None:
    """ISO below the reference threshold (clean capture) → strength
    passes through unchanged. The auto-scaling only fires for ISO
    above the reference."""
    import struct as _struct
    from unittest.mock import patch as mock_patch

    fields = [0.0] * 8 + [0.0] * 6 + [0] + [0.0] * 84 + [0] * 5
    fields[2] = 1.0
    src = _struct.pack("<8f6fi42f42f3iii", *fields).hex()

    raw_path = tmp_path / "fake.arw"
    raw_path.write_bytes(b"x")

    with mock_patch("chemigram.core.exif.read_camera_iso", return_value=100):
        out = patch(src, raw_path=raw_path)

    out_fields = decode(out)
    assert out_fields[2] == pytest.approx(1.0, abs=0.001)


def test_patch_with_raw_path_explicit_strength_wins(tmp_path: Path) -> None:
    """When an explicit denoise_strength is supplied, it wins over the
    ISO-derived auto-scaling."""
    import struct as _struct
    from unittest.mock import patch as mock_patch

    fields = [0.0] * 8 + [0.0] * 6 + [0] + [0.0] * 84 + [0] * 5
    fields[2] = 1.0
    src = _struct.pack("<8f6fi42f42f3iii", *fields).hex()

    raw_path = tmp_path / "fake.arw"
    raw_path.write_bytes(b"x")

    with mock_patch("chemigram.core.exif.read_camera_iso", return_value=6400):
        out = patch(src, raw_path=raw_path, denoise_strength=2.5)

    out_fields = decode(out)
    # Explicit value 2.5 wins, NOT the ISO-scaled value
    assert out_fields[2] == pytest.approx(2.5, abs=0.001)


def test_patch_with_unreadable_raw_falls_back_to_source(tmp_path: Path) -> None:
    """If EXIF can't be read, the auto-scaling silently skips and the
    source strength is preserved."""
    import struct as _struct

    fields = [0.0] * 8 + [0.0] * 6 + [0] + [0.0] * 84 + [0] * 5
    fields[2] = 1.0
    src = _struct.pack("<8f6fi42f42f3iii", *fields).hex()

    bad_raw = tmp_path / "junk.arw"
    bad_raw.write_bytes(b"not a raw file")
    out = patch(src, raw_path=bad_raw)
    out_fields = decode(out)
    assert out_fields[2] == pytest.approx(1.0, abs=0.001)
