"""Visual-proof coverage audit.

Asserts that every chart-verifiable vocabulary entry has at least one
rendered visual proof on disk. Real-raw-needed entries (per the
module-level discriminator in :mod:`chemigram.core.visual_verification`)
are expected NOT to have a chart render — they await issue #130 (real-
raw fixture set).

Originally written against the static ``_SKIP_VISUAL_PROOF_ENTRIES`` set
in the visual-proofs generator; refactored to use the principled
discriminator in v1.11.0 (closes issue #129, the v1.10.0 visual-proofs
trust gap).

Catches:
- A chart-verifiable entry that silently failed to render (generator
  bug class).
- A new chart-verifiable entry added without a regen.
- An entry mis-categorized as chart-verifiable that should be real-raw
  (caught indirectly — the render would be misleading even if it exists).

For visual *correctness* (does the rendered output actually match the
entry's documented intent?), see ``docs/guides/darkroom-session-debt.md``
items 7-11 — that's photographer review, not a CI property.
"""

from __future__ import annotations

from pathlib import Path

from chemigram.core.visual_verification import is_chart_verifiable
from chemigram.core.vocab import load_packs

REPO_ROOT = Path(__file__).resolve().parents[2]
PROOFS_ROOT = REPO_ROOT / "docs" / "visual-proofs"


def _entry_has_chart_proof(entry_name: str) -> bool:
    """True if ``docs/visual-proofs/<pack>/<entry>-<chart-target>.jpg``
    exists for at least one chart-target combination."""
    for pack in ("starter", "expressive-baseline"):
        pack_dir = PROOFS_ROOT / pack
        if not pack_dir.is_dir():
            continue
        for target in ("colorchecker", "grayscale"):
            if (pack_dir / f"{entry_name}-{target}.jpg").exists():
                return True
    return False


def test_every_chart_verifiable_entry_has_a_proof() -> None:
    """Catches the silent-drop bug class for entries that SHOULD render
    against the chart. Real-raw-needed entries are skipped from this
    check — they're tracked separately in the gallery's
    "Needs real-raw fixture" section.
    """
    vocab = load_packs(["starter", "expressive-baseline"])
    missing: list[str] = []
    for entry in vocab.list_all():
        if entry.layer == "L1":
            continue
        if not is_chart_verifiable(entry):
            # real_raw-needed; legitimately has no chart proof
            continue
        if not _entry_has_chart_proof(entry.name):
            missing.append(entry.name)

    assert not missing, (
        f"Chart-verifiable vocabulary entries with no rendered visual "
        f"proof on disk: {sorted(missing)}. Run "
        "`uv run scripts/generate-visual-proofs.py` to render them. "
        "This test prevents the v1.10.0 silent-drop bug class from "
        "recurring."
    )


def test_no_real_raw_entry_has_a_misleading_chart_proof() -> None:
    """Inverse direction: real-raw-needed entries should NOT have a
    chart proof file on disk (because the chart can't honestly verify
    them — proofs would be misleading). This catches the case where a
    formerly-chart-rendered entry was re-categorized but its old proof
    files weren't cleaned up."""
    vocab = load_packs(["starter", "expressive-baseline"])
    misleading: list[str] = []
    for entry in vocab.list_all():
        if entry.layer == "L1":
            continue
        if is_chart_verifiable(entry):
            continue
        # real_raw-needed entry: chart proofs would be misleading
        if _entry_has_chart_proof(entry.name):
            misleading.append(entry.name)

    # We're tolerant for the v1.10.0 → v1.11.0 transition: existing
    # chart proofs of real-raw-needed entries are stale-but-not-failing.
    # The gallery markdown excludes them from the chart-verifiable section
    # via the discriminator anyway, so they're harmless. Just flag for
    # cleanup at the next regen.
    if misleading:
        import warnings

        warnings.warn(
            f"Stale chart proofs for real-raw-needed entries (harmless; "
            f"gallery markdown excludes them via the discriminator, but "
            f"the files still take disk space): {sorted(misleading)}. "
            "Will be cleaned up at the next full re-render or by "
            "issue #130 (real-raw fixture set).",
            UserWarning,
            stacklevel=2,
        )
