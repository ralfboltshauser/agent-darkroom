# ADR-095 — Camera-aware `filmicrgb` auto-tuned tone points

> Status · Draft (impl shipped; flips to Accepted on darkroom validation)
> Date · 2026-05-23
> TA anchor · /components/synthesizer · /constraints/opaque-hex-blobs
> Related RFC · RFC-039 (follow-up sibling under ADR-091 machinery)

## Context

The third raw-derived parameter RFC-039 named. `filmicrgb`'s black point + white point + middle gray map the raw's tonal range onto a display-referred output curve. Authored against one raw, those values don't translate to another raw with a different dynamic range — a shadow-heavy capture's black point is meaningfully different from a high-key capture's. The fixed-byte approach pre-RFC-039 produced over-clipped shadows on dark raws and washed-out highlights on bright raws.

`chemigram.core.parameterize.filmicrgb.patch()` operated on opaque bytes before this ADR. RFC-039 closes the gap by reading the raw's histogram at apply time and auto-tuning the tone points.

## Decision

`chemigram.core.parameterize.filmicrgb.patch()` gains an optional `raw_path: Path | None` keyword argument. When supplied:

- The function reads the raw's pixel histogram via `chemigram.core.exif.read_filmic_auto_points(raw_path)` — which uses rawpy to decode the raw at low resolution, computes luma percentiles via numpy, and returns suggested `black_point_source` (1st percentile), `grey_point_source` (50th percentile mapped to 18% gray), and `white_point_source` (99th percentile).
- The source values in the filmicrgb op_params are replaced with the histogram-derived points before any photographer overrides apply.
- Explicit `black_point` / `grey_point` / `white_point` overrides bypass the substitution — the caller is opting into raw-tone control.
- The output transfer function (output black/grey/white, contrast, latitude, balance shadows-highlights) stays at the source values — those are photographic-intent fields, not raw-property fields.

If `raw_path` is `None` or the raw is unreadable, behavior is unchanged: source values pass through.

## Rationale

Filmic's input tone points describe "what does this raw's tonal range look like"; the output side describes "what should the rendered image look like." Only the input side benefits from per-raw substitution — the output side is the photographer's authored taste.

Percentile-based black/white point derivation is the industry-standard heuristic for auto-exposure / auto-tone (Lightroom's Auto-button, darktable's filmic auto-tuner). The 1st / 99th percentile thresholds protect against single-pixel outliers (specular hits, dust) while still anchoring to real scene content. The 50th percentile mapped to 18% (middle gray on Zone V) anchors the curve's pivot to where photographic intuition expects it.

Reading the histogram via rawpy + numpy keeps the chemigram-core boundary clean — same `raw_path` pattern as ADR-093 / ADR-094, same lazy-reader pattern, no new dependencies.

## Alternatives considered

- **Min/max instead of percentiles**. Rejected — single-pixel outliers (sensor hot pixels, lens flare specular hits) move min/max meaningfully without representing the actual tonal range.
- **Read from the raw's matrix profile + camera-default WB**. Rejected — the camera matrix tells us about color space, not about THIS shot's tonal range. The shot-specific histogram is what filmic actually needs.
- **Defer to darktable's built-in filmic auto-tuner**. Considered — darktable has an auto-tune button. Rejected because chemigram's apply path runs through dtstyle bytes, not through interactive darktable UI; we'd need to invoke darktable headlessly to get its auto-tune output, which is a much heavier dependency than reading the raw directly via rawpy.

## Consequences

Positive:
- Filmic L2 looks (cinematic, dramatic, high-key, low-key) port across raws — the same look on a backlit landscape and a low-light portrait both anchor their tonal range to the actual scene.
- Same engine machinery as ADR-091 / ADR-093 / ADR-094.
- Output-side tone shaping (contrast, latitude) stays a photographer-intent field, preserved unchanged.

Negative:
- 50th-percentile-to-18% mapping doesn't handle scenes that legitimately want a non-Zone-V pivot (silhouettes, high-key portraits). Photographer can override via explicit `grey_point` if needed.
- Histogram computation requires a full raw decode; the lazy reader caches per workspace, so the cost is once-per-raw-per-session, not once-per-entry.

## Implementation notes

- `src/chemigram/core/parameterize/filmicrgb.py` — `patch()` accepts `raw_path` kwarg
- `src/chemigram/core/exif.py` — `read_filmic_auto_points(path)` helper (rawpy + numpy)
- `tests/unit/core/parameterize/test_filmicrgb.py` — histogram substitution tests
- Closes RFC-039 follow-up question 3 (filmic per histogram).
