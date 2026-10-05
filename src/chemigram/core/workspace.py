"""Per-image workspace orchestrator.

A :class:`Workspace` is the runtime object that ties one image's pieces
together: the per-image ``ImageRepo`` (objects/refs/HEAD/log), the copied
raw, the rendered preview/export caches, and references to shared
resources (configdir, vocabulary). Owns the directory layout from
``contracts/per-image-repo``.

Public surface:
    - :class:`Workspace` — runtime handle
    - :func:`init_workspace_root` — directory bootstrap
    - :func:`workspace_id_for` — derive a stable ``image_id`` from a raw path
    - :func:`Workspace.ingest` — full bootstrap (copies raw, extracts EXIF,
      creates ``ImageRepo``, writes a baseline XMP, snapshots it, tags
      ``baseline``)
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from chemigram.core.binding import VocabularyIndex, bind_l1
from chemigram.core.dtstyle import DtstyleEntry
from chemigram.core.exif import ExifData, read_exif
from chemigram.core.versioning import ImageRepo
from chemigram.core.versioning.ops import snapshot, tag
from chemigram.core.xmp import HistoryEntry, Xmp


@dataclass
class Workspace:
    """Runtime handle for one image's per-image directory.

    Attributes:
        image_id: Stable identifier (typically the basename of the raw
            without extension, plus a disambiguator if needed).
        root: Workspace directory, one level above the per-image repo.
        repo: :class:`ImageRepo` rooted at ``root``.
        raw_path: Absolute path to the copied original at
            ``root / "raw" / <basename>``.
        baseline_ref: Tag (or branch) name marking the session's baseline
            snapshot. Bare name — versioning's ``_resolve_input`` searches
            ``refs/heads/<name>`` then ``refs/tags/<name>``. Defaults to
            ``"baseline"`` (a tag): the ``ingest`` flow creates a
            ``baseline`` tag at the first snapshot so ``reset`` always
            returns to that point even after ``main`` advances.
        configdir: Optional dedicated darktable configdir per ADR-005.
            ``None`` means "use the global one".

    The previews/exports/sessions/vocabulary_gaps subpaths follow
    ``contracts/per-image-repo`` and are surfaced as properties so callers
    don't restate the layout.
    """

    image_id: str
    root: Path
    repo: ImageRepo
    raw_path: Path
    baseline_ref: str = "baseline"
    configdir: Path | None = None
    exif: ExifData | None = None
    suggested_bindings: list[DtstyleEntry] = field(default_factory=list)

    @property
    def previews_dir(self) -> Path:
        return self.root / "previews"

    @property
    def exports_dir(self) -> Path:
        return self.root / "exports"

    @property
    def sessions_dir(self) -> Path:
        return self.root / "sessions"

    @property
    def vocabulary_gaps_path(self) -> Path:
        return self.root / "vocabulary_gaps.jsonl"


def init_workspace_root(root: Path) -> None:
    """Create the directory shape declared in ``contracts/per-image-repo``.

    Only the directories whose existence the workspace assumes — the repo
    pieces (``objects/``, ``refs/``, ``HEAD``, ``log.jsonl``) come from
    :meth:`ImageRepo.init`, called separately by callers that need them.
    """
    root.mkdir(parents=True, exist_ok=True)
    for sub in ("raw", "previews", "exports", "sessions"):
        (root / sub).mkdir(exist_ok=True)


def tastes_dir() -> Path:
    """Global tastes directory (per ADR-048).

    Defaults to ``~/.chemigram/tastes/``. Override via the
    ``CHEMIGRAM_TASTES_DIR`` env var (used by tests for isolation and by
    photographers who want a non-standard location).
    """
    import os

    raw = os.environ.get("CHEMIGRAM_TASTES_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.home() / ".chemigram" / "tastes"


_SAFE_ID = re.compile(r"[^a-zA-Z0-9_.-]+")


def workspace_id_for(raw_path: Path, *, suffix: str | None = None) -> str:
    """Derive a stable, filesystem-safe ``image_id`` from a raw filename.

    Uses the basename without extension, sanitized to ``[A-Za-z0-9_.-]``.
    ``suffix`` (typically a short hash or timestamp) disambiguates collisions
    when the same basename has been ingested before.
    """
    base = _SAFE_ID.sub("_", raw_path.stem) or "image"
    return f"{base}_{suffix}" if suffix else base


def _baseline_xmp(exif: ExifData, suggested_l1: list[DtstyleEntry]) -> Xmp:
    """Pin the initial exposure module so the first edit has a stable base.

    The historical fixture contains camera-specific processing and creator
    metadata from another photograph. An empty history changes its automatic
    exposure when the first explicit edit is added, making unmasked regions
    change during a local edit. This zero-EV module pins that behavior.
    The params and blend blob come from darktable 5.4's exposure style and
    were rendered on 5.6.2 as well. New module versions require rechecking.
    """
    return Xmp(
        rating=0,
        label="",
        auto_presets_applied=False,
        history_end=1,
        iop_order_version=4,
        history=(
            HistoryEntry(
                num=0,
                operation="exposure",
                enabled=True,
                modversion=7,
                params="00000000000080b90000000000004842000080c00100000001000000",
                multi_name="",
                multi_name_hand_edited=False,
                multi_priority=0,
                blendop_version=14,
                blendop_params=(
                    "gz08eJxjYGBgYAFiCQYYOOHEgAZY0QWAgBGLGANDgz0Ej1Q+dlAx68oBEMbFxwX+AwGIBgCbGCeh"
                ),
            ),
        ),
        raw_extra_fields=(
            ("attr", "darktable:xmp_version", "5"),
            ("attr", "darktable:raw_params", "0"),
        ),
    )


def ingest_workspace(
    raw_path: Path,
    *,
    workspace_root: Path,
    image_id: str | None = None,
    vocabulary: VocabularyIndex | None = None,
) -> Workspace:
    """Bootstrap a :class:`Workspace` for ``raw_path``.

    Steps:
        1. Resolve ``image_id`` (caller-provided or derived from raw stem).
        2. Create the per-image directory layout under ``workspace_root /
           image_id`` and initialize the :class:`ImageRepo`.
        3. Copy the raw into ``raw/<basename>`` and record its hash.
        4. Read EXIF, suggest L1 bindings via :func:`bind_l1`.
        5. Build a neutral baseline :class:`Xmp`, snapshot
           it, and tag the snapshot ``baseline``.

    Idempotent on the per-image directory: re-ingesting the same image_id
    does NOT clobber an existing repo — raises ``FileExistsError`` if the
    target root already has an ``objects/`` directory. Caller decides
    whether to disambiguate via ``image_id``.
    """
    if image_id is None:
        image_id = workspace_id_for(raw_path)
    root = workspace_root / image_id
    if (root / "objects").exists():
        raise FileExistsError(
            f"workspace at {root} already exists — pass a fresh image_id to ingest again"
        )

    init_workspace_root(root)
    repo = ImageRepo.init(root)

    raw_link = root / "raw" / raw_path.name
    shutil.copy2(raw_path, raw_link)
    with raw_link.open("rb") as source_file:
        source_hash = hashlib.file_digest(source_file, "sha256").hexdigest()
    (root / "source.json").write_text(
        json.dumps({"original_path": str(raw_path.resolve()), "sha256": source_hash}, indent=2)
        + "\n",
        encoding="utf-8",
    )

    exif = read_exif(raw_path)
    suggested = bind_l1(exif, vocabulary) if vocabulary is not None else []
    baseline_xmp = _baseline_xmp(exif, suggested)
    h = snapshot(repo, baseline_xmp, label="baseline", metadata={"ingested_at": _now_iso()})
    tag(repo, "baseline", h)

    return Workspace(
        image_id=image_id,
        root=root,
        repo=repo,
        raw_path=raw_link,
        exif=exif,
        suggested_bindings=list(suggested),
    )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def append_markdown(target: Path, content: str) -> None:
    """Append a markdown block to ``target``, separated from prior content.

    Used by both adapters to write taste/notes updates. Adds a leading
    blank line if the file already has content, and a trailing newline
    if the content doesn't end with one. Creates parent directories
    as needed. Single-process write — concurrent invocations against
    the same file may interleave. Adapters that need stronger guarantees
    take their own locks.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    suffix = "" if content.endswith("\n") else "\n"
    with target.open("a", encoding="utf-8") as fh:
        if target.stat().st_size > 0:
            fh.write("\n")
        fh.write(content + suffix)
