"""Cross-pack composition stress test (#145 / option E).

The RFC-018 + RFC-039 (#137) multi-pack loader is theoretically N-pack-
tolerant; in practice only the 2-pack ``[starter, expressive-baseline]``
scenario is exercised by the rest of the suite. This module covers the
3-pack shape by adding three synthetic stress packs under
``tests/fixtures/vocabulary/`` and verifying each of:

- Cross-pack ``composes`` reference (a 3rd pack composes starter's
  ``wb_kelvin_delta`` primitive — pack-name boundaries don't break
  the composition resolver)
- Cross-pack name collision (a 3rd pack declares ``wb_kelvin_delta``
  — must raise ``ManifestError`` with a clear, actionable message)
- Modversion drift (a 3rd pack declares ``modversions['temperature']=99``
  — must fire the drift warning during load)

RFC-028 will be the architectural answer to N-pack semantics. Until then
this is the engineering safety net under the v1.11.0 loader.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from chemigram.core.helpers import apply_entry
from chemigram.core.vocab import (
    ManifestError,
    VocabularyIndex,
    _resolve_starter_path,
)
from chemigram.core.xmp import parse_xmp

_REPO = Path(__file__).resolve().parents[4]
_BASELINE_TEMPLATE = _REPO / "src/chemigram/core/_baseline_v1.xmp"
_STRESS_PACKS = _REPO / "tests" / "fixtures" / "vocabulary"

_COMPOSE_PACK = _STRESS_PACKS / "cross_pack_compose"
_COLLISION_PACK = _STRESS_PACKS / "cross_pack_collision"
_DRIFT_PACK = _STRESS_PACKS / "cross_pack_drift"


def _starter() -> Path:
    return _resolve_starter_path()


def test_cross_pack_compose_resolves_starter_primitive() -> None:
    """A 3rd pack's L2 entry composes the starter pack's
    ``wb_kelvin_delta``. Loading both packs together must populate the
    combined index AND the composing entry must apply through
    :func:`apply_entry` without raising."""
    idx = VocabularyIndex([_starter(), _COMPOSE_PACK])

    # Both entries present in the merged namespace
    assert idx.lookup_by_name("wb_kelvin_delta") is not None
    composer = idx.lookup_by_name("cross_pack_warm_subtle")
    assert composer is not None
    assert composer.composes is not None
    assert len(composer.composes) == 1
    assert composer.composes[0].primitive == "wb_kelvin_delta"

    # The composition resolves at apply time — the starter primitive
    # is found via the merged index and the kelvin_delta param flows
    # through.
    baseline = parse_xmp(_BASELINE_TEMPLATE)
    applied = apply_entry(baseline, composer, vocab=idx)
    assert applied is not None


def test_cross_pack_name_collision_raises_manifest_error() -> None:
    """The collision pack declares ``wb_kelvin_delta`` — the same name
    starter ships. Loading both must raise :class:`ManifestError` with
    a message that names BOTH packs (so the photographer knows which
    pack to rename)."""
    with pytest.raises(ManifestError) as exc_info:
        VocabularyIndex([_starter(), _COLLISION_PACK])
    msg = str(exc_info.value)
    assert "wb_kelvin_delta" in msg
    # The message should reference both source packs, not just one
    assert "starter" in msg
    assert "cross_pack_collision" in msg


def test_cross_pack_modversion_drift_fires_warning() -> None:
    """The drift pack declares ``modversions['temperature']=99`` against
    an engine that pins it at 4. Loading must fire the drift warning
    (via :func:`emit_drift_signals`)."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        VocabularyIndex([_starter(), _DRIFT_PACK])
    drift_messages = [str(w.message) for w in caught if "modversion drift" in str(w.message)]
    assert len(drift_messages) >= 1, (
        f"expected modversion-drift warning; got: {[str(w.message) for w in caught]}"
    )
    drift_msg = drift_messages[0]
    assert "cross_pack_drift_entry" in drift_msg
    assert "temperature" in drift_msg
    assert "99" in drift_msg


def test_three_packs_together_compose_resolves_when_no_collision() -> None:
    """The 3-pack shape #145's spec named: load starter + compose pack +
    drift pack together (collision pack is excluded — it'd block load).
    Verifies the loader handles N=3 distinct packs in a single
    construction; drift warning fires; cross-pack compose still works."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        idx = VocabularyIndex([_starter(), _COMPOSE_PACK, _DRIFT_PACK])

    # Drift warning fired
    assert any("modversion drift" in str(w.message) for w in caught)

    # Compose entry still resolvable + composes starter's primitive
    composer = idx.lookup_by_name("cross_pack_warm_subtle")
    assert composer is not None
    assert idx.lookup_by_name("wb_kelvin_delta") is not None

    # Drift entry still resolvable (warning doesn't drop the entry; the
    # entry is loaded but flagged for the photographer's attention)
    drift_entry = idx.lookup_by_name("cross_pack_drift_entry")
    assert drift_entry is not None
