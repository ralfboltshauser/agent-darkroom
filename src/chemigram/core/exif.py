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


def read_filmic_auto_points(
    path: Path, *, black_percentile: float = 1.0, white_percentile: float = 99.0
) -> tuple[float, float] | None:
    """Compute filmic-friendly black_point_source / white_point_source
    in log2-EV space from the raw's actual histogram.

    Returns ``(black_ev, white_ev)`` where both values are relative to
    the camera's mid-gray reference (18.45% of white_level). Mirrors
    darktable's "Auto-tune levels" button on the filmic module.

    Used by camera-aware filmic (#135 / RFC-039): at apply time, the
    parametric primitive substitutes these auto-tuned points for the
    dtstyle's authored defaults (typically -8.0 / +4.0), producing a
    tone curve fitted to the actual scene's dynamic range.

    Returns ``None`` if rawpy can't read the file or compute valid
    percentiles (very dark / completely clipped raw). Callers treat
    None as "skip auto-tune, use source coefficients."

    Raises:
        FileNotFoundError: ``path`` does not exist.
        ExifReadError: rawpy can't parse the raw.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        import math

        import numpy as np
        import rawpy

        with rawpy.imread(str(path)) as raw:
            img = raw.raw_image_visible
            black_level = (
                float(raw.black_level_per_channel[0]) if raw.black_level_per_channel else 0.0
            )
            white_level = float(raw.white_level) if raw.white_level else float(img.max())
            grey = (white_level - black_level) * 0.1845 + black_level
            p_black = float(np.percentile(img, black_percentile))
            p_white = float(np.percentile(img, white_percentile))
            # Need positive distances above black_level for log2
            if p_black <= black_level or p_white <= black_level or grey <= black_level:
                return None
            black_ev = math.log2((p_black - black_level) / (grey - black_level))
            white_ev = math.log2((p_white - black_level) / (grey - black_level))
            return black_ev, white_ev
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise ExifReadError(f"failed to compute filmic auto-points for {path}: {exc}") from exc


def read_camera_iso(path: Path) -> int | None:
    """Read the raw's ISO speed rating from EXIF.

    Returns the ISO as an integer (typically 100..51200 range), or
    ``None`` if the tag is missing. Used by camera-aware denoise (#134
    / RFC-039): noise floor scales with ISO, so the parametric apply
    path scales the denoise threshold relative to the raw's ISO at
    apply time.

    Uses ``exifread.process_file`` (no rawpy needed for this field; ISO
    is in standard EXIF). Returns None rather than raising on missing
    tag — callers (parametric denoise.patch) treat absence as "skip
    auto-scaling, use source coefficients."
    """
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        with path.open("rb") as fh:
            tags = exifread.process_file(fh, details=False)
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
        raise ExifReadError(f"failed to read EXIF from {path}: {exc}") from exc
    tag = tags.get("EXIF ISOSpeedRatings") or tags.get("Image ISOSpeedRatings")
    if tag is None:
        return None
    try:
        values = tag.values
        first = values[0] if isinstance(values, list) else values
        return int(first)
    except (TypeError, ValueError, IndexError, AttributeError):
        return None


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
