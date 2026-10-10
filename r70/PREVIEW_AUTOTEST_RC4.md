# r70-rc4 — Preview Browser Auto-Test (HOLD / NOT RELEASED)

Problem demonstrated by the user on TREK (Hotbird 13E): `Mapping NONE`, `Result UNKNOWN`, **17 candidates** from PRIMARY/B1/B2, displayed as `NON MESURÉ / REVIEW`. Candidate availability alone does not mean a working stream or a safe SAT↔IPTV association.

## Changes

- **BLUE while focused on SAT column**: start a bounded automatic real-player preview trial using the current candidate order. Existing BLUE/OK on IPTV column still previews exactly the selected source.
- **Key 3**: start the same Auto-Test from either panel.
- Up to **six distinct candidates** on the selected SAT channel, tested **one at a time** with the already-existing Enigma2 player, decoder evidence, 4097/5002 fallback and timeout behavior.
- Skip user-rejected candidates, hard-rejected identity conflicts, candidates lacking URLs, and duplicate fingerprints. Preserve exact provider/market decisions from the existing ranker.
- On failed preview, queue the next candidate with a 120 ms Enigma2 timer. Never block the GUI while waiting and never start background streams during ordinary channel zapping.
- On confirmed decoded video: **select/highlight that source and stop**. Display `GREEN = USE / LOCK`; **do not save mappings automatically** for REVIEW results. Video alone cannot validate country, subtitles, audio, or regional feed identity.
- If the player opens but reliable decoder evidence is unavailable (`VERIFY`), stop the scan and ask the user to check picture and sound. Do not mark the source failed or move away automatically.
- On manual remote movement, SAT cursor change, screen close, or user BLUE on IPTV column, **cancel** any pending auto-test.
- No change to the monitor's automatic SAFE/ALLOWED policy, existing manual locks, the r70-rc3 no-signal FTA gate, the live Fast Zap path or Preview ranking algorithm.

## TV steps

1. Select SAT channel **TREK** in the left column.
2. Press **BLUE** (now AUTO TEST / PREVIEW), or **3** from either column.
3. Wait for the first genuine working IPTV candidate to reach `PLAYING`. If the first fails, a maximum of five further candidates are tried.
4. Compare **picture, region and sound**; only then press **GREEN** to keep this candidate for that SAT channel. Future Fast Zap uses the saved manual lock.
5. If the stream says `VERIFY`, inspect the visible image and audio and press GREEN only if correct. If none works, YELLOW opens All Sources with the full list.

## Release gate

- GitHub Actions: previous FTA/policy/Preview/security suites plus rc4 Auto-Test mocks and pinned r69 package compatibility; **no automatic mapping from an unverified REVIEW candidate**.
- Before official publication: Vu+ Zero 4K OpenATV 8.0.1 real testing of TREK and other unmatched channels, prior manual mappings, SAT/no-signal mode, timeshift, picons, UHD/decoder, and backup rollback.
- NO merge to `main`, NO `update.json` change, NO Online Update publication. This is a test candidate.

## Known limitation

The new Auto-Test is user-initiated **inside Preview Browser**. It does **not** autonomously test IPTV streams every time the user changes TV channels, which could add seconds of delay, increase network load and override valid SAT reception. Only verified/explicitly locked candidates are treated as trusted mappings.
