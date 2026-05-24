"""Round-trip and patching tests for the lens Path C decoder.

Closes #95 (decoder shipped; EXIF auto-binding tracked separately).
The lens mv10 struct is 356 bytes — the largest in the parameterize
registry — with two embedded 128-byte char arrays (camera, lens) for
lensfun identifier lookup. 10 magnitude axes parameterized; the other
17 fields preserved verbatim.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest

from chemigram.core.parameterize.lens import (
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
    _REPO_ROOT / "vocabulary/packs/expressive-baseline/layers/L3/lens/lens_correction.dtstyle"
)


def _read_op_params(dtstyle_path: Path) -> str:
    text = dtstyle_path.read_text()
    m = re.search(r"<op_params>(.+?)</op_params>", text, re.DOTALL)
    assert m, f"no op_params in {dtstyle_path}"
    return m.group(1).strip()


def test_supported_modversion_is_ten() -> None:
    assert SUPPORTED_MODVERSION == 10


def test_struct_format_matches_size() -> None:
    assert struct.calcsize(_STRUCT_FORMAT) == _STRUCT_SIZE
    assert _STRUCT_SIZE == 356


def test_axis_count_is_10() -> None:
    assert len(_AXIS_FIELD_INDICES) == 10


def test_axes_use_lens_prefix() -> None:
    """All axis names carry the lens_ prefix for disambiguation."""
    for name in _AXIS_FIELD_INDICES:
        assert name.startswith("lens_"), f"{name!r} should start with 'lens_'"


def test_round_trip_on_shipped_dtstyle() -> None:
    op_params = _read_op_params(_SHIPPED_DTSTYLE)
    assert encode(decode(op_params)) == op_params


def test_decode_extracts_baseline_state() -> None:
    """Shipped lens_correction.dtstyle has darktable defaults: LENSFUN
    method (1), modify_flags=ALL (7), inverse=CORRECT (0), tca_r/tca_b=1.0
    (no manual TCA), v_radius/v_steepness=1.0, everything else 0."""
    fields = decode(_read_op_params(_SHIPPED_DTSTYLE))
    assert fields[0] == 1  # method = LENSFUN
    assert fields[1] == 7  # modify_flags = ALL
    assert fields[2] == 0  # inverse = CORRECT
    # Camera/lens are empty bytes (null-padded 128 bytes)
    assert fields[9] == b"\x00" * 128
    assert fields[10] == b"\x00" * 128
    # Manual TCA defaults to 1.0 (no shift)
    assert fields[12] == pytest.approx(1.0, abs=1e-5)
    assert fields[13] == pytest.approx(1.0, abs=1e-5)
    # Manual vignette: strength=0 (off), radius/steepness=1.0
    assert fields[22] == pytest.approx(0.0, abs=1e-5)
    assert fields[23] == pytest.approx(1.0, abs=1e-5)
    assert fields[24] == pytest.approx(1.0, abs=1e-5)


@pytest.mark.parametrize("axis", list(_AXIS_FIELD_INDICES.keys()))
def test_patch_sets_one_axis_only(axis: str) -> None:
    """Patching one axis preserves the other 26 fields."""
    src = _read_op_params(_SHIPPED_DTSTYLE)
    src_fields = decode(src)
    test_value = 0.5
    out = patch(src, **{axis: test_value})
    fields = decode(out)
    target_idx = _AXIS_FIELD_INDICES[axis]
    assert fields[target_idx] == pytest.approx(test_value, abs=1e-5)
    for i in range(len(src_fields)):
        if i == target_idx:
            continue
        assert fields[i] == src_fields[i], f"field {i} changed unexpectedly"


def test_patch_all_10_axes_simultaneously() -> None:
    src = _read_op_params(_SHIPPED_DTSTYLE)
    values = {
        "lens_scale": 1.0,
        "lens_tca_r": 1.005,
        "lens_tca_b": 0.995,
        "lens_cor_distortion": 0.8,
        "lens_cor_vignette": 0.6,
        "lens_cor_ca_r": 0.3,
        "lens_cor_ca_b": -0.3,
        "lens_v_strength": 0.4,
        "lens_v_radius": 1.5,
        "lens_v_steepness": 2.0,
    }
    out = patch(src, **values)
    fields = decode(out)
    for axis, expected in values.items():
        assert fields[_AXIS_FIELD_INDICES[axis]] == pytest.approx(expected, abs=1e-5)


def test_patch_with_no_args_is_identity() -> None:
    src = _read_op_params(_SHIPPED_DTSTYLE)
    assert patch(src) == src


def test_patch_preserves_method_enum_and_camera_lens_strings() -> None:
    """method, modify_flags, inverse, target_geom enums + camera/lens
    char arrays + tca_override/has_been_set gbools must survive every patch."""
    src = _read_op_params(_SHIPPED_DTSTYLE)
    src_fields = decode(src)
    out = patch(src, lens_scale=1.5, lens_v_strength=0.4, lens_cor_distortion=0.7)
    fields = decode(out)
    assert fields[0] == src_fields[0]  # method
    assert fields[1] == src_fields[1]  # modify_flags
    assert fields[2] == src_fields[2]  # inverse
    assert fields[8] == src_fields[8]  # target_geom
    assert fields[9] == src_fields[9]  # camera bytes
    assert fields[10] == src_fields[10]  # lens bytes
    assert fields[11] == src_fields[11]  # tca_override
    assert fields[19] == src_fields[19]  # md_version
    assert fields[21] == src_fields[21]  # has_been_set


def test_patch_preserves_exif_floats() -> None:
    """crop, focal, aperture, distance (would be EXIF-bound at apply time)
    are preserved verbatim across patches — the parameterized strength
    axes don't touch them."""
    src = _read_op_params(_SHIPPED_DTSTYLE)
    src_fields = decode(src)
    out = patch(src, lens_tca_r=1.005, lens_tca_b=0.995)
    fields = decode(out)
    for idx in [4, 5, 6, 7]:  # crop, focal, aperture, distance
        assert fields[idx] == src_fields[idx]


def test_patch_unknown_kwarg_raises() -> None:
    src = _read_op_params(_SHIPPED_DTSTYLE)
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        patch(src, scale=1.5)  # missing lens_ prefix
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        patch(src, lens_scale=1.5, focal=50.0)  # focal is preserved, not parameterized


def test_decode_rejects_short_blob() -> None:
    with pytest.raises(ValueError, match="expected 356 bytes"):
        decode("00" * 8)


def test_decode_rejects_wrong_size_blob() -> None:
    with pytest.raises(ValueError, match="modversion"):
        decode("00" * 200)


def test_axis_offsets_dict_matches_struct_layout() -> None:
    """Cross-check the documented byte offsets against the struct unpack."""
    src = _read_op_params(_SHIPPED_DTSTYLE)
    src_bytes = bytes.fromhex(src)
    # Patch lens_tca_r to 1.007 — bytes 296..299 should change
    out_bytes = bytes.fromhex(patch(src, lens_tca_r=1.007))
    assert (
        src_bytes[_AXIS_OFFSETS["lens_tca_r"] : _AXIS_OFFSETS["lens_tca_r"] + 4]
        != out_bytes[_AXIS_OFFSETS["lens_tca_r"] : _AXIS_OFFSETS["lens_tca_r"] + 4]
    )
    # All other bytes preserved
    for i in range(len(src_bytes)):
        if _AXIS_OFFSETS["lens_tca_r"] <= i < _AXIS_OFFSETS["lens_tca_r"] + 4:
            continue
        assert src_bytes[i] == out_bytes[i], f"byte {i} changed unexpectedly"


# Camera-aware EXIF binding (#136 / RFC-039)


def test_patch_with_raw_path_populates_camera_lens_from_exif() -> None:
    """When raw_path is supplied AND camera bytes are empty in the
    source, patch() reads EXIF and populates camera/lens/focal length
    on the dtstyle's lens op_params. End-to-end test against the
    bundled Sony landscape fixture."""
    raw_path = Path(__file__).resolve().parents[4] / "tests/fixtures/raws/landscape.ARW"
    if not raw_path.exists():
        pytest.skip("landscape fixture not available (git lfs pull?)")

    from tests._lfs import skip_if_lfs_pointer

    skip_if_lfs_pointer(raw_path)
    from chemigram.core.parameterize.lens import (
        _CAMERA_FIELD_INDEX,
        _FOCAL_FIELD_INDEX,
        decode,
    )
    from chemigram.core.vocab import load_packs

    v = load_packs(["starter", "expressive-baseline"])
    entry = v.lookup_by_name("lens_correction")
    assert entry is not None
    src = entry.dtstyle.plugins[0].op_params
    src_fields = decode(src)
    assert src_fields[_CAMERA_FIELD_INDEX].rstrip(b"\x00") == b""
    out = patch(src, raw_path=raw_path)
    fields = decode(out)
    camera = fields[_CAMERA_FIELD_INDEX].rstrip(b"\x00").decode("utf-8")
    assert "SONY" in camera.upper() or "Sony" in camera
    # Landscape fixture's EXIF has focal length present (non-zero)
    assert fields[_FOCAL_FIELD_INDEX] > 0.0


def test_patch_preserves_existing_camera_string(tmp_path: Path) -> None:
    """When the source already has a camera string populated, patch()
    does NOT overwrite it from EXIF. The photographer's existing
    binding wins."""
    import struct as _struct

    from chemigram.core.parameterize.lens import _CAMERA_FIELD_INDEX, _STRUCT_FORMAT, decode

    # Build a source with a pre-populated camera string
    fields: list[int | float | bytes] = [
        0,
        0,
        0,
        1.0,
        0.0,
        50.0,
        2.8,
        1.0,  # 5 floats (scale, crop, focal, aperture, distance)
        0,
        b"Canon EOS R5".ljust(128, b"\x00"),  # camera (pre-populated)
        b"".ljust(128, b"\x00"),  # lens
        0,
        1.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1,
        0.0,
        0,
        0.0,
        1.0,
        1.0,
        0.0,
        0.0,
    ]
    src = _struct.pack(_STRUCT_FORMAT, *fields).hex()

    # Even with a raw_path pointing at a Sony fixture, the pre-bound
    # camera string should win
    raw_path = Path(__file__).resolve().parents[4] / "tests/fixtures/raws/landscape.ARW"
    if not raw_path.exists():
        pytest.skip("landscape fixture not available")

    from tests._lfs import skip_if_lfs_pointer

    skip_if_lfs_pointer(raw_path)
    out = patch(src, raw_path=raw_path)
    out_fields = decode(out)
    assert out_fields[_CAMERA_FIELD_INDEX].rstrip(b"\x00") == b"Canon EOS R5"


def test_patch_unreadable_raw_falls_back(tmp_path: Path) -> None:
    """If EXIF read fails (corrupt file), patch silently preserves
    the source bytes (camera stays empty)."""
    import struct as _struct

    from chemigram.core.parameterize.lens import _CAMERA_FIELD_INDEX, _STRUCT_FORMAT, decode

    fields: list[int | float | bytes] = [
        0,
        0,
        0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0,
        b"".ljust(128, b"\x00"),
        b"".ljust(128, b"\x00"),
        0,
        1.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1,
        0.0,
        0,
        0.0,
        1.0,
        1.0,
        0.0,
        0.0,
    ]
    src = _struct.pack(_STRUCT_FORMAT, *fields).hex()

    bad_raw = tmp_path / "junk.arw"
    bad_raw.write_bytes(b"not a raw file")
    out = patch(src, raw_path=bad_raw)
    out_fields = decode(out)
    assert out_fields[_CAMERA_FIELD_INDEX].rstrip(b"\x00") == b""
