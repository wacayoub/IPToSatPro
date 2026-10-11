# IPToSatPro — Enigma2 / OpenATV

**Latest published online release:** `1.0.46-r70-final` (11 October 2026), built from the SHA256-verified `r69-beta` release. Published in `main`, but not yet field-validated on the user's receiver.

## What is actually finalized

- Retains the verified r69 audio/video player logic, fast MANUAL LOCK, prewarm, fallback, timeshift and TS relay byte-for-byte.
- Retains the r69 Preview candidate scoring, including French vs explicit Italian/Polish feed protection, provider family and channel number checks. Current behavior is regression tested directly from the actual package, not invented simulations.
- Adds a reproducible package build, strict SHA256 and size verification, and an offline check that **no runtime Python methods, user settings or relay files change**.
- Keeps experimental TOD out of this version completely.
- Preserves the receiver's installed plugins, mappings and credentials until the owner explicitly runs an update.

**Important:** This release consolidates and verifies the existing code. It does not demonstrate a new 1–2-second zapping speed or resolve every black-screen/4K/audio problem on the physical Vu+ Zero 4K. Real hardware validation is still required to prove performance and stability.

## Online update (available now)

Open **IPToSatPro → Dashboard → 2 Online Update → GREEN Check GitHub**, check the version `1.0.46-r70-final`, then confirm only if you want to install it.

The updater uses `update.json`, downloads the versioned Base64 IPK, and validates package size and SHA256.

## Alternative verified download (without installation)

The official [download-latest.sh](download-latest.sh) downloads and checks `/tmp/iptosatpro.ipk` without installing or restarting Enigma2. There is no need to copy an IPK through ChatGPT. The user can choose to install the package manually afterward.

## Restore existing r69 (after intentional installation only)

The versioned `download-r69-beta.sh` script remains in the repository. Keep a copy of personal mappings/settings before any installation and follow normal OpenATV opkg practices.

## Build/test (offline)

```bash
python3 scripts/build-r70-final.py
python3 -m unittest discover -s scripts -p 'test_r70_candidate.py' -v
python3 scripts/check_locked_fast_guard.py r70-final.ipk
python3 scripts/test_r70_preview_logic.py
```

Publication is gated on a deterministic `277002`-byte IPK with SHA256 `471039d712e81c03bacbcf0394325dd07b56d8bbf3f2002bf6a48f89f93b791c`. The exact hash must match on reconstruction. The repository CI cannot substitute for testing a decoder.
