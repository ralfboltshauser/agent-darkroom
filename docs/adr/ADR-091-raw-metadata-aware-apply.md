# ADR-091 — Engine raw-metadata-aware apply API

> Status · Draft (impl shipped; flips to Accepted on darkroom validation)
> Date · 2026-05-23
> TA anchor · /components/synthesizer · /contracts/mcp-tools
> Related RFC · RFC-039

## Context

Before RFC-039, the chemigram apply path was a pure function: baseline XMP + entry → synthesized XMP. The engine had no access to the target raw's metadata at apply time. This was fine for entries whose effects are independent of the source raw (sigmoid, colorbalancergb, vignette, grain), but broke for entries whose effects depend on raw metadata: temperature WB coefficients depend on the camera body's color matrix; denoise threshold depends on ISO; filmic black/white points depend on histogram shape; lens correction depends on the lensfun camera+lens identifier.

The vocabulary's WB-touching entries papered over this by inlining authoring-camera coefficients directly in their `.dtstyle` blobs — which then produced a visible cast when applied to any other camera body. RFC-039 closed this gap by making the apply path raw-aware.

## Decision

`chemigram.core.helpers.apply_entry()` gains an optional `raw_path: Path | None` parameter. When supplied, the engine threads it through to `_apply_parameter_values_to_dtstyle` and then to `chemigram.core.parameterize.patch_op_params`, which in turn passes it to per-module patch functions whose signatures accept `raw_path`. Modules that don't care about raw metadata simply don't declare `raw_path` in their signature and are unaffected (`patch_op_params` inspects the target function's signature via `inspect.signature` to decide whether to pass `raw_path`).

The parametric apply path now runs even with empty `parameter_values` when `raw_path` is supplied AND the entry has declared parameters — this gives camera-aware modules a chance to perform raw-derived substitution at identity (kelvin_delta=0).

Raw metadata reading lives in `chemigram.core.exif.read_camera_daylight_wb()` (rawpy-backed; reads the camera's as-shot WB coefficients normalized to G=1.0). Per-module raw-data needs are declared implicitly via signature acceptance: a module that wants raw data declares `raw_path` as a kwarg.

## Rationale

Threading `raw_path` through the apply chain keeps the engine pure and explicit — every call site that wants camera-aware behavior must opt in by passing the path. This is preferred to a global state mechanism (workspace-keyed lookup) because:

- The synthesizer stays a pure function (baseline + entry + optional raw_path → XMP).
- Test fixtures that don't have a raw file simply pass `raw_path=None` and get the existing (pre-RFC-039) behavior — backward compatibility is automatic.
- Adding new raw-derived modules later doesn't require engine changes; the module just declares `raw_path` in its patch signature.

## Alternatives considered

- **Workspace-keyed lookup**: rejected — introduces global state, complicates testing, and doesn't compose with synthesize_xmp's pure-function model.
- **Per-module explicit `requires_raw_metadata` declaration**: rejected as premature — signature inspection is simpler and works for the today's single camera-aware module (temperature). If we need richer declarations later (e.g., "this module needs ISO, that one needs lensfun id"), we add them when the second module materializes.
- **Always read raw when present**: rejected — wasteful for non-raw-aware modules and would force tests to mock the EXIF reader. Lazy-read-on-signature-match is the right default.

## Consequences

Positive:
- L2 looks can now compose parametric primitives that depend on raw metadata, and the engine routes raw_path automatically.
- The parametric `temperature` entry is camera-portable at delta values (kelvin_delta != 0): applying the same entry to two different camera bodies produces directionally-correct (warmer / cooler) shifts relative to each camera's own daylight.
- Backward compat: every call site that doesn't pass `raw_path` gets the pre-RFC-039 behavior.

Negative:
- Identity case (`kelvin_delta=0` with `raw_path`) doesn't exactly match a no-temperature-op render. Once any temperature op is in the XMP, darktable suppresses its internal auto-insert, and rawpy's `camera_whitebalance` is a close-but-not-exact reproduction of darktable's internal default. Documented as a known limitation; tracked as a follow-up (sibling RFC or Phase 5 patch).
- `rawpy` added as a dependency for the core engine. Native wheel; widely distributed but a non-trivial addition vs. the existing pure-Python `exifread`.

## Implementation notes

- `src/chemigram/core/helpers.py:apply_entry()` — adds optional `raw_path` + `vocab` kwargs.
- `src/chemigram/core/helpers.py:_apply_parameter_values_to_dtstyle()` — threads raw_path to patch.
- `src/chemigram/core/parameterize/__init__.py:patch_op_params()` — inspects function signature to decide whether to pass raw_path.
- `src/chemigram/core/exif.py:read_camera_daylight_wb()` — rawpy-backed reader; robust fallback to source coefficients on read failure.
- Tests: `tests/unit/core/parameterize/test_temperature.py` (5 camera-aware tests), `tests/unit/core/test_exif.py` (3 reader tests).
- Phase 2 commit: `29995b8`.
