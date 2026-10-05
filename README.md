# Agent Darkroom

A headless RAW photo editor that a coding agent can drive through a CLI. The agent loads a photo, inspects a preview, applies a reversible adjustment, renders again, checks the change, and exports. [darktable](https://www.darktable.org/) does the pixel processing; this tool manages edits as versioned XMP sidecars and gives agents predictable JSON responses.

This project builds on [Chemigram](https://github.com/chipi/chemigram) and preserves its MIT license and attribution. It focuses the existing engine on a reliable CLI feedback loop. No AI model, account, or service is bundled.

## Requirements

- Python 3.11 or newer
- `darktable-cli` 5.4 or 5.6 on `PATH`, or set `DARKTABLE_CLI` to its executable path
- Lensfun shared library and profile database for automatic optical correction
- A coding agent that can read command output and inspect local image files

The current release was exercised with darktable 5.4.1 and 5.6.2 on Ubuntu. The baseline exposure and multi-instance XMP order are calibrated for darktable 5.x; check new major versions with `status --probe` and a test render before relying on them.

## Install

[uv](https://docs.astral.sh/uv/) provides an isolated install from the public repository:

```bash
uv tool install git+https://github.com/ralfboltshauser/agent-darkroom.git
agent-darkroom --json status --probe /path/to/photo.ARW
```

`chemigram` remains an alias for compatibility. The Python import package is also `chemigram`, so this distribution and upstream Chemigram should be installed in separate Python environments.

For development:

```bash
git clone https://github.com/ralfboltshauser/agent-darkroom.git
cd agent-darkroom
uv sync --extra dev
uv run agent-darkroom --json status --probe /path/to/photo.ARW
```

The installer includes the starter and expressive vocabulary packs. The latter has the primary exposure, tone, color, crop, and look controls. A workspace stores a private copy of the source RAW, content-addressed XMP snapshots, previews, and exports. By default it lives at `~/Pictures/Chemigram`; set `CHEMIGRAM_WORKSPACE` to place it elsewhere. Each workspace root gets its own darktable config directory automatically.

## Agent loop

All editing commands return one JSON result or error line when `--json` is set. Use the full `snapshot_hash` as the expected HEAD for the next edit. Preview and export paths are tied to that hash, so an old preview never silently becomes the current one.

```bash
export CHEMIGRAM_WORKSPACE=/tmp/agent-photos

agent-darkroom --json ingest /path/to/photo.ARW --image-id portrait
agent-darkroom --json render-preview portrait --size 1024
agent-darkroom --json inspect portrait
agent-darkroom --json vocab list --query exposure --names-only
agent-darkroom --json vocab show exposure

agent-darkroom --json apply-primitive portrait --entry exposure --value 1.5 \
  --expect-head BASELINE_HASH
agent-darkroom --json render-preview portrait --size 1024
```

The agent should open the returned `jpeg_path`, judge the photo, and keep or change the edit. For a local lift, place an ellipse in normalized image coordinates and check its actual footprint:

```bash
agent-darkroom --json apply-primitive portrait --entry exposure --value 0.6 \
  --mask-spec '{"dt_form":"ellipse","dt_params":{"center_x":0.5,"center_y":0.45,"radius_x":0.3,"radius_y":0.35,"border":0.1}}' \
  --expect-head GLOBAL_HASH
agent-darkroom --json compare portrait GLOBAL_HASH LOCAL_HASH --size 1024 --difference
agent-darkroom --json inspect portrait
agent-darkroom --json export-final portrait --format jpeg
```

On ingest, the expressive pack automatically applies a Lensfun correction when camera and lens metadata resolve to one compatible installed profile. The JSON `lens_correction` field says which profile matched and whether distortion, lateral chromatic aberration, and vignetting data are available. Fixed lens cameras can match by their unique mount even when EXIF omits the lens name. Lensfun calculates an output scale to remove invalid borders. If there is no unambiguous profile, the field says `unavailable` and the image remains uncorrected. Set `CHEMIGRAM_LENSFUN_DB_DIR` to use a custom Lensfun `version_1` directory. The tool does not yet apply corrections from embedded RAW metadata or Adobe LCP profiles; coverage depends on the installed Lensfun database. To compare with the uncorrected image, run `agent-darkroom --json remove-module portrait --operation lens`, then render again.

`compare --difference` returns a side-by-side image and an amplified difference PNG. Open the difference image to catch misplaced masks or unexpected global changes. The `inspect` result reports luminance percentiles, near-black and near-white fractions, dimensions, camera metadata, and whether an ICC profile is embedded. These measurements help diagnose exposure and clipping; visual inspection still decides whether an edit is good.

Use `agent-darkroom --json checkout portrait HASH --branch retry-name` to revisit a snapshot and keep editing from it. `reset portrait` returns the current branch to the baseline. `get-state` lists enabled operations and instance priorities; `log` and `diff` show version history. `--mask-spec-file` accepts a JSON file when shell quoting is inconvenient.

The CLI rejects masked `bilat` clarity: a real darktable 5.6.2 trial showed a large effect outside the requested ellipse. Other module and mask combinations should be checked with `compare --difference` before final export. See [mask controls](docs/guides/mask-applicable-controls.md) for shape parameters.

## Validation

The first independent agent trial and a fresh retry graded the [portrait RAW fixture](tests/fixtures/raws/README.md) through the CLI and exported full resolution JPEGs with embedded ICC profiles. The retry used global exposure, a masked local exposure, a crop, visual preview checks, and a difference image. That trial exposed the same-module stacking bug, which is now covered by a live RAW regression test. The original photographer published the fixture under CC BY-SA 4.0; provenance is recorded with the fixture.

Run tests and checks from a checkout:

```bash
uv run --extra dev ruff check .
uv run --extra dev pytest -q
DARKTABLE_CLI=/path/to/darktable-cli uv run --extra dev pytest -q tests/e2e/test_agent_masked_exposure.py
uv build
```

The general test suite skips tests that require optional RAW fixtures or a configured renderer when those are unavailable. The live test above requires the LFS portrait file and darktable-cli.

## Scope and attribution

This is a CLI orchestration layer over darktable, built from Chemigram's XMP, vocabulary, masking, and versioning engine. It supports RAW ingest, named and parameterized edits, drawn masks, snapshots, preview inspection, comparisons, and JPEG or PNG export. Darktable's own license and installation are separate from this repository. The source code is MIT licensed; bundled RAW test photos have their own licenses in [fixture provenance](tests/fixtures/raws/README.md).
