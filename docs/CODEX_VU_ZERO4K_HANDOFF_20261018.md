# IPToSatPro — Codex ↔ Vu+ Zero 4K finalization handoff (2026-10-18)

## Goal
Finish the user's existing IPToSatPro project **once**, using Codex for repository analysis/build/tests and an **explicitly authorized SSH session from a trusted machine on the Vu+ LAN** for the last receiver checks. Minimize user intervention and repeated audits. No new features or independent rewrites.

## Source-of-truth / release warning
- Repository: `wacayoub/IPToSatPro`, stable branch `main`.
- `main/update.json` still advertises **`1.0.46-r80.2-final`**, SHA256 `5c7e48ba51e5ed1689c5930df72309c7c495cc702f5cff6b91142ddc2985606a`. DO NOT presume R80.3 is published.
- Draft integration PR: https://github.com/wacayoub/IPToSatPro/pull/9 ; branch `fix/r803-playback-verification-20261017`.
- Most recent *in-chat local artifact* was named `IPToSatPro_FINAL.ipk`, metadata version **`1.0.46-r80.3.3-final`**, size 464714 bytes, claimed SHA256 `bfdbe0cb1e93113f5fa50d1243d19b61e589af0edd0ac4b3bf8e7992cbd49081`. **This local artifact is NOT the same as the published GitHub main release.** Codex must locate the genuine artifact from an authorized user-provided transfer or reproducibly reconstruct it from pinned source before any rollout. Never substitute another package with the same name.
- Expected frozen core sha256 `74cd89b8c6a41b4537fd758cedb3a07b2bc0f9a5c215063e4c45b99e5d92cd2a`.
- Receiver: Vu+ Zero 4K, OpenATV 8.0.1, Python 3.14.x (historical observation), plugin path `/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge`; log `/etc/enigma2/SatIPTVBridge/bridge.log`. These are historical facts, not a current SSH observation.
- The user is fatigued by endless beta revisions, repetitive SSH commands and audits; prefer a single coherent finish.

## User-validated behavior (and still-open issue)
- On R80.3 RC1, **picture + sound PASSED 4/4** on beIN SPORTS 3, beIN SPORTS 4, MBC1 HD and CANAL+ LIVE 2 (user reported, not machine telemetry).
- beIN 4K with TOD: sound present on same selected stream **inside Preview Browser**, absent during automatic Live playback after leaving Preview. Later R80.3.1 and R80.3.2 targeted audio changes were prepared; final hardware audio parity **was NOT user-confirmed**.
- Prior R70-RC6 TOD recovery code/documentation resides on `feature/r70-rc6-tod-audio-recovery`: `r70/tod_audio_recovery_rc6.py`, `r70/TOD_AUDIO_RECOVERY_RC6.md`. Exact TOD EVENT 1 4K HDR detection and audio-safe ServiceApp modes 5002/4097 were the important regressions to preserve.
- Priority exact FHD manual mapping and UNMAP tombstones/forced_correct from R80.2.2; never silently downgrade FHD→HD or alter mappings.
- Performance: earlier cold preview samples were much slower than warm cached hits; R80.3.3 already includes R76.15/R80 indexed nomination, local ranking cache, lazy/async Preview. No validated comparative cold P95 on receiver. Do not retroport older speed hacks blindly.
- Other behaviors to preserve: GREEN manual correction and pins, PRIMARY/BACKUP1/BACKUP2 stream replicas, Neo Dark Classic Preview B, themes, candidate logos/EPG, video resolution, source selection, no-signal SAT fallback, existing native timeshift/AV behavior.

## Access architecture
**Option A recommended:** Run Codex CLI or desktop Codex **on a trusted Windows/Linux/Mac computer on the same home LAN as Vu+** and give the shell narrowly scoped SSH access. Codex Cloud can work on the GitHub code, but does not automatically have a route to the receiver's private address. For access outside the home network, use a privately authenticated VPN (e.g. an approved WireGuard/Tailscale gateway on an always-on trusted host), not a public exposed SSH port.
- **Never** place SSH password, private keys, IPTV provider credentials, URL tokens, or WAN IP addresses in this repository, PR, chat, logs or Codex prompts.
- Use an SSH key with verified host fingerprint; prefer dedicated restricted identity / no root unless receiver operations require root. Receiver-specific work may require explicit sudo/root and approval.
- No router port-forwarded SSH; no remote root exposed to internet.
- Machine with LAN/VPN link must be online for receiver access. Codex Windows remote control is not in itself an SSH tunnel.

## Codex execution contract
1. **Inventory READ ONLY:** `uname -a`, `python3 --version`, `opkg list-installed | grep -i` related package, parse `PLUGIN_VERSION` and `CURRENT_VERSION`, hash installed `core.py` and `monitor.py`, discover installed update feed, list current logs with sanitized channel-level events only. Do NOT dump mapping files or URLs/usernames/passwords. Verify current playback state and package provenance before edits.
2. **Source & build:** Compare installed artifacts to pinned GitHub PR/source and local FINAL artifact. Identify only genuine remaining functional errors. Run offline tests and deterministic IPK builder. Preserve existing private receiver settings, mappings, logos and caches. Assess whether final artifact is actually reproducible; if not, explicitly flag instead of claiming a verified release.
3. **Before installation:** Save a time-stamped private backup of plugin directory, `/etc/enigma2/SatIPTVBridge`, `/etc/enigma2/settings`. Hash the resulting backup. Never upload the backup, secret logs or credentials to public GitHub. Check free storage. Don't run `opkg`, stop Enigma2 or reboot without the user's explicit approval, even if a package is called FINAL.
4. **Small hardware acceptance:** With consent and preferably when TV is available, verify a non-beIN control channel (MBC1 or CANAL+ LIVE 2) with decoded picture, check audio tracks and user-audible result separately; verify beIN 4K TOD Preview vs Live uses same selected IPTV fingerprint and same safe playback identity. Track actual ServiceApp type and player logs but don't infer sound from `IPTV_OK`, `validated-ts-data` or `audioTracks()>0`. Bounded mode retry and candidate rollback only.
5. **Release:** Once tests pass, build **one** reproducible checksum-pinned release, update `main/update.json` + payload only after explicit approval, open/merge reviewed PR, and record known limitations. Do not publish a beta as final merely because compilation passes.

## First user-facing Codex task
"Open wacayoub/IPToSatPro and read docs/CODEX_VU_ZERO4K_HANDOFF_20261018.md and draft PR #9. Verify R80.2 stable vs the unpublished R80.3.3 FINAL artifact. Run the complete offline tests and produce a concise release-gate report. If your machine has authorized SSH access to the Vu+ on my private LAN, perform read-only receiver observation only. Preserve all private mappings/settings. Do not install, restart Enigma2, publish to main or access external IPTV URLs without asking my approval. Focus on beIN 4K TOD Preview sound vs Live mismatch and preserve four already passing channels."
