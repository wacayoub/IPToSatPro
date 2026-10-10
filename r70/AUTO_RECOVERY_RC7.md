# IPToSat Pro r70-rc7 — Smart Automatic Candidate Selection (TEST ONLY)

## Situation confirmed on Vu+ Zero 4K (10 Oct)

Manual beIN SPORTS 1/2/3 mappings point to TOD EVENT SPORTS 7/14/13. rc6 now correctly retries 5002 -> 4097, yet both players fail and the plan remains **candidate 1/1**. The original manual direct mapping code searches only normalized replicas of the pinned *IPTV* name. It never searches the SAT channel identity after all the pinned streams fail.

Preview Browser displays other available sources, including exact-name channels classified **REVIEW / NON MESURÉ** that have previously been excluded from auto mapping.

## r70-rc7 behavior

- New **Settings → Auto-recover failed IPTV mapping (same channel)**, default **ON**. User can turn off at any time.
- Healthy pinned mappings (manual/learned/PRIMARY/B1/B2) retain exactly the original playback and speed. Recovery is started only **after all playback modes and direct exact replicas fail**.
- Then an asynchronous, bounded, **cached-index-only** search by the original SAT name, channel number, provider/market context and language selects up to **four** alternative IPTV sources. Same receiver playback verification, timers and audio-safe TOD routing apply.
- Auto choices include SAFE / ALLOWED; optionally include **REVIEW** only where normalized full channel names match, scoring confirms strong identity, and market/language/context are not contradictory. This also fixes initial unassigned channels such as TREK without forcing an unrelated programme.
- **Never** treat `TOD EVENT SPORTS 7` as equivalent to `beIN SPORTS 1` just because a manually pinned stream was assigned wrongly. Refuse wrong service number/market, reject histories, hard rejects, stale service generations and duplicate candidates.
- No automatic persistent overwrite of existing manually locked channel. A verified working recovered source is used for that playback session only until explicitly saved. This preserves user control of permanent mappings.
- Up to one async rescue search per SAT attempt, four alternatives, four-second index timeout and cancellation when the user zaps elsewhere or the UI tears down. No network crawler/full-catalogue scan nor parallel IPTV streams.
- If all alternatives fail or none is safe, preserve the original SAT reference rather than selecting a random source. The existing cooldown protects against repeated dead streams.
- Full rc6 TOD audio/4097, r70-rc4 Preview, rc3 FTA safeguards, timeshift, relay and all previous player routines preserved by AST regression tests.

## Testing

The feature is still **test-only**. GitHub offline CI uses 9 new tests for dead manual locks, wrong TOD identity, exact REVIEW, stale-zap cancellation, opt-out and no duplicate search, together with all prior rc6 suites and package integrity checks.

Verify on Vu+ Zero 4K after backing up config:
```sh
grep -E 'AUTO_RESCUE_START|AUTO_RESCUE_PLAN|AUTO_RESCUE_EMPTY|AUTO_RESCUE_ERR|CANDIDATE_NEXT|IPTV_OK|IPTV_FAIL|RETRY_PLAYER' /etc/enigma2/SatIPTVBridge/bridge.log | tail -90
```
Success criterion: after exhausted TOD source, auto-rescue discovers a same-identity beIN SPORTS stream, independently verifies decoded video/audio and does not save an incorrect mapping.

**HOLD:** No official update, no merge to `main`, no receiver hands-on testing yet.