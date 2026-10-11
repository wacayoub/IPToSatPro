# Experimental: fast zap + King TOD dynamic routing

**Status:** offline policy prototype. NOT deployed. Current r69-beta IPK and receiver configuration remain unchanged. Do NOT publish or merge without Enigma2 receiver regression testing.

## Scope

1. **Blacklist navigation:** ignore blacklisted receiver channels before playback on CH+/CH-. Preserve direction, wrap at most once, and avoid an endless loop when every channel is denied. Integrate at channel-list handler, not inside IPTV fallback.
2. **King source TOD 1-14 only:** short-lived TOD-to-beIN mapping from verified on-screen VIDEO logo, e.g. TOD Sports 3 carrying beIN Sports 6 -> SAT beIN Sports 6 may use TOD Sports 3. Change to beIN 8 at next event and invalidate old mapping. Do not infer logo from IPTV title/EPG.
3. **Fast zap:** protect r64 MANUAL_LOCK known-good path and bridge. Cache verified player choices and stream hints; avoid discovery and repeated HTTP checks on already locked entries. Never prewarm all 14 TOD streams on Vu+ Zero 4K.

## Offline prototype

- experiments/king_tod_router.py: pure Python stdlib, no Enigma2 imports, network or playback change.
- next_non_blacklisted: forward/reverse blacklist skip, including wrap and all-blacklisted.
- KingTodRouter.observe: takes an externally recognized on-screen logo number (1-10) and confidence, requires 3 well-spaced high-confidence observations, resets on event/stream changes, invalidates conflicting matches, and expires after 150s.
- by_bein: returns recently confirmed TOD slots. No saved permanent mapping.
- experiments/test_king_tod_router.py: 9 offline test scenarios (TOD3->beIN6, event change, source isolation, confidence, duplicate frames, skip CH+/CH-).

## Must complete before receiver install

- Verify exact provider SOURCE ID for King; do not depend on broad name matching.
- Integrate blacklist with actual native Enigma2 bouquet navigation and existing plugin configuration, preserving parental and FTA rules.
- Build a real **video logo recognizer**: obtain small crops of on-air watermark, collect templates from genuine King TOD broadcast frames, recognize beIN number robustly; reject unrelated screen overlays and stale frames.
- Run image probes asynchronously with a strict CPU/network budget. Do NOT decode all 14 TOD streams concurrently. First-time recognition may be slower than warm cached mapping.
- Detect event/URL transitions and revalidate. Never assign automatically if the on-air logo is unclear or absent; keep normal fallback and manual mapping.
- Route SAT beIN only when mapping verified, then choose candidate with valid video/audio and preferred quality.
- Measure decoder-first-frame-with-audio latency (median/p95) across 20 locked channels, 4K, failing URLs and King TOD. 1-2 seconds remains only a goal.
- Run existing locked fast guard and receiver regression suite. Do NOT edit main release/update.json before testing.

## Offline test command

    python3 -m unittest discover -s experiments -p 'test_*.py' -v

## Limitations

The actual image/frame/logo classifier has NOT yet been integrated. Therefore this is not an immediately working automatic TOD-on-air solution; it is a verified routing decision engine awaiting frame recognition and Enigma2 wiring. No existing IPK or receiver state changes.
