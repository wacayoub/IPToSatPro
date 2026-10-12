# IPToSatPro R74 — Unified Preview Beta

**Build**: `1.0.46-r74.2-preview-close-hotfix-beta`

**Branch**: `feature/r74-unified-preview-actual-bouquet` (not merged into production `main`).

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
