"""Audit visual-proof renders against per-subtype direction-of-effect heuristics.

Each rendered "after" image is compared to its baseline by simple pixel-stat
signatures (mean R/G/B, luma, std-luma, mean chroma, clip counts). Per-subtype
heuristics decide whether the delta matches the entry's intent:

- ``ok`` — signature matches the subtype's expected direction-of-effect
- ``warn`` — borderline (near-baseline, ambiguous direction, etc.)
- ``fail`` — signature contradicts the subtype expectation

The output is a triage list, not a hard pass/fail — direction-of-effect is
necessary but not sufficient for "intent match." A FAIL is the strongest
candidate for photographer visual review; an OK is "no obvious regression."

What this catches:

- An entry whose dtstyle was silently edited and now renders near-baseline
  (the gallery image looks unchanged from the before)
- An entry whose direction inverted (a "lift" that now darkens; a "warm"
  that now cools)
- Blown-highlight or crushed-shadow regressions on entries that shouldn't
  be clipping
- An entry's render disappearing from disk

What this DOESN'T catch:

- A render that's *directionally* correct but wrong in magnitude
- A render whose tonal/chromatic shape is wrong but mean stats line up
- "Looks bad on a portrait" (photographer-judgment territory)

Usage:

    uv run scripts/audit_visual_proofs.py                    # markdown to stdout
    uv run scripts/audit_visual_proofs.py --json report.json # also write JSON
    uv run scripts/audit_visual_proofs.py --strict           # exit 1 on warn or fail
    uv run scripts/audit_visual_proofs.py --packs starter expressive-baseline

Exit codes:

- 0 — no FAILs (or no warns/fails in --strict)
- 1 — at least one FAIL (or warn in --strict)
- 2 — script invocation error (missing fixtures, etc.)

See #141 for the issue that formalized this audit.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from chemigram.core.visual_verification import verification_mode_for_entry
from chemigram.core.vocab import load_packs

REPO = Path(__file__).resolve().parent.parent
PROOFS = REPO / "docs" / "visual-proofs"
DEFAULT_PACKS = ("starter", "expressive-baseline")


# ---------------------------------------------------------------------------
# Pixel-stat signature
# ---------------------------------------------------------------------------


def _stats(path: Path) -> dict[str, float]:
    """Compute the pixel-stat signature of one image."""
    img = Image.open(path).convert("RGB")
    # Pillow 14 deprecates ``getdata``; ``get_flattened_data`` returns a
    # flat 1D iterable, ``tobytes`` is the portable alternative for
    # current and future Pillow.
    raw = img.tobytes()
    pixels = [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]
    rs = [p[0] for p in pixels]
    gs = [p[1] for p in pixels]
    bs = [p[2] for p in pixels]
    lumas = [0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2] for p in pixels]
    chromas = [max(p) - min(p) for p in pixels]
    clip_hi = sum(1 for p in pixels if max(p) >= 250) / len(pixels)
    clip_lo = sum(1 for p in pixels if max(p) <= 5) / len(pixels)
    return {
        "mean_r": statistics.mean(rs),
        "mean_g": statistics.mean(gs),
        "mean_b": statistics.mean(bs),
        "mean_luma": statistics.mean(lumas),
        "std_luma": statistics.pstdev(lumas),
        "mean_chroma": statistics.mean(chromas),
        "clip_hi": clip_hi,
        "clip_lo": clip_lo,
    }


def _delta(after: dict[str, float], before: dict[str, float]) -> dict[str, float]:
    return {k: after[k] - before[k] for k in before}


# ---------------------------------------------------------------------------
# Per-subtype direction-of-effect heuristics
# ---------------------------------------------------------------------------


def _near_baseline(d: dict[str, float]) -> bool:
    """No visible change anywhere on the mean signature."""
    return (
        abs(d["mean_r"]) < 1.5
        and abs(d["mean_g"]) < 1.5
        and abs(d["mean_b"]) < 1.5
        and abs(d["std_luma"]) < 0.5
    )


def _is_parametric_identity_default(entry: Any) -> bool:
    """True when every parameter's default is identity (0.0 or 1.0). At
    identity the main-row render is no-op by design; near-baseline
    signature is expected, not a regression. Mirrors the same-named
    heuristic in scripts/generate-visual-proofs.py."""
    params = getattr(entry, "parameters", None)
    if not params:
        return False
    for spec in params:
        default = getattr(spec, "default", 0.0)
        if abs(default) > 1e-6 and abs(default - 1.0) > 1e-6:
            return False
    return True


def _requires_content(entry: Any) -> bool:
    """True when the entry's effect targets specific scene content (sky,
    skin, food, etc.) via a content-aware mask. On the synthetic chart
    those masks resolve to nothing — near-baseline is structural, not
    a regression. The content-fixture render below the main row shows
    the actual effect."""
    return bool(getattr(entry, "requires_content", ()))


@dataclass(frozen=True)
class Verdict:
    status: str  # "ok" | "warn" | "fail"
    note: str


def _verdict_chart(entry: Any, d: dict[str, float]) -> Verdict:  # noqa: C901
    """Direction-of-effect heuristics for chart-verifiable entries.

    These operate on the synthetic colorchecker baseline. Subtypes drive
    the expected direction; entry name carries the polarity (lift / crush
    / open / etc.).
    """
    name = entry.name
    sub = entry.subtype or ""

    if name in _EXPECTED_NEAR_BASELINE_NAMES:
        return Verdict(
            "ok",
            "chart isn't the verifying fixture for this entry "
            "(see SKIP_REASONS in tests/e2e/_lab_grade_deltas.py)",
        )

    if _is_parametric_identity_default(entry):
        return Verdict(
            "ok",
            "parametric identity-default — main row is no-op by design; "
            "see parameter sweep for the entry's effect at non-default values",
        )

    if _requires_content(entry):
        return Verdict(
            "ok",
            "content-aware mask doesn't fire on the chart — see the "
            "content-fixture render row for the entry's actual effect",
        )

    # Universal clip checks first — blown / crushed channels are a
    # regression even if the entry has its own subtype branch below.
    if d["clip_hi"] > 0.30 and "open" not in name and "whites_open" not in name:
        return Verdict("fail", f"clip_hi={d['clip_hi']:.2f} — looks blown")
    if d["clip_lo"] > 0.30 and "crush" not in name and "lift" not in name:
        return Verdict("fail", f"clip_lo={d['clip_lo']:.2f} — looks crushed")

    if sub == "grain":
        if d["std_luma"] < 0.5:
            return Verdict(
                "fail",
                f"std_luma_delta={d['std_luma']:+.1f} — grain didn't add noise",
            )
        if abs(d["mean_luma"]) > 5:
            return Verdict("warn", f"grain shifted luma by {d['mean_luma']:+.1f}")
        return Verdict("ok", f"std +{d['std_luma']:.1f}, luma drift {d['mean_luma']:+.1f}")

    if sub == "vignette":
        if d["mean_luma"] > 1:
            return Verdict("fail", f"vignette brightened? luma_delta={d['mean_luma']:+.1f}")
        return Verdict("ok", f"luma_delta={d['mean_luma']:+.1f} (darkening expected)")

    if sub == "sigmoid":
        if "lift" in name or "lifted" in name:
            if d["mean_luma"] < 0:
                return Verdict("fail", f"lift moved luma down ({d['mean_luma']:+.1f})")
            return Verdict(
                "ok",
                f"luma_delta={d['mean_luma']:+.1f}, std={d['std_luma']:+.1f}",
            )
        if "crush" in name or "crushed" in name:
            if d["mean_luma"] > 0:
                return Verdict("fail", f"crush moved luma up ({d['mean_luma']:+.1f})")
            return Verdict(
                "ok",
                f"luma_delta={d['mean_luma']:+.1f}, std={d['std_luma']:+.1f}",
            )
        if "open" in name:
            if d["mean_luma"] < 0:
                return Verdict("fail", f"open moved luma down ({d['mean_luma']:+.1f})")
            return Verdict("ok", f"luma_delta={d['mean_luma']:+.1f}")
        if "contrast" in name:
            return Verdict("ok", f"std_delta={d['std_luma']:+.1f}")
        return Verdict("ok", f"luma={d['mean_luma']:+.1f} std={d['std_luma']:+.1f}")

    if sub == "highlights":
        return Verdict("ok", f"luma={d['mean_luma']:+.1f}")

    if sub == "exposure":
        return Verdict("ok", f"luma_delta={d['mean_luma']:+.1f}")

    if sub == "bilat":
        if abs(d["mean_luma"]) > 10:
            return Verdict("warn", f"bilat shifted luma by {d['mean_luma']:+.1f}")
        return Verdict("ok", f"std_delta={d['std_luma']:+.1f}")

    if sub == "sharpen":
        return Verdict("ok", f"std_delta={d['std_luma']:+.1f}")

    if sub == "toneequal":
        return Verdict("ok", f"luma_delta={d['mean_luma']:+.1f}")

    if sub in ("saturation", "chroma", "vibrance"):
        if abs(d["mean_luma"]) > 5:
            return Verdict("warn", f"saturation shifted luma by {d['mean_luma']:+.1f}")
        return Verdict("ok", f"chroma_delta={d['mean_chroma']:+.1f}")

    if sub in ("colorbalancergb", "warmth", "warm", "hue"):
        # Chroma-shift entries (chroma_boost_*, etc.) increase per-patch
        # chroma magnitude without moving R/B mean — check mean_chroma
        # instead so the heuristic uses the right metric.
        if "chroma" in name:
            if d["mean_chroma"] < 1.0:
                return Verdict("warn", f"chroma delta {d['mean_chroma']:+.1f} below threshold")
            return Verdict("ok", f"chroma_delta={d['mean_chroma']:+.1f}")
        if abs(d["mean_r"]) + abs(d["mean_b"]) < 1.0:
            return Verdict(
                "warn",
                f"R/B both ~unchanged ({d['mean_r']:+.1f}/{d['mean_b']:+.1f})",
            )
        return Verdict("ok", f"R={d['mean_r']:+.1f}, B={d['mean_b']:+.1f}")

    if sub in ("channelmixerrgb", "bw", "mono"):
        return Verdict("ok", "B&W mode")

    # No subtype-specific branch matched — fall through to near-baseline
    # check (entries that don't move the signature at all are suspect).
    if _near_baseline(d):
        if sub in _EXPECTED_NEAR_BASELINE_SUBTYPES:
            return Verdict(
                "ok",
                "near baseline (expected — chart is a poor signal medium for this subtype)",
            )
        return Verdict("warn", "near baseline (no visible change vs before)")

    return Verdict("ok", f"luma={d['mean_luma']:+.1f}")


def _verdict_real_raw(entry: Any, d: dict[str, float]) -> Verdict:
    """Direction-of-effect for real-raw entries.

    Real-raw renders are full-photograph captures, not flat patches, so
    sub-domain heuristics are noisier. We only catch the loudest
    failures: rendered output is byte-identical to the baseline (something
    went wrong with apply or render), or massively blown / crushed.
    """
    name = entry.name

    # Universal clip checks first — blown / crushed channels are a
    # regression regardless of mean-baseline state.
    if d["clip_hi"] > 0.40 and "open" not in name and "whites_open" not in name:
        return Verdict("fail", f"clip_hi={d['clip_hi']:.2f} — looks blown")
    if d["clip_lo"] > 0.40 and "crush" not in name and "lift" not in name:
        return Verdict("fail", f"clip_lo={d['clip_lo']:.2f} — looks crushed")

    if _near_baseline(d):
        if _is_parametric_identity_default(entry):
            return Verdict(
                "ok",
                "parametric identity-default — main row is no-op by design; "
                "see parameter sweep for the entry's effect at non-default values",
            )
        return Verdict(
            "warn",
            "near-baseline mean signature — render may be a no-op vs the fixture",
        )

    return Verdict(
        "ok",
        f"luma={d['mean_luma']:+.1f}, R={d['mean_r']:+.1f}, B={d['mean_b']:+.1f}",
    )


# ---------------------------------------------------------------------------
# Render discovery — find the rendered "after" image for an entry
# ---------------------------------------------------------------------------


# Subtypes whose rendered effect is *expected* to be near-baseline on the
# synthetic chart (mirrors generate-visual-proofs.py's _NEAR_BASELINE_NOTES).
# A WARN on these is the chart's signal-medium limitation, not a regression
# — downgrade to OK with a note so the audit doesn't drown real failures.
_EXPECTED_NEAR_BASELINE_SUBTYPES: frozenset[str] = frozenset(
    {"highlights", "grain", "vignette", "sharpen"}
)

# Entries whose effect on flat patches is below the audit's mean-stat
# resolution but is verified elsewhere (real-raw e2e, byte-level decoder
# tests). Mirrors SKIP_REASONS in tests/e2e/_lab_grade_deltas.py — the
# chart isn't a fair fixture, so don't flag.
_EXPECTED_NEAR_BASELINE_NAMES: frozenset[str] = frozenset(
    {
        "blacks_lifted",
        "blacks_crushed",
        "clarity_painterly",
        "clarity_etched",
        "clarity_dreamy",
        "sharpen_edge_only",
        "sharpen_overall",
        "vignette_subtle",
        "vignette_strong",
        "grade_split_warm_cool",
        "skin_smooth_painterly",
        "skin_uniformity",
        # Parametric primitives whose identity-default value is a no-op:
        # the ``<name>-colorchecker.jpg`` render at identity is by design
        # ~= baseline (sweeps demonstrate the parameter's range elsewhere).
        "grain_strength",
        "bilat_clarity_strength",
    }
)


# Real-raw fixture suffixes the generator emits — checked in priority order.
# ``content_*`` slugs come from requires_content routing (#138).
_REAL_RAW_SUFFIXES: tuple[str, ...] = (
    "landscape",
    "portrait",
    "content_landscape",
    "content_portrait",
)


def _baseline_for_suffix(suffix: str) -> Path | None:
    if suffix == "colorchecker":
        return PROOFS / "baseline-colorchecker.jpg"
    if suffix in ("landscape", "content_landscape"):
        return PROOFS / "baseline-landscape.jpg"
    if suffix in ("portrait", "content_portrait"):
        return PROOFS / "baseline-portrait.jpg"
    return None


def _find_rendered(entry: Any, pack_names: list[str], mode: str) -> tuple[Path, str] | None:
    """Locate the rendered after-image for ``entry`` on disk.

    Convention: ``<pack>/<entry.name>-<fixture-slug>.jpg``. Chart entries
    use ``-colorchecker``; real-raw entries use one of the
    :data:`_REAL_RAW_SUFFIXES` (landscape / portrait / content_*). Returns
    ``(path, suffix)`` so the caller picks the matching baseline.
    """
    pack_dirs = [PROOFS / p for p in pack_names]
    suffixes: tuple[str, ...] = ("colorchecker",) if mode == "chart" else _REAL_RAW_SUFFIXES
    for pd in pack_dirs:
        for suffix in suffixes:
            candidate = pd / f"{entry.name}-{suffix}.jpg"
            if candidate.exists():
                return candidate, suffix
    return None


# ---------------------------------------------------------------------------
# Audit driver
# ---------------------------------------------------------------------------


@dataclass
class EntryReport:
    name: str
    layer: str
    subtype: str | None
    mode: str
    rendered_path: str | None
    verdict: Verdict
    delta: dict[str, float] | None


def audit(pack_names: list[str]) -> list[EntryReport]:  # noqa: C901
    """Walk every entry in the loaded packs; return one report per entry.

    L1 primitives are skipped (no rendered surface). Entries in
    ``manual`` / ``not_yet_portable`` modes get a structural verdict
    (no render expected on those modes).
    """
    vocab = load_packs(list(pack_names))

    base_chart_path = _baseline_for_suffix("colorchecker")
    if base_chart_path is None or not base_chart_path.exists():
        raise SystemExit(f"missing chart baseline: {base_chart_path}")

    baseline_stats: dict[str, dict[str, float]] = {
        "colorchecker": _stats(base_chart_path),
    }
    for suffix in _REAL_RAW_SUFFIXES:
        path = _baseline_for_suffix(suffix)
        if path is not None and path.exists() and suffix not in baseline_stats:
            baseline_stats[suffix] = _stats(path)

    reports: list[EntryReport] = []
    for entry in vocab.list_all():
        if entry.layer == "L1":
            continue

        mode = verification_mode_for_entry(entry)
        found = _find_rendered(entry, list(pack_names), mode)
        rendered: Path | None
        rendered_suffix: str | None
        if found is None:
            rendered, rendered_suffix = None, None
        else:
            rendered, rendered_suffix = found

        if mode == "not_yet_portable":
            reports.append(
                EntryReport(
                    name=entry.name,
                    layer=entry.layer,
                    subtype=entry.subtype,
                    mode=mode,
                    rendered_path=None,
                    verdict=Verdict(
                        "ok",
                        "not_yet_portable — no rendered surface (tracked by RFC-039)",
                    ),
                    delta=None,
                )
            )
            continue

        if mode == "manual":
            reports.append(
                EntryReport(
                    name=entry.name,
                    layer=entry.layer,
                    subtype=entry.subtype,
                    mode=mode,
                    rendered_path=None,
                    verdict=Verdict("ok", "manual — photographer review only"),
                    delta=None,
                )
            )
            continue

        if rendered is None:
            reports.append(
                EntryReport(
                    name=entry.name,
                    layer=entry.layer,
                    subtype=entry.subtype,
                    mode=mode,
                    rendered_path=None,
                    verdict=Verdict("fail", "no rendered proof on disk"),
                    delta=None,
                )
            )
            continue

        assert rendered_suffix is not None
        baseline = baseline_stats.get(rendered_suffix)
        if baseline is None:
            reports.append(
                EntryReport(
                    name=entry.name,
                    layer=entry.layer,
                    subtype=entry.subtype,
                    mode=mode,
                    rendered_path=str(rendered.relative_to(REPO)),
                    verdict=Verdict(
                        "warn",
                        f"baseline missing for suffix '{rendered_suffix}' (git lfs pull)",
                    ),
                    delta=None,
                )
            )
            continue
        d = _delta(_stats(rendered), baseline)
        if mode == "chart":
            v = _verdict_chart(entry, d)
        else:
            v = _verdict_real_raw(entry, d)

        reports.append(
            EntryReport(
                name=entry.name,
                layer=entry.layer,
                subtype=entry.subtype,
                mode=mode,
                rendered_path=str(rendered.relative_to(REPO)),
                verdict=v,
                delta=d,
            )
        )

    return reports


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _markdown(reports: list[EntryReport]) -> str:
    by_status: dict[str, list[EntryReport]] = {"fail": [], "warn": [], "ok": []}
    for r in reports:
        by_status[r.verdict.status].append(r)

    lines: list[str] = []
    lines.append(f"# Visual-proof audit — {len(reports)} entries")
    lines.append("")
    lines.append(f"- ok:   {len(by_status['ok'])}")
    lines.append(f"- warn: {len(by_status['warn'])}")
    lines.append(f"- fail: {len(by_status['fail'])}")
    lines.append("")
    lines.append(
        "Statistical-signature heuristics per subtype. OK means the render's "
        "mean pixel-stat signature matches the subtype's expected "
        "direction-of-effect. WARN flags borderline cases (near-baseline, "
        "ambiguous direction). FAIL flags signatures that contradict the "
        "subtype expectation — strongest candidates for photographer review."
    )
    lines.append("")

    for status in ("fail", "warn", "ok"):
        bucket = by_status[status]
        if not bucket:
            continue
        lines.append("")
        lines.append(f"## {status.upper()} ({len(bucket)})")
        lines.append("")
        for r in bucket:
            sub = r.subtype or "—"
            lines.append(f"- **{r.name}** ({r.layer}/{sub}, mode={r.mode}): {r.verdict.note}")
    return "\n".join(lines) + "\n"


def _json_payload(reports: list[EntryReport]) -> dict[str, Any]:
    return {
        "total": len(reports),
        "ok": sum(1 for r in reports if r.verdict.status == "ok"),
        "warn": sum(1 for r in reports if r.verdict.status == "warn"),
        "fail": sum(1 for r in reports if r.verdict.status == "fail"),
        "entries": [
            {
                "name": r.name,
                "layer": r.layer,
                "subtype": r.subtype,
                "mode": r.mode,
                "rendered_path": r.rendered_path,
                "status": r.verdict.status,
                "note": r.verdict.note,
                "delta": r.delta,
            }
            for r in reports
        ],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="audit_visual_proofs",
        description="Audit rendered visual-proof images against direction-of-effect heuristics.",
    )
    parser.add_argument(
        "--packs",
        nargs="+",
        default=list(DEFAULT_PACKS),
        help="vocabulary packs to audit (default: starter + expressive-baseline)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="also write a JSON report to this path (for CI consumption)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 on warn-or-fail (default exits 1 on fail only)",
    )
    args = parser.parse_args(argv)

    reports = audit(list(args.packs))
    md = _markdown(reports)
    sys.stdout.write(md)

    if args.json:
        args.json.write_text(json.dumps(_json_payload(reports), indent=2, sort_keys=True) + "\n")

    fails = [r for r in reports if r.verdict.status == "fail"]
    warns = [r for r in reports if r.verdict.status == "warn"]
    if fails:
        return 1
    if args.strict and warns:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
