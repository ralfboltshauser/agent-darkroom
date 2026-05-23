"""Unit tests for chemigram.core.exif.read_exif.

Real-NEF integration test lives in tests/integration/core/test_exif_integration.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from chemigram.core.exif import ExifData, ExifReadError, read_exif


class _FakeTag:
    """Stand-in for exifread.IfdTag — str() yields the value."""

    def __init__(self, value: Any) -> None:
        self.values = value

    def __str__(self) -> str:
        return str(self.values)


def _patch_exifread(monkeypatch: pytest.MonkeyPatch, tags: dict[str, Any]) -> None:
    monkeypatch.setattr(
        "chemigram.core.exif.exifread.process_file",
        lambda fh, **_kw: tags,
    )


def test_read_exif_returns_dataclass(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    raw = tmp_path / "fake.nef"
    raw.write_bytes(b"not really a raw")
    _patch_exifread(
        monkeypatch,
        {
            "Image Make": _FakeTag("NIKON CORPORATION"),
            "Image Model": _FakeTag("NIKON D850"),
            "EXIF LensModel": _FakeTag("NIKKOR Z 24-70mm f/2.8 S"),
        },
    )
    result = read_exif(raw)
    assert isinstance(result, ExifData)
    assert result.make == "NIKON CORPORATION"
    assert result.model == "NIKON D850"
    assert result.lens_model == "NIKKOR Z 24-70mm f/2.8 S"


def test_read_exif_missing_lens_returns_empty_string(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw = tmp_path / "fake.nef"
    raw.write_bytes(b"not really a raw")
    _patch_exifread(
        monkeypatch,
        {
            "Image Make": _FakeTag("CANON"),
            "Image Model": _FakeTag("EOS R5"),
            # No LensModel — manual lens
        },
    )
    result = read_exif(raw)
    assert result.lens_model == ""


def test_read_exif_strips_trailing_nulls_and_whitespace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw = tmp_path / "fake.nef"
    raw.write_bytes(b"x")
    _patch_exifread(
        monkeypatch,
        {
            "Image Make": _FakeTag("NIKON CORPORATION  \x00\x00"),
            "Image Model": _FakeTag("\tNIKON D850\n"),
        },
    )
    result = read_exif(raw)
    assert result.make == "NIKON CORPORATION"
    assert result.model == "NIKON D850"


def test_read_exif_falls_back_to_makernote_lens(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw = tmp_path / "fake.nef"
    raw.write_bytes(b"x")
    _patch_exifread(
        monkeypatch,
        {
            "Image Make": _FakeTag("NIKON"),
            "Image Model": _FakeTag("D850"),
            "MakerNote LensModel": _FakeTag("AF-S NIKKOR 24-70mm f/2.8E ED VR"),
        },
    )
    result = read_exif(raw)
    assert result.lens_model == "AF-S NIKKOR 24-70mm f/2.8E ED VR"


def test_read_exif_focal_length_parsed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    raw = tmp_path / "fake.nef"
    raw.write_bytes(b"x")
    _patch_exifread(
        monkeypatch,
        {
            "Image Make": _FakeTag("X"),
            "Image Model": _FakeTag("Y"),
            "EXIF FocalLength": _FakeTag([70.0]),
        },
    )
    result = read_exif(raw)
    assert result.focal_length_mm == 70.0


def test_read_exif_missing_focal_length_is_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw = tmp_path / "fake.nef"
    raw.write_bytes(b"x")
    _patch_exifread(
        monkeypatch,
        {"Image Make": _FakeTag("X"), "Image Model": _FakeTag("Y")},
    )
    result = read_exif(raw)
    assert result.focal_length_mm is None


def test_read_exif_invalid_file_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    raw = tmp_path / "junk.nef"
    raw.write_bytes(b"x")

    def _raises(*_args: Any, **_kw: Any) -> Any:
        raise ValueError("not a recognizable image format")

    monkeypatch.setattr("chemigram.core.exif.exifread.process_file", _raises)
    with pytest.raises(ExifReadError, match="failed to read EXIF"):
        read_exif(raw)


def test_read_exif_file_not_found(tmp_path: Path) -> None:
    nonexistent = tmp_path / "missing.nef"
    with pytest.raises(FileNotFoundError):
        read_exif(nonexistent)


def test_read_camera_daylight_wb_landscape_fixture() -> None:
    """Sanity check the camera-WB reader on the bundled landscape ARW.

    Verifies (a) the function returns a 3-float tuple, (b) values are
    normalized to G=1.0, (c) values are physically plausible for a
    Sony body (R and B both > 1.0, reflecting Bayer green dominance
    that gets compensated).

    Used by RFC-039 / #131 Step 2 camera-aware parametric apply.
    """
    from chemigram.core.exif import read_camera_daylight_wb

    raw_path = Path(__file__).resolve().parents[3] / "tests/fixtures/raws/landscape.ARW"
    if not raw_path.exists():
        pytest.skip("landscape fixture not available (git lfs pull?)")

    r, g, b = read_camera_daylight_wb(raw_path)
    assert g == pytest.approx(1.0, abs=1e-9), "must be normalized to G=1"
    assert 1.5 < r < 3.5, f"R coefficient out of plausible range: {r}"
    assert 1.0 < b < 2.5, f"B coefficient out of plausible range: {b}"


def test_read_camera_daylight_wb_file_not_found(tmp_path: Path) -> None:
    """Missing raw raises FileNotFoundError (no ExifReadError wrapping)."""
    from chemigram.core.exif import read_camera_daylight_wb

    nonexistent = tmp_path / "missing.arw"
    with pytest.raises(FileNotFoundError):
        read_camera_daylight_wb(nonexistent)


def test_read_camera_daylight_wb_invalid_file(tmp_path: Path) -> None:
    """Corrupt file raises ExifReadError."""
    from chemigram.core.exif import read_camera_daylight_wb

    raw = tmp_path / "junk.arw"
    raw.write_bytes(b"not a raw file")
    with pytest.raises(ExifReadError, match="failed to read camera daylight WB"):
        read_camera_daylight_wb(raw)


def test_read_exif_focal_length_malformed_returns_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Malformed FocalLength value should not crash; returns None."""
    raw = tmp_path / "fake.nef"
    raw.write_bytes(b"x")

    class _BrokenTag:
        @property
        def values(self) -> Any:
            raise AttributeError("simulated broken IfdTag")

    _patch_exifread(
        monkeypatch,
        {
            "Image Make": _FakeTag("X"),
            "Image Model": _FakeTag("Y"),
            "EXIF FocalLength": _BrokenTag(),
        },
    )
    result = read_exif(raw)
    assert result.focal_length_mm is None


def test_read_exif_strips_leading_nul_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Leading NUL bytes are an unusual but valid EXIF case."""
    raw = tmp_path / "fake.nef"
    raw.write_bytes(b"x")
    _patch_exifread(
        monkeypatch,
        {
            "Image Make": _FakeTag("\x00\x00NIKON\x00"),
            "Image Model": _FakeTag("D850"),
        },
    )
    result = read_exif(raw)
    assert result.make == "NIKON"


def test_read_camera_iso_landscape_fixture() -> None:
    """ISO reader returns an int for the bundled landscape ARW."""
    from chemigram.core.exif import read_camera_iso

    raw_path = Path(__file__).resolve().parents[3] / "tests/fixtures/raws/landscape.ARW"
    if not raw_path.exists():
        pytest.skip("landscape fixture not available (git lfs pull?)")
    iso = read_camera_iso(raw_path)
    assert isinstance(iso, int) and iso > 0


def test_read_camera_iso_returns_none_for_corrupt_file(tmp_path: Path) -> None:
    """Corrupt file → exifread raises → wrapped in ExifReadError."""
    from chemigram.core.exif import ExifReadError, read_camera_iso

    raw = tmp_path / "junk.arw"
    raw.write_bytes(b"not a raw file")
    # exifread tolerates many malformed inputs, returning empty tags;
    # corrupt input that DOES raise propagates as ExifReadError. Either
    # outcome (None or ExifReadError) is acceptable for this robustness
    # property.
    try:
        result = read_camera_iso(raw)
        assert result is None
    except ExifReadError:
        pass


def test_read_camera_iso_file_not_found(tmp_path: Path) -> None:
    """Missing file raises FileNotFoundError."""
    from chemigram.core.exif import read_camera_iso

    nonexistent = tmp_path / "missing.arw"
    with pytest.raises(FileNotFoundError):
        read_camera_iso(nonexistent)
