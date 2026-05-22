"""Visual-verification mode per vocabulary entry.

The synthetic chart fixture (colorchecker + grayscale ramp) can honestly
verify some entries but not others. The discriminator is **which darktable
modules the entry touches** — modules that operate on already-developed
sRGB / working-profile pixels render correctly on the chart; modules that
operate on raw sensor data or need the full input/output color-profile
chain produce nonsense on the chart.

This module gives every entry a verification mode:

- ``chart`` — synthetic chart is a legitimate fixture. The render in
  the gallery is what the entry actually does on already-developed
  pixels. Trust the after-image.
- ``real_raw`` — chart is structurally wrong; needs a real raw photo
  for honest verification. The entry touches a raw-domain module
  (temperature / colorequal / lens / etc.) or composes one.
- ``manual`` — neither fixture verifies meaningfully; needs darkroom-
  session photographer review against the photographer's own raws.
  Mask-bound entries with content-aware named maskdefs (sky / subject /
  skin / eye) typically fall here unless the mask resolves to a
  parametric range filter on a chart-verifiable module.

The categorization closes the v1.10.0 visual-proof trust gap: previously
every entry was rendered on the chart and 21 of them produced misleading
"after" images that suggested the entry was broken. The entries weren't
broken — the fixture was wrong. This module names that explicitly.

Background: when bw_convert v2 (colorequal-based) shipped in v1.10.0,
the existing `_SKIP_VISUAL_PROOF_ENTRIES = {hsl_hue, hsl_luminance,
hsl_saturation}` set wasn't extended. The same chart-pipeline issue that
made HSL renders broken made bw_convert v2 renders broken, plus all 5
look_bw_* + skin_uniformity + look_food_green/orange + look_landscape_autumn_pop.
This module replaces the ad-hoc skip-list with a principled module-level
discriminator.
"""

from __future__ import annotations

from typing import Any

# Modules that operate on already-developed sRGB / working-profile pixels.
# The synthetic chart is a legitimate fixture for these — the after-image
# in the gallery shows exactly what the entry does on this pixel domain.
#
# When adding a module: only add if you've verified the module produces
# the expected effect on synthetic-chart input. Test by rendering a few
# values and confirming the output reads as intended.
_CHART_VERIFIABLE_MODULES: frozenset[str] = frozenset(
    {
        # Tone — operate on luminance, work on any pixel domain
        "exposure",
        "sigmoid",
        "highlights",
        "toneequal",
        # Local contrast — operates on luminance
        "bilat",
        # Sharpening — edge detection; produces some patch-boundary artifacts
        # on flat patches but direction-of-effect is honest
        "sharpen",
        # Geometric — pure positional / textural overlays
        "vignette",
        "grain",
        # Color shifts in working RGB — work on chart's sRGB-encoded patches
        "colorbalancergb",
        # Channel-mixer B&W in destination=grey mode — operates on sRGB
        # input and produces correct grayscale per supplied weights
        "channelmixerrgb",
    }
)

# Modules that need raw-domain input or the full input/output profile chain.
# Rendering against the synthetic chart produces structurally-misleading
# output (extreme color casts, blown highlights, all-black patches, etc.).
# These entries need a real raw fixture to verify honestly.
_RAW_DOMAIN_MODULES: frozenset[str] = frozenset(
    {
        # Raw-domain white-balance coefficients
        "temperature",
        # HSL panel — needs input/output profile chain
        "colorequal",
        # Per-camera EXIF-bound modules
        "denoiseprofile",
        "lens",
        # Pipeline-stage-dependent
        "filmicrgb",
        # Depth/content-signal-dependent
        "hazeremoval",
        # Framing-bound — chart isn't a framed photo
        "ashift",
        "crop",
        # Location-specific patch operations
        "retouch",
        # Texture/content-signal-dependent — rendering produces
        # patch-boundary artifacts not real texture signal
        "diffuse",
    }
)


def verification_mode_for_entry(entry: Any) -> str:
    """Return ``"chart"`` | ``"real_raw"`` | ``"manual"`` for a vocab entry.

    Pure module-level discriminator: if every touched module is in
    :data:`_CHART_VERIFIABLE_MODULES`, the entry is chart-verifiable.
    Otherwise it's real_raw (chart will produce misleading output).

    Mask-bound entries follow the same rule — the mask geometry is
    rendered on top of the underlying effect; the chart-verifiability
    is dominated by which modules the entry touches.

    The future ``manual`` return (not yet returned by this function)
    is reserved for entries whose effect is genuinely undecidable
    against any fixture — pure photographer judgment. Currently
    everything maps to chart or real_raw.
    """
    touches = set(getattr(entry, "touches", ()))
    if not touches:
        # No touches → no opinion; treat as chart-default (safe — empty
        # touch list means no module is invoked).
        return "chart"
    if touches.issubset(_CHART_VERIFIABLE_MODULES):
        return "chart"
    # Any single touched module not in the chart-verifiable set demotes
    # the whole entry. Multi-module L2 looks composed of chart-verifiable
    # primitives are still chart-verifiable; one raw-domain module taints
    # the composition.
    return "real_raw"


def is_chart_verifiable(entry: Any) -> bool:
    """Sugar for the common case."""
    return verification_mode_for_entry(entry) == "chart"


# Public exports
__all__ = [
    "_CHART_VERIFIABLE_MODULES",
    "_RAW_DOMAIN_MODULES",
    "is_chart_verifiable",
    "verification_mode_for_entry",
]
