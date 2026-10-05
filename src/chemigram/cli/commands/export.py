"""``chemigram export-final`` (#57).

Mirrors MCP ``export_final`` (per ADR-033/056). Calls
:func:`chemigram.core.pipeline.render` directly with ``high_quality=True``
and the workspace's exports/ directory as the destination.
"""

from __future__ import annotations

import hashlib
from typing import cast

import typer
from PIL import Image

from chemigram.cli._batch import aggregate_exit_code, iter_image_ids
from chemigram.cli._context import CliContext
from chemigram.cli._workspace import resolve_workspace_or_fail
from chemigram.cli.commands.render import _render_to, _snapshot_hash
from chemigram.cli.exit_codes import ExitCode

_VALID_FORMATS = ("jpeg", "png")
_FULL_RES_SENTINEL = 0


def _do_export_final(
    ctx: typer.Context,
    image_id: str,
    *,
    ref_or_hash: str,
    format_: str,
    size: int | None,
) -> int:
    obj = cast(CliContext, ctx.obj)
    writer = obj["writer"]
    try:
        workspace = resolve_workspace_or_fail(ctx, image_id)
    except typer.Exit as exc:
        return int(exc.exit_code)
    try:
        snapshot_hash = _snapshot_hash(workspace, ref_or_hash)
    except Exception as exc:
        writer.error(str(exc), ExitCode.VERSIONING_ERROR, image_id=image_id)
        return ExitCode.VERSIONING_ERROR.value
    extension = "jpg" if format_ == "jpeg" else "png"
    size_key = "full" if size is None else str(size)
    output_path = workspace.exports_dir / f"export_{snapshot_hash}_{size_key}.{extension}"
    width = height = size if size is not None else _FULL_RES_SENTINEL
    ok, err, details = _render_to(
        workspace, snapshot_hash, output_path, width=width, height=height, high_quality=True
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
            err or "export failed",
            ExitCode.DARKTABLE_ERROR,
            image_id=image_id,
            **details,
        )
        return ExitCode.DARKTABLE_ERROR.value
    with Image.open(output_path) as rendered:
        pixel_width, pixel_height = rendered.size
        icc_embedded = bool(rendered.info.get("icc_profile"))
    with output_path.open("rb") as export_file:
        output_sha256 = hashlib.file_digest(export_file, "sha256").hexdigest()
    writer.result(
        message=f"exported {ref_or_hash[:8]} as {format_}",
        image_id=image_id,
        ref_or_hash=ref_or_hash,
        snapshot_hash=snapshot_hash,
        format=format_,
        output_path=details["output_path"],
        width=pixel_width,
        height=pixel_height,
        bytes=output_path.stat().st_size,
        sha256=output_sha256,
        profile_requested="sRGB",
        icc_embedded=icc_embedded,
        warnings=[] if icc_embedded else ["export contains no embedded ICC profile"],
        duration_seconds=details["duration_seconds"],
    )
    return ExitCode.SUCCESS.value


def export_final(
    ctx: typer.Context,
    image_id: str = typer.Argument(None, help="Image ID (or '-' with --stdin for batch)."),
    ref_or_hash: str = typer.Option(
        "HEAD", "--ref", help="Ref name or hash to export. Defaults to HEAD."
    ),
    format_: str = typer.Option("jpeg", "--format", help="Output format: jpeg or png."),
    size: int | None = typer.Option(
        None,
        "--size",
        min=64,
        max=16384,
        help="Max width/height in pixels. Omit for full resolution.",
    ),
    stdin: bool = typer.Option(
        False, "--stdin", help="Read image_ids from stdin (one per line); export each."
    ),
) -> None:
    """High-quality export to the workspace's exports/ directory."""
    obj = cast(CliContext, ctx.obj)
    writer = obj["writer"]

    if format_ not in _VALID_FORMATS:
        writer.error(
            f"--format must be one of {list(_VALID_FORMATS)}, got {format_!r}",
            ExitCode.INVALID_INPUT,
            got=format_,
        )
        raise typer.Exit(code=ExitCode.INVALID_INPUT.value)

    codes = [
        _do_export_final(ctx, img, ref_or_hash=ref_or_hash, format_=format_, size=size)
        for img in iter_image_ids(stdin, image_id)
    ]
    final = aggregate_exit_code(codes)
    if final != ExitCode.SUCCESS.value:
        raise typer.Exit(code=final)
