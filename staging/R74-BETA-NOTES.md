# IPToSatPro R74 — Unified Preview Beta

**Build**: `1.0.46-r74.6-dvb-black-picture-beta`

**Branch**: `feature/r74-unified-preview-actual-bouquet` (not merged into production `main`).

## R74.6 Decode-aware SAT fallback — DMAX / TLC black screen

- Corrects R74.5's false recovery decision: tuner `LOCKED` or nonzero PMT **does not prove decoded picture** and must not erase a recent transponder TUNE_FAILED cache entry without decoder evidence.
- Samples DVB decoder PTS at ~850ms after SAT start; at ~2000ms uses the actual SAT decoded-video event or advancing decoder PTS to decide whether the screen is truly functioning.
- If video remains absent after independent checks even though tuner claims `LOCKED` and a provisional FTA flag is present, execute the existing safe DVB->IPTV fallback, logging `DVB_BLACK_FALLBACK`; manual mappings and normal SmartMatch safety/identity rules remain respected.
- A working FTA channel with decoded video is always kept on satellite. Cached no-signal transponders are invalidated by native DVB video, not mere RF lock.
- Logging: `DVB_LOCK_NO_VIDEO`, `DVB_VIDEO_SAMPLE`, `DVB_BLACK_FALLBACK`, `DVB_BLACK_ALLOW`, `DVB_BLACK_CANCEL`.
- Existing PAT/PMT 1250ms no-crash protection and 2-second encryption correction unchanged. This is not a guaranteed sub-second first frame on previously unknown transponders.

## R74.5 cached confirmed No Signal / fast return

- True native Enigma2 TUNE_FAILED/NO_LOCK proves a failed transponder and caches (TSID, ONID, namespace) **in receiver RAM only** for 120s. Never treat SNR=0 alone as proof.
- Subsequent channels on the **same proven-unavailable transponder** get 180ms + 250ms foreground-lock checks and may start the standard guarded fallback at roughly 430ms rather than waiting 5s again for the tuner. The first ever unknown failure must still be confirmed by the tuner; **1 second end-to-end cannot be guaranteed**.
- `NO_SIGNAL_CACHE_HIT`, `NO_SIGNAL_FAST_TRY`, `NO_SIGNAL_DEDUP`, `NO_SIGNAL_CACHE_CLEAR`, `NO_SIGNAL_PROVEN` log evidence and recovery.
- Limit native fallback to **one request per DVB zap** so repeated 5-second tuner-failed events do not cause infinite attempts on no-match/failed IPTV.
- Any recovered LOCKED tuner, PMT PID or native decoded video invalidates cached no-signal evidence before switching. Native PMT/PAT 1250ms crash guard remains intact; safety before an unrealistic <1s video guarantee.
- No user settings, IPTV mappings, persistent caching or manual locks changed.

## R74.4 Fast signal-priority engine

- **SIGNAL+CRYPTED**: start IPTV with existing safe tuner/PMT guard; no extra crypto wait when positive CA evidence exists.
- **NO SIGNAL+FTA/CRYPTED**: initiate IPTV as soon as actual tuner failure is confirmed (do not use SNR=0 alone).
- **SIGNAL+FTA**: keep SAT; the ONLY deliberately excluded path.
- **FTA at the start, ENCRYPTED at two seconds**: native Enigma2 timer re-reads live DVB crypto and CAIDs after 2000ms and starts IPTV automatically if the channel has become encrypted; no second zap.
- Uses mainloop timer, current-service token, single-start protection and no forced channel switch during an existing IPTV transition. Preserves user mappings.
- Controlled tests for all four priorities plus FTA-changing-to-encrypted and cancellation during CH+/CH-.

## R74.3 First-zap DVB crypto detection correction

- Early `sIsCrypted=0` (NO) while CA/PMT is initializing becomes provisional `?` and is revisited through an 880ms bounded mainloop timer.
- Saved `sat_crypted=False` is revisable; live positive and native static CAID positive can override it at the first zap.
- After the grace period, a manual mapping can recover despite a historical negative when no native SAT picture was verified; this is logged as `CRYPT_MANUAL_RECOVER` without falsely marking the SAT encrypted.
- Confirmed native FTA video remains protected. Cross-zap deferred callbacks are cancelled.
- Only monitor.py access-check and timer logic changes: player, audio, timeshift, mapping files and Enigma2 settings remain unmodified.
- New regression suite covers early NO-to-YES, old saved NO, healthy FTA and stale callbacks.

## Critical crash hotfix R74.2

- Fixes Enigma2 traceback `TypeError: _open_preview_sources_direct.<locals>.<lambda>() missing 1 required positional argument: 'result'`, triggered when Auto Play closes Preview with no result.
- Callback now accepts zero or one result argument; the existing Preview return handler already treats `None` as no manual action.
- Seven regression checks cover zero-argument close, explicit return, mapping workflow, and protected player modules.

## Implemented

- Preview SAT left panel defaults to the **currently selected native Enigma2 bouquet**, reads the actual `InfoBar.instance.servicelist.getRoot()` through `eServiceCenter`, and preserves that bouquet's original order. SAT DVB TV entries include FTA, encrypted and unknown; IPTV/radio/directory entries are omitted from this SAT panel.
- Numeric **7** switches between the native current bouquet and the currently selected satellite's channels. Satellite's original encrypted-only filter and numeric 6 FTA option remain available; 6 automatically selects satellite mode.
- Compact 1700x790 **Neo Dark R74** skin with all 20 original widgets, properly separated panels, status labels and keys. XML bounding-box tests reject overlapping widgets (picon and fallback are intentionally co-located).
- 48 detailed all-server scoring evaluations (up from R73.8's 36, originally 18), still bounded to keep Vu+ responsive. Unscored candidates remain REVIEW, not unsafe auto-locks.
- **Original SAT language only**: prefer actual DVB audio languages of the currently tuned SAT channel (or channel-specific explicit identity hint when audio is unavailable). No global FR/AR/EN order, user language preference, or country-market bonus is placed ahead of the score. An observed DVB audio mismatch is not Auto Locked. Without audio/language evidence, the numeric score breaks ties after SAFE and identity.
- Language and country filters on 3 are **manual display filters only**; they never decide Auto Mapping.\n- Numeric **8** cycles IPTV sources ALL/PRIMARY/BACKUP1/BACKUP2; **9** toggles SAFE-only; **3** cycles FR/AR/EN and HD+/FHD+/UHD metadata filters. Numeric 5 retains full IPTV name search. Filters are in-memory display-only; the full candidate cache, server duplicates and mappings remain untouched.
- Candidate rows distinguish **REAL measured video quality** from **CAT catalog-declared quality**. Existing BLUE details, OK full-screen video test and verification data retained.
- Inherits R73.8 SAFE Auto Select/Auto Lock/Auto Play for current active SAT with prior Auto locks, stale-zap protections, guarded native DVB picture, existing player watchdog and same-channel failover.
- Reuses existing Preview cache, pagination and low-cost deferred native roster loading; writes `R74_BOUQUET_ROSTER`, `R74_ROSTER_MODE`, `R74_FILTER` and existing Auto Play logs.

## Verification & limitations

- GitHub CI builds a real IPK, parses every shipped Python module, confirms original monitor/player/timeshift/mappings untouched, and runs R74 + R73.8/R73.7/R73.6 + 20-channel regression suites.
- **Not tested on physical Vu+ Zero 4K**. Layout, decoder, native bouquet retrieval, source URL failures and 1–2 second zap goals require real receiver verification.
- This is an opt-in beta, **not** a stable online update via main. No receiver changes while owner is away.

## Delivery

`download-r74-beta.sh` verifies SHA-256 and size against `staging/r74-unified-preview.update.json` and only downloads by default. `--install` explicitly backs up settings/mappings then installs the verified IPK, without auto-restarting the GUI.
