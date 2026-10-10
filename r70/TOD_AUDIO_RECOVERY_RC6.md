# r70-rc6 — TOD Event audio/decoder recovery (TEST ONLY)

## Incident evidenced by real Vu+ Zero 4K logs, 10 October 2026

- beIN SPORTS 1/2/3 manually mapped respectively to **TOD EVENT SPORTS 7/14/13**;
  `5002` fails with no decoded video after 1.9 s and previous build immediately
  applied ~12-second cooldown without a 4097 attempt.
- beIN 4K maps to both `TOD EVENT 1 4K HDR` and `AR BEIN SPORTS 4K HDR`;
  one recorded `dvb` `IPTV_OK actual=PENDING evidence=validated-ts-data`
  and user reports **picture but no sound**. TS-ready is not proof of audible
  sound, audio decoder output, or correct audio language.
- Manual Preview opens the IPTV URL directly in ServiceApp, often with a
  different mode; the native manual-lock route was restricted to one mode for TOD.

## Implemented in rc6

- Detect *all* TOD EVENT channel labels, including `TOD EVENT 1 4K HDR`,
  not only names containing both "event" and "sports". This activates the
  existing ServiceApp-audio-safe canonical stream identity, instead of
  inadvertently preferring DVB SAT-identity bridge where audio PIDs/program
  could be wrong.
- For TOD Event channels in automatic player mode with retries enabled,
  extend single-mode `5002` to `[5002,4097]`. After **failed** 5002,
  try 4097 on the **same source** via the existing native retry timer, with
  no SAT bounce, no re-ranking and no mapping changes.
- If 4097 has **proven decoder video** for the exact stream in the past 24h,
  it may be preferred on later zaps. Never reorder during the current
  failure just because `last_failed_player=5002` was updated: doing so
  would cause a duplicate 5002 attempt.
- Keep manual player override, explicit DVB/ServiceApp mode, disabled retries,
  prior reliable non-TOD playback and existing plans untouched. Museum 4K,
  Mezzo and other players follow the original logic.
- No automatic audio-track changing or assumption that an audio track exists
  merely because the transport/codec metadata is available.

## Validation and limitations

Offline CI: previous 60 playback, FTA, Preview, mappings and recovery tests
plus 13 new TOD-specific tests (73 total); package version and native code
comparison, GitHub receiver bootstrap, and unchanged `main` updater.

**NOT hardware tested on Vu+ Zero 4K.** This addresses the confirmed missing
5002→4097 attempt and a likely TOD 4K audio-identity issue, but it does not
prove that the actual provider stream contains an audible track. If
`AUDIO_GUARD_PASS` appears and the sound is still absent, inspect the
selected audio track/codec from the Enigma2 remote AUDIO menu (or AVR mute,
Passthrough/AC3 downmix), and test whether 4097 produces audible output.
Do not bounce a successfully decoded 4K picture automatically based solely
on a missing or misleading audioTracks API.

For beIN SPORTS 1/2/3: the mappings to TOD EVENT 7/14/13 might refer
to **different events**. They must be checked in Preview for exact content,
region and audio before GREEN lock. No automatic rename.

## Test command (read-only)

```sh
grep -E 'TOD_PLAYER_PLAN|AUDIO_SAFE_PLAYER|AUDIO_SAFE_IDENTITY|AUDIO_GUARD|RETRY_PLAYER|RETRY_NOW|IPTV_FAIL|IPTV_OK|PLAYER_LATE_VIDEO' /etc/enigma2/SatIPTVBridge/bridge.log | tail -100
```

**HOLD** — draft only, no online update, no `main` merge, no live receiver
changes or automatic installations.
