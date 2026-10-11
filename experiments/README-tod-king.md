# Experimental: dynamic King TOD + real black-screen recovery

**Status:** isolated, offline-tested policy modules only. NOT DEPLOYED. The main r69-beta updater, existing IPK, mappings and receiver settings remain untouched. No merge or release without actual receiver validation.

## User requirement (corrected 11 October 2026)

1. **ÉCRAN NOIR, NOT BLACKLIST**: when decoder/video evidence proves a channel has no playable picture, try the next playable IPTV candidate first; if no candidate remains and user enabled auto-skip, temporarily skip to the next channel. Never use a permanent name-based blacklist to decide what to skip. Do not skip on a short black transition, dark movie scene, missing bitrate, source title or EPG alone.
2. **King source TOD 1–14 only:** map TOD slots to SAT beIN Sports 1–10 dynamically from repeated on-air **video logo** evidence (e.g. TOD Sports 3 displaying beIN Sports 6). Invalidate old association when URL, event, watermark or stream identity changes. A title-only fuzzy match must NOT be evidence.
3. **Fast Zap:** preserve existing r64+ MANUAL LOCK and audio/decoder behavior. Avoid probes/discovery on already proven streams and never scan all 14 TOD feeds concurrently on Vu+ Zero 4K.

## Code actually created

- `experiments/king_tod_router.py`: temporary in-memory TOD/beIN associations from at least 3 properly spaced high-confidence logo detections; event+stream discontinuities clear old routes *even when the new frame has no visible logo*. TTL expiry, no saved mappings.
- `experiments/tod_dynamic_runtime.py`: exact King provider-ID scope, accepts evidence only from `decoded_video`, needs stream/event identity, respects manual locks during automatic route lookup; exposes on-air change and playback recovery APIs. It does not perform device-level navigation.
- `experiments/black_screen_recovery.py`: advisory, evidence-driven first-backup/then-next-channel recovery, startup grace, dark-image+confirmed silence safeguards, stale-generation rejection and bounded consecutive skips. This is **not** a blacklist; no channel is permanently excluded.
- `experiments/test_tod_dynamic_runtime.py` + `test_king_tod_router.py`: offline simulations for dynamic source isolation, logo switch, stale event invalidation, false-positive protections, decoder no-frames, dark+silent, EOF, fallback priority, hop limits and manual locks.
- `.github/workflows/king-tod-tests.yml`: runs offline Python tests on pushes/PRs. A green test is NOT evidence of real hardware playback.

## Integrations still REQUIRED before use on your receiver

1. Identify the exact internal provider ID for your King source rather than relying on an alias.
2. Attach a **real live decoded-video frame reader** and a logo recognizer using on-air beIN watermark templates. The recognizer does not exist in this branch yet. Synthetic or playlist-title labels must NEVER mark a channel as beIN.
3. Feed reliable video-frame counters, first actual decoded frame, EOF and independent audio evidence into BlackScreenAutoSkip from the active Enigma2 generation; the current module does not collect receiver telemetry itself.
4. Connect optional advisory recovery to actual channel-list CH+/CH- navigation, preserving direction, parental control, timeshift, SAT native channels and recorded manual locks; cap retries and cancel on zap race.
5. Supply verifiable provider/URL/event transitions to invalidate old TOD mapping immediately; reject stale/wrong-provider decoder frames.
6. Measure zapping p50/p95 on 20 LOCKED and TOD channels including 4K, stream with no image, genuinely dark video, 5002/4097, sound-only cases, source failover, audio loss and timeshift. 1–2 seconds remains a performance target, not a claim.
7. Run a rollback check and test the exact packaging/install paths on Vu+ Zero 4K OpenATV 8.0.1.

## Offline test command

```sh
python3 -m unittest discover -s experiments -p 'test_*.py' -v
```

## Safety status

- Not installed; no IPK available for this feature.
- No `main`, `update.json`, `latest-version.txt`, package payload or receiver file was changed.
- Do not use this as automatic TOD logo switching until video capture, detection and actual integration are present.


## 11 Oct 2026 — additional isolated prototype

- `enigma2_tod_event_bridge.py`: optional `nav.event` handler for real Enigma2 evStart, evEnd, evEOF, evUpdatedEventInfo. It monitors only the exact configured King source ID and TOD slot; video-logo callbacks are bound to the current service reference and navigation generation. Event/stream changes invalidate routes, including when no new logo is yet recognizable. On verified EOF it may **propose** backup recovery; timeshift/recording/manual-LOCK bypass it. It does NOT call playService or install a hook automatically.
- `video_logo_probe.py`: bounded **video-only** `grab -v -r 480` BMP capture using only stdlib, plus confidence/margin-gated white-watermark shape comparison against explicit manually verified cropped beIN logo templates. **No logo templates supplied yet; no real beIN recognition in production.** Different ROI/capture sizes and uncertain/ambiguous matches fail closed. This conservative recognizer may often return no result until actual broadcaster frames and ROIs are calibrated.
- `test_enigma2_tod_event_bridge.py`, `test_video_logo_probe.py`: fake navigation events and synthetic BMP frames, **not receiver evidence**.

### Integration and release gate
1. Determine exact provider ID from the real source configuration, and wire monitor-owned service context and lifecycle to the bridge; refuse title/EPG inference.
2. Obtain at least three **real, independent** decoded-video frames per actual logo from King at 480-pixel width; calibrate source-specific ROI/contrast and manually verify authentic beIN 1–10 templates. Do not misinterpret screenshot errors as black-screen evidence.
3. Call `grab_video_bmp` OFF the GUI thread, rate-limited to the currently selected TOD; discard identical capture digests, stale generation, switched reference or event changes before passing classifier output to the bridge. Never scan all 14 simultaneously.
4. Wire a **separate** reliable current decoder frame counter and independent audio state before enabling the no-picture/dark recovery rules. The current bridge only safely handles a verified EOF proposal; no automatic navigation is enabled.
5. Preserve explicit manual mappings, parental controls, timeshift, recordings and existing fast-LOCK path; validate 20 real channels, 4K/audio and fallback interactions on Vu+ Zero 4K OpenATV 8.0.1.
6. Only after hardware acceptance, create an opt-in test package with an install and rollback route. Do not modify `main`, `update.json`, latest version or publish an automatic IPK before then.

**As of this commit:** simulator CI passed for new modules, but actual on-air beIN watermark accuracy and receiver hooks are NOT validated. No user installation required.

## 11 Oct 2026 — static screenshots in BOTH upper corners

- No video recording: use individual screenshots of the live decoded picture with Enigma2 grab -v -r 480; -v excludes GUI/OSD overlays. Worker integration is not yet deployed.
- The beIN number watermark may be UPPER-RIGHT or UPPER-LEFT. VideoLogoMatcher now accepts verified reference watermarks with rois for left and right or individually calibrated placements. The top_corner_rois() helper is only an initial search region: real coordinates need broadcaster screenshot calibration.
- TodScreenshotSession checks exact service reference, navigation generation, provider ID, TOD slot, stream and event across each capture. Duplicate SHA-256 screenshot digests, stale events, rapid repeats and wrong providers are rejected. Distinct accepted captures must be >=0.45 seconds apart and the downstream router still requires 3 matching observations.
- Conflicting different broadcaster logos return NO assignment. Do not infer a channel from playlist text, EPG or the location of a crop alone.
- Offline tests cover right-to-left logo moves, competing logos, stale/duplicate screenshots, event changes and wrong provider; these are not real King signal or Vu+ Zero 4K measurements.
- Still missing: manually verified genuine beIN 1-10 on-air screenshot reference crops, a non-blocking worker scheduler with GUI handoff, actual decoder/audio-state telemetry for black-screen recovery and hardware acceptance. No live deployment or automatic release.
