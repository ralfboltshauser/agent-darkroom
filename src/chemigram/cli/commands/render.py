"""Render CLI verbs (#57): render-preview, compare.

Mirrors MCP ``render_preview`` and ``compare`` (per ADR-033/056). Both
call :func:`chemigram.core.pipeline.render` directly (per ADR-071);
subprocess invocation lives inside core.

``compare``'s side-by-side stitch logic lives in
:func:`chemigram.core.helpers.stitch_side_by_side` (Pillow); both the
MCP and CLI adapters import from there.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import cast
from uuid import uuid4

import typer
from PIL import Image, ImageChops, ImageEnhance

from chemigram.cli._batch import aggregate_exit_code, iter_image_ids
from chemigram.cli._context import CliContext
from chemigram.cli._workspace import resolve_workspace_or_fail
from chemigram.cli.exit_codes import ExitCode
from chemigram.core.helpers import load_xmp_bytes_at, parse_xmp_at, stitch_side_by_side
from chemigram.core.pipeline import render as core_render
from chemigram.core.versioning import (
    ObjectNotFoundError,
    RefNotFoundError,
    RepoError,
)
from chemigram.core.versioning.ops import VersioningError
from chemigram.core.workspace import Workspace
from chemigram.core.xmp import write_xmp


def _snapshot_hash(workspace: Workspace, ref_or_hash: str) -> str:
    return hashlib.sha256(load_xmp_bytes_at(workspace.repo, ref_or_hash)).hexdigest()


def _render_to(
    workspace: Workspace,
    ref_or_hash: str,
    output_path: Path,
    *,
    width: int,
    height: int,
    high_quality: bool,
) -> tuple[bool, str | None, dict[str, object]]:
    """Render workspace's ref/hash to ``output_path``. Returns
    ``(ok, error_message, details)`` so the caller can map to a writer.

    Mirrors the MCP ``_render_to`` path in
    ``chemigram.mcp.tools.rendering`` — same ref-resolution + temp-XMP
    sequence, same darktable-cli invocation via
    :func:`chemigram.core.pipeline.render`.
    """
    try:
        xmp = parse_xmp_at(workspace.repo, ref_or_hash)
    except (RefNotFoundError, ObjectNotFoundError, RepoError, VersioningError) as exc:
        return False, str(exc), {"kind": "versioning"}

    xmp_path = workspace.previews_dir / f"_render_{uuid4().hex}.xmp"
    write_xmp(xmp, xmp_path)
    temporary_output = output_path.with_name(
        f"{output_path.stem}.{uuid4().hex}{output_path.suffix}"
    )
    try:
        result = core_render(
            raw_path=workspace.raw_path,
            xmp_path=xmp_path,
            output_path=temporary_output,
            width=width,
            height=height,
            high_quality=high_quality,
            configdir=workspace.configdir,
        )
    finally:
        xmp_path.unlink(missing_ok=True)

    if not result.success:
        temporary_output.unlink(missing_ok=True)
        return (
            False,
            result.error_message or "render failed",
            {"kind": "darktable", "stderr": result.stderr[-2000:]},
        )
    os.replace(temporary_output, output_path)
    return (
        True,
        None,
        {"output_path": str(output_path), "duration_seconds": result.duration_seconds},
    )


def _do_render_preview(ctx: typer.Context, image_id: str, *, size: int, ref_or_hash: str) -> int:
    obj = cast(CliContext, ctx.obj)
    writer = obj["writer"]
    try:
        workspace = resolve_workspace_or_fail(ctx, image_id)
    except typer.Exit as exc:
        return int(exc.exit_code)
    try:
        snapshot_hash = _snapshot_hash(workspace, ref_or_hash)
    except (RefNotFoundError, ObjectNotFoundError, RepoError, VersioningError) as exc:
        writer.error(
            str(exc), ExitCode.VERSIONING_ERROR, image_id=image_id, ref_or_hash=ref_or_hash
        )
        return ExitCode.VERSIONING_ERROR.value
    output_path = workspace.previews_dir / f"preview_{snapshot_hash}_{size}.jpg"
    ok, err, details = _render_to(
        workspace, snapshot_hash, output_path, width=size, height=size, high_quality=False
    )
    if not ok:
        kind = details.get("kind")
        if kind == "versioning":
            writer.error(
                err or "ref not resolvable",
                ExitCode.VERSIONING_ERROR,
                image_id=image_id,
                ref_or_hash=ref_or_hash,
            )
            return ExitCode.VERSIONING_ERROR.value
        writer.error(
            err or "render failed",
            ExitCode.DARKTABLE_ERROR,
            image_id=image_id,
            **details,
        )
        return ExitCode.DARKTABLE_ERROR.value
    with Image.open(output_path) as rendered:
        width, height = rendered.size
    writer.result(
        message=f"rendered {ref_or_hash[:8]}",
        image_id=image_id,
        ref_or_hash=ref_or_hash,
        snapshot_hash=snapshot_hash,
        jpeg_path=details["output_path"],
        width=width,
        height=height,
        output_profile="sRGB",
        duration_seconds=details["duration_seconds"],
    )
    return ExitCode.SUCCESS.value


def render_preview(
    ctx: typer.Context,
    image_id: str = typer.Argument(None, help="Image ID (or '-' with --stdin for batch)."),
    size: int = typer.Option(1024, "--size", min=64, max=8192, help="Max width/height in pixels."),
    ref_or_hash: str = typer.Option(
        "HEAD",
        "--ref",
        help="Ref name or content hash to render (defaults to HEAD).",
    ),
    stdin: bool = typer.Option(
        False, "--stdin", help="Read image_ids from stdin (one per line); render each."
    ),
) -> None:
    """Render one snapshot to a JPEG preview in the workspace's previews/."""
    codes = [
        _do_render_preview(ctx, img, size=size, ref_or_hash=ref_or_hash)
        for img in iter_image_ids(stdin, image_id)
    ]
    final = aggregate_exit_code(codes)
    if final != ExitCode.SUCCESS.value:
        raise typer.Exit(code=final)


def compare(
    ctx: typer.Context,
    image_id: str = typer.Argument(..., help="Image ID."),
    hash_a: str = typer.Argument(..., help="First ref or hash."),
    hash_b: str = typer.Argument(..., help="Second ref or hash."),
    size: int = typer.Option(1024, "--size", min=64, max=8192, help="Max width/height per side."),
    difference: bool = typer.Option(
        False, "--difference", help="Also produce a pixel difference image."
    ),
) -> None:
    """Render two snapshots and stitch them side-by-side as a labeled comparison JPEG."""
    obj = cast(CliContext, ctx.obj)
    writer = obj["writer"]

    workspace = resolve_workspace_or_fail(ctx, image_id)
    try:
        resolved_a = _snapshot_hash(workspace, hash_a)
        resolved_b = _snapshot_hash(workspace, hash_b)
    except (RefNotFoundError, ObjectNotFoundError, RepoError, VersioningError) as exc:
        writer.error(str(exc), ExitCode.VERSIONING_ERROR, image_id=image_id)
        raise typer.Exit(code=ExitCode.VERSIONING_ERROR.value) from exc
    a_out = workspace.previews_dir / f"preview_{resolved_a}_{size}.jpg"
    b_out = workspace.previews_dir / f"preview_{resolved_b}_{size}.jpg"

    for ref, target in ((resolved_a, a_out), (resolved_b, b_out)):
        ok, err, details = _render_to(
            workspace, ref, target, width=size, height=size, high_quality=False
        )
        if not ok:
            kind = details.get("kind")
            if kind == "versioning":
                writer.error(
                    err or "ref not resolvable",
                    ExitCode.VERSIONING_ERROR,
                    image_id=image_id,
                    ref_or_hash=ref,
                )
                raise typer.Exit(code=ExitCode.VERSIONING_ERROR.value)
            writer.error(
                err or "render failed",
                ExitCode.DARKTABLE_ERROR,
                image_id=image_id,
                **details,
            )
            raise typer.Exit(code=ExitCode.DARKTABLE_ERROR.value)

    output = workspace.previews_dir / f"compare_{resolved_a}_{resolved_b}_{size}.jpg"
    stitch_side_by_side(a_out, b_out, output, label_left=hash_a[:8], label_right=hash_b[:8])

    diff_path: str | None = None
    changed_fraction: float | None = None
    warnings: list[str] = []
    if difference:
        with Image.open(a_out) as a_image, Image.open(b_out) as b_image:
            a_rgb, b_rgb = a_image.convert("RGB"), b_image.convert("RGB")
        if a_rgb.size != b_rgb.size:
            warnings.append("different image dimensions; aligned pixel difference unavailable")
        else:
            diff = ImageChops.difference(a_rgb, b_rgb)
            changed = diff.convert("L").point(lambda value: 255 if value > 3 else 0)
            changed_fraction = sum(changed.histogram()[1:]) / (a_rgb.width * a_rgb.height)
            diff = ImageEnhance.Contrast(diff).enhance(4)
            target = workspace.previews_dir / f"difference_{resolved_a}_{resolved_b}_{size}.png"
            diff.save(target)
            diff_path = str(target)
            if changed_fraction < 0.001:
                warnings.append("rendered images are nearly identical at this preview size")

    writer.result(
        message=f"compared {hash_a[:8]} vs {hash_b[:8]}",
        image_id=image_id,
        hash_a=hash_a,
        hash_b=hash_b,
        jpeg_path=str(output),
        before_path=str(a_out),
        after_path=str(b_out),
        difference_path=diff_path,
        changed_pixel_fraction=changed_fraction,
        warnings=warnings,
    )
