# IPToSatPro R80.3.3 FINAL — historical opening-speed review (2026-10-17)

## Scope
User requested to compare older releases for faster channel/Preview opening **excluding beIN** and apply the safest proven improvements to the final package. This is a **read-only source/runtime-code review**. No receiver access, no source changes and no new IPK published.

## Historical observations
- R76.11-era 15 Oct receiver log analysis: 2 Preview samples, p50 ~13.0s and p95 ~21.6s; tiny sample. Some older uncached runs were >20s.
- 15 Oct 21:59 Preview log: cold `PREVIEW_STAGE total=2359ms nominate=62ms score=2096ms rescue=4ms sort=195ms cache=0 scored=49`, while a cached hit logged ~1ms overall. Exact package attribution to all intermediate betas is uncertain.
- R80.1 hotpath proposal: LRU ratios and request-local sort-key memoization; GitHub `docs/R801_CONSOLIDATED_HANDOFF_20261015.md` explicitly warns cold path did **not** achieve certified goal; its first release encountered receiver core mismatch and was blocked.
- R80.2 Index Focus: indexed nomination and lazy guards, no reliable cold Preview P95 established on actual device.
- R80.3.3 FINAL retains R80.2 functional core and inherited Preview speed changes.

## Exact code audit of delivered local FINAL IPK (SHA256 bfdbe0cb1e93113f5fa50d1243d19b61e589af0edd0ac4b3bf8e7992cbd49081)
Found already integrated:
- R74.14 immediate exact seed `_r7414_fast_exact_seed`.
- R76.11 no full decorated-name cold scan.
- R76.12 `PREVIEW_STAGE` numeric-only detailed instrumentation.
- R76.13 scoring postings reused.
- R76.14 `functools.lru_cache(maxsize=2048)` for stable string-normalization helpers.
- R76.15 bounded indexed nomination for normal Preview.
- R76.9 Preview/Manual candidate parity `48 / 16 per server` and deep/Yellow expanded `192 / 64`.
- R80 `_r80_preview_ratio` LRU for string similarity, request-local sort-key memoization, provider index lazy guards.
- `fast_rank_matches_all_servers` caches up to 96 SAT contexts per Catalog instance; hit avoids recomputing candidate scores.
- `SatIPTVBridgePreview._sat_selection_changed` immediate first paint, `_expand_selected_sat_candidates` background thread, guarded cache and stale-result avoidance.
- The normal Preview and full expanded YELLOW path are separate; Live decoder and audio source paths are unaffected by Preview optimizations.

## Limited synthetic test (NOT on Vu+; illustrative only)
Ran off-receiver on a tiny, synthetic 180-stream three-server catalogue, excluding beIN:
- Four normal uncached examples took ~3.4 to 12.9ms to rank after index creation; cached repeats ~0.07 to 0.11ms. First-paint estimates 7.9 to 33.6ms. Times reflect a faster PC and small catalogue and **must not** be represented as actual Vu+ times.
- A larger synthetic catalogue exceeded the test time budget; that is NOT hardware latency evidence and could include catalogue-build overhead.
- R80.3.3 current code already implements the fastest safe concepts from the historical release tree. No earlier package has a trustworthy apples-to-apples 10-channel cold-vs-warm hardware comparison certifying greater speed.

## Release decision
**KEEP R80.3.3 FINAL IPK UNCHANGED.** Retro-porting existing optimizations or swapping to an older engine cannot produce a proven gain and risks losing manual locks, MENA scoring, preserved Preview state, fallback and TOD repairs.

For future hardware work, a credible speed win requires 10+ different non-beIN channels with `PREVIEW_STAGE` (cold/warm, same playlist), plus separately measured decoder first-frame latency; do not confuse a cached hit with cold. Until the user requests it, **no additional tests, SSH commands or new version**.

This review is not a claim that the live IPTV source opens faster or that network/server times were measured.