"""Tests for the chart-verifiable / real-raw-needed module-level
discriminator (closes the v1.10.0 visual-proofs trust gap; issue #129).

The discriminator must:
- Return a resolved mode for every loaded vocabulary entry
- Correctly identify chart-verifiable modules vs raw-domain modules
- Treat L2 looks as chart-verifiable IFF every touched module is chart-verifiable
- Be deterministic (no edge cases that flap)
"""

from __future__ import annotations

from chemigram.core.visual_verification import (
    _CHART_VERIFIABLE_MODULES,
    _RAW_DOMAIN_MODULES,
    is_chart_verifiable,
    verification_mode_for_entry,
)
from chemigram.core.vocab import load_packs


def test_chart_and_raw_module_sets_are_disjoint() -> None:
    """A module can't be both chart-verifiable and raw-domain. Catches
    mistakes when editing the registries."""
    overlap = _CHART_VERIFIABLE_MODULES & _RAW_DOMAIN_MODULES
    assert not overlap, (
        f"Modules listed in both registries: {sorted(overlap)}. "
        "A module must be in exactly one bucket."
    )


def test_every_loaded_entry_resolves_to_a_mode() -> None:
    """Every vocabulary entry in starter + expressive-baseline must
    resolve to a verification mode. Catches new entries whose touched
    modules aren't in either registry."""
    vocab = load_packs(["starter", "expressive-baseline"])
    unresolved: list[tuple[str, tuple[str, ...]]] = []
    for entry in vocab.list_all():
        # If an entry has touches that aren't in either registry, the
        # mode resolution falls back to "real_raw" (the conservative
        # choice). Surface those — they should be deliberately
        # categorized.
        touches = set(entry.touches)
        unknown = touches - _CHART_VERIFIABLE_MODULES - _RAW_DOMAIN_MODULES
        if unknown:
            unresolved.append((entry.name, tuple(sorted(unknown))))
    assert not unresolved, (
        "Entries touch modules not categorized in either "
        "_CHART_VERIFIABLE_MODULES or _RAW_DOMAIN_MODULES:\n  - "
        + "\n  - ".join(f"{name}: {modules}" for name, modules in unresolved)
        + "\nAdd them to the appropriate registry in "
        "chemigram.core.visual_verification."
    )


def test_chart_verifiable_examples() -> None:
    """Spot-check that classically-chart-verifiable entries resolve
    correctly. These never need a real-raw fixture."""
    vocab = load_packs(["expressive-baseline"])
    for name in (
        "exposure",
        "sigmoid_contrast",
        "vignette",
        "grain_strength",
        "sharpen",
        "bilat_clarity_strength",
        "saturation_global",  # colorbalancergb single axis
    ):
        entry = vocab.lookup_by_name(name)
        assert entry is not None, f"{name} not found"
        assert is_chart_verifiable(entry), f"{name} should be chart-verifiable"


def test_real_raw_examples() -> None:
    """Spot-check that classically-raw-domain entries resolve correctly.
    These produce misleading output on the synthetic chart."""
    vocab = load_packs(["expressive-baseline"])
    for name in (
        "temperature",
        "hsl_hue",
        "hsl_saturation",
        "bw_convert",
        "denoise",
        "lens_correction",
        "dehaze",
    ):
        entry = vocab.lookup_by_name(name)
        assert entry is not None, f"{name} not found"
        assert not is_chart_verifiable(entry), (
            f"{name} should NOT be chart-verifiable (touches a raw-domain module)"
        )


def test_l2_look_with_one_raw_module_is_not_chart_verifiable() -> None:
    """An L2 look composed of mostly-chart-verifiable modules + one
    raw-domain module is NOT chart-verifiable. The contaminating module
    taints the composition."""
    vocab = load_packs(["expressive-baseline"])
    # look_landscape_dramatic_moody is sigmoid + colorbalancergb + bilat
    # — all chart-verifiable.
    entry = vocab.lookup_by_name("look_landscape_dramatic_moody")
    assert is_chart_verifiable(entry)

    # look_70s_film composes sigmoid + colorbalancergb + grain + temperature.
    # The single temperature touch taints the composition.
    entry = vocab.lookup_by_name("look_70s_film")
    assert not is_chart_verifiable(entry)


def test_starter_pack_is_real_raw_by_module_definition() -> None:
    """Both starter-pack entries touch temperature; the chart can't
    verify either. Documents the v1.10.0 finding that even the most
    basic starter entries need the real-raw fixture."""
    vocab = load_packs(["starter"])
    for entry in vocab.list_all():
        if entry.layer == "L1":
            continue
        assert verification_mode_for_entry(entry) == "real_raw", (
            f"{entry.name} (touches={entry.touches}) should be real_raw — "
            "starter pack all touches temperature"
        )
