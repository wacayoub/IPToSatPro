# IPToSat Pro r70 — Unified RC (HOLD / NOT RELEASED)

Branch: `feature/r70-unified-rc`  
Baseline: published `1.0.46-r69-beta`, size 276666, SHA256 `123e1118a7471075ad18dee3014b7367fa9a2cf02f8cdd52ad1e5e65034035ed`  
Candidate: `1.0.46-r70-rc2` (Preview Browser UI upgrade), **offline build only**. r70-rc1 remains the previous test baseline.

## Eight features consolidated into one candidate

| Feature | Stage in r70 code | Must still verify on receiver |
|---|---|---|
| Real Playback Verification | State machine CONNECTED / VIDEO_DECODED / STABLE, adapter captures r69 verified late video | First-frame callbacks for DVB/5002/4097; note decoded-size event alone can be insufficient proof of rendered frame |
| Black Screen Detector | Nonblocking, bounded **no-frame observation** warning after start | True black pixels or stuck frame cannot be inferred from size; needs legitimate decoder/frame metric |
| Persistent Manual Lock | Atomic, hashed lock mirror + native manual lock/unlock hooks + verified native JSON backup; native mapping data stays authoritative | Verify lock/unlock and persistence after reboot on receiver |
| Anti-Freeze Watchdog | Per-generation, nonblocking eTimer advisory; retry/cooldown policy | GUI watchdog cannot fire while GUI thread is blocked; validate actual freezes |
| Source Health Monitor | Sanitized bounded candidate/source history, aggregate reliability and no provider-wide blacklist | Health UI and scoring integration, no server-wide blacklist |
| Audio Auto-Recovery | Safe recovery decision policy; **does not switch audio tracks automatically** without proof | Validate TOD Events and audio track APIs before action |
| Candidate History | Bounded per-candidate OK/fail/decoder mode, atomic delayed disk flush | Reboot persistence and read/write performance |
| Safe Online Update | SHA-256/size/header/version preflight API; **existing updater unchanged** | Backups, actual install/rollback flow and user confirmation in Enigma2 UI |

## Preview Browser overhaul in r70-rc2

- Initial P/B1/B2 Preview rank remains first-paint instant. A previously completed shared cache is no longer overwritten by an incomplete seed when reopening Preview.
- The deferred full Manual Mapping/All Sources rank now runs off Enigma2's GUI thread, with one bounded worker and stale-service result protection. Existing core ranking/scoring is unmodified.
- New All Sources browse/search page navigation: **8 = previous page**, **9 = next page**; 48 rows painted at once, full 10,000+ candidate collections retained. CH± continues to navigate SAT channels.
- Background SAT ranking on old cursor selection is discarded sooner (230ms rerun delay rather than 680ms) without parallel workers or new network scans.
- Live image/codec/Dolby statistics update while the candidate list repaint is throttled to 1s; final decoder sample repaints immediately.
- When ranked candidates reorder, the source selection is restored using the exact candidate fingerprint rather than an unrelated old row index. If the manually selected All Sources candidate lies outside the best 36, it is preserved as an extra visible row, not silently replaced.
- Preview/All Sources typography and row density are adjusted for a FHD screen (two columns preserved).
- Tests exercise source patch against pinned r69, simulated 10k-row page navigation, asynchronous rank, core/relay preservation, no online release.
- Actual GUI smoothness and ranking latency on Vu+ Zero 4K still require receiver tests; this is **not** a measured 1–2s Preview guarantee.

## Explicit non-regressions

- Exact existing r69 monitor AST methods retained; only an adapter call is appended.
- Existing core.py, timeshift_seek_patch.py, neo_theme.py, relay binary/init and all pre-existing plugin/monitor methods unchanged. Appended optional mapping + telemetry hooks; version labels updated.
- No network probes, active mass scan, blocking disk write or persistent timer loop on fast zap.
- No forced service selection, lock rewrite, audio switching or player plan changes in the candidate.
- CI builds candidate from pinned r69 and checks no changes to main's update.json/latest-version.txt/download-latest.sh.
- Unit tests validate state generations, false positives, persistence, privacy, retry budgets, preflight checks and non-invasive monitor wrapping.

## Known incomplete / gates

- Hardware playback validation required for all eight features.
- Critical: true screen-black detection needs a trusted decoded frame metric; no guessing from a timeout.
- Audio auto recovery must only be enabled after receiver confirms audio signal and track selection APIs; otherwise no speculative fixes.
- Existing manual mapping overrides remain the source of truth; mirror now hooks manual save/remove. Hardware reboot and rollback verification are still mandatory.
- Safe Online Update preflight is present but not wired into GUI/installer; do not claim rollback has been exercised.
- First frame metrics are an approximation until the receiver confirms precise decoded image events; no promise of 1–2 s.
- Previous generic r64 guard reports a deviation in r69's _on_start; dedicated r70 checker enforces byte-identical original r69 monitor and no ADDITIONAL regression.

## Development verification — 9 October 2026

- Corrected real decoded FHD below UHD target: a quality downgrade must not be reported as a black screen.
- Added native manual lock/unlock hooks: after native operation the auxiliary hashed mirror and restricted-permission backup are updated; no added writes on normal zap.
- Added read-only per-source aggregate health; no global blacklists or automatic source changes.
- Corrected misleading inherited r62 installation message in offline r70 candidate when present.
- CI now retains a short-lived **TEST-ONLY** candidate as a GitHub Actions artifact after all offline checks pass. This is not a public online update or release; manual receiver validation remains required.
- Latest CI state is tracked in `.github/workflows/validate-r70-rc.yml`. A successful Actions run is **not** proof of 1–2 s playback or audio recovery.

## Validation order

1. All offline tests PASS and comparison against r69 PASS.
2. Test candidate on Vu+ Zero 4K OpenATV 8.0.1, 20+ matched zaps, median/p95 first image, ensure r69 not degraded.
3. Test audio including TOD Event Sports, timeshift, manual locks, picons, SAT DVB and UHD.
4. Run failing inputs (EOF, no data, late decoder, slow provider, zapping race), ensure no infinite recovery or GUI freeze.
5. Implement/enable receiver-dependent recovery only after reliable hardware instrumentation.
6. Obtain explicit approval to publish; **only then** update main/online manifest and release IPK.

**Current decision: NO RELEASE; NO MERGE INTO MAIN.** The branch consolidates the architecture; not all receiver-dependent behaviors are active yet.
