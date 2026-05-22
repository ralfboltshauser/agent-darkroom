# Visual proofs — vocabulary-entry before/after gallery

> Side-by-side renders of the synthetic ColorChecker chart and the synthetic grayscale ramp, before and after each vocabulary entry. For human visual validation: does each primitive *visibly* do what its description claims?

> Renders use an **empty-history baseline** + ``--apply-custom-presets false`` so the chart passes through the darktable pipeline cleanly (input profile → output profile only, no scene-referred tone mapping). Each primitive is then applied in isolation — the only difference between baseline and per-entry renders is *that primitive's effect*. This lets you eyeball each primitive against the reference chart and verify it does what its description claims.

> Production raw renders use the full ``_baseline_v1.xmp`` with sigmoid + colorbalancergb defaults — that path is correct for raws. The empty-baseline trick is specifically for chart-input isolation testing; it would not be appropriate for editing real photographs.

> **Masked columns**: every non-mask-bound primitive renders additionally through a centered ellipse mask (``radius=0.2``, ``border=0.05``) so you can see the spatial shaping in action. The mask covers the middle 16% of the frame; anything outside it should remain at baseline. This visually demonstrates that **any** primitive can be applied through a mask — see [`mask-applicable-controls.md`](mask-applicable-controls.md) for the per-module compatibility matrix.

> **Auto-generated.** Regenerate via ``uv run python scripts/generate-visual-proofs.py`` after vocabulary changes. Commit the regenerated images alongside any vocabulary commit so the gallery and the manifest stay in sync.

> Render size: 400x400, JPEG quality default. Inputs: synthetic targets from [`tests/fixtures/reference-targets/`](https://github.com/chipi/chemigram/blob/main/tests/fixtures/reference-targets/README.md).

> **🎯 Trust basis — what the chart can and can't verify.** The synthetic chart is a legitimate fixture for entries whose touched darktable modules operate on already-developed sRGB / working-profile pixels (`exposure`, `sigmoid`, `bilat`, `vignette`, `grain`, `sharpen`, single-axis `colorbalancergb` shifts, `channelmixerrgb` in destination=grey mode, `highlights`, `toneequal`). For these — listed in the **Chart-verifiable** sections below — the after-image shows exactly what the entry does. Trust it.

> Entries that touch raw-domain modules (`temperature`, `colorequal`, `denoiseprofile`, `lens`, `hazeremoval`, `ashift`, `crop`, `retouch`, `filmicrgb`, `diffuse`) can't be honestly verified against a synthetic sRGB chart — those modules need the full raw → input-profile → working-profile pipeline. Such entries are listed in the **Needs real-raw fixture** section at the bottom, awaiting [issue #130](https://github.com/chipi/chemigram/issues/130). The principled module-level discriminator lives at `src/chemigram/core/visual_verification.py`.

> **📷 Real-raw fixtures (#130).** Entries that touch raw-domain modules render against one of two CC BY-SA 4.0 fixtures from [discuss.pixls.us](https://discuss.pixls.us): `landscape.ARW` (Sony DSC-RX10M4 — sky, foliage, water, horizon) or `portrait.ARW` (Sony ZV-E10 — indoor single subject). Routing per entry by name heuristic — skin/face/eye/portrait/subject/hair → portrait; everything else → landscape. See [`tests/fixtures/raws/README.md`](https://github.com/chipi/chemigram/blob/main/tests/fixtures/raws/README.md) for provenance, license, and attribution.

---

## Baseline reference

These are the reference targets rendered through the baseline XMP with no primitive applied — the *before* state every row below compares against.

| ColorChecker | Grayscale ramp |
|-|-|
| ![baseline ColorChecker](../visual-proofs/baseline-colorchecker.jpg) | ![baseline grayscale](../visual-proofs/baseline-grayscale.jpg) |

---

## `starter` pack — 2 entries (0 chart-verifiable, 2 needs real-raw)

### Real-raw entries

These entries touch raw-domain darktable modules (`temperature`, `colorequal`, `denoiseprofile`, `lens`, `hazeremoval`, `ashift`, `crop`, `retouch`, `filmicrgb`, or `diffuse`) — or compose looks that include one. The synthetic chart can't represent the input these modules expect; rendering against it produces structurally-misleading output. Each entry is routed to either the landscape or portrait CC BY-SA 4.0 fixture from `tests/fixtures/raws/` so the after-image is honest. Apply-path correctness is independently verified by the unit + integration + e2e test coverage.

> The following real_raw entries have no real-raw render on disk yet. Run `uv run python scripts/generate-visual-proofs.py` (without `--markdown-only`) after fetching the fixtures via `git lfs pull`.

| Entry | Routed fixture | Modules touched | What the entry does |
|-|-|-|-|
| `wb_warm_subtle` | landscape | `temperature` | Warm white balance, subtle. |
| `look_neutral` | landscape | `exposure`, `temperature` | Neutral L2 look — exposure + warm-subtle WB baseline. |

---

## `expressive-baseline` pack — 112 entries (76 chart-verifiable, 36 needs real-raw)

### Chart-verifiable entries

These entries' touched darktable modules operate on already-developed sRGB / working-profile pixels. The chart is an honest fixture; the after-image shows exactly what the entry does in that pixel domain. Trust the result.

### `grain_strength`

_Parameterized grain strength (RFC-021). Pass --value V; range [0.0, 100.0]. 8 = grain_fine-equivalent, 25 = grain_medium-equivalent, 50 = grain_heavy-equivalent. Replaces the v1.5.x discrete grain_fine / grain_medium / grain_heavy entries with a single continuous-magnitude primitive._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/grain_strength-colorchecker.jpg" alt="grain_strength ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/grain_strength-grayscale.jpg" alt="grain_strength grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/grain_strength-colorchecker-masked.jpg" alt="grain_strength ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/grain_strength-grayscale-masked.jpg" alt="grain_strength grayscale masked" width="180"> |

**On the clipped-gradient fixture** (continuous tone + blown highlights — chart designed to show this module's effect; see [`reference-targets/README.md`](https://github.com/chipi/chemigram/blob/main/tests/fixtures/reference-targets/README.md)):

| Clipped gradient (global) | Clipped gradient (centered ellipse mask) |
|-|-|
| <img src="../visual-proofs/expressive-baseline/grain_strength-clipped.jpg" alt="grain_strength clipped-gradient global" width="180"> | <img src="../visual-proofs/expressive-baseline/grain_strength-clipped-masked.jpg" alt="grain_strength clipped-gradient masked" width="180"> |

### `vignette`

_Parameterized vignette (RFC-021). Pass --value V (CLI) or value: V (MCP); range [-1.0, +1.0] (negative darkens corners; positive lifts). Replaces the v1.5.x discrete vignette_subtle / vignette_medium / vignette_heavy entries with a single continuous-magnitude primitive._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/vignette-colorchecker.jpg" alt="vignette ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/vignette-grayscale.jpg" alt="vignette grayscale global" width="180"> | _(n/a)_ | _(n/a)_ |

### `highlights_clip_threshold`

_Parameterized highlight-recovery clip threshold (RFC-021). Pass --value V; range [0.0, 2.0]: lower = more aggressive recovery (0.95 = subtle, 0.85 = strong, 0.5 = aggressive). Default 1.0 (darktable default; recovers only above 1.0). Replaces the v1.5.x discrete highlights_recovery_subtle / highlights_recovery_strong entries._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/highlights_clip_threshold-colorchecker.jpg" alt="highlights_clip_threshold ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/highlights_clip_threshold-grayscale.jpg" alt="highlights_clip_threshold grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/highlights_clip_threshold-colorchecker-masked.jpg" alt="highlights_clip_threshold ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/highlights_clip_threshold-grayscale-masked.jpg" alt="highlights_clip_threshold grayscale masked" width="180"> |

**On the clipped-gradient fixture** (continuous tone + blown highlights — chart designed to show this module's effect; see [`reference-targets/README.md`](https://github.com/chipi/chemigram/blob/main/tests/fixtures/reference-targets/README.md)):

| Clipped gradient (global) | Clipped gradient (centered ellipse mask) |
|-|-|
| <img src="../visual-proofs/expressive-baseline/highlights_clip_threshold-clipped.jpg" alt="highlights_clip_threshold clipped-gradient global" width="180"> | <img src="../visual-proofs/expressive-baseline/highlights_clip_threshold-clipped-masked.jpg" alt="highlights_clip_threshold clipped-gradient masked" width="180"> |

### `sigmoid_contrast`

_Parameterized sigmoid tone-curve contrast (RFC-021). Pass --value V (CLI) or value: V (MCP); range [0.5, 5.0] (1.0 = mild s-curve, 1.5 = darktable default / no curve change, 2.5 = aggressive s-curve). Replaces the v1.5.x discrete contrast_low / contrast_high entries with a single continuous-magnitude primitive._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/sigmoid_contrast-colorchecker.jpg" alt="sigmoid_contrast ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/sigmoid_contrast-grayscale.jpg" alt="sigmoid_contrast grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/sigmoid_contrast-colorchecker-masked.jpg" alt="sigmoid_contrast ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/sigmoid_contrast-grayscale-masked.jpg" alt="sigmoid_contrast grayscale masked" width="180"> |

### `blacks_lifted`

_Lift target black to 0.5._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/blacks_lifted-colorchecker.jpg" alt="blacks_lifted ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/blacks_lifted-grayscale.jpg" alt="blacks_lifted grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/blacks_lifted-colorchecker-masked.jpg" alt="blacks_lifted ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/blacks_lifted-grayscale-masked.jpg" alt="blacks_lifted grayscale masked" width="180"> |

### `blacks_crushed`

_Crush blacks: target 0.001 + skew -0.3._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/blacks_crushed-colorchecker.jpg" alt="blacks_crushed ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/blacks_crushed-grayscale.jpg" alt="blacks_crushed grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/blacks_crushed-colorchecker-masked.jpg" alt="blacks_crushed ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/blacks_crushed-grayscale-masked.jpg" alt="blacks_crushed grayscale masked" width="180"> |

### `whites_open`

_Open whites: target 300 (3x default)._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/whites_open-colorchecker.jpg" alt="whites_open ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/whites_open-grayscale.jpg" alt="whites_open grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/whites_open-colorchecker-masked.jpg" alt="whites_open ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/whites_open-grayscale-masked.jpg" alt="whites_open grayscale masked" width="180"> |

### `bw_sky_drama`

_B&W with sky-drama mix (red-emphasis: R 0.5 / G 0.4 / B 0.1). Lightens reds and darkens blues — classic 'red filter' landscape look that emphasizes clouds against sky. normalize_grey=true._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/bw_sky_drama-colorchecker.jpg" alt="bw_sky_drama ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/bw_sky_drama-grayscale.jpg" alt="bw_sky_drama grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/bw_sky_drama-colorchecker-masked.jpg" alt="bw_sky_drama ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/bw_sky_drama-grayscale-masked.jpg" alt="bw_sky_drama grayscale masked" width="180"> |

### `bw_foliage`

_B&W with foliage mix (green-emphasis: R 0.1 / G 0.7 / B 0.2). Lightens greens — separates foliage from neighboring tones; useful for forest / botanical work where green is the dominant subject. normalize_grey=true._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/bw_foliage-colorchecker.jpg" alt="bw_foliage ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/bw_foliage-grayscale.jpg" alt="bw_foliage grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/bw_foliage-colorchecker-masked.jpg" alt="bw_foliage ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/bw_foliage-grayscale-masked.jpg" alt="bw_foliage grayscale masked" width="180"> |

### `toneequalizer`

_Parameterized 9-band tone equalizer (RFC-022 Tier 2; most complex multi-parameter ship). Pass --param NODE=V for any of: noise, ultra_deep_blacks, deep_blacks, blacks, shadows, midtones, highlights, whites, speculars. Each in [-2.0, +2.0] EV; default 0.0. Algorithm fields preserved at darktable defaults._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/toneequalizer-colorchecker.jpg" alt="toneequalizer ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/toneequalizer-grayscale.jpg" alt="toneequalizer grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/toneequalizer-colorchecker-masked.jpg" alt="toneequalizer ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/toneequalizer-grayscale-masked.jpg" alt="toneequalizer grayscale masked" width="180"> |

### `sharpen`

_Parameterized sharpening (RFC-022 Tier 2). Pass --value V; range [0.0, 2.0] (0.0 = no sharpen, 0.5 = subtle, 1.0 = strong, 2.0 = aggressive). Radius preserved at darktable default 2.0 px, threshold at 0.5._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/sharpen-colorchecker.jpg" alt="sharpen ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/sharpen-grayscale.jpg" alt="sharpen grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/sharpen-colorchecker-masked.jpg" alt="sharpen ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/sharpen-grayscale-masked.jpg" alt="sharpen grayscale masked" width="180"> |

### `bilat_clarity_strength`

_Parameterized clarity strength on bilat / local laplacian (RFC-021). Pass --value V; range [-1.0, 4.0]. 1.5 = clarity_strong-equivalent. clarity_painterly stays as a separate discrete entry — different kind, not strength._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/bilat_clarity_strength-colorchecker.jpg" alt="bilat_clarity_strength ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/bilat_clarity_strength-grayscale.jpg" alt="bilat_clarity_strength grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/bilat_clarity_strength-colorchecker-masked.jpg" alt="bilat_clarity_strength ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/bilat_clarity_strength-grayscale-masked.jpg" alt="bilat_clarity_strength grayscale masked" width="180"> |

### `clarity_painterly`

_Soft painterly local contrast (detail 0.4)._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/clarity_painterly-colorchecker.jpg" alt="clarity_painterly ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/clarity_painterly-grayscale.jpg" alt="clarity_painterly grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/clarity_painterly-colorchecker-masked.jpg" alt="clarity_painterly ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/clarity_painterly-grayscale-masked.jpg" alt="clarity_painterly grayscale masked" width="180"> |

### `clarity_etched`

_L3 discrete kind — etched / over-defined clarity (#110). bilat_clarity_strength=2.0 (high local-contrast bite)._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/clarity_etched-colorchecker.jpg" alt="clarity_etched ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/clarity_etched-grayscale.jpg" alt="clarity_etched grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/clarity_etched-colorchecker-masked.jpg" alt="clarity_etched ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/clarity_etched-grayscale-masked.jpg" alt="clarity_etched grayscale masked" width="180"> |

### `clarity_dreamy`

_L3 discrete kind — soft / dreamy clarity (#110). bilat_clarity_strength=-0.5 (negative bite — softens local contrast)._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/clarity_dreamy-colorchecker.jpg" alt="clarity_dreamy ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/clarity_dreamy-grayscale.jpg" alt="clarity_dreamy grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/clarity_dreamy-colorchecker-masked.jpg" alt="clarity_dreamy ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/clarity_dreamy-grayscale-masked.jpg" alt="clarity_dreamy grayscale masked" width="180"> |

### `sharpen_edge_only`

_L3 discrete kind — edge-only sharpening (#110). amount=0.6 with default radius (2.0 px) and threshold (0.5). Threshold gates sharpening to detected edges only._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/sharpen_edge_only-colorchecker.jpg" alt="sharpen_edge_only ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/sharpen_edge_only-grayscale.jpg" alt="sharpen_edge_only grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/sharpen_edge_only-colorchecker-masked.jpg" alt="sharpen_edge_only ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/sharpen_edge_only-grayscale-masked.jpg" alt="sharpen_edge_only grayscale masked" width="180"> |

### `sharpen_overall`

_L3 discrete kind — whole-image sharpening with bite (#110). amount=1.2 (strong)._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/sharpen_overall-colorchecker.jpg" alt="sharpen_overall ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/sharpen_overall-grayscale.jpg" alt="sharpen_overall grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/sharpen_overall-colorchecker-masked.jpg" alt="sharpen_overall ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/sharpen_overall-grayscale-masked.jpg" alt="sharpen_overall grayscale masked" width="180"> |

### `vignette_subtle`

_L3 discrete kind — gentle peripheral darkening (#110). brightness=-0.15._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/vignette_subtle-colorchecker.jpg" alt="vignette_subtle ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/vignette_subtle-grayscale.jpg" alt="vignette_subtle grayscale global" width="180"> | _(n/a)_ | _(n/a)_ |

### `vignette_strong`

_L3 discrete kind — pronounced peripheral darkening (#110). brightness=-0.5._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/vignette_strong-colorchecker.jpg" alt="vignette_strong ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/vignette_strong-grayscale.jpg" alt="vignette_strong grayscale global" width="180"> | _(n/a)_ | _(n/a)_ |

### `exposure`

_Parameterized exposure compensation (RFC-021). Pass --value V (CLI) or value: V (MCP) in EV stops; range [-3.0, +3.0]. Replaces the v1.5.x discrete expo_+0.3 / expo_+0.5 / expo_-0.3 / expo_-0.5 / shadows_global_+/- entries with a single continuous-magnitude primitive._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/exposure-colorchecker.jpg" alt="exposure ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/exposure-grayscale.jpg" alt="exposure grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/exposure-colorchecker-masked.jpg" alt="exposure ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/exposure-grayscale-masked.jpg" alt="exposure grayscale masked" width="180"> |

### `saturation_global`

_Parameterized global saturation in colorbalancergb (RFC-021). Pass --value V (CLI) or value: V (MCP); range [-1.0, +1.0] (-1.0 = fully desaturated / monochrome; +0.5 = strong boost). Replaces the v1.5.x discrete sat_kill / sat_boost_moderate / sat_boost_strong entries with a single continuous-magnitude primitive._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/saturation_global-colorchecker.jpg" alt="saturation_global ColorChecker global" width="180"> | _(n/a)_ | <img src="../visual-proofs/expressive-baseline/saturation_global-colorchecker-masked.jpg" alt="saturation_global ColorChecker masked" width="180"> | _(n/a)_ |

### `vibrance`

_Parameterized vibrance on colorbalancergb (RFC-022 Tier 2). Pass --value V; range [-1.0, +1.0]. 0.3 = vibrance_+0.3-equivalent. Vibrance protects already-saturated pixels — gentler chroma push than saturation_global. Replaces v1.5.x vibrance_+0.3._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/vibrance-colorchecker.jpg" alt="vibrance ColorChecker global" width="180"> | _(n/a)_ | <img src="../visual-proofs/expressive-baseline/vibrance-colorchecker-masked.jpg" alt="vibrance ColorChecker masked" width="180"> | _(n/a)_ |

### `chroma_global`

_Parameterized global chroma on colorbalancergb (RFC-022 Tier 2). Pass --value V; range [-1.0, +1.0]. Less saturated-pixel protection than vibrance, more aggressive than saturation_global at equal magnitudes._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/chroma_global-colorchecker.jpg" alt="chroma_global ColorChecker global" width="180"> | _(n/a)_ | <img src="../visual-proofs/expressive-baseline/chroma_global-colorchecker-masked.jpg" alt="chroma_global ColorChecker masked" width="180"> | _(n/a)_ |

### `hue_angle`

_Parameterized global hue rotation on colorbalancergb (RFC-022 Tier 2). Pass --value V in degrees; range [-180.0, +180.0]. Rotates every pixel's hue around the color wheel without changing saturation or luminance._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/hue_angle-colorchecker.jpg" alt="hue_angle ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/hue_angle-grayscale.jpg" alt="hue_angle grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/hue_angle-colorchecker-masked.jpg" alt="hue_angle ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/hue_angle-grayscale-masked.jpg" alt="hue_angle grayscale masked" width="180"> |

### `brilliance_global`

_Parameterized global brilliance on colorbalancergb (RFC-022 Tier 2 / #86). Pass --value V; range [-1.0, +1.0]. Brilliance shapes per-zone luminance — the global axis moves all zones together. Per-zone variants (highlights/midtones/shadows) target specific tonal ranges._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/brilliance_global-colorchecker.jpg" alt="brilliance_global ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/brilliance_global-grayscale.jpg" alt="brilliance_global grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/brilliance_global-colorchecker-masked.jpg" alt="brilliance_global ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/brilliance_global-grayscale-masked.jpg" alt="brilliance_global grayscale masked" width="180"> |

### `brilliance_highlights`

_Parameterized highlight-zone brilliance on colorbalancergb (RFC-022 Tier 2 / #86). Pass --value V; range [-1.0, +1.0]. Targets only the highlight tonal zone — useful for selectively brightening or compressing high-key areas without affecting shadows / midtones._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/brilliance_highlights-colorchecker.jpg" alt="brilliance_highlights ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/brilliance_highlights-grayscale.jpg" alt="brilliance_highlights grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/brilliance_highlights-colorchecker-masked.jpg" alt="brilliance_highlights ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/brilliance_highlights-grayscale-masked.jpg" alt="brilliance_highlights grayscale masked" width="180"> |

### `brilliance_midtones`

_Parameterized midtone-zone brilliance on colorbalancergb (RFC-022 Tier 2 / #86). Pass --value V; range [-1.0, +1.0]. Targets only the midtone tonal zone — selectively shapes the body of the tonal distribution._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/brilliance_midtones-colorchecker.jpg" alt="brilliance_midtones ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/brilliance_midtones-grayscale.jpg" alt="brilliance_midtones grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/brilliance_midtones-colorchecker-masked.jpg" alt="brilliance_midtones ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/brilliance_midtones-grayscale-masked.jpg" alt="brilliance_midtones grayscale masked" width="180"> |

### `brilliance_shadows`

_Parameterized shadow-zone brilliance on colorbalancergb (RFC-022 Tier 2 / #86). Pass --value V; range [-1.0, +1.0]. Targets only the shadow tonal zone — selectively lifts or deepens dark areas without affecting highlights / midtones._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/brilliance_shadows-colorchecker.jpg" alt="brilliance_shadows ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/brilliance_shadows-grayscale.jpg" alt="brilliance_shadows grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/brilliance_shadows-colorchecker-masked.jpg" alt="brilliance_shadows ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/brilliance_shadows-grayscale-masked.jpg" alt="brilliance_shadows grayscale masked" width="180"> |

### `hue_shadows`

_Parameterized per-zone hue rotation for shadows (#91 Bucket A.5; Lightroom Color Grading shadows wheel). Pass --value V; range [0.0, 360.0] degrees. Default 0.0._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/hue_shadows-colorchecker.jpg" alt="hue_shadows ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/hue_shadows-grayscale.jpg" alt="hue_shadows grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/hue_shadows-colorchecker-masked.jpg" alt="hue_shadows ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/hue_shadows-grayscale-masked.jpg" alt="hue_shadows grayscale masked" width="180"> |

### `hue_midtones`

_Parameterized per-zone hue rotation for midtones (#91 Bucket A.5; Lightroom Color Grading midtones wheel). Pass --value V; range [0.0, 360.0] degrees. Default 0.0._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/hue_midtones-colorchecker.jpg" alt="hue_midtones ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/hue_midtones-grayscale.jpg" alt="hue_midtones grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/hue_midtones-colorchecker-masked.jpg" alt="hue_midtones ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/hue_midtones-grayscale-masked.jpg" alt="hue_midtones grayscale masked" width="180"> |

### `hue_highlights`

_Parameterized per-zone hue rotation for highlights (#91 Bucket A.5; Lightroom Color Grading highlights wheel). Pass --value V; range [0.0, 360.0] degrees. Default 0.0._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/hue_highlights-colorchecker.jpg" alt="hue_highlights ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/hue_highlights-grayscale.jpg" alt="hue_highlights grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/hue_highlights-colorchecker-masked.jpg" alt="hue_highlights ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/hue_highlights-grayscale-masked.jpg" alt="hue_highlights grayscale masked" width="180"> |

### `saturation_shadows`

_Parameterized per-zone saturation for shadows (#91 Bucket A.5; pairs with hue_shadows for full Lightroom shadow-zone color-grading control). Pass --value V; range [-1.0, +1.0]._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/saturation_shadows-colorchecker.jpg" alt="saturation_shadows ColorChecker global" width="180"> | _(n/a)_ | <img src="../visual-proofs/expressive-baseline/saturation_shadows-colorchecker-masked.jpg" alt="saturation_shadows ColorChecker masked" width="180"> | _(n/a)_ |

### `saturation_midtones`

_Parameterized per-zone saturation for midtones (#91 Bucket A.5). Pass --value V; range [-1.0, +1.0]._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/saturation_midtones-colorchecker.jpg" alt="saturation_midtones ColorChecker global" width="180"> | _(n/a)_ | <img src="../visual-proofs/expressive-baseline/saturation_midtones-colorchecker-masked.jpg" alt="saturation_midtones ColorChecker masked" width="180"> | _(n/a)_ |

### `saturation_highlights`

_Parameterized per-zone saturation for highlights (#91 Bucket A.5). Pass --value V; range [-1.0, +1.0]._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/saturation_highlights-colorchecker.jpg" alt="saturation_highlights ColorChecker global" width="180"> | _(n/a)_ | <img src="../visual-proofs/expressive-baseline/saturation_highlights-colorchecker-masked.jpg" alt="saturation_highlights ColorChecker masked" width="180"> | _(n/a)_ |

### `shadows_weight`

_Parameterized shadow-zone falloff weight (#91 Bucket A.5; Lightroom Color Grading 'Blending' bottom). Pass --value V; range [0.0, 4.0]; default 1.0. Higher = more aggressive zone overlap._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/shadows_weight-colorchecker.jpg" alt="shadows_weight ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/shadows_weight-grayscale.jpg" alt="shadows_weight grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/shadows_weight-colorchecker-masked.jpg" alt="shadows_weight ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/shadows_weight-grayscale-masked.jpg" alt="shadows_weight grayscale masked" width="180"> |

### `highlights_weight`

_Parameterized highlights-zone falloff weight (#91 Bucket A.5; Lightroom Color Grading 'Blending' top). Pass --value V; range [0.0, 4.0]; default 1.0._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/highlights_weight-colorchecker.jpg" alt="highlights_weight ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/highlights_weight-grayscale.jpg" alt="highlights_weight grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/highlights_weight-colorchecker-masked.jpg" alt="highlights_weight ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/highlights_weight-grayscale-masked.jpg" alt="highlights_weight grayscale masked" width="180"> |

### `white_fulcrum`

_Parameterized shadow/highlight balance point (#91 Bucket A.5; Lightroom Color Grading 'Balance' slider). Pass --value V; range [-2.0, 2.0]; default 0.0 (neutral midpoint). Negative shifts the split toward shadows; positive toward highlights._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/white_fulcrum-colorchecker.jpg" alt="white_fulcrum ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/white_fulcrum-grayscale.jpg" alt="white_fulcrum grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/white_fulcrum-colorchecker-masked.jpg" alt="white_fulcrum ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/white_fulcrum-grayscale-masked.jpg" alt="white_fulcrum grayscale masked" width="180"> |

### `grade_shadows_warm`

_Warm shadows (orange tint, hue 30 deg, chroma 0.3)._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/grade_shadows_warm-colorchecker.jpg" alt="grade_shadows_warm ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_shadows_warm-grayscale.jpg" alt="grade_shadows_warm grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_shadows_warm-colorchecker-masked.jpg" alt="grade_shadows_warm ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_shadows_warm-grayscale-masked.jpg" alt="grade_shadows_warm grayscale masked" width="180"> |

### `grade_shadows_cool`

_Cool shadows (blue tint, hue 210 deg, chroma 0.3)._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/grade_shadows_cool-colorchecker.jpg" alt="grade_shadows_cool ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_shadows_cool-grayscale.jpg" alt="grade_shadows_cool grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_shadows_cool-colorchecker-masked.jpg" alt="grade_shadows_cool ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_shadows_cool-grayscale-masked.jpg" alt="grade_shadows_cool grayscale masked" width="180"> |

### `grade_highlights_warm`

_Warm highlights (orange tint, hue 45 deg, chroma 0.2)._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/grade_highlights_warm-colorchecker.jpg" alt="grade_highlights_warm ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_highlights_warm-grayscale.jpg" alt="grade_highlights_warm grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_highlights_warm-colorchecker-masked.jpg" alt="grade_highlights_warm ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_highlights_warm-grayscale-masked.jpg" alt="grade_highlights_warm grayscale masked" width="180"> |

### `grade_highlights_cool`

_Cool highlights (blue tint, hue 200 deg, chroma 0.2)._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/grade_highlights_cool-colorchecker.jpg" alt="grade_highlights_cool ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_highlights_cool-grayscale.jpg" alt="grade_highlights_cool grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_highlights_cool-colorchecker-masked.jpg" alt="grade_highlights_cool ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_highlights_cool-grayscale-masked.jpg" alt="grade_highlights_cool grayscale masked" width="180"> |

### `grade_midtones_warm`

_Warm midtones (orange tint, hue 35 deg, chroma 0.25)._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/grade_midtones_warm-colorchecker.jpg" alt="grade_midtones_warm ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_midtones_warm-grayscale.jpg" alt="grade_midtones_warm grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_midtones_warm-colorchecker-masked.jpg" alt="grade_midtones_warm ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_midtones_warm-grayscale-masked.jpg" alt="grade_midtones_warm grayscale masked" width="180"> |

### `grade_midtones_cool`

_Cool midtones (blue tint, hue 215 deg, chroma 0.25)._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/grade_midtones_cool-colorchecker.jpg" alt="grade_midtones_cool ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_midtones_cool-grayscale.jpg" alt="grade_midtones_cool grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_midtones_cool-colorchecker-masked.jpg" alt="grade_midtones_cool ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_midtones_cool-grayscale-masked.jpg" alt="grade_midtones_cool grayscale masked" width="180"> |

### `grade_split_warm_cool`

_L3 discrete kind — classic split-toning composite (#110). Combines grade_shadows_cool (blue tint, hue 210 deg / chroma 0.3) with grade_highlights_warm (orange tint, hue 45 deg / chroma 0.2) in one entry. The signature 'cinematic' split-tone in a single primitive._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/grade_split_warm_cool-colorchecker.jpg" alt="grade_split_warm_cool ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_split_warm_cool-grayscale.jpg" alt="grade_split_warm_cool grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_split_warm_cool-colorchecker-masked.jpg" alt="grade_split_warm_cool ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/grade_split_warm_cool-grayscale-masked.jpg" alt="grade_split_warm_cool grayscale masked" width="180"> |

### `chroma_boost_shadows`

_Boost shadow chroma +0.3._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/chroma_boost_shadows-colorchecker.jpg" alt="chroma_boost_shadows ColorChecker global" width="180"> | _(n/a)_ | <img src="../visual-proofs/expressive-baseline/chroma_boost_shadows-colorchecker-masked.jpg" alt="chroma_boost_shadows ColorChecker masked" width="180"> | _(n/a)_ |

### `chroma_boost_midtones`

_Boost mid-tone chroma +0.3._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/chroma_boost_midtones-colorchecker.jpg" alt="chroma_boost_midtones ColorChecker global" width="180"> | _(n/a)_ | <img src="../visual-proofs/expressive-baseline/chroma_boost_midtones-colorchecker-masked.jpg" alt="chroma_boost_midtones ColorChecker masked" width="180"> | _(n/a)_ |

### `chroma_boost_highlights`

_Boost highlight chroma +0.3._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/chroma_boost_highlights-colorchecker.jpg" alt="chroma_boost_highlights ColorChecker global" width="180"> | _(n/a)_ | <img src="../visual-proofs/expressive-baseline/chroma_boost_highlights-colorchecker-masked.jpg" alt="chroma_boost_highlights ColorChecker masked" width="180"> | _(n/a)_ |

### `gradient_top_dampen_highlights` 🟦 mask-bound

_Dampen top-half highlights via -0.5 EV through a top-bright gradient._

| ColorChecker | Grayscale ramp |
|-|-|
| <img src="../visual-proofs/expressive-baseline/gradient_top_dampen_highlights-colorchecker.jpg" alt="gradient_top_dampen_highlights ColorChecker" width="180"> | <img src="../visual-proofs/expressive-baseline/gradient_top_dampen_highlights-grayscale.jpg" alt="gradient_top_dampen_highlights grayscale" width="180"> |

### `gradient_bottom_lift_shadows` 🟦 mask-bound

_Lift bottom-half shadows via +0.4 EV through a bottom-bright gradient._

| ColorChecker | Grayscale ramp |
|-|-|
| <img src="../visual-proofs/expressive-baseline/gradient_bottom_lift_shadows-colorchecker.jpg" alt="gradient_bottom_lift_shadows ColorChecker" width="180"> | <img src="../visual-proofs/expressive-baseline/gradient_bottom_lift_shadows-grayscale.jpg" alt="gradient_bottom_lift_shadows grayscale" width="180"> |

### `radial_subject_lift` 🟦 mask-bound

_Lift +0.6 EV in a centered radial mask region (subject emphasis)._

| ColorChecker | Grayscale ramp |
|-|-|
| <img src="../visual-proofs/expressive-baseline/radial_subject_lift-colorchecker.jpg" alt="radial_subject_lift ColorChecker" width="180"> | <img src="../visual-proofs/expressive-baseline/radial_subject_lift-grayscale.jpg" alt="radial_subject_lift grayscale" width="180"> |

### `rectangle_subject_band_dim` 🟦 mask-bound

_Dim -0.3 EV in a horizontal mid-band rectangle (de-emphasize a horizon line)._

| ColorChecker | Grayscale ramp |
|-|-|
| <img src="../visual-proofs/expressive-baseline/rectangle_subject_band_dim-colorchecker.jpg" alt="rectangle_subject_band_dim ColorChecker" width="180"> | <img src="../visual-proofs/expressive-baseline/rectangle_subject_band_dim-grayscale.jpg" alt="rectangle_subject_band_dim grayscale" width="180"> |

### `look_portrait`

_L2 look — gentle skin-protective composition. exposure +0.2 EV, sigmoid_contrast 1.2 (soft s-curve), colorbalancergb saturation_global=-0.1 + vibrance=+0.2 (mild chroma push that protects saturated pixels). Targets portraiture; avoid stacking with aggressive contrast or clarity._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/look_portrait-colorchecker.jpg" alt="look_portrait ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_portrait-grayscale.jpg" alt="look_portrait grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_portrait-colorchecker-masked.jpg" alt="look_portrait ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/look_portrait-grayscale-masked.jpg" alt="look_portrait grayscale masked" width="180"> |

### `look_landscape`

_L2 look — vibrant dramatic landscape composition. sigmoid_contrast 2.0 (strong s-curve), colorbalancergb saturation_global=+0.3 + vibrance=+0.2, bilat_clarity_strength 1.0 (definite local-contrast pop). Aggressive — pull back via sigmoid to ~1.5 if it feels harsh._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/look_landscape-colorchecker.jpg" alt="look_landscape ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_landscape-grayscale.jpg" alt="look_landscape grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_landscape-colorchecker-masked.jpg" alt="look_landscape ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/look_landscape-grayscale-masked.jpg" alt="look_landscape grayscale masked" width="180"> |

### `look_cinematic_teal_orange`

_L2 look — Hollywood blockbuster teal-and-orange grade (#104). sigmoid_contrast 1.4 + colorbalancergb hue_shadows=210 deg / saturation_shadows=+0.3 (teal) + hue_highlights=30 deg / saturation_highlights=+0.2 (orange) + saturation_global=+0.1._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/look_cinematic_teal_orange-colorchecker.jpg" alt="look_cinematic_teal_orange ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_cinematic_teal_orange-grayscale.jpg" alt="look_cinematic_teal_orange grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_cinematic_teal_orange-colorchecker-masked.jpg" alt="look_cinematic_teal_orange ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/look_cinematic_teal_orange-grayscale-masked.jpg" alt="look_cinematic_teal_orange grayscale masked" width="180"> |

### `look_high_key_portrait`

_L2 look — high-key portrait (Adler-style fashion / commercial). exposure +0.3 EV + sigmoid_contrast 0.8 (soft s-curve) + colorbalancergb brilliance_highlights=+0.2 + saturation_global=-0.05 (retains skin saturation while reducing global). For magazine / beauty work where bright skin tones drive the look. Compose with skin_uniformity for a complete editorial pass._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/look_high_key_portrait-colorchecker.jpg" alt="look_high_key_portrait ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_high_key_portrait-grayscale.jpg" alt="look_high_key_portrait grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_high_key_portrait-colorchecker-masked.jpg" alt="look_high_key_portrait ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/look_high_key_portrait-grayscale-masked.jpg" alt="look_high_key_portrait grayscale masked" width="180"> |

### `look_low_key_portrait`

_L2 look — low-key portrait (Tucker / chiaroscuro voice). exposure -0.2 EV + sigmoid_contrast 1.8 (strong s-curve) + colorbalancergb brilliance_shadows=-0.3 + saturation_global=-0.10. For dramatic editorial / character portraits where deep shadows carry the mood. Compose with look_portrait_split_tone_moody for a more cinematic grade._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/look_low_key_portrait-colorchecker.jpg" alt="look_low_key_portrait ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_low_key_portrait-grayscale.jpg" alt="look_low_key_portrait grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_low_key_portrait-colorchecker-masked.jpg" alt="look_low_key_portrait ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/look_low_key_portrait-grayscale-masked.jpg" alt="look_low_key_portrait grayscale masked" width="180"> |

### `look_moody_dramatic`

_L2 look — moody / dramatic editorial (#104). sigmoid_contrast 2.0 (strong s-curve) + colorbalancergb saturation_global=-0.3 + vibrance=+0.1 + grain_strength=25._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/look_moody_dramatic-colorchecker.jpg" alt="look_moody_dramatic ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_moody_dramatic-grayscale.jpg" alt="look_moody_dramatic grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_moody_dramatic-colorchecker-masked.jpg" alt="look_moody_dramatic ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/look_moody_dramatic-grayscale-masked.jpg" alt="look_moody_dramatic grayscale masked" width="180"> |

### `look_subject_lift_dark_only` 🟦 mask-bound

_L2 look — lift only the *dark pixels* in a centered subject region. Drawn ellipse around the subject + luminance shadows filter. Composes RFC-029 drawn mask + RFC-024 range_filter. The user's mental model: 'in this drawn mask, only affect the dark pixels.'_

| ColorChecker | Grayscale ramp |
|-|-|
| <img src="../visual-proofs/expressive-baseline/look_subject_lift_dark_only-colorchecker.jpg" alt="look_subject_lift_dark_only ColorChecker" width="180"> | <img src="../visual-proofs/expressive-baseline/look_subject_lift_dark_only-grayscale.jpg" alt="look_subject_lift_dark_only grayscale" width="180"> |

### `look_sky_blue_deepen` 🟦 mask-bound

_L2 look — deepen sky blues in the upper half. Drawn gradient (top half) + color_h filter on cyan-blue range. Composes RFC-029 + RFC-024. Real-world workflow: dramatic sky without affecting foreground or non-blue elements above the horizon._

| ColorChecker | Grayscale ramp |
|-|-|
| <img src="../visual-proofs/expressive-baseline/look_sky_blue_deepen-colorchecker.jpg" alt="look_sky_blue_deepen ColorChecker" width="180"> | <img src="../visual-proofs/expressive-baseline/look_sky_blue_deepen-grayscale.jpg" alt="look_sky_blue_deepen grayscale" width="180"> |

### `look_horizon_warm_glow` 🟦 mask-bound

_L2 look — lift warm tones near the horizon. Horizontal gradient anchored at midline + color_h filter on warm tones (orange/red). Sunset / golden-hour enhancement without affecting cool tones._

| ColorChecker | Grayscale ramp |
|-|-|
| <img src="../visual-proofs/expressive-baseline/look_horizon_warm_glow-colorchecker.jpg" alt="look_horizon_warm_glow ColorChecker" width="180"> | <img src="../visual-proofs/expressive-baseline/look_horizon_warm_glow-grayscale.jpg" alt="look_horizon_warm_glow grayscale" width="180"> |

### `look_subject_brighten_highlights` 🟦 mask-bound

_L2 look — brighten only the bright pixels in the subject region. Drawn ellipse + luminance highlights filter. Catchlights, skin highlights, sparkle without blowing out midtones._

| ColorChecker | Grayscale ramp |
|-|-|
| <img src="../visual-proofs/expressive-baseline/look_subject_brighten_highlights-colorchecker.jpg" alt="look_subject_brighten_highlights ColorChecker" width="180"> | <img src="../visual-proofs/expressive-baseline/look_subject_brighten_highlights-grayscale.jpg" alt="look_subject_brighten_highlights grayscale" width="180"> |

### `look_dark_pixels_global_lift` 🟦 mask-bound

_L2 look — lift dark pixels globally (no spatial mask). Pure parametric range_filter — luminance shadows. Useful when the intent is purely tonal: 'open up all the dark areas in the image, regardless of where they are.' Demonstrates the parametric-only path of RFC-024 / ADR-085._

| ColorChecker | Grayscale ramp |
|-|-|
| <img src="../visual-proofs/expressive-baseline/look_dark_pixels_global_lift-colorchecker.jpg" alt="look_dark_pixels_global_lift ColorChecker" width="180"> | <img src="../visual-proofs/expressive-baseline/look_dark_pixels_global_lift-grayscale.jpg" alt="look_dark_pixels_global_lift grayscale" width="180"> |

### `skin_smooth_painterly` 🟦 mask-bound

_Approximate frequency separation for skin smoothing (Portrait Gap #4, cheap variant). Reduces local contrast (texture-band frequency) within the skin region — the color band stays untouched. Pass --value V or --param clarity_strength=V; range [-1.0, 4.0], typical -0.3 to -0.7 for natural smoothing. -0.5 default. Pre-baked with mask_skin_region. **Not** Photoshop's true frequency separation (band decomposition); approximation via bilat softening on a hue-masked region. Compose orthogonally with skin_uniformity (color-band uniformity) for the full skin-uniformity-plus-smoothing move. For sharper precision, override mask_spec via render_preview + LLM-vision (see docs/guides/llm-vision-for-masks.md Pattern 7)._

| ColorChecker | Grayscale ramp |
|-|-|
| <img src="../visual-proofs/expressive-baseline/skin_smooth_painterly-colorchecker.jpg" alt="skin_smooth_painterly ColorChecker" width="180"> | <img src="../visual-proofs/expressive-baseline/skin_smooth_painterly-grayscale.jpg" alt="skin_smooth_painterly grayscale" width="180"> |

### `look_portrait_editorial`

_Magazine / fashion editorial grade. Punchier sigmoid contrast (1.6), global saturation pull-back (-0.10) — counterintuitive but the move Adler/Woloszynowicz reach for; reduced overall sat lets the split-tone read. Cool-shadows + warm-highlights split (hue_shadows=210, hue_highlights=45). Compose with skin_uniformity if skin patches fight the grade._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/look_portrait_editorial-colorchecker.jpg" alt="look_portrait_editorial ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_portrait_editorial-grayscale.jpg" alt="look_portrait_editorial grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_portrait_editorial-colorchecker-masked.jpg" alt="look_portrait_editorial ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/look_portrait_editorial-grayscale-masked.jpg" alt="look_portrait_editorial grayscale masked" width="180"> |

### `look_portrait_background_dim` 🟦 mask-bound

_Dim and de-saturate the background to push the subject forward. Exposure -0.4 EV + saturation_global -0.15. Pre-baked with mask_subject + invert: true (RFC-034) — the photographer doesn't have to construct an inverse-subject mask manually. The parametric fallback for mask_subject is coarse (midtone luminance + center-bias); for clean subject vs. background separation override the mask_spec at apply time with a manually-drawn inverted ellipse, or escalate via render_preview + LLM-vision construction (llm-vision-for-masks.md Pattern 7) for a path-form subject mask._

| ColorChecker | Grayscale ramp |
|-|-|
| <img src="../visual-proofs/expressive-baseline/look_portrait_background_dim-colorchecker.jpg" alt="look_portrait_background_dim ColorChecker" width="180"> | <img src="../visual-proofs/expressive-baseline/look_portrait_background_dim-grayscale.jpg" alt="look_portrait_background_dim grayscale" width="180"> |

### `look_portrait_split_tone_moody`

_Cinematic split-tone portrait — cool blue shadows (hue 210, sat 0.30) + warm orange highlights (hue 45, sat 0.20), sigmoid contrast 1.4. Stronger split than look_portrait_editorial; some photographers (Adler) consider this 'fashion-only' rather than a general portrait move. Borderline survey candidate — ships, but exercise judgment._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/look_portrait_split_tone_moody-colorchecker.jpg" alt="look_portrait_split_tone_moody ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_portrait_split_tone_moody-grayscale.jpg" alt="look_portrait_split_tone_moody grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_portrait_split_tone_moody-colorchecker-masked.jpg" alt="look_portrait_split_tone_moody ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/look_portrait_split_tone_moody-grayscale-masked.jpg" alt="look_portrait_split_tone_moody grayscale masked" width="180"> |

### `look_landscape_grand_vista`

_Heaton/PureRAW-style grand vista. Sigmoid contrast 1.4, mildly warm shadows (hue 30, sat 0.10), vibrance +0.10, bilat clarity_strength 0.5. The chemigram shape of LR's adaptive sky + foreground lift workflow rendered globally; for sky-specific work compose with look_landscape_sky_enhance instead._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/look_landscape_grand_vista-colorchecker.jpg" alt="look_landscape_grand_vista ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_landscape_grand_vista-grayscale.jpg" alt="look_landscape_grand_vista grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_landscape_grand_vista-colorchecker-masked.jpg" alt="look_landscape_grand_vista ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/look_landscape_grand_vista-grayscale-masked.jpg" alt="look_landscape_grand_vista grayscale masked" width="180"> |

### `look_landscape_intimate_quiet`

_Marino-style intimate / small-scene restraint. Very gentle sigmoid contrast (1.05), saturation pulled back (-0.10), bilat softened (clarity_strength -0.3 — opposite of clarity boost). The defining stylistic choice for forest interiors, abstract details, and any scene where drama would betray the subject. Applies LESS than the baseline does, deliberately._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/look_landscape_intimate_quiet-colorchecker.jpg" alt="look_landscape_intimate_quiet ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_landscape_intimate_quiet-grayscale.jpg" alt="look_landscape_intimate_quiet grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_landscape_intimate_quiet-colorchecker-masked.jpg" alt="look_landscape_intimate_quiet ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/look_landscape_intimate_quiet-grayscale-masked.jpg" alt="look_landscape_intimate_quiet grayscale masked" width="180"> |

### `look_landscape_dramatic_moody`

_Page/Adamus-style dramatic atmospheric. Sigmoid contrast 1.7 (strong), cool shadows (hue 210, sat 0.20) + warm highlights (hue 30, sat 0.15), bilat clarity_strength 0.6. The dramatic counterpart to intimate_quiet — for stormy skies, rugged terrain, and weather drama. Pair with mask_luminosity_brightest_quartile darkening for stormy-cloud emphasis._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/look_landscape_dramatic_moody-colorchecker.jpg" alt="look_landscape_dramatic_moody ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_landscape_dramatic_moody-grayscale.jpg" alt="look_landscape_dramatic_moody grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_landscape_dramatic_moody-colorchecker-masked.jpg" alt="look_landscape_dramatic_moody ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/look_landscape_dramatic_moody-grayscale-masked.jpg" alt="look_landscape_dramatic_moody grayscale masked" width="180"> |

### `look_landscape_sky_enhance` 🟦 mask-bound

_Sky-targeted enhancement (Heaton 'adaptive sky' shape). Cool-tone highlights shift (hue 200, sat 0.15) + slight vibrance (+0.05). Pre-baked with mask_sky (RFC-032) so the move scopes to the sky region automatically. **Compose, don't replace** — this is a focused enhancement to stack on top of any landscape look. For complex skies (sunsets, partial clouds, trees protruding into sky), override mask_spec with a constructed path mask via render_preview + LLM-vision (llm-vision-for-masks.md Pattern 7)._

| ColorChecker | Grayscale ramp |
|-|-|
| <img src="../visual-proofs/expressive-baseline/look_landscape_sky_enhance-colorchecker.jpg" alt="look_landscape_sky_enhance ColorChecker" width="180"> | <img src="../visual-proofs/expressive-baseline/look_landscape_sky_enhance-grayscale.jpg" alt="look_landscape_sky_enhance grayscale" width="180"> |

### `look_landscape_water_silk` 🟦 mask-bound

_Water surfaces — silky water in long-exposure work, glassy lakes. Bilat clarity_strength -0.4 (smooths the texture, OPPOSITE of clarity), cool-tone shadows (hue 200, sat 0.10), vibrance +0.05. Pre-baked with mask_water_blue_cyan so the smoothing scopes to water without affecting rocks, foliage, or sky. Reduces clarity selectively to enhance the smoothness photographers spent shutter-time creating._

| ColorChecker | Grayscale ramp |
|-|-|
| <img src="../visual-proofs/expressive-baseline/look_landscape_water_silk-colorchecker.jpg" alt="look_landscape_water_silk ColorChecker" width="180"> | <img src="../visual-proofs/expressive-baseline/look_landscape_water_silk-grayscale.jpg" alt="look_landscape_water_silk grayscale" width="180"> |

### `look_wildlife_subject_sharpen` 🟦 mask-bound

_Subject-isolated wildlife sharpening — feather / fur / scale detail lifted ON THE SUBJECT only via mask_subject (RFC-032). Sharpen amount 2.0 + bilat clarity 0.3. The chemigram realization of LR's Subject-mask + Sharpening + selective Texture pattern (Sweileh, Matiash, Dale, Gardner all reach for this). Compose with mask_subject in the manifest; pair with look_wildlife_background_blur for compositional subject emphasis._

| ColorChecker | Grayscale ramp |
|-|-|
| <img src="../visual-proofs/expressive-baseline/look_wildlife_subject_sharpen-colorchecker.jpg" alt="look_wildlife_subject_sharpen ColorChecker" width="180"> | <img src="../visual-proofs/expressive-baseline/look_wildlife_subject_sharpen-grayscale.jpg" alt="look_wildlife_subject_sharpen grayscale" width="180"> |

### `look_wildlife_background_blur` 🟦 mask-bound

_Background softening for wildlife — bilat clarity_strength -0.5 (the softening direction; opposite of clarity boost). Pre-baked with mask_subject + invert: true (RFC-034) so the softening scopes to everything-except-subject. Mimics longer-lens / shallower-DOF rendering at edit time. Pair with look_wildlife_subject_sharpen for complete subject emphasis. Marc/Bushcrafter darktable-discipline made portable._

| ColorChecker | Grayscale ramp |
|-|-|
| <img src="../visual-proofs/expressive-baseline/look_wildlife_background_blur-colorchecker.jpg" alt="look_wildlife_background_blur ColorChecker" width="180"> | <img src="../visual-proofs/expressive-baseline/look_wildlife_background_blur-grayscale.jpg" alt="look_wildlife_background_blur grayscale" width="180"> |

### `look_wildlife_eye_lift` 🟦 mask-bound

_Catchlight emphasis on the wildlife subject's eye — exposure +0.3 EV + sharpen amount 1.5, scoped to mask_eye_region (RFC-032). The eye becomes the brightest, sharpest point in the frame; gives the bird / animal its 'life.' Cross-genre echo of Portrait Move 7 (eye-detail lift). For close-up wildlife where the subject's gaze is the picture._

| ColorChecker | Grayscale ramp |
|-|-|
| <img src="../visual-proofs/expressive-baseline/look_wildlife_eye_lift-colorchecker.jpg" alt="look_wildlife_eye_lift ColorChecker" width="180"> | <img src="../visual-proofs/expressive-baseline/look_wildlife_eye_lift-grayscale.jpg" alt="look_wildlife_eye_lift grayscale" width="180"> |

### `look_food_texture_subtle` 🟦 mask-bound

_Subtle texture lift for food — bread crust, pastry layers, meat fibers, fruit skin texture. Bilat clarity_strength +0.20 — explicit ceiling matching the food-photography-academy 'never overdone' discipline (Kopcok: 'overdoing clarity makes food look dry and unappealing'). Pre-baked with mask_subject so the texture lift scopes to the food, not the table / plate. Compose with look_food_appetizing_warm._

| ColorChecker | Grayscale ramp |
|-|-|
| <img src="../visual-proofs/expressive-baseline/look_food_texture_subtle-colorchecker.jpg" alt="look_food_texture_subtle ColorChecker" width="180"> | <img src="../visual-proofs/expressive-baseline/look_food_texture_subtle-grayscale.jpg" alt="look_food_texture_subtle grayscale" width="180"> |

### `look_product_packshot_clean`

_Commercial packshot baseline — gentle sigmoid 1.10 (avoids the punch-the-product look), subtle vignette -0.10 (-10% brightness edges; pulls the eye to the centered product). Karl Taylor / Zoe Noble's commercial-product clean-on-white starting point. Assumes WB has been gray-card-corrected (use wb_from_gray_card MCP tool / CLI before this look applies)._

| ColorChecker (global) | Grayscale (global) | ColorChecker (centered ellipse mask) | Grayscale (centered ellipse mask) |
|-|-|-|-|
| <img src="../visual-proofs/expressive-baseline/look_product_packshot_clean-colorchecker.jpg" alt="look_product_packshot_clean ColorChecker global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_product_packshot_clean-grayscale.jpg" alt="look_product_packshot_clean grayscale global" width="180"> | <img src="../visual-proofs/expressive-baseline/look_product_packshot_clean-colorchecker-masked.jpg" alt="look_product_packshot_clean ColorChecker masked" width="180"> | <img src="../visual-proofs/expressive-baseline/look_product_packshot_clean-grayscale-masked.jpg" alt="look_product_packshot_clean grayscale masked" width="180"> |

### Real-raw entries

These entries touch raw-domain darktable modules (`temperature`, `colorequal`, `denoiseprofile`, `lens`, `hazeremoval`, `ashift`, `crop`, `retouch`, `filmicrgb`, or `diffuse`) — or compose looks that include one. The synthetic chart can't represent the input these modules expect; rendering against it produces structurally-misleading output. Each entry is routed to either the landscape or portrait CC BY-SA 4.0 fixture from `tests/fixtures/raws/` so the after-image is honest. Apply-path correctness is independently verified by the unit + integration + e2e test coverage.

> The following real_raw entries have no real-raw render on disk yet. Run `uv run python scripts/generate-visual-proofs.py` (without `--markdown-only`) after fetching the fixtures via `git lfs pull`.

| Entry | Routed fixture | Modules touched | What the entry does |
|-|-|-|-|
| `crop` | landscape | `crop` | Parameterized crop (RFC-022 Tier 2). |
| `transform` | landscape | `ashift` | Parameterized perspective / transform (#101). |
| `lens_correction` | landscape | `lens` | Parameterized lens correction (#95). |
| `denoise` | landscape | `denoiseprofile` | Parameterized denoising via darktable's denoiseprofile module (#96). |
| `filmic` | landscape | `filmicrgb` | Parameterized filmic v6 tone mapping (#97). |
| `texture` | landscape | `diffuse` | Parameterized texture (#92 Bucket A. |
| `hsl_saturation` | landscape | `colorequal` | Parameterized HSL Saturation row (RFC-023). |
| `hsl_hue` | landscape | `colorequal` | Parameterized HSL Hue row (RFC-023). |
| `hsl_luminance` | landscape | `colorequal` | Parameterized HSL Luminance row (RFC-023). |
| `dehaze` | landscape | `hazeremoval` | Parameterized dehaze (#90 Bucket A. |
| `wb_kelvin_delta` | landscape | `temperature` | WB Kelvin / tint UX wrapper (#102). |
| `temperature` | landscape | `temperature` | Parameterized white balance (RFC-021; first multi-parameter ship). |
| `look_vintage_film` | landscape | `colorbalancergb`, `grain`, `sigmoid`, `temperature` | L2 look — nostalgia / faded film aesthetic. |
| `look_film_kodachrome` | landscape | `colorbalancergb`, `grain`, `sigmoid`, `temperature` | L2 look — Kodachrome film simulation (#104). |
| `look_film_portra` | landscape | `colorbalancergb`, `grain`, `sigmoid`, `temperature` | L2 look — Kodak Portra 400 portrait film (#104). |
| `look_70s_film` | landscape | `colorbalancergb`, `grain`, `sigmoid`, `temperature` | L2 look — 1970s film aesthetic (#104). |
| `look_90s_grain` | landscape | `grain`, `sigmoid`, `temperature` | L2 look — 1990s film aesthetic (#104). |
| `look_2000s_digital` | landscape | `colorbalancergb`, `sigmoid`, `temperature` | L2 look — early-2000s digital camera aesthetic (#104). |
| `skin_uniformity` | portrait | `colorequal` | Skin-tone uniformity (RFC-033). |
| `look_portrait_natural_skin` | portrait | `colorbalancergb`, `exposure`, `sigmoid`, `temperature` | Restraint-first portrait foundation — Tucker/Marino-aligned. |
| `look_portrait_skin_warm_lift` | portrait | `exposure`, `temperature` | Subject-region warm + brighten. |
| `look_landscape_golden_hour` | landscape | `colorbalancergb`, `sigmoid`, `temperature` | Sunset / sunrise mood. |
| `look_landscape_blue_hour_cool` | landscape | `colorbalancergb`, `sigmoid`, `temperature` | Twilight / pre-dawn / blue-hour mood. |
| `look_landscape_atmospheric_haze` | landscape | `bilat`, `colorbalancergb`, `hazeremoval` | Misty / hazy / fog-as-subject mood. |
| `look_landscape_autumn_pop` | landscape | `bilat`, `colorequal`, `temperature` | Autumn foliage / fall color. |
| `bw_convert` | landscape | `colorequal` | B&W conversion (RFC-033 follow-up; survey Gap #1). |
| `look_bw_classic_neutral` | landscape | `bilat`, `colorequal`, `sigmoid` | Classic B&W foundation — neutral channel weighting (no filter), mid contrast (sigmoid 1. |
| `look_bw_high_contrast_chiaroscuro` | landscape | `colorbalancergb`, `colorequal`, `sigmoid` | Tucker/Thompson-style chiaroscuro B&W — strong sigmoid contrast (1. |
| `look_bw_landscape_dramatic` | landscape | `bilat`, `colorequal`, `sigmoid` | Page/Adamus dramatic B&W landscape — red-filter-emulated conversion (bright_red +0. |
| `look_bw_split_tone_warm_shadows` | landscape | `colorbalancergb`, `colorequal`, `sigmoid` | Subtle warm-shadows toned B&W — sepia / selenium print evocation. |
| `look_bw_silver_efex_zone_balanced` | landscape | `bilat`, `colorequal`, `sigmoid` | Whalley/Boutwell zone-system-aware balanced B&W — the restraint discipline applied to monochrome. |
| `look_wildlife_high_iso_recovery` | landscape | `bilat`, `denoiseprofile`, `sigmoid` | High-ISO wildlife recovery (low-light dance-floor, late dusk owl, early-dawn bird-burst). |
| `look_wildlife_natural_warm` | landscape | `colorbalancergb`, `sigmoid`, `temperature` | Warm golden-hour wildlife default — temperature +0. |
| `look_food_appetizing_warm` | landscape | `colorbalancergb`, `sigmoid`, `temperature` | Default food editorial — warm WB (+0. |
| `look_food_orange_pop` | landscape | `colorequal` | Lift the orange / red food band — tomato, carrot, salmon, paprika, peach. |
| `look_food_green_natural` | landscape | `colorequal` | Lift greens — fresh herbs, salad, parsley, basil — without crossing into the cartoonish lime-green that over-edited food photography shows. |

---

## Notes

- **Inputs are sRGB PNGs**, not raw files. darktable processes them through its non-raw path — input color profile applies, demosaic does not. Some primitives (e.g., raw-aware white-balance moves) behave differently from how they would on a real raw. The gallery is for *visual response validation*, not pipeline calibration; for raw-pipeline direction-of-change validation see the e2e suite in [`tests/e2e/`](https://github.com/chipi/chemigram/blob/main/tests/e2e/).

- **Mask-bound entries** (gradient/ellipse/rectangle, marked 🟦 above) route through the drawn-mask apply path per ADR-076. The mask geometry encodes into the XMP's `masks_history`; you see the spatial shaping in the rendered chart.

- **Out-of-gamut patches** on the ColorChecker (notably patch #18 Cyan) clip to nearest in-gamut sRGB; that clipping is in the input, not the primitive. See [`reference-targets/README.md`](https://github.com/chipi/chemigram/blob/main/tests/fixtures/reference-targets/README.md).
