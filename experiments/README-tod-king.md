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
