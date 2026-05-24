# ADR-094 — Camera-aware `denoiseprofile` threshold scaling

> Status · Draft (impl shipped; flips to Accepted on darkroom validation)
> Date · 2026-05-23
> TA anchor · /components/synthesizer · /constraints/opaque-hex-blobs
> Related RFC · RFC-039 (follow-up sibling under ADR-091 machinery)

## Context

RFC-039's engine machinery (ADR-091) ships raw_path threading through `apply_entry` and per-module declaration of raw-metadata needs. ADR-093 used the machinery for the first raw-derived parameter — camera-aware WB on the `temperature` module. The RFC explicitly named denoise as the next module to fold into the same pattern: a denoise threshold authored against ISO 200 should scale up automatically when applied to an ISO 6400 raw, because shot noise grows roughly as √ISO.

Before this ADR, `chemigram.core.parameterize.denoiseprofile.patch()` operated in raw bytes — the photographer authored a fixed threshold against a specific shot's ISO and the same bytes applied unchanged to every other shot. A daylight-ISO threshold over-denoised low-ISO output (smearing detail) and under-denoised high-ISO output (visible chroma noise).

## Decision

`chemigram.core.parameterize.denoiseprofile.patch()` gains an optional `raw_path: Path | None` keyword argument. When supplied:

- The function reads the raw's ISO via `chemigram.core.exif.read_camera_iso(raw_path)` (rawpy's `other.iso_speed`, with exifread fallback).
- The source threshold values in the denoiseprofile op_params are scaled by `2 ** log2(iso / _DENOISE_REFERENCE_ISO)` where `_DENOISE_REFERENCE_ISO = 200`. The factor is 1.0 at ISO 200, 2.0 at ISO 400, 4.0 at ISO 800, 8.0 at ISO 1600, etc.
- The scaling applies multiplicatively to the strength axis; the chroma/luma split and frequency profile stay at the source values.
- Explicit `strength` overrides bypass the substitution — the caller is opting into raw-strength control.

If `raw_path` is `None` (synthetic chart fixtures), behavior is unchanged. If the raw is unreadable, the substitution silently falls back to source.

## Rationale

Shot noise in a sensor's raw output grows approximately as √ISO, so a noise-suppression threshold tuned for ISO 200 needs to grow roughly linearly with ISO to maintain the same perceptual smoothness. The log2-scaled factor above ISO 200 (the reference) tracks the ISO doubling cadence: every ISO doubling doubles the threshold, matching the noise floor's doubling. Below ISO 200 (clean territory) the factor stays at 1.0 — over-attenuation here would smear detail that doesn't need denoising.

Reading ISO via rawpy is the architecturally consistent path with ADR-093's WB substitution: same engine API, same lazy reader, same `raw_path` parameter, same fallback semantics. The vocabulary author writes one entry; the entry adapts to whatever the photographer's raw was shot at.

## Alternatives considered

- **Linear ISO scaling** (factor = iso / 200). Rejected because shot noise grows as √ISO, not linearly — linear scaling would over-attenuate high-ISO output. Log2 sits between √ISO (1.41× per stop) and linear (2× per stop) but matches the ISO-doubling cadence cleanly.
- **Strength curves per camera body**. Rejected because the per-body strength tables would require empirical calibration the project doesn't have bandwidth for. Log2 scaling is body-agnostic and matches the photographic intuition "two stops of ISO = two stops more denoise."
- **Skip the substitution at low ISO** (e.g., < 200). Considered and adopted by-omission: the formula already returns 1.0 at the reference ISO and below; no explicit branch needed.

## Consequences

Positive:
- Denoise vocabulary entries port across ISO without per-shot reauthoring.
- Same engine machinery as ADR-091 / ADR-093 — no new infrastructure.
- Photographer's intent (e.g., "remove visible noise") survives ISO changes.

Negative:
- The log2 formula is a heuristic, not a calibrated noise model. At extreme ISOs (above ISO 25600) the formula may over-attenuate; per-body calibration would be more accurate.
- ISO probes via rawpy's `other.iso_speed` can be None for some bodies; the fallback is "use source threshold" which is the safe degradation.

## Implementation notes

- `src/chemigram/core/parameterize/denoiseprofile.py` — `patch()` accepts `raw_path` kwarg
- `src/chemigram/core/exif.py` — `read_camera_iso(path)` helper
- `tests/unit/core/parameterize/test_denoiseprofile.py` — ISO scaling tests
- Closes RFC-039 follow-up question 2 (denoise per ISO scaling).
