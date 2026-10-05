# Agent grading trials

On 2026-10-05, a separate coding agent graded `tests/fixtures/raws/portrait.ARW` through the CLI using darktable 5.6.2. The source is a Sony ZV-E10 RAW licensed CC BY-SA 4.0; see the [fixture provenance](../tests/fixtures/raws/README.md). The agent inspected each returned JPEG and the amplified difference image, then exported a full resolution JPEG with an embedded sRGB profile. Trial command traces and output images are kept locally under `.scratch/` because they include a photograph of a person.

## First trial

The agent applied global exposure (+1.5 EV), tried to add a masked exposure (+0.6 EV), then used masked tone equalizer and crop to finish. The masked exposure silently replaced the global exposure and darkened the preview. A masked tone equalizer worked; `compare --difference` localized its effect to the intended ellipse. The exported portrait was 3460 × 4881 pixels.

## Fix and retry

The first bug had two causes. XMP synthesis replaced the first exposure instance, then darktable ignored a new instance without an explicit `darktable:iop_order_list`. After both were fixed, a fresh agent trial used global +1.5 EV followed by a masked +0.6 EV exposure. The visual difference was centered on the subject, with a changed-pixel fraction of 0.260. A live RAW regression test now checks that the center changes substantially while an outside corner stays stable.

The retry found one further failure: masked `bilat` clarity changed 76.5% of pixels and its difference image was bright outside the ellipse. The agent discarded that edit. The CLI now rejects masked `bilat` with a specific error and suggests masked exposure or tone equalizer. The agent then cropped and exported a full 3460 × 4881 JPEG with an embedded ICC profile. Visual review found a readable low-key portrait with controlled highlights and no obvious color cast.

## What the trial changed in the CLI

- A neutral, explicit exposure baseline prevents the first edit from changing darktable's automatic starting exposure.
- Masked edits of an already used operation receive their own module instance and an explicit pipeline order list.
- `--expect-head`, revision-keyed render paths, `inspect`, and `compare --difference` make the edit loop observable.
- `get-state` reports actual operations and instance priorities; XMP does not retain vocabulary layer provenance.
- `checkout IMAGE HASH --branch NAME` starts an editable branch at an earlier version in one call.
- The expressive vocabulary is bundled and loaded by default; `vocab list --query ... --names-only` makes discovery concise.

This validates the demonstrated workflow on one real RAW and darktable 5.6.2. Mask behavior for other modules, other cameras, and future darktable versions still requires a rendered difference check.
