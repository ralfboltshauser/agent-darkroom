# Real-raw fixtures for visual-proof rendering

Two real photographic raws used by `scripts/generate-visual-proofs.py` to
render the ~38 vocabulary entries that touch raw-domain modules
(`temperature`, `colorequal`, `denoiseprofile`, `lens`, `filmicrgb`,
`hazeremoval`, `ashift`, `crop`, `retouch`, `diffuse`). The synthetic
ColorChecker fixture is structurally wrong for these modules — see
`src/chemigram/core/visual_verification.py` and issue #129 for the
full discriminator rationale.

Both files are stored via Git LFS (see `.gitattributes` for the tracked
extensions). To work with them locally:

```bash
git lfs install --skip-repo   # one-time, avoids clobbering pre-commit's pre-push hook
git lfs pull                  # fetch the actual bytes for these fixtures
```

## Fixtures

| File | Camera | Size | Used by |
|---|---|---|---|
| `landscape.ARW` | Sony DSC-RX10M4 (RX10 IV) | ~20 MB | Sky / foliage / horizon / haze / lens / WB / filmic entries |
| `portrait.ARW` | Sony ZV-E10 | ~24 MB | Skin / eye / subject mask / retouch / portrait-look entries |
| `cross_camera_canon.CR3` | Canon EOS R6 | ~5 MB | Cross-body verification of the RFC-039 raw-aware apply path (#142) |
| `cross_camera_nikon.NEF` | Nikon D70 | ~5 MB | Cross-body verification of the RFC-039 raw-aware apply path (#142) |

The generator routes each real-raw vocabulary entry to one of the two
fixtures based on which terrain the entry needs:
- Entries whose `touches` set or name implies skin/face/eye/portrait work
  render against `portrait.ARW`.
- Everything else (the landscape/scene default) renders against
  `landscape.ARW`.

## Provenance and license

Both files are **CC BY-SA 4.0** — Creative Commons Attribution-ShareAlike
4.0 International. License terms: https://creativecommons.org/licenses/by-sa/4.0/

### landscape.ARW

- **Source thread**: https://discuss.pixls.us/t/moody-landscape/52605
- **Direct URL** (current short-URL at time of import):
  https://discuss.pixls.us/uploads/short-url/2VAHfh9N7AxgHQ8AhQ9nIABYvMx.ARW
- **License text on source page**:
  > "This file is licensed Creative Commons, By-Attribution, Share-Alike."
- **Attribution line**:
  Photo by the original poster on discuss.pixls.us thread "Moody Landscape"
  (https://discuss.pixls.us/t/moody-landscape/52605), licensed CC BY-SA 4.0.
- **Content**: clean horizon over water, sky+clouds, foliage, neutral
  capture (not pre-styled). Exercises `colorequal` sky-blue, `hazeremoval`,
  `filmicrgb` tone mapping, `ashift` perspective, `crop` framing, sky and
  foliage masks.

### portrait.ARW

- **Source thread**: https://discuss.pixls.us/t/home-portrait-give-me-your-version/54329
- **Direct URL** (current short-URL at time of import):
  https://discuss.pixls.us/uploads/short-url/fvSUwztV1q8xT54QDDrc3nIbHmr.ARW
- **License text on source page** (from poster pu.photograph):
  > "This file is licensed Creative Commons, By-Attribution, Share-Alike."
- **Attribution line**:
  Photo by pu.photograph on discuss.pixls.us thread "Home Portrait — give
  me your version"
  (https://discuss.pixls.us/t/home-portrait-give-me-your-version/54329),
  licensed CC BY-SA 4.0.

### cross_camera_canon.CR3

- **Source**: https://raw.pixls.us/ (curated CC0 raw sample repository)
- **Direct URL**: https://raw.pixls.us/getfile.php/4659/nice/Canon%20-%20EOS%20R6%20-%203%3A2.CR3
- **License**: CC0 / Public Domain — the raw.pixls.us upload form requires
  contributors to release their submissions under CC0. Per-file license is
  recorded in the site's JSON index (`getrepository.php?set=all`).
- **Attribution line** (not required under CC0, but recorded for
  traceability): raw.pixls.us community sample collection.
- **Content**: photographic ("nice"-path curation, not a colorchart). Used
  by #142's cross-body integration test to verify the RFC-039 camera-aware
  apply path produces directionally-correct WB shifts on a Canon body's
  EXIF coefficients (different from Sony / Nikon).

### cross_camera_nikon.NEF

- **Source**: https://raw.pixls.us/ (curated CC0 raw sample repository)
- **Direct URL**: https://raw.pixls.us/getfile.php/2060/nice/Nikon%20-%20D70%20-%2012bit%2012bit%20compressed%20(Lossy%20(type%201))%20(3%3A2).NEF
- **License**: CC0 / Public Domain — see notes under cross_camera_canon.
- **Attribution line** (not required under CC0): raw.pixls.us community
  sample collection.
- **Content**: photographic ("nice"-path curation). Used by #142's
  cross-body integration test against the Nikon D70's 12-bit compressed
  NEF — a third manufacturer's EXIF WB layout and Bayer pattern.
- **Content**: indoor single subject, face and eyes visible, neutral-cool
  capture, background visually separable from subject. Exercises skin
  `colorequal`, `retouch` heal/clone, skin / eye / subject masks.

## Caveats

- **Model release** — the portrait subject's identity is the photographer's
  to publish, not ours. We redistribute the raw under the CC BY-SA license
  the photographer chose to publish it under on the public forum thread,
  but we don't republish their identity beyond what's already on that
  public thread. If the photographer requests removal, we honor it.
- **Share-alike inheritance** — the visual-proof renders we ship under
  `docs/visual-proofs/` are derivative works of these raws. They inherit
  CC BY-SA 4.0. Compatible with the project's GPLv3 codebase; the
  derivative-render license is noted in the gallery markdown and in
  `LICENSING.md`.
- **Short-URL drift** — the `discuss.pixls.us/uploads/short-url/...` paths
  occasionally rotate. The source thread URLs are stable; if a re-import
  is needed, navigate to the thread and grab the current attachment URL.
- **Camera bodies** — primary gallery fixtures are both Sony. DSC-RX10M4
  (1-inch sensor bridge, 20 MP) for landscape; ZV-E10 (APS-C, 24 MP) for
  portrait. Both well-supported by darktable 5.x and by lensfun for
  lens-correction tests. The `cross_camera_*` fixtures (Canon EOS R6,
  Nikon D70) are used by #142's cross-body integration test, not by the
  gallery generator.

## Why ARW (and not JPEG or DNG)

The discriminator categorizes ~38 entries as `real_raw` because they need
darktable's input-profile chain (Sony color matrix → working profile →
display). A JPEG export has already been through that chain and can't
exercise it. A converted DNG would work but loses the camera-body-specific
input profile that's the whole point of testing these modules. Native
ARWs from real cameras are the honest fixture.

## Adding more fixtures

If a future real-raw entry needs terrain neither fixture covers (e.g.,
wildlife backlit, low-light street), add a new file here, document
provenance / license / attribution in this README, and update the
generator's routing in `scripts/generate-visual-proofs.py`.
