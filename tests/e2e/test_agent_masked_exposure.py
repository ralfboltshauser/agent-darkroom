"""Real RAW regression for the global-then-local editing loop."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageStat

RAW = Path(__file__).resolve().parents[1] / "fixtures" / "raws" / "portrait.ARW"


def _run(workspace: Path, *args: str) -> dict:
    env = os.environ.copy()
    env["CHEMIGRAM_WORKSPACE"] = str(workspace)
    result = subprocess.run(
        [sys.executable, "-m", "chemigram.cli.main", "--json", *args],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout.splitlines()[-1])


def test_global_then_masked_exposure_stacks_and_stays_local(tmp_path: Path) -> None:
    if not os.environ.get("DARKTABLE_CLI") or not RAW.exists() or RAW.stat().st_size < 1_000_000:
        pytest.skip("needs DARKTABLE_CLI and the LFS portrait RAW")

    ingest = _run(tmp_path, "ingest", str(RAW), "--image-id", "photo")
    global_edit = _run(
        tmp_path,
        "apply-primitive",
        "photo",
        "--entry",
        "exposure",
        "--value",
        "1.5",
        "--expect-head",
        ingest["snapshot_hash"],
    )
    before = _run(tmp_path, "render-preview", "photo", "--size", "1024")
    local_edit = _run(
        tmp_path,
        "apply-primitive",
        "photo",
        "--entry",
        "exposure",
        "--value",
        "0.6",
        "--mask-spec",
        '{"dt_form":"ellipse","dt_params":{"center_x":0.5,"center_y":0.45,"radius_x":0.3,"radius_y":0.35,"border":0.1}}',
        "--expect-head",
        global_edit["snapshot_hash"],
    )
    assert local_edit["state_after"]["operations"]["exposure"] == [0, 1]
    after = _run(tmp_path, "render-preview", "photo", "--size", "1024")

    with Image.open(before["jpeg_path"]) as first, Image.open(after["jpeg_path"]) as second:
        diff = ImageChops.difference(first.convert("RGB"), second.convert("RGB"))
        w, h = diff.size
        center = diff.crop((int(w * 0.45), int(h * 0.4), int(w * 0.55), int(h * 0.5)))
        corner = diff.crop((0, 0, int(w * 0.1), int(h * 0.1)))
        assert sum(ImageStat.Stat(center).mean) / 3 > 10
        assert sum(ImageStat.Stat(corner).mean) / 3 < 2
