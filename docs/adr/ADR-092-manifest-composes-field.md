# ADR-092 — Manifest `composes` field for L2 composition by reference

> Status · Draft (impl shipped; flips to Accepted on darkroom validation)
> Date · 2026-05-23
> TA anchor · /contracts/vocabulary-manifest · /components/synthesizer
> Related RFC · RFC-039

## Context

Pre-RFC-039, L2 vocabulary entries were monolithic: each `.dtstyle` file inlined every plugin (sigmoid, colorbalancergb, temperature, etc.) directly as raw `op_params` byte blobs. For most modules this is fine, but for raw-derived parameters (temperature WB, denoise threshold, filmic tone points, lens correction) the hardcoded blobs are camera-specific — making the L2 look non-portable across camera bodies.

RFC-039 introduces composition: L2 looks reference parametric L3 primitives by name + parameter values. The engine resolves references at apply time and splices the primitive's output into the L2's history.

## Decision

The manifest schema gains an optional `composes` field on L2 entries. The shape:

```json
{
  "name": "look_landscape_golden_hour",
  "layer": "L2",
  "touches": ["sigmoid", "colorbalancergb", "temperature"],
  "composes": [
    {
      "primitive": "wb_kelvin_delta",
      "parameter_values": {"kelvin_delta": 1500.0}
    }
  ],
  ...
}
```

`composes` is a tuple of `CompositionRef(primitive, parameter_values)` after manifest parsing. Validation runs at `VocabularyIndex` build time:

- Every referenced primitive must exist in the loaded index (load-time error, not apply-time KeyError).
- Referenced primitives must declare `parameters` (only parametric primitives are composable).
- `parameter_values` keys must match parameter names on the referenced primitive.
- Composition is **depth-1**: referenced primitive must not itself have a `composes` field (no nested composition in v1).

At apply time, `apply_entry()` resolves each composition reference: looks up the primitive in the supplied `vocab` (a new optional kwarg), calls `_apply_parameter_values_to_dtstyle` on the primitive's dtstyle with the reference's `parameter_values` + `raw_path`, and prepends the resolved dtstyles to the L2's own dtstyle in `synthesize_xmp`'s entries list. Last-writer-wins semantics for same-(operation, multi_priority) collisions: the L2's own dtstyle takes precedence, which is the safe default if a composed primitive overlaps with the L2's inlined ops.

`apply_entry` raises `ValueError` if `entry.composes` is set but `vocab` is not passed (the caller forgot to thread the index).

`touches` continues to declare the full effect set (composed modules included), but for discriminator routing (`chemigram.core.visual_verification.verification_mode_for_entry`), the "not_yet_portable" check uses DIRECT touches only (plugins in the entry's own dtstyle). Entries whose only not-yet-portable touch comes via composition are camera-portable and graduate to `real_raw`.

## Rationale

Composition-by-reference (rather than inline composition) is the right shape because:

- It encodes vocabulary intent: "this look is sigmoid + grade + warm-WB-via-camera-default" instead of "this look applies these specific RGB multipliers."
- It composes naturally with the camera-aware parametric apply path (ADR-091): the primitive's parameterized apply runs with the target's raw_path; the L2 just declares which primitive and at what parameter values.
- It's backward compatible: existing L2 entries with no `composes` field continue to work unchanged.
- Depth-1 keeps the v1 implementation tractable; the cyclic-composition prevention check is one validation step at load time. If L2-composes-L2 becomes useful later, a follow-up RFC can relax the constraint.

## Alternatives considered

- **Inline composition (parametric `op_params` on L2)**: rejected — would require each L2 to declare its own `parameters` for the composed module, duplicating the spec across every L2 that uses it. Reference-by-name centralizes the declaration on the L3 primitive.
- **Cross-pack composition**: deliberately constrained — composition references must resolve within the loaded pack set. Starter-pack L2 entries can't compose expressive-baseline L3 primitives unless both packs are loaded. Today this manifests as `look_neutral` and `wb_warm_subtle` staying in `not_yet_portable` because their potential composition target (`wb_kelvin_delta`) is in a different pack; tracked as a follow-up (move `wb_kelvin_delta` to starter, or add cross-pack resolution).
- **Deep / cyclic composition (depth > 1)**: rejected for v1. The validation enforces depth-1 explicitly; relaxing this is a future RFC.

## Consequences

Positive:
- 13 L2 looks reauthored to compose parametric `wb_kelvin_delta`; they now render with camera-correct WB on any body the photographer brings.
- Vocabulary architecture matches the project's "vocabulary, not sliders" foundational discipline — entries describe intent, not specific raw coefficients.
- The same mechanism is now available for future raw-derived parameter compositions (denoise/filmic/lens — separate follow-up issues).

Negative:
- `apply_entry` gains an additional kwarg (`vocab`). Callers that compose entries must thread it. Tests that previously called `apply_entry(baseline, entry)` on composed entries fail with a clear error; required updates were ~3 test files.
- Apply-time composition adds a small overhead per L2 look (one extra dtstyle resolution per composes ref). Negligible in practice.
- Mask binding + composes is not supported in v1 (`apply_entry` rejects the combination with an explanatory error). Tracked as a follow-up if needed.

## Implementation notes

- `src/chemigram/core/vocab/__init__.py:CompositionRef` — frozen dataclass.
- `src/chemigram/core/vocab/__init__.py:VocabEntry.composes` — optional tuple.
- `src/chemigram/core/vocab/__init__.py:_extract_composes()` — manifest shape validation.
- `src/chemigram/core/vocab/__init__.py:VocabularyIndex._validate_composes_references()` — cross-reference validation at load time.
- `src/chemigram/core/helpers.py:apply_entry()` — resolves `composes` via `vocab` at apply time.
- Phase 3 commit: `db86dfa`.
- Phase 4 commit: (reauthor of 13 L2 looks).
