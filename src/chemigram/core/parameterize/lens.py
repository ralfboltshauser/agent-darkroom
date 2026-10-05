"""Path C decoder/encoder for darktable's ``lens`` module (mv10).

When a RAW path is supplied, this binds an installed Lensfun profile,
focal length, aperture, focus distance, and an automatically calculated
output scale. The module also exposes manual fine-tuning axes.

Struct layout (verified against darktable 5.4.1 ``src/iop/lens.cc``
``dt_iop_lens_params_t`` v10):

    Method selector + modification flags (preserved verbatim)
    offset 0..3   : enum  method               (default LENSFUN = 1)
    offset 4..7   : enum  modify_flags         (default ALL = 7; distortion+TCA+vignette)
    offset 8..11  : enum  inverse              (default CORRECT = 0)

    Lensfun shooting parameters (bound from EXIF when a RAW is supplied)
    offset 12..15  : float scale               ← auto-scaled or parameterized
    offset 16..19  : float crop                (preserved; default 0.0)
    offset 20..23  : float focal               (EXIF-bound)
    offset 24..27  : float aperture            (EXIF-bound)
    offset 28..31  : float distance            (EXIF or infinity fallback)
    offset 32..35  : enum  target_geom         (preserved; default UNKNOWN = 0)
    offset 36..163 : char  camera[128]         (Lensfun profile-bound)
    offset 164..291: char  lens[128]           (Lensfun profile-bound)

    Manual TCA override (parameterized)
    offset 292..295: gbool tca_override        (preserved; default FALSE = 0)
    offset 296..299: float tca_r               ← parameterized (default 1.0 = no TCA shift)
    offset 300..303: float tca_b               ← parameterized (default 1.0)

    Embedded-metadata method per-correction strengths (parameterized)
    offset 304..307: float cor_dist_ft         ← parameterized (default 0.0)
    offset 308..311: float cor_vig_ft          ← parameterized (default 0.0)
    offset 312..315: float cor_ca_r_ft         ← parameterized (default 0.0)
    offset 316..319: float cor_ca_b_ft         ← parameterized (default 0.0)

    Trailing metadata (preserved)
    offset 320..323: float scale_md_v1         (preserved; default 0.0)
    offset 324..327: enum  md_version          (preserved; default V2 = 1)
    offset 328..331: float scale_md            (preserved; default 0.0)
    offset 332..335: gbool has_been_set        (preserved; default FALSE = 0)

    Manual vignette correction (parameterized)
    offset 336..339: float v_strength          ← parameterized (default 0.0)
    offset 340..343: float v_radius            ← parameterized (default 1.0)
    offset 344..347: float v_steepness         ← parameterized (default 1.0)

    Reserved (preserved)
    offset 348..355: float reserved[2]         (preserved; default 0.0, 0.0)

Total size: 356 bytes.

Ten parameterized magnitude axes — the manual-override knobs. Axis names
use the ``lens_`` prefix for disambiguation:

- ``lens_scale`` — output scaling after correction (range [0.0, 4.0])
- ``lens_tca_r`` — manual red-channel TCA shift (range [0.99, 1.01]; 1.0 = no shift)
- ``lens_tca_b`` — manual blue-channel TCA shift (range [0.99, 1.01])
- ``lens_cor_distortion`` — distortion-correction strength (range [0.0, 1.0])
- ``lens_cor_vignette`` — vignette-correction strength (range [0.0, 1.0])
- ``lens_cor_ca_r`` — red-CA correction strength (range [-2.0, 2.0])
- ``lens_cor_ca_b`` — blue-CA correction strength (range [-2.0, 2.0])
- ``lens_v_strength`` — manual vignette correction strength (range [-1.0, 1.0])
- ``lens_v_radius`` — manual vignette radius (range [0.0, 3.0])
- ``lens_v_steepness`` — manual vignette steepness (range [0.0, 5.0])

Other 17 fields preserved verbatim. Mode enums, the 256-byte camera/lens
char arrays, and the EXIF-bound floats (focal/aperture/distance) all flow
through patch() unchanged.
"""

from __future__ import annotations

import math
import struct
from pathlib import Path

# Field indices for the EXIF-bound (preserved-but-now-populated) fields.
_CAMERA_FIELD_INDEX = 9
_LENS_FIELD_INDEX = 10
_FOCAL_FIELD_INDEX = 5
_APERTURE_FIELD_INDEX = 6

# Struct: 3 enums + 5 floats + 1 enum + 128-byte camera + 128-byte lens
# + 1 gbool + 2 floats + 4 floats + 1 float + 1 enum + 1 float + 1 gbool
# + 3 floats + 2 reserved floats = 356 bytes.
_STRUCT_FORMAT = "<3i5fi128s128si2f4ffifi3f2f"
_STRUCT_SIZE = 356

SUPPORTED_MODVERSION = 10

# Map every parameterized axis to its struct field index in the unpacked
# tuple. Field indices: 0 method, 1 modify_flags, 2 inverse, 3 scale,
# 4 crop, 5 focal, 6 aperture, 7 distance, 8 target_geom, 9 camera (bytes),
# 10 lens (bytes), 11 tca_override, 12 tca_r, 13 tca_b, 14 cor_dist_ft,
# 15 cor_vig_ft, 16 cor_ca_r_ft, 17 cor_ca_b_ft, 18 scale_md_v1,
# 19 md_version, 20 scale_md, 21 has_been_set, 22 v_strength,
# 23 v_radius, 24 v_steepness, 25 reserved[0], 26 reserved[1].
_AXIS_FIELD_INDICES: dict[str, int] = {
    "lens_scale": 3,
    "lens_tca_r": 12,
    "lens_tca_b": 13,
    "lens_cor_distortion": 14,
    "lens_cor_vignette": 15,
    "lens_cor_ca_r": 16,
    "lens_cor_ca_b": 17,
    "lens_v_strength": 22,
    "lens_v_radius": 23,
    "lens_v_steepness": 24,
}

# Field-index-to-byte-offset map (variable struct, can't use 4 * idx).
# Computed once for documentation and tests.
_AXIS_OFFSETS: dict[str, int] = {
    "lens_scale": 12,
    "lens_tca_r": 296,
    "lens_tca_b": 300,
    "lens_cor_distortion": 304,
    "lens_cor_vignette": 308,
    "lens_cor_ca_r": 312,
    "lens_cor_ca_b": 316,
    "lens_v_strength": 336,
    "lens_v_radius": 340,
    "lens_v_steepness": 344,
}


def decode(op_params: str) -> tuple[int | float | bytes, ...]:
    """Decode a 356-byte lens ``op_params`` hex blob.

    Returns a 27-tuple in struct order. Raises :class:`ValueError` on
    size mismatch (most often a different modversion than mv10).
    """
    raw = bytes.fromhex(op_params)
    if len(raw) != _STRUCT_SIZE:
        raise ValueError(
            f"lens op_params: expected {_STRUCT_SIZE} bytes, got {len(raw)}; "
            f"likely a different modversion than mv10"
        )
    return struct.unpack(_STRUCT_FORMAT, raw)


def encode(fields: tuple[int | float | bytes, ...]) -> str:
    """Encode a 27-tuple back to a 356-byte lens ``op_params`` hex blob."""
    return struct.pack(_STRUCT_FORMAT, *fields).hex()


def patch(
    op_params: str,
    *,
    raw_path: Path | None = None,
    **values: float | None,
) -> str:
    """Patch any combination of lens's 10 parameterized magnitude axes.

    Multi-axis partial-update: caller may supply any subset of the 10
    parameterized axes via keyword arguments. Unknown keys raise
    :class:`TypeError`. Unspecified axes preserved.

    Preserved verbatim through patch():
    - method, modify_flags, inverse (3 mode enums)
    - crop, focal, aperture, distance (4 EXIF-bound or preserved floats)
    - target_geom (lens-shape enum)
    - camera[128], lens[128] (lensfun identifier strings)
    - tca_override (gbool flag toggling whether tca_r/tca_b are honored)
    - scale_md_v1, md_version, scale_md, has_been_set (4 metadata fields)
    - reserved[2] (2 reserved floats)

    Parameterized axes (10 total — manual-override knobs):

    - ``lens_scale`` — output scale after correction
    - ``lens_tca_r``, ``lens_tca_b`` — manual TCA shifts (1.0 = no shift)
    - ``lens_cor_distortion`` — distortion-correction strength
    - ``lens_cor_vignette`` — vignette-correction strength
    - ``lens_cor_ca_r``, ``lens_cor_ca_b`` — chromatic-aberration corrections
    - ``lens_v_strength``, ``lens_v_radius``, ``lens_v_steepness`` — manual vignette knobs

    Args:
        op_params: hex-encoded source ``op_params`` (356 bytes / 712 hex chars).
        **values: any subset of the 10 axis names listed above.

    Returns:
        New hex-encoded ``op_params`` (356 bytes / 712 hex chars).

    Raises:
        ValueError: input blob is not 356 bytes after hex-decode.
        TypeError: an unrecognized keyword argument was passed.
    """
    unknown = set(values.keys()) - set(_AXIS_FIELD_INDICES.keys())
    if unknown:
        raise TypeError(
            f"lens.patch() got unexpected keyword argument(s): {sorted(unknown)}; "
            f"valid axes: {sorted(_AXIS_FIELD_INDICES.keys())}"
        )
    fields = list(decode(op_params))
    # Bind only a verified camera/lens pair. An unmatched profile must be
    # reported rather than producing a successful edit with no optical effect.
    if raw_path is not None:
        from chemigram.core.exif import read_exif
        from chemigram.core.lens_profiles import find_lens_profile, lens_auto_scale

        camera_bytes = fields[_CAMERA_FIELD_INDEX]
        assert isinstance(camera_bytes, bytes)
        if not camera_bytes.rstrip(b"\x00"):
            exif = read_exif(raw_path)
            profile = find_lens_profile(exif)
            if profile is None:
                raise ValueError(
                    f"no unambiguous Lensfun profile for {exif.make} {exif.model} / "
                    f"{exif.lens_model}; lens correction was not applied"
                )
            focal, aperture = exif.focal_length_mm, exif.aperture
            if (
                focal is None
                or aperture is None
                or not math.isfinite(focal)
                or not math.isfinite(aperture)
                or focal <= 0
                or aperture <= 0
            ):
                raise ValueError("lens correction requires positive focal length and aperture EXIF")
            fields[0] = 1  # Lensfun method
            fields[3] = lens_auto_scale(profile, exif, raw_path)
            fields[_CAMERA_FIELD_INDEX] = profile.camera.encode("utf-8")[:127].ljust(128, b"\x00")
            fields[_LENS_FIELD_INDEX] = profile.lens.encode("utf-8")[:127].ljust(128, b"\x00")
            fields[_FOCAL_FIELD_INDEX] = float(focal)
            fields[_APERTURE_FIELD_INDEX] = float(aperture)
            distance = exif.focus_distance_m
            fields[7] = float(
                distance if distance and math.isfinite(distance) and distance > 0 else 1000.0
            )
            fields[8] = 1  # rectilinear target geometry
            fields[21] = 1
    for axis_name, value in values.items():
        if value is not None:
            fields[_AXIS_FIELD_INDICES[axis_name]] = float(value)
    return encode(tuple(fields))
