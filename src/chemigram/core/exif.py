"""Read camera/lens metadata from raw files for L1 vocabulary binding
+ camera-default WB coefficients for camera-aware parametric apply.

Two readers:

- :func:`read_exif` (``exifread``) — extracts ``Make``, ``Model``,
  ``LensModel``, ``FocalLength``. Per RFC-015 / ADR-053, downstream
  binding (:mod:`chemigram.core.binding`) is exact-match on
  ``(make, model, lens_model)``.
- :func:`read_camera_daylight_wb` (``rawpy``) — extracts the raw's
  camera-default daylight WB coefficients as RGB multipliers. Used by
  RFC-039 to make parametric temperature camera-aware: at
  ``kelvin_delta=0`` the parametric primitive emits these coefficients
  (preserves camera default); at non-zero delta it shifts relative to
  this base.

Both libraries are pure-Python or wheel-distributed (no exiftool
binary required). PyExifTool (faster, more complete) is rejected for
v1 because it requires the ``exiftool`` binary as an external dep.

Public API:
    - :func:`read_exif` — extract EXIF identity fields from a raw
    - :func:`read_camera_daylight_wb` — read camera daylight WB coefficients
    - :class:`ExifData` — frozen dataclass with the four identity fields
    - :class:`ExifReadError` — raised on unreadable input
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import exifread


class ExifReadError(Exception):
    """Raised when EXIF cannot be read from a file."""


@dataclass(frozen=True)
class ExifData:
    """The EXIF fields chemigram cares about for L1 binding.

    String fields are whitespace- and null-stripped. Missing string
    fields become empty strings (not ``None``) so callers don't need
    to special-case absence vs. presence-of-empty.
    """

    make: str
    model: str
    lens_model: str
    focal_length_mm: float | None


def _stringify_tag(tag: Any) -> str:
    """Coerce an exifread IfdTag (or absent value) into a clean string.

    EXIF strings often have trailing ``\\x00`` from C-string encoding
    plus whitespace on either side; strip both in one pass.
    """
    if tag is None:
        return ""
    return str(tag).strip("\x00 \t\r\n\v\f")


def _focal_length_mm(tag: Any) -> float | None:
    """Parse an EXIF FocalLength tag into millimetres.

    exifread returns FocalLength as ``IfdTag`` whose ``.values`` is a
    list of ``Ratio`` objects (numerator/denominator). We take the
    first ratio and coerce to float.
    """
    if tag is None:
        return None
    try:
        values = tag.values
        first = values[0] if isinstance(values, list) else values
        return float(first)
    except (TypeError, ValueError, IndexError, AttributeError):
        return None


def read_exif(path: Path) -> ExifData:
    """Read relevant EXIF tags from a raw file.

    Args:
        path: path to a raw (NEF, ARW, RAF, CR2, ...).

    Returns:
        :class:`ExifData` with whitespace-stripped strings; missing
        string fields become ``""``; missing ``focal_length_mm``
        becomes ``None``.

    Raises:
        ExifReadError: corrupt or unreadable file.
        FileNotFoundError: ``path`` does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(path)

    try:
        with path.open("rb") as fh:
            tags = exifread.process_file(fh, details=False)
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
        # exifread doesn't expose a single error type; these cover the
        # families we've observed (corrupt files, malformed IFD pointers,
        # truncated streams). Letting other exceptions propagate is
        # intentional — they signal genuine bugs, not bad input.
        raise ExifReadError(f"failed to read EXIF from {path}: {exc}") from exc

    make = _stringify_tag(tags.get("Image Make"))
    model = _stringify_tag(tags.get("Image Model"))
    lens_model = _stringify_tag(tags.get("EXIF LensModel")) or _stringify_tag(
        tags.get("MakerNote LensModel")
    )
    focal_length = _focal_length_mm(tags.get("EXIF FocalLength"))

    return ExifData(
        make=make,
        model=model,
        lens_model=lens_model,
        focal_length_mm=focal_length,
    )


def read_camera_daylight_wb(path: Path) -> tuple[float, float, float]:
    """Read the camera-default daylight WB coefficients from a raw file.

    Returns ``(red_coeff, green_coeff, blue_coeff)`` as float multipliers
    matching darktable's ``temperature`` module struct layout, normalized
    to ``green_coeff == 1.0``. This is the form darktable uses internally
    when it auto-inserts a temperature op for a raw with no explicit
    history.

    The values come from libraw's ``camera_whitebalance`` field (the
    raw's as-shot WB metadata, divided by the green coefficient to
    normalize). Using camera_whitebalance (rather than
    daylight_whitebalance) matches darktable's behavior: darktable reads
    the as-shot multipliers from EXIF / MakerNote and applies them at
    raw-prepare time, before the chromatic-adaptation channelmixerrgb
    step. Using daylight_whitebalance instead would interact differently
    with the chromatic-adaptation chain and produce a visible cast.

    Used by camera-aware parametric apply (RFC-039 / #131 Step 2): at
    ``kelvin_delta=0`` the parametric temperature primitive emits these
    coefficients (preserves camera default); at non-zero delta the
    primitive shifts relative to this base.

    Raises:
        FileNotFoundError: ``path`` does not exist.
        ExifReadError: rawpy can't parse the raw (corrupt / unsupported
            format / DNG without WB).
    """
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        import rawpy

        with rawpy.imread(str(path)) as raw:
            wb = raw.camera_whitebalance
            # rawpy returns 4 floats (R, G, B, G2) in libraw's internal
            # scale. Normalize to G=1 — that's the canonical scale
            # darktable's temperature module expects.
            r, g, b = float(wb[0]), float(wb[1]), float(wb[2])
            if g == 0.0:
                # G=0 is a malformed reading; fall back to daylight
                wb = raw.daylight_whitebalance
                r, g, b = float(wb[0]), float(wb[1]), float(wb[2])
                if g == 0.0:
                    raise ExifReadError(
                        f"camera WB has G=0; both camera_whitebalance and "
                        f"daylight_whitebalance are unusable for {path}"
                    )
            return (r / g, 1.0, b / g)
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise ExifReadError(f"failed to read camera daylight WB from {path}: {exc}") from exc
