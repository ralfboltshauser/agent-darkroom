"""B6 — manifest.touches[] vs dtstyle plugin operations audit.

Would have caught the starter ``tone_lifted_shadows_subject`` bug
(#62) where the dtstyle file held the wrong content for its manifest
entry. Runs against every loaded pack at import time so adding an
entry whose dtstyle plugin operations don't match its manifest
``touches[]`` fails CI loudly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemigram.core.vocab import VocabularyIndex, load_packs

REPO_ROOT = Path(__file__).resolve().parents[4]


def _packs_to_audit() -> list[VocabularyIndex]:
    """Every pack that ships in-tree."""
    indices = []
    starter_root = REPO_ROOT / "vocabulary" / "starter"
    if starter_root.exists():
        indices.append(VocabularyIndex(starter_root))
    expressive_root = REPO_ROOT / "vocabulary" / "packs" / "expressive-baseline"
    if expressive_root.exists():
        indices.append(VocabularyIndex(expressive_root))
    return indices


@pytest.mark.parametrize("index", _packs_to_audit(), ids=lambda i: str(i.pack_roots[0].name))
def test_every_entry_dtstyle_operations_match_manifest_touches(index: VocabularyIndex) -> None:
    """Pre-RFC-039 invariant was plugin_ops == manifest_touches.

    Post-RFC-039, L2 entries may declare touches for modules that come
    via composition (composes references) without having a matching
    plugin in the dtstyle. The updated invariant:

    - Every plugin operation MUST be declared in touches (catches the
      bug class the test was originally for — dtstyle holds wrong
      content).
    - Every touches entry that has NO matching plugin MUST be
      explainable by a composes reference whose target primitive
      touches that module.
    """
    failures = []
    for entry in index.list_all():
        plugin_ops = {p.operation for p in entry.dtstyle.plugins}
        manifest_touches = set(entry.touches)
        # plugin_ops must be a subset of touches (catches stray plugins)
        stray_plugins = plugin_ops - manifest_touches
        if stray_plugins:
            failures.append(
                f"{entry.name} ({entry.path.name}): "
                f"plugin ops {sorted(stray_plugins)} not declared in touches"
            )
        # Every extra touches entry (in touches, not in plugin_ops) must
        # be touched by a composes target.
        extra_touches = manifest_touches - plugin_ops
        if extra_touches:
            composed_touches: set[str] = set()
            for ref in entry.composes or ():
                target = index.lookup_by_name(ref.primitive)
                if target is not None:
                    composed_touches.update(target.touches)
            unexplained = extra_touches - composed_touches
            if unexplained:
                failures.append(
                    f"{entry.name} ({entry.path.name}): "
                    f"touches {sorted(unexplained)} have no matching plugin "
                    f"and no composes target covers them"
                )
    assert not failures, "\n".join(failures)


def test_starter_pack_via_load_packs_helper_consistent() -> None:
    """Sanity: same audit through the load_packs() entry point."""
    index = load_packs(["starter"])
    failures = []
    for entry in index.list_all():
        plugin_ops = {p.operation for p in entry.dtstyle.plugins}
        manifest_touches = set(entry.touches)
        if not plugin_ops.issubset(manifest_touches):
            failures.append(entry.name)
    assert not failures, f"inconsistent entries in starter via load_packs: {failures}"
