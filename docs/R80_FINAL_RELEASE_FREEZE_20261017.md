# IPToSatPro R80 FINAL — Release freeze / 17 October 2026

Status: **release branch prepared, binary intake pending, NOT yet published to stable channel**.

## Frozen hardware-validated source

- Verified on Vu+ Zero 4K / OpenATV 8.0.1, after restarting Enigma2.
- Installed and tested: `1.0.46-r80.1-indexfocus-hotpath-rc1`.
- Package filename on receiver:
  `/tmp/iptosatpro-r801-indexfocus-hotpath-rc1-NOT_INSTALLED.ipk`.
- Package bytes: **461250**.
- Package SHA256: `b6b1fe72ffbcbfaa398bd261c000f9361159a9e08f606a0af9d6da3d5ef04e5e`.
- Installed exact core SHA256: `74cd89b8c6a41b4537fd758cedb3a07b2bc0f9a5c215063e4c45b99e5d92cd2a`.
- Receiver-local verified backup:
  `/home/root/iptosatpro-r76-backups/r801-indexfocus-20261017T095700-11732`.
- Post-install `opkg rc=0`, 6 tracked mapping/config hashes unchanged.
- Owner reports post-restart: Preview Browser OK; picture/audio beIN, TOD, OSN and Moroccan channels OK; no-signal SAT -> IPTV fallback OK.
- First-display/cold Preview latency was NOT measured. Therefore do not market a specific speed/P95 target as met.

## Functional freeze policy

This is a **code freeze**. The release artifact must preserve the validated
`core.py`, player, themes, layout, monitor, TS bridge, mapping engine, and
all package resources exactly. It is permissible to update only version and
safe update-channel metadata (plugin.py, updater.py, control) once verified by
an independent package diff; no functional code changes.

## Publication blocker and precise next step

The exact receiver-built IPK has not been uploaded into GitHub; it cannot
be reconstructed from SHA256 alone. Retrieve the receiver file above through
SFTP and attach the binary to the GitHub release preparation or ChatGPT
conversation. Check **461250 bytes** and **SHA256
b6b1fe72ffbcbfaa398bd261c000f9361159a9e08f606a0af9d6da3d5ef04e5e**
before treating it as the validated source.

Do not publish a reconstructed R76.15/R80 RC1 payload as if it were this
validated Index Focus build. Do not promote the old R80.1 beta payload, whose
core differs, to stable. Do not update production `main/update.json` until
the distributable, reproducible final IPK has been verified.

## Offline final packaging progress (17 October)

- Offline final packager: `scripts/prepare_r80_final_offline.py`.
- Proposed final package metadata version: `1.0.46-r80.2-final`. This is
  intentionally higher than installed `1.0.46-r80.1-indexfocus-hotpath-rc1`,
  to avoid an inadvertent opkg downgrade classification.
- Final updater points to the **R80-only**, not-yet-published manifest:
  `release/r80-indexfocus-final-20261017/staging/r80-final.update.json`.
  `main/update.json` remains R70; never use it as the R80 final update
  target while production has not changed.
- Ten offline synthetic tests (8 package, 2 distribution bundle) passed locally. GitHub
  Actions runs on Python 3.11 and 3.14 are configured; their outcomes must
  not be described as passing without actual logs.
- Final binary is **NOT built or distributed**, pending the exact pinned IPK
  intake. No more receiver tests needed for the existing hardware-validated
  functional paths. No R80 stable update is live.

## Offline release-bundle construction verified (17 October)

- Source code: `scripts/prepare_r80_release_bundle_offline.py`.
- A **real local Python 3.13.5 run** completed **10 of 10** offline tests,
  including eight final-package safety tests and two release-bundle tests.
  These are synthetic package fixtures; they are **not** a test of the missing
  461250-byte receiver-generated candidate.
- Bundle creation yields four matching deliverables:
  `iptosatpro-r80-final.ipk`, `r80-final.b64`,
  `r80-final.update.json`, and `SHA256SUMS.txt`.
- Version monotonicity verified locally using `dpkg --compare-versions`:
  `1.0.46-r80.2-final` sorts newer than `1.0.46-r80.1-indexfocus-hotpath-rc1`.
- The package remains unpublished; `main/update.json` is unchanged.
- Once the exact original RC1 package is supplied, no further fixture work
  should be needed: perform the final pinned source and generated-bundle
  integrity verification, then separately approve publication.
- GitHub Actions execution and results are **not confirmed** here.

## Final distributable IPK received and independently inspected (17 October)

The exact receiver-generated metadata-promotion candidate was supplied in chat:
- Received candidate: **461200 bytes**, SHA256
  `8828d8271a3e192822c49d36fdf2c7a1a2635fbcc5083b9169bebcf29ee29a02`.
- Validated that its Base64, manifest and SHA256SUMS matched exactly, and that its
  operational core matched SHA256
  `74cd89b8c6a41b4537fd758cedb3a07b2bc0f9a5c215063e4c45b99e5d92cd2a`.
- Discovered legacy package-control branding that still described `r68 BETA`,
  listed `OpenAI` as maintainer, and logged a release-candidate install message.
  For release quality and correct attribution, corrected **only** those three
  *control.tar.gz* text fields: description, maintainer `wacayoub`, and
  passive postinst message. No maintainer hook operations beyond an informational
  `printf` and `exit 0`.
- Corrected final artifact: **461198 bytes**, SHA256
  `5c7e48ba51e5ed1689c5930df72309c7c495cc702f5cff6b91142ddc2985606a`.
- Byte-for-byte **entire data.tar.gz identical** to received candidate.
  All 87 plugin files, 2 tsbridge files, and 17 compiled Python module files
  are unchanged; operational core SHA256 unchanged.
- Corrected Base64, update manifest, SHA256SUMS and an independent JSON audit
  were generated in the current chat session and are available as artifacts.
- Version `1.0.46-r80.2-final` orders newer than the installed R80.1 RC1.
- **Publication remains blocked** pending upload of the *corrected* Base64
  payload and matching manifest to this GitHub release branch. Do NOT upload
  the old 461200-byte manifest together with the corrected 461198-byte binary.
  `main/update.json` remains R70 final. The corrected R80 final IPK has not
  yet been installed or independently validated on receiver as a final binary.

## Final sign-off scope

Validated: installation, config preservation, Preview functionality,
image/audio selected streams, fallback, Enigma2 restart.
Not certified: quantitative cold-Preview P95, 4K/HDR exhaustive matrix,
unattended long-term uptime. Explicitly state these limitations.

No additional manual tests should be required for the already confirmed
paths unless the actual final distributable differs in executable code.
