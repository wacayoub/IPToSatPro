# IPToSatPro — Enigma2 / OpenATV

**Latest stable release:** `1.0.46-r80.2-final` (17 October 2026), also known as **R80 FINAL / Index Focus**.

## Verified release

- **Receiver:** Vu+ Zero 4K, OpenATV 8.0.1 (Python 3.14).
- **Functional reference:** previously installed R80.1 Index Focus RC1 passed Preview Browser, image/audio on beIN/TOD/OSN/Moroccan channels and no-signal SAT → IPTV fallback checks.
- **R80 FINAL installation:** the receiver's Online Update interface displayed `Installed version: 1.0.46-r80.2-final`, `Latest GitHub version: 1.0.46-r80.2-final` and `IPToSat Pro is up to date.`
- **Code freeze:** same exact operational `core.py` SHA256 `74cd89b8c6a41b4537fd758cedb3a07b2bc0f9a5c215063e4c45b99e5d92cd2a`. Release differences from R80.1 are package/version/update metadata, not candidate-ranking, playback, timeshift, TS bridge, GUI layout or mapping logic.
- **Package:** `461198` bytes, SHA256 `5c7e48ba51e5ed1689c5930df72309c7c495cc702f5cff6b91142ddc2985606a`.
- **Limitations:** first-display/cold Preview P95, exhaustive 4K/HDR/audio paths and long-term unattended uptime have **not** been quantitatively certified. Earlier user-observed functional checks do not establish those performance targets.

## Online update

Open **IPToSatPro → Online Update → Check GitHub** to view the available version. Installation should be explicit and backed up. The update feed on `main` references the checksum-pinned Base64 artifact `payload/r80-final.b64`.

For the tested Vu+ already showing R80 FINAL, **no reinstall is necessary**.

## Download only — no installation

`download-latest.sh` downloads `/tmp/iptosatpro.ipk` from the stable R80 Base64 artifact and verifies both byte count and SHA256; it does not install or restart Enigma2. The known-good R80.1 user backup, existing configurations and mappings should be preserved.

## Release integrity

- [Stable update feed](update.json)
- [R80 FINAL Base64 artifact](payload/r80-final.b64)
- [Release-branch acceptance record](https://github.com/wacayoub/IPToSatPro/blob/release/r80-indexfocus-final-20261017/docs/R80_FINAL_RELEASE_FREEZE_20261017.md)
- [R80 FINAL optional guarded installer](https://github.com/wacayoub/IPToSatPro/blob/release/r80-indexfocus-final-20261017/scripts/install_r80_final_guarded.py)

The older R70 build and tests remain available for historical verification; they are not the current stable download. R80.2 is installed and recognized on the primary user receiver, but those observations are not a claim of exhaustive hardware validation.
