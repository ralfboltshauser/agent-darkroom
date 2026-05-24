"""Helpers for tests that depend on Git LFS-tracked fixtures.

The two ARW raws under ``tests/fixtures/raws/`` are stored via Git LFS.
When a checkout doesn't pull LFS (default on CI's ``actions/checkout@v4``
without ``lfs: true``), the file on disk is a ~130-byte pointer text,
not the real ~20 MB raw. Tests that try to read it via rawpy / exifread
get cryptic "unsupported file format" errors deep inside the parser.

``skip_if_lfs_pointer(path)`` detects the pointer-not-content case by
size + magic and calls ``pytest.skip()`` with a clear message. Callers
just invoke it before any LFS-dependent assertion.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# LFS pointer files start with this magic and are <1 KiB. Real raws
# are tens of MB.
_LFS_POINTER_MAGIC = b"version https://git-lfs"
_LFS_POINTER_MAX_SIZE = 1024


def is_lfs_pointer(path: Path) -> bool:
    """True iff ``path`` exists but contains a Git LFS pointer rather
    than the real bytes the pointer references."""
    if not path.exists():
        return False
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size > _LFS_POINTER_MAX_SIZE:
        return False
    try:
        with path.open("rb") as fh:
            head = fh.read(64)
    except OSError:
        return False
    return head.startswith(_LFS_POINTER_MAGIC)


def skip_if_lfs_pointer(path: Path) -> None:
    """``pytest.skip`` with a clear message when ``path`` is an
    unfetched LFS pointer. Used by tests that consume LFS-tracked raws.

    No-op when the path is either absent (existing
    ``raw_path.exists()`` checks already handle that case) or contains
    the real bytes (the common local-dev case after ``git lfs pull``).
    """
    if not path.exists():
        return  # caller's own existence check handles this
    if is_lfs_pointer(path):
        pytest.skip(
            f"LFS fixture {path.name} not pulled (CI default); "
            f"run 'git lfs pull' locally or enable lfs:true in CI checkout"
        )
