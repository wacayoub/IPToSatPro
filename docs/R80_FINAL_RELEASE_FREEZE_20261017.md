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
- Eight offline synthetic package regression tests passed locally. GitHub
  Actions runs on Python 3.11 and 3.14 are configured; their outcomes must
  not be described as passing without actual logs.
- Final binary is **NOT built or distributed**, pending the exact pinned IPK
  intake. No more receiver tests needed for the existing hardware-validated
  functional paths. No R80 stable update is live.

## Final sign-off scope

Validated: installation, config preservation, Preview functionality,
image/audio selected streams, fallback, Enigma2 restart.
Not certified: quantitative cold-Preview P95, 4K/HDR exhaustive matrix,
unattended long-term uptime. Explicitly state these limitations.

No additional manual tests should be required for the already confirmed
paths unless the actual final distributable differs in executable code.
