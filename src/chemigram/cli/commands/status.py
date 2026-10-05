"""``chemigram status`` — diagnostic, not a tool wrapper (RFC-020 §H).

Reports six fields:

1. chemigram package version (``importlib.metadata``)
2. darktable-cli path + version (env: ``DARKTABLE_CLI`` or PATH)
3. workspace root (``--workspace`` global, default ``~/Pictures/Chemigram``)
4. configured packs (default: ``starter``)
5. prompt store version (active version of ``mode_a/system``)
6. output schema version (constant from :mod:`chemigram.cli.output`)

This is the **only** module in ``chemigram.cli`` allowed to call
``subprocess.run`` — the ``darktable-cli --version`` call is metadata,
not domain logic. ``scripts/audit-cli-imports.py`` allowlists this
module specifically.
"""

from __future__ import annotations

import os
import shutil
import subprocess  # allowlisted: see module docstring
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, cast

import typer

from chemigram.cli._context import CliContext
from chemigram.cli.exit_codes import ExitCode
from chemigram.cli.output import OUTPUT_SCHEMA_VERSION
from chemigram.core.vocab import load_packs
from chemigram.mcp.prompts import PromptStore

# Reuse the MCP server's prompts-root resolver. The function is
# underscore-prefixed but is genuinely shared infrastructure between the
# two adapter layers; refactoring it to public is a small follow-up.
from chemigram.mcp.server import _resolve_prompts_root


def _darktable_path() -> str | None:
    """Resolve ``darktable-cli`` via env var then PATH (matches ADR-004)."""
    env = os.environ.get("DARKTABLE_CLI")
    if env:
        return env if Path(env).is_file() else None
    found = shutil.which("darktable-cli")
    return found


def _darktable_version(binary: str) -> str:
    """Parse ``darktable-cli --version`` first line.

    The output is darktable-version-specific; this parser tolerates a
    range of formats by returning the first non-empty line stripped.
    """
    try:
        proc = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return "unknown"
    out = (proc.stdout or proc.stderr or "").strip()
    for line in out.splitlines():
        s = line.strip()
        if s:
            return s
    return "unknown"


def _tool_version() -> str:
    try:
        return version("agent-darkroom-cli")
    except PackageNotFoundError:
        return "unknown"


def _prompt_active_version() -> str:
    try:
        store = PromptStore(_resolve_prompts_root())
        return store.active_version("mode_a/system")
    except Exception:
        return "unknown"


def status(
    ctx: typer.Context,
    probe: Path | None = typer.Option(
        None,
        "--probe",
        exists=True,
        dir_okay=False,
        help="Render this image in a fresh headless config.",
    ),
) -> None:
    """Implementation. Wired via the root app in :mod:`chemigram.cli.main`."""
    obj = cast(CliContext, ctx.obj)
    writer = obj["writer"]

    tool_version = _tool_version()
    dt_path = _darktable_path()
    workspace_root = obj["workspace"] or Path.home() / "Pictures" / "Chemigram"
    pack_names = ["expressive-baseline"]
    try:
        index = load_packs(pack_names)
        pack_roots = [str(p) for p in index.pack_roots]
        entry_count = len(list(index.list_all()))
    except Exception as exc:
        pack_roots = []
        entry_count = 0
        writer.event("warning", message=f"pack discovery failed: {exc}")
    prompt_version = _prompt_active_version()

    warnings: list[str] = []
    if dt_path is None:
        warnings.append(
            "darktable-cli not found — install darktable, or set DARKTABLE_CLI to the absolute path"
        )

    configdir = obj["configdir"] or workspace_root / ".darktable-config"
    fields: dict[str, Any] = {
        "tool_version": tool_version,
        "darktable_cli_path": dt_path,
        "darktable_cli_version": _darktable_version(dt_path) if dt_path else None,
        "workspace_root": str(workspace_root),
        "configdir": str(configdir),
        "configured_packs": pack_names,
        "configured_pack_roots": pack_roots,
        "vocabulary_entries": entry_count,
        "prompt_store_active": {"mode_a/system": prompt_version},
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "warnings": warnings,
    }

    if probe is not None:
        if dt_path is None:
            writer.error("darktable-cli is required for --probe", ExitCode.DARKTABLE_ERROR)
            raise typer.Exit(code=ExitCode.DARKTABLE_ERROR.value)
        configdir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="chemigram-probe-") as temp:
            output = Path(temp) / "probe.jpg"
            command = [
                dt_path,
                str(probe.resolve()),
                str(output),
                "--width",
                "256",
                "--height",
                "256",
                "--hq",
                "false",
                "--apply-custom-presets",
                "false",
                "--core",
                "--configdir",
                str(configdir),
            ]
            try:
                process = subprocess.run(command, capture_output=True, text=True, timeout=90)
            except subprocess.TimeoutExpired as exc:
                writer.error("darktable render probe timed out", ExitCode.DARKTABLE_ERROR)
                raise typer.Exit(code=ExitCode.DARKTABLE_ERROR.value) from exc
            if process.returncode or not output.is_file() or output.stat().st_size == 0:
                writer.error(
                    "darktable render probe failed",
                    ExitCode.DARKTABLE_ERROR,
                    stderr=process.stderr[-2000:],
                )
                raise typer.Exit(code=ExitCode.DARKTABLE_ERROR.value)
            fields["probe"] = {"success": True, "input_path": str(probe.resolve())}

    # `status` is a diagnostic — it always exits 0 and reports missing
    # components as fields/warnings. Scripts that need a hard check
    # for darktable can branch on `darktable_cli_path is None` in the
    # JSON output. Erroring out would defeat the discoverability use
    # case (you'd need darktable installed to ask whether it's installed).
    for w in warnings:
        writer.event("warning", message=w)
    writer.result(message="status", **fields)
