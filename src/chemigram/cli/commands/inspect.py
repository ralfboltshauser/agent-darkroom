"""Measurements from the rendered preview an agent is about to view."""

from __future__ import annotations

from typing import cast

import typer
from PIL import Image

from chemigram.cli._context import CliContext
from chemigram.cli._workspace import resolve_workspace_or_fail
from chemigram.cli.commands.render import _render_to, _snapshot_hash
from chemigram.cli.exit_codes import ExitCode
from chemigram.core.exif import read_exif


def _percentile(histogram: list[int], fraction: float) -> int:
    target = sum(histogram) * fraction
    count = 0
    for value, n in enumerate(histogram):
        count += n
        if count >= target:
            return value
    return 255


def inspect(
    ctx: typer.Context,
    image_id: str = typer.Argument(..., help="Image ID."),
    ref_or_hash: str = typer.Option("HEAD", "--ref", help="Revision to inspect."),
    size: int = typer.Option(1024, "--size", min=64, max=8192),
) -> None:
    obj = cast(CliContext, ctx.obj)
    writer = obj["writer"]
    workspace = resolve_workspace_or_fail(ctx, image_id)
    try:
        snapshot_hash = _snapshot_hash(workspace, ref_or_hash)
    except Exception as exc:
        writer.error(str(exc), ExitCode.VERSIONING_ERROR, image_id=image_id)
        raise typer.Exit(code=ExitCode.VERSIONING_ERROR.value) from exc

    path = workspace.previews_dir / f"preview_{snapshot_hash}_{size}.jpg"
    if not path.is_file():
        ok, error, details = _render_to(
            workspace, snapshot_hash, path, width=size, height=size, high_quality=False
        )
        if not ok:
            writer.error(error or "render failed", ExitCode.DARKTABLE_ERROR, **details)
            raise typer.Exit(code=ExitCode.DARKTABLE_ERROR.value)

    with Image.open(path) as image:
        rendered_size = image.size
        icc_embedded = bool(image.info.get("icc_profile"))
        rgb = image.convert("RGB")
        rgb.thumbnail((1024, 1024))
        pixels = rgb.width * rgb.height
        red, green, blue = (channel.histogram() for channel in rgb.split())
        luminance = rgb.convert("L").histogram()
        exif = read_exif(workspace.raw_path)
        writer.result(
            image_id=image_id,
            snapshot_hash=snapshot_hash,
            preview_path=str(path),
            width=rendered_size[0],
            height=rendered_size[1],
            profile_requested="sRGB",
            icc_embedded=icc_embedded,
            sample_pixels=pixels,
            luminance_percentiles={
                "p5": _percentile(luminance, 0.05),
                "p50": _percentile(luminance, 0.5),
                "p95": _percentile(luminance, 0.95),
            },
            near_black_pct=round(100 * sum(luminance[:6]) / pixels, 2),
            near_white_pct=round(100 * sum(luminance[250:]) / pixels, 2),
            channel_near_white_pct={
                "red": round(100 * sum(red[250:]) / pixels, 2),
                "green": round(100 * sum(green[250:]) / pixels, 2),
                "blue": round(100 * sum(blue[250:]) / pixels, 2),
            },
            camera={"make": exif.make, "model": exif.model} if exif else None,
            warnings=[] if icc_embedded else ["JPEG contains no embedded ICC profile"],
        )
