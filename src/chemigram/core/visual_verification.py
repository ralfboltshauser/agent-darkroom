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
- ``real_raw`` — chart is structurally wrong; the chemigram apply path
  + real-raw fixture produces an honest render. The entry touches a
  raw-domain module (haze / lens / ashift / etc.) but the engine
  applies it correctly to any raw.
- ``not_yet_portable`` — entry touches a raw-domain module whose
  chemigram apply path isn't yet camera-aware. The entry's dtstyle
  carries hardcoded raw-domain coefficients from its authoring camera;
  applying to a different body produces a foreign-WB cast that masks
  the entry's actual photographic effect. Tracked in #131 Step 2 /
  RFC-039 (raw-derived parameters in L2 composition). Today this
  applies to ``temperature``-touching entries only; expands when other
  raw-derived parameters are identified.
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

# Subset of raw-domain modules whose chemigram apply path isn't yet
# camera-aware. Entries touching these still carry their authoring-
# camera's hardcoded coefficients in their dtstyle blobs; applying to a
# different body produces a foreign-WB cast. The chemigram parametric
# path needs camera-aware extension (RFC-039 / #131 Step 2) before these
# entries can be honestly rendered on the real-raw fixtures. Until then
# the gallery routes them to a "Not yet honestly verifiable" section
# with no rendered image (because every rendering would be misleading).
#
# When camera-aware parametric apply ships for a module, REMOVE it from
# this set so the discriminator graduates affected entries from
# ``not_yet_portable`` to ``real_raw``.
_NOT_YET_PORTABLE_MODULES: frozenset[str] = frozenset(
    {
        "temperature",
    }
)


def _direct_touches(entry: Any) -> set[str]:
    """Modules the entry touches DIRECTLY via its own dtstyle plugins
    (excluding modules touched only via :data:`composes` references).

    RFC-039 composition: an L2 look may have ``temperature`` in its
    declared ``touches`` (the aggregated effect set) while NOT having
    a temperature plugin in its own dtstyle — the temperature op
    comes via composition of the parametric ``wb_kelvin_delta``
    primitive, which is camera-aware at apply time. Such entries are
    camera-portable; direct touches is what the discriminator uses
    to identify "carries a hardcoded coefficient blob" vs "delegates
    to a camera-aware primitive."
    """
    dtstyle = getattr(entry, "dtstyle", None)
    if dtstyle is None:
        return set()
    return {p.operation for p in getattr(dtstyle, "plugins", ())}


def verification_mode_for_entry(entry: Any) -> str:
    """Return ``"chart"`` | ``"real_raw"`` | ``"not_yet_portable"`` |
    ``"manual"`` for a vocab entry.

    Module-level discriminator:

    1. Every touched module in :data:`_CHART_VERIFIABLE_MODULES` →
       ``"chart"`` (synthetic chart is an honest fixture).
    2. The entry DIRECTLY touches (via its own dtstyle, not via
       composition) any module in :data:`_NOT_YET_PORTABLE_MODULES` →
       ``"not_yet_portable"`` (the entry's dtstyle carries
       camera-specific coefficients that aren't yet computed per-raw at
       apply time; until that ships, the real-raw render shows a
       foreign-camera cast rather than the entry's intended effect).
       RFC-039 composition is exempt: an L2 look that composes a
       parametric primitive (e.g., ``wb_kelvin_delta``) for the
       not-yet-portable module's effect is CAMERA-PORTABLE because
       composition routes through the camera-aware apply path.
    3. Otherwise (raw-domain but camera-portable) → ``"real_raw"``
       (chemigram applies it correctly on any raw via the real-raw
       fixture).

    Mask-bound entries follow the same rule — the mask geometry is
    rendered on top of the underlying effect; the verifiability is
    dominated by which modules the entry touches.

    The future ``"manual"`` return (not yet returned by this function)
    is reserved for entries whose effect is genuinely undecidable
    against any fixture — pure photographer judgment.
    """
    touches = set(getattr(entry, "touches", ()))
    if not touches:
        # No touches → no opinion; treat as chart-default (safe — empty
        # touch list means no module is invoked).
        return "chart"
    if touches.issubset(_CHART_VERIFIABLE_MODULES):
        return "chart"
    # not_yet_portable check uses DIRECT touches only (RFC-039): if the
    # entry's own dtstyle has a not-yet-portable module's plugin
    # inlined with hardcoded coefficients, the entry can't be honestly
    # rendered on a foreign body. Two exceptions:
    #   (a) the not-yet-portable module is touched only via composition
    #       — apply path is camera-aware, entry IS portable
    #   (b) the entry declares ``parameters`` covering that module —
    #       the parametric apply path is camera-aware (Phase 2), entry
    #       IS portable
    not_yet_portable_direct = _direct_touches(entry) & _NOT_YET_PORTABLE_MODULES
    if not_yet_portable_direct:
        # Check exception (b): are the touched not-yet-portable modules
        # all covered by the entry's parameter declarations?
        params = getattr(entry, "parameters", None) or ()
        parametric_modules = {getattr(p.field, "module", None) for p in params}
        if not_yet_portable_direct.issubset(parametric_modules):
            return "real_raw"
        return "not_yet_portable"
    # Any single touched module not in the chart-verifiable set demotes
    # the whole entry to real_raw. Multi-module L2 looks composed of
    # chart-verifiable primitives are still chart-verifiable; one
    # raw-domain module taints the composition.
    return "real_raw"


def is_chart_verifiable(entry: Any) -> bool:
    """Sugar for the chart-verifiable case."""
    return verification_mode_for_entry(entry) == "chart"


def is_not_yet_portable(entry: Any) -> bool:
    """Sugar for the not-yet-portable case (#131 Step 2 / RFC-039)."""
    return verification_mode_for_entry(entry) == "not_yet_portable"


# Public exports
__all__ = [
    "_CHART_VERIFIABLE_MODULES",
    "_NOT_YET_PORTABLE_MODULES",
    "_RAW_DOMAIN_MODULES",
    "is_chart_verifiable",
    "is_not_yet_portable",
    "verification_mode_for_entry",
]
