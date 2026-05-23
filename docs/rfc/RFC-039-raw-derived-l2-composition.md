# RFC-039 — Raw-derived parameters in L2 composition

> Status · Decided; ADR-091/092/093 Draft until darkroom validation
> TA anchor · /components/synthesizer · /contracts/vocabulary-manifest · /contracts/mcp-tools · /constraints/opaque-hex-blobs
> Related · RFC-021 (parameterized vocabulary magnitudes / ADR-077..080), RFC-022 (bulk parameterization / ADR-081), RFC-035 (parametric L2 strength / ADR-088)
> Closes into · ADR-091 (engine raw-metadata-aware apply API), ADR-092 (manifest `composes` field), ADR-093 (camera-aware parametric temperature semantics)
> Why this is an RFC · 17 vocabulary entries (14 L2 looks + 3 L3 primitives) carry hardcoded raw-domain WB coefficients from their authoring camera body; applying them to a different body produces a foreign-WB cast that contradicts the entry's name. The same defect class applies to denoise (threshold per ISO), filmic (black point per histogram), and lens (correction per body+lens). The vocabulary's foundational claim — "an entry is reusable across photographers AND across raws" — is currently false for raw-derived parameters. Three real options for restoring the claim, each with substantial architectural cost. The right answer isn't obvious and the engine API needs to be designed once across all raw-derived parameters, not retrofitted module-by-module.

## The question

Across the v1.11.0 vocabulary, 17 entries touch the `temperature` module: 14 L2 looks (`look_landscape_golden_hour`, `look_70s_film`, `look_portrait_natural_skin`, etc.) and 3 L3 primitives (`temperature`, `wb_kelvin_delta`, `wb_warm_subtle`). Each one's `.dtstyle` blob carries raw-domain WB coefficients — three floats encoding RGB multipliers that darktable applies before demosaic. When the vocabulary was authored, those coefficients came from a specific camera body's daylight WB. Applied to a raw from any other body, the coefficients overwrite the target's EXIF WB and produce a visible color cast that masks the entry's actual photographic intent.

The same defect applies to other raw-derived parameters:

- **`denoiseprofile`** — denoise threshold is meaningful relative to the raw's noise floor, which depends on ISO. Hardcoded thresholds work on the authoring ISO; underflow / overflow on others.
- **`filmicrgb`** — black/white points are meaningful relative to the raw's histogram. Hardcoded values clip on raws darker than the authoring scene; lift on brighter ones.
- **`lens`** — correction parameters need the lensfun camera+lens identifier strings, which are EXIF-derived. Hardcoded lensfun strings work for the authoring body; produce wrong correction (or no correction) on any other.

Today the vocabulary papers over this by either (a) inlining the authoring camera's values, (b) parameterizing without camera-awareness (RFC-021's L3 `temperature` parametric entry — it ships fixed reference coefficients at default, which OVERRIDE camera EXIF rather than preserving it), or (c) shipping the entry but tagging it with caveats in the gallery.

The genuinely-open question: **how should L2 looks express intent that depends on raw metadata in a way that ports cleanly across cameras, ISOs, and lighting — without breaking composition with masks, without forcing the engine to special-case each module, and without expanding the vocabulary surface to camera-keyed variants?**

## Use cases

- **A photographer applies `look_landscape_golden_hour` to their own raw from any body** — the warm WB shift is computed relative to their camera's daylight, not the authoring camera's. The "golden hour mood" lands as intended.
- **A photographer applies `look_portrait_natural_skin` across multiple cameras in their kit** — skin tones read naturally on each, because the WB delta is camera-aware.
- **Vocabulary contributions stay portable** — when another photographer authors a new L2 look, they express WB intent as a kelvin/tint delta (camera-agnostic) rather than as raw RGB multipliers (camera-specific).
- **Future raw-derived params reuse the mechanism** — when denoise / filmic / lens entries get the same treatment, they plug into the same engine machinery rather than each module getting bespoke camera-awareness code.

## Goals

1. **Raw-derived parameters are computed per-raw at apply time** — engine reads the necessary raw metadata (EXIF WB, ISO, histogram, lensfun identifier) and feeds it to the parametric primitive's compute path.
2. **L2 looks can compose parametric primitives** — manifest entries reference parametric L3 primitives by name + parameter values; engine resolves the references at apply time rather than the L2 looks inlining raw coefficients.
3. **Identity preserves camera defaults** — at the parameter's identity value (e.g., `kelvin_delta=0`), the parametric primitive emits coefficients that preserve the camera's EXIF WB (no override). Non-zero values shift relative to that camera-default state.
4. **One engine API across all raw-derived parameters** — per-module raw-data needs are declared in the parametric module (which fields it reads from the raw); the engine provides them uniformly. Adding denoise/filmic/lens later doesn't require new engine plumbing.
5. **Backwards compatible with existing atomic L2 looks** — non-composed L2 looks continue to work as before.

## Constraints

- **TA/components/synthesizer** — synthesizes XMP from baseline + entry. Today it has no `raw_path` awareness; entries are applied symbolically. The proposed change introduces a `raw_path` parameter that flows through to parameterize-time computations.
- **TA/contracts/vocabulary-manifest** — manifest schema gains an optional `composes` field listing `(primitive_name, parameter_values)` tuples per L2 entry. Existing entries with no `composes` field continue to work atomically.
- **TA/contracts/mcp-tools** — `apply_primitive` and `apply_per_region` already accept `parameter_values`; the change is internal (the engine's compute path becomes raw-aware), the public MCP surface stays the same. The agent's vocabulary mental model gets simpler (no per-camera variants).
- **TA/constraints/opaque-hex-blobs** — ADR-008 establishes that `op_params` are opaque blobs. Parametric primitives (RFC-021 Path C) already decode specific modules' params; this RFC extends the same Path C machinery to be camera-aware for the specific modules where raw metadata matters.
- **No engine PyTorch / AI dependencies** — reading raw EXIF is mechanical (libraw / exiftool / Python EXIF lib); no AI capabilities involved. Stays within `chemigram.core`'s "no AI deps" rule.

## Proposed approach

A three-part change spanning engine + vocabulary + manifest schema:

### 1. Engine reads raw metadata at apply time

`apply_entry()` gains an optional `raw_path: Path | None` parameter. When supplied, the engine reads the raw's EXIF / metadata (lazily — only if a parametric module declares it needs that data). The mechanism:

- **Per-module raw-data needs** — each parametric module in `chemigram.core.parameterize.*` declares what raw fields it requires. `temperature` declares `requires_raw_metadata = {"wb_coefficients"}`. Future `denoise` would declare `{"iso"}`, `filmic` would declare `{"histogram_summary"}`, `lens` would declare `{"lensfun_camera", "lensfun_lens"}`.
- **Lazy reader** — engine inspects the entries being applied; if any parametric module needs raw metadata, the engine reads only the requested fields. Cached per-apply so multiple parametric primitives composing on one raw don't trigger N reads.
- **Fallback when raw_path is unavailable** — synthetic inputs (the chart fixtures, tests) pass `raw_path=None`. Modules with raw-metadata requirements either (a) emit identity coefficients (no-op), (b) emit a generic-camera fallback, or (c) raise — the RFC defaults to (a) "emit identity" so synthetic fixtures don't break.

### 2. Camera-aware parametric `temperature`

`chemigram.core.parameterize.temperature.patch()` becomes camera-aware:

- At `kelvin_delta=0.0` (identity), it emits coefficients that PRESERVE the raw's EXIF daylight WB. Previously it emitted hardcoded `(1.0, 1.0, 1.0)` which OVERRODE EXIF; the new behavior reads EXIF, emits exactly those coefficients (no-op for the rendering engine).
- At non-zero `kelvin_delta` / `tint_delta`, it shifts the EXIF-derived coefficients in coefficient space using the existing linear approximation. Camera-portable because the base is per-raw, not per-authoring-camera.
- At explicit `(red_coeff, green_coeff, blue_coeff)`, behavior is unchanged from RFC-021 — the photographer is opting into raw-coefficient control, accepting camera-specific results.

### 3. L2 looks compose parametric primitives by reference

`VocabEntry` (the vocab dataclass) gains an optional `composes: tuple[CompositionRef, ...]` field. Each `CompositionRef` is `(primitive_name: str, parameter_values: dict[str, float])`. At apply time:

- For each composition ref, look up the primitive in the `VocabularyIndex`, call its parameterized apply path with the supplied parameter values + the `raw_path`. The primitive's parametric output (the XMP history items) gets spliced into the L2 entry's dtstyle history at the correct iop_order position.
- **Depth-1 only** — an L2 look composes L3 primitives; an L2 look does NOT compose another L2 look (no recursive composition in v1).
- **Load-time validation** — `VocabularyIndex` checks every `composes` reference resolves at load time, fails loud with a clear error if a primitive isn't found.

### 4. Per-module roll-out (this RFC's scope)

The RFC's IMMEDIATE scope is WB: extend Path C parametric apply to the `temperature` module to be camera-aware, then reauthor the 17 WB-touching vocabulary entries to compose the parametric `temperature` with their intended kelvin/tint deltas.

The RFC's DESIGN scope is the broader pattern: the engine API is designed once across all raw-derived modules. Future work applies the same pattern to `denoise` (per-ISO threshold), `filmic` (per-histogram tone points), `lens` (per-body lensfun id). Each gets its own implementation issue but reuses the engine machinery.

## Alternatives considered

### Option A — Strip raw-domain ops from .dtstyle blobs entirely

Edit each affected `.dtstyle` to remove its `temperature` op (and later `denoise`, `filmic`, `lens` ops). After this, applying a look adds no WB / denoise / filmic op on top of the baseline; the photographer gets whatever camera-default state darktable provides.

**Why rejected**: It replaces one false claim (foreign-WB cast on real-raw renders) with another false claim (the entry doesn't do what its name promises). `look_landscape_golden_hour` is named for its warm WB shift; if we strip the temperature op, the entry becomes "sigmoid + grade with no WB warm-up." Photographers reaching for golden-hour will get less than the name promises and won't know to compose `wb_warm_subtle` on top. The vocabulary becomes architecturally inaccurate in a different way — the inaccuracy is just less visible.

### Option C — Hybrid (strip from some entries, parameterize others)

Strip temperature from entries where WB isn't load-bearing (`look_landscape_autumn_pop`, `look_portrait_natural_skin`); parameterize the rest. Smaller engine scope; fewer dtstyles reauthored.

**Why rejected**: The architectural decision (engine raw-metadata-aware apply, manifest `composes` field) is the same regardless of whether 3 or 17 entries use it. Once Option B's machinery exists, the "should this look use parametric WB at all?" question is per-look judgment, not architecture. Mixing approaches now leaves the codebase with two patterns (atomic vs composed L2 looks) for no architectural benefit. Better to ship Option B's machinery, then make per-look decisions cleanly downstream.

### Option D — Defer (ship vocabulary as-is; document the limitation)

Leave the cast in place; add a note to the gallery and onboarding docs explaining that WB-touching entries are calibrated for a specific camera body.

**Why rejected**: The "vocabulary, not sliders" foundational discipline (PA / 02-project-concept) says a vocabulary entry's claim is portability across photographers AND across raws. Deferral entrenches a documented design defect. Phase 0 of this work (commit 8675603) already shipped a tactical mitigation — the gallery section explicitly explaining the limitation — but Phase 0 explicitly tracks this RFC as the destination, not the final answer.

### Option E — Use camera-matched fixtures

Source new visual-proof fixtures from the camera the dtstyles were authored on, so the existing coefficients work correctly on the fixture.

**Why rejected**: Doesn't solve the underlying defect — it just shifts which cameras work. Photographers using chemigram on their own raws will still hit the issue. And we don't know what camera the dtstyles were authored on (the params are an opaque blob; even if we found the author, the dtstyle generation pipeline may have introduced inconsistencies). This is a fixture-side workaround for a vocabulary-side defect.

## Trade-offs

- **Engine complexity**: `apply_entry()` gains a `raw_path` parameter and a lazy raw-metadata reader. The engine becomes mildly more stateful per-apply (the reader is cached). Mitigation: the read is cheap (small EXIF chunks, not the full raw); the cache is per-apply, not global; backwards compat means most code paths don't need to pass `raw_path`.
- **Vocabulary authoring shifts**: authoring a WB-touching L2 look becomes "describe your intent as a kelvin delta" rather than "open darktable, adjust WB sliders, export style." The kelvin-delta semantics aren't trivial — a photographer who wants "+1500K warmth at golden hour" has to know that's the right number. Mitigation: provide an authoring helper that lets photographers calibrate by example (apply at value X, render, photographer judges).
- **Some looks may reveal vocabulary-shape gaps**: Kodachrome had a specific color science that's not just kelvin+tint. Reauthoring `look_film_kodachrome` may reveal that the kelvin/tint shape isn't expressive enough. Mitigation: this RFC explicitly leaves "color-science profiles beyond kelvin+tint" out of scope; if Phase 4 surfaces the gap, file a separate RFC for it.
- **Existing photographers' personal vocabulary**: if photographers have local copies of the affected dtstyles in their personal vocabulary directory, they'll need to update to the new composing-by-reference shape. Mitigation: the change is backwards-compatible (old shape still works); we update the bundled vocabulary, photographers' personal copies keep working until they choose to migrate.
- **Test scope**: every WB-touching entry's test surface needs to extend to cover camera-aware behavior. The lab-grade fixture (sRGB chart, no EXIF) becomes one input; real-raw fixtures with different EXIFs become the camera-portability assertion.

## Open questions

1. **Engine API: pass `raw_path` through `apply_entry` directly, or fetch via a workspace lookup?**
   The synthesizer doesn't currently know about workspaces (it's a pure function: baseline + entry → XMP). Adding `raw_path` to `apply_entry` keeps it pure (no global state) but introduces a new parameter that callers must thread through. The alternative — a workspace-keyed lookup — keeps the signature stable but introduces global state. **Tentative answer**: thread `raw_path` through; purity is worth the parameter.

2. **Fallback when raw metadata is unavailable** (synthetic input, test fixtures without EXIF):
   - (a) Emit identity coefficients (no-op) — safe but tests that exercise non-identity parameters won't catch regressions
   - (b) Emit a generic-camera fallback (sRGB-as-camera) — useful for synthetic-chart tests; semantically reasonable
   - (c) Raise — strict but breaks chart-input rendering for parametric entries
   **Tentative answer**: (a) for the chart-input fixture (preserves existing chart-fixture renderings); (b) for tests that explicitly opt into a "synthetic camera" via a test fixture flag.

3. **When a composed parametric primitive isn't loaded** (vocabulary edge case):
   - Load-time error vs apply-time error?
   **Tentative answer**: load-time error. Catches typos and missing-dependency issues at vocab-load time, not at apply time.

4. **Cyclic composition / depth limits**:
   Default proposal is depth-1 (L2 composes L3 primitives, doesn't compose other L2). The RFC should explicitly say so. If we ever want L2-composes-L2 (e.g., a meta-look that bundles `look_landscape_golden_hour` + `look_landscape_atmospheric_haze`), that's a follow-up RFC.

5. **Does the RFC ship reauthored dtstyles, or is that a separate work item?**
   The RFC argues the architecture. The dtstyle reauthoring (Phase 4 of the implementation plan) is mechanical work that follows from the architecture being agreed. Reauthoring lands as a separate commit (or commits) after the engine machinery ships.

## How this closes

This RFC closes into at least 3 ADRs:

- **ADR-NNN-engine-raw-metadata-aware-apply**: documents the engine API change (`raw_path` parameter on `apply_entry`; per-module `requires_raw_metadata` declaration; lazy cached reader; fallback semantics). Closes the engine-API question.
- **ADR-NNN-manifest-composes-field**: documents the `composes` field on L2 entries (depth-1 only; load-time validation; backwards compat). Closes the manifest-schema question.
- **ADR-NNN-camera-aware-temperature-semantics**: documents the specific behavior of `chemigram.core.parameterize.temperature` post-RFC (identity preserves EXIF; deltas apply in coefficient space). Closes the per-module semantics question for the FIRST raw-derived parameter.

Future raw-derived parameters (denoise, filmic, lens) each get their own follow-up sibling ADR for their per-module semantics, all under the same engine machinery established by the first two ADRs.

The RFC stays as the rationale anchor for the whole pattern — when a photographer or contributor asks "why do these vocabulary entries reference primitives instead of inlining ops?", they read RFC-039.

## Links

- TA/components/synthesizer
- TA/contracts/vocabulary-manifest
- TA/contracts/mcp-tools
- TA/constraints/opaque-hex-blobs (ADR-008 amended by RFC-022 / ADR-081)
- Related: RFC-021 (parameterized vocabulary magnitudes), RFC-022 (Tier 2 multi-parameter), RFC-035 (parametric L2 strength)
- Implementation tracking: #131 (umbrella issue for visual-proofs Step 2 + this RFC's implementation)
- Phase 0 mitigation: commit 8675603 (gallery's "Not yet honestly verifiable" section)
