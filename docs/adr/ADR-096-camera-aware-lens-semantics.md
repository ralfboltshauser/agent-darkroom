# ADR-096 — Camera-aware `lens` correction (per-body lensfun identifier)

> Status · Draft (impl shipped; flips to Accepted on darkroom validation)
> Date · 2026-05-23
> TA anchor · /components/synthesizer · /constraints/opaque-hex-blobs
> Related RFC · RFC-039 (follow-up sibling under ADR-091 machinery)

## Context

The fourth and final raw-derived parameter RFC-039 named. Darktable's `lens` module uses lensfun: it loads the per-body, per-lens correction profile (distortion + chromatic aberration + vignetting) from a lensfun database lookup keyed by `camera` + `lens` + `focal length`. The op_params blob carries those identifier strings.

Pre-RFC-039, a `lens_correction` vocabulary entry baked the authoring shot's camera + lens identifiers into the bytes. Applying that entry to another body produced lensfun lookups against the WRONG camera + lens — silently fell back to "no correction" (lensfun has no profile match) or worse, applied a wrong-body's correction. The photographer's intent ("apply this lens's correction") didn't carry across cameras.

## Decision

`chemigram.core.parameterize.lens.patch()` gains an optional `raw_path: Path | None` keyword argument. When supplied:

- The function reads the raw's EXIF `camera` (model maker + model name) and `lens` (lens model) strings via exifread.
- The source identifier strings in the lens op_params are replaced with the raw-derived identifiers before any photographer overrides apply.
- The focal length field is similarly populated from EXIF `EXIF FocalLength`.
- Explicit overrides bypass the substitution — the caller is opting into per-shot lens control.
- Correction-strength fields (distortion / TCA / vignetting magnitude) stay at the source values — those are photographic-intent fields, not raw-property fields.

If `raw_path` is `None` or the EXIF tags are missing, behavior is unchanged: source identifiers pass through.

## Rationale

The lensfun lookup table works on exact-match identifier strings. A "use my lens's correction profile" vocabulary entry has to know which lens — and the lens that captured this shot is what the EXIF says, not what the authoring shot used. The substitution is mechanical: read EXIF, format the identifier strings to lensfun's expected layout, write into the op_params byte offsets.

Per-shot focal length matters because zoom lenses have focal-length-varying distortion profiles; populating it from EXIF means the lensfun lookup picks the right per-focal-length correction without the photographer thinking about it.

Reading EXIF via exifread keeps the chemigram-core boundary clean. Same `raw_path` pattern as ADR-091 / 093 / 094 / 095. The four ADRs together establish the full pattern: temperature reads camera-default WB; denoise reads ISO; filmic reads histogram; lens reads camera + lens identifiers.

## Alternatives considered

- **Hardcode body-pair tables in chemigram.core**. Rejected — defers to lensfun's external database, which darktable already ships. Chemigram just needs to populate the identifier fields correctly; lensfun does the actual lookup at render time.
- **Defer to lensfun's `lf_db_find_lenses_hd` fuzzy match**. Rejected — lensfun's fuzzy lookup expects identifier strings; we still need to populate THOSE from EXIF. Skipping the substitution doesn't avoid the work, it just moves it into the wrong layer (darktable can't read chemigram's intent without the bytes set correctly).
- **Skip lens correction if EXIF lens tag is missing**. Considered — fallback "source identifier passes through" is safer: the entry still applies, the photographer can verify in the gallery, and the warn path stays clean.

## Consequences

Positive:
- Lens correction entries port across bodies — `lens_correction` applies the right correction for whatever camera + lens captured the raw.
- Same engine machinery as ADR-091 / 093 / 094 / 095. Pattern is now established.
- Photographer's intent (distortion off, vignetting strength 0.7) is preserved as the configurable axis.

Negative:
- Lensfun database completeness varies — some camera + lens combinations don't have profiles. The op_params populate correctly but darktable's render silently no-ops the correction. The `requires_content`-style gallery routing can't surface this; it's a render-side limitation.
- EXIF lens tag is sometimes missing on adapted lenses or third-party bodies; the fallback is "source identifier passes through" which may produce a wrong-lens correction. Photographer override is the escape hatch.

## Implementation notes

- `src/chemigram/core/parameterize/lens.py` — `patch()` accepts `raw_path` kwarg; `_CAMERA_FIELD_INDEX`, `_LENS_FIELD_INDEX`, `_FOCAL_FIELD_INDEX` constants name the byte positions
- `src/chemigram/core/exif.py` — EXIF camera + lens + focal-length readers (exifread-based)
- `tests/unit/core/parameterize/test_lens.py` — per-body EXIF substitution tests
- Closes RFC-039 follow-up question 4 (lens per body + lens identifier).
