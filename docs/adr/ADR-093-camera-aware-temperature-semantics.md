# ADR-093 — Camera-aware parametric `temperature` semantics

> Status · Draft (impl shipped; flips to Accepted on darkroom validation)
> Date · 2026-05-23
> TA anchor · /components/synthesizer · /constraints/opaque-hex-blobs
> Related RFC · RFC-039

## Context

ADR-077..080 (RFC-021 closure) shipped the parameterized `temperature` module's `patch()` function, which decodes the temperature `op_params` blob, allows callers to override `red_coeff` / `green_coeff` / `blue_coeff` / `kelvin_delta` / `tint_delta`, and re-encodes. The function operated in coefficient space only — no awareness of the source raw's camera or as-shot WB.

The result, surfaced during the visual-proofs Step 2 work (#131): applying the parametric `temperature` entry at default `kelvin_delta=0` to a Sony DSC-RX10M4 raw produced a green-dominant render, NOT a camera-default daylight render. The reason: the dtstyle's identity coefficients (1.0, 1.0, 1.0) DON'T mean "no change" — they mean "use raw Bayer values unscaled," which leaves the Bayer pattern's 2× green dominance unmitigated. Darktable's normal behavior (no temperature op in history) auto-inserts a camera-detected daylight WB; explicit (1.0, 1.0, 1.0) overrides that with neutral coefficients and produces the cast.

RFC-039 closes this gap by making the parametric temperature path camera-aware.

## Decision

`chemigram.core.parameterize.temperature.patch()` gains an optional `raw_path: Path | None` keyword argument. When supplied:

- The function reads the raw's camera-default WB coefficients via `chemigram.core.exif.read_camera_daylight_wb(raw_path)` — which uses `rawpy.imread().camera_whitebalance` normalized to `green_coeff == 1.0`.
- The source RGB coefficients in the temperature op_params are REPLACED with the raw's camera-default WB before any deltas are applied.
- Subsequent `kelvin_delta` / `tint_delta` shifts are then applied relative to the camera's daylight (not the dtstyle's hardcoded source).
- Explicit `red_coeff` / `green_coeff` / `blue_coeff` overrides bypass the substitution — the caller is opting into raw-coefficient control.

If `raw_path` is `None` (synthetic chart fixtures, no raw available), behavior is unchanged: source coefficients pass through. If `raw_path` is supplied but unreadable (corrupt file, unsupported format), the substitution silently falls back to the source coefficients — the patch function never raises on raw-read failure.

## Rationale

Reading the raw's WB at apply time is the architecturally honest fix for raw-domain parameter portability. The alternative (continuing to use hardcoded coefficients) makes the vocabulary's claim "applicable to any photographer's raw" untrue. Substituting at the coefficient-space level (rather than emitting nothing at identity, or computing a Bradford / CAT02 transform) preserves the existing function signature and decoder behavior — `red_coeff` / `green_coeff` / `blue_coeff` arguments still work the same way; the only behavioral change is that the IDENTITY values come from the raw instead of from the dtstyle.

Using rawpy's `camera_whitebalance` (rather than `daylight_whitebalance`) was an empirical decision: `camera_whitebalance` produces renders that more closely match darktable's internal auto-default WB behavior on the Sony test fixtures.

## Alternatives considered

- **Emit no temperature op at identity**: would produce darktable-default behavior cleanly but requires the dtstyle apply path to support "skip plugin at identity" — a structural change beyond the patch function. Deferred to a future RFC if it becomes necessary.
- **Use rawpy's `daylight_whitebalance` (D65 reference)**: rejected after empirical testing — produces renders that don't match darktable's internal default. The as-shot WB is closer to the photographer's experience.
- **Implement chromatic-adaptation transform (CAT02 / Bradford) per camera primaries**: rejected for v1 — adds substantial complexity for a daily-use-accurate UX feature. The current linear-coefficient-space approximation is sufficient for the kelvin/tint delta photographic UX wrapper.

## Consequences

Positive:
- Non-zero `kelvin_delta` / `tint_delta` shifts are camera-portable: a +1500K warm shift produces the same direction-of-effect on Sony, Canon, Nikon, Fujifilm raws.
- L2 looks composing this primitive (RFC-039 / ADR-092) get camera-correct WB shifts at apply time.
- Existing call sites passing `red_coeff` / `green_coeff` / `blue_coeff` directly are unaffected.

Negative (known limitation):
- At strict identity (`kelvin_delta=0` with `raw_path`), the emitted op_params encode camera WB but darktable's render still differs slightly from a no-temperature-op render. Once any temperature op is in the XMP, darktable suppresses its internal auto-insert pathway, and rawpy's `camera_whitebalance` is a close-but-not-exact reproduction of darktable's internal computation. The DELTA path is unaffected (and is the load-bearing case for L2 composition); identity-render fidelity is documented as a follow-up.
- Test fixtures without EXIF / readable raw data must explicitly pass `raw_path=None` to get the previous behavior. The patch path's robust fallback (silent skip on read failure) covers most cases automatically.

## Implementation notes

- `src/chemigram/core/parameterize/temperature.py:patch()` — adds `raw_path` kwarg; substitutes source coefficients with rawpy's camera_whitebalance before delta application.
- `src/chemigram/core/exif.py:read_camera_daylight_wb()` — rawpy-backed reader.
- Tests: `tests/unit/core/parameterize/test_temperature.py` — 5 new tests for the raw_path path (no-raw passthrough, identity substitution, delta-relative shift, explicit override wins, unreadable-raw fallback).
- Phase 2 commit: `29995b8`.
