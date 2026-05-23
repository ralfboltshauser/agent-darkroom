"""Path C decoder/encoder for darktable's ``temperature`` (white balance) module (mv4).

Struct layout (verified against darktable 5.4.1 ``src/iop/temperature.c``
``dt_iop_temperature_params_t`` v4; cross-checked empirically against the
shipped ``wb_warm_subtle`` / ``wb_cool_subtle`` ``.dtstyle`` entries):

    offset 0..3   : float red       (0..8; multiplier coefficient)  ← parameterized
    offset 4..7   : float green     (0..8; multiplier coefficient)  ← parameterized (tint)
    offset 8..11  : float blue      (0..8; multiplier coefficient)  ← parameterized
    offset 12..15 : float various   (0..8; 4Bayer/CYGM 4th channel; +inf sentinel)
    offset 16..19 : int   preset

Total size: 20 bytes (4 floats + 1 int).

Three photographic axes (#90 Bucket A.3 — Lightroom WB Tint parity):

- **Warmth (Kelvin)**: red↑ + blue↓ → warmer; red↓ + blue↑ → cooler.
  Driven by ``red_coeff`` and ``blue_coeff``.
- **Tint (green-magenta)**: green↑ → magenta-shifted (less green); green↓ → green-shifted.
  Driven by ``green_coeff``. Lightroom's Tint slider maps directly here.

Storage is RGB coefficients, not temperature/tint photographically. The
mapping is camera-specific (depends on primaries). This decoder operates
in the coefficient space directly.

The :func:`patch` function accepts:

- Coefficient axes (raw bytes-level): ``red_coeff``, ``green_coeff``,
  ``blue_coeff`` — direct multiplier overrides.
- Photographic-units delta axes (#102 / Kelvin UX wrapper): ``kelvin_delta``,
  ``tint_delta`` — apply a relative shift on top of the source coefficients.
  Linear approximation, daily-use accurate.

When both a coefficient axis and the corresponding delta axis are supplied,
the explicit coefficient wins (last-write semantics — the coefficient kwarg
overrides the delta-derived value).

``various`` and ``preset`` are always preserved.
"""

from __future__ import annotations

import struct
from pathlib import Path

# Struct format (little-endian): 4 floats + 1 int32.
_STRUCT_FORMAT = "<4fi"
_STRUCT_SIZE = 20
_RED_FIELD_INDEX = 0
_RED_OFFSET = 0
_GREEN_FIELD_INDEX = 1
_GREEN_OFFSET = 4
_BLUE_FIELD_INDEX = 2
_BLUE_OFFSET = 8

SUPPORTED_MODVERSION = 4

# Linear approximation factor for the photographic-units delta axes
# (#102 / Kelvin UX wrapper). 0.0001 yields ~10% coefficient shift per
# 1000K — a daily-use-accurate photographic feel; not a chromatic-
# adaptation-perfect mapping. Real CAT02/Bradford conversion would be
# camera-primaries-aware, which is out of scope for the UX wrapper.
_KELVIN_PER_COEFF_UNIT = 0.0001
_TINT_PER_COEFF_UNIT = 0.0001


def decode(op_params: str) -> tuple[float | int, ...]:
    """Decode a 20-byte temperature ``op_params`` hex blob.

    Returns ``(red, green, blue, various, preset)``. Raises
    :class:`ValueError` on size mismatch.
    """
    raw = bytes.fromhex(op_params)
    if len(raw) != _STRUCT_SIZE:
        raise ValueError(
            f"temperature op_params: expected {_STRUCT_SIZE} bytes, got {len(raw)}; "
            f"likely a different modversion than mv4"
        )
    return struct.unpack(_STRUCT_FORMAT, raw)


def encode(fields: tuple[float | int, ...]) -> str:
    """Encode a 5-tuple back to a 20-byte temperature ``op_params`` hex blob."""
    return struct.pack(_STRUCT_FORMAT, *fields).hex()


def patch(
    op_params: str,
    *,
    red_coeff: float | None = None,
    green_coeff: float | None = None,
    blue_coeff: float | None = None,
    kelvin_delta: float | None = None,
    tint_delta: float | None = None,
    raw_path: Path | None = None,
) -> str | None:
    """Patch ``red``, ``green`` and/or ``blue`` coefficient fields in a
    20-byte temperature blob.

    Two parameterization shapes are supported:

    1. **Direct coefficient kwargs** (``red_coeff``, ``green_coeff``,
       ``blue_coeff``) — overwrite the source field with the supplied
       multiplier. Range validation is the caller's responsibility
       (manifest declares range [0.5, 4.0] for each).

    2. **Photographic-units delta kwargs** (``kelvin_delta``, ``tint_delta``)
       — apply a relative linear shift on top of the source coefficients.
       Linear approximation:
       - ``kelvin_delta`` ↑ → red_coeff ↑, blue_coeff ↓ (warmer Kelvin).
         red_coeff *= 1 + kelvin_delta * 0.0001
         blue_coeff *= 1 + (-kelvin_delta * 0.0001)
       - ``tint_delta`` ↑ → green_coeff ↑ (magenta-shifted).
         green_coeff *= 1 + tint_delta * 0.0001
       Daily-use accurate; not chromatic-adaptation-perfect (real CAT02 /
       Bradford conversion would be camera-primaries-aware, which is out
       of scope for the UX wrapper).

    When both a coefficient kwarg and the corresponding delta kwarg are
    supplied, the explicit coefficient wins (last-write semantics — the
    delta is computed first, then the coefficient overwrites).

    Multi-parameter partial-update: caller may supply any subset of the
    five kwargs. Unspecified axes preserved. ``various`` (often +inf
    sentinel) and ``preset`` always preserved.

    Args:
        op_params: hex-encoded source ``op_params`` (20 bytes / 40 hex chars).
        red_coeff, green_coeff, blue_coeff: direct coefficient overrides.
        kelvin_delta: relative warmth shift; positive = warmer. Typical
            range [-3000, 3000]; default 0 (no change).
        tint_delta: relative tint shift; positive = magenta-shifted.
            Typical range [-200, 200]; default 0.

    Returns:
        New hex-encoded ``op_params`` (20 bytes / 40 hex chars).

    When ``raw_path`` is supplied, the source coefficients are first
    REPLACED with the raw's as-shot camera WB coefficients (normalized
    to G=1) read via :func:`chemigram.core.exif.read_camera_daylight_wb`.
    Non-zero kelvin/tint deltas then shift relative to the raw's
    camera-default — making the delta path camera-aware (RFC-039 /
    #131 Step 2). E.g., a composed L2 look saying ``kelvin_delta=+1500``
    produces a warming shift on top of *that specific camera's*
    daylight, not the authoring camera's daylight.

    Known limitation (#131 follow-up): at strict identity
    (no parameters supplied), the emitted op_params encode camera
    WB but darktable's render still differs slightly from a no-
    temperature-op render. The reason: once any temperature op is
    present in the XMP, darktable suppresses its internal
    auto-insert pathway, and rawpy's camera_whitebalance values are
    a close-but-not-exact reproduction of what darktable's internal
    auto-default computes. The DELTA path is unaffected (and is the
    load-bearing case for L2 composition); identity-render fidelity
    is tracked as a follow-up for Phase 5 or a sibling RFC.

    When ``raw_path`` is None (synthetic chart fixtures, no raw
    available), behavior is unchanged (source coefficients passed
    through).

    If the raw is unreadable (corrupt, missing EXIF, etc.), the
    substitution silently falls back to the source coefficients — the
    function never raises on raw-read failure. This keeps the parametric
    apply path robust for test fixtures.

    Returns ``None`` when called with ``raw_path`` and no shift (zero
    deltas, no explicit coefficients) — the engine drops the plugin
    entirely so darktable applies its own camera-default WB. Avoids
    the identity-render-fidelity gap noted in ADR-093: an explicit
    op_params with rawpy-derived coefficients renders slightly
    differently from a no-temperature-op render because darktable
    suppresses its internal auto-insert when any temperature op is
    present.

    Raises:
        ValueError: input blob is not 20 bytes after hex-decode.
    """
    fields = list(decode(op_params))
    # Identity-skip (RFC-039 ADR-093 follow-up): when raw_path is
    # supplied AND no shift is requested (no explicit coefficients, no
    # non-zero deltas), return None to signal "skip this plugin." The
    # caller (_apply_parameter_values_to_dtstyle) drops the plugin and
    # darktable falls back to its internal camera-default WB —
    # producing a render that exactly matches the no-temperature-op
    # baseline.
    coefficient_overrides_supplied = any(
        c is not None for c in (red_coeff, green_coeff, blue_coeff)
    )
    no_kelvin_shift = kelvin_delta is None or kelvin_delta == 0
    no_tint_shift = tint_delta is None or tint_delta == 0
    if (
        raw_path is not None
        and not coefficient_overrides_supplied
        and no_kelvin_shift
        and no_tint_shift
    ):
        return None

    # Camera-aware substitution (RFC-039 / #131 Step 2): when raw_path is
    # supplied, swap the source RGB coefficients with the camera's
    # daylight WB before applying any deltas. Bypassed if any direct
    # coefficient override (red/green/blue_coeff) is supplied — those
    # take precedence over the camera-default since the caller is
    # explicitly opting into raw-coefficient control.
    if raw_path is not None and not coefficient_overrides_supplied:
        try:
            from chemigram.core.exif import read_camera_daylight_wb

            r, g, b = read_camera_daylight_wb(raw_path)
            fields[_RED_FIELD_INDEX] = r
            fields[_GREEN_FIELD_INDEX] = g
            fields[_BLUE_FIELD_INDEX] = b
            # Preserve "various" (offset 12..15) and "preset" (offset
            # 16..19) — the raw doesn't change those, only the R/G/B
            # multipliers.
        except Exception:  # noqa: S110
            # Robust fallback: if rawpy can't read the file (corrupt,
            # unsupported format, missing libraw codec for this body),
            # keep the source coefficients. The caller's explicit-
            # coefficient or delta path still works. Deliberately broad
            # except — raw-read failures span many libraw error types
            # and aren't worth logging individually here.
            pass
    # Apply photographic-units deltas first (relative to source).
    if kelvin_delta is not None and kelvin_delta != 0:
        factor = 1.0 + (kelvin_delta * _KELVIN_PER_COEFF_UNIT)
        fields[_RED_FIELD_INDEX] = float(fields[_RED_FIELD_INDEX]) * factor
        fields[_BLUE_FIELD_INDEX] = float(fields[_BLUE_FIELD_INDEX]) * (
            2.0 - factor  # inverse direction; equivalent to *= (1 - kelvin_delta * c)
        )
    if tint_delta is not None and tint_delta != 0:
        factor = 1.0 + (tint_delta * _TINT_PER_COEFF_UNIT)
        fields[_GREEN_FIELD_INDEX] = float(fields[_GREEN_FIELD_INDEX]) * factor
    # Direct coefficient kwargs override any delta-derived values.
    if red_coeff is not None:
        fields[_RED_FIELD_INDEX] = float(red_coeff)
    if green_coeff is not None:
        fields[_GREEN_FIELD_INDEX] = float(green_coeff)
    if blue_coeff is not None:
        fields[_BLUE_FIELD_INDEX] = float(blue_coeff)
    return encode(tuple(fields))
