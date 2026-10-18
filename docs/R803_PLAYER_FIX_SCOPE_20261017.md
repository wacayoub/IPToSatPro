# R80.3 — playback reliability corrective scope (17 October 2026)

Status: **investigation and test design**, NOT a built/installed hotfix. Production R80.2 FINAL stays unchanged.

## Receiver evidence

- 15:39:46 beIN SPORTS 3, manually pinned KING365 FHD 50 FPS: `AUDIO_SAFE_PLAYER mode=5002 reason=TOD_EVENT`; `IPTV_FAIL` with no decoded video after 1.9s; SAT restored after candidate exhaustion.
- 15:45:17 beIN SPORTS 2: same mode 5002 and no decoded IPTV video after 1.9s; SAT restored.
- 15:45:23 beIN SPORTS 3: `IPTV_OK mode=dvb latency=242ms evidence=validated-ts-data actual=PENDING`.
- CANAL+LIVE 2: `PLAYER_VERIFIED_RE mode=dvb evidence=decoder-video`, `IPTV_OK`, `AUDIO_GUARD_PASS native_tracks=1`.
- `IPTV_OK` with TS evidence is **not** proof of decoded picture **and audible sound**. The audio guard track count proves track presence, not audibility.

## Root cause hypotheses (not yet confirmed)

1. Forced `5002` for TOD_EVENT starts slower than the fixed 1.9s video deadline, or suffers a codec/player mismatch.
2. A failed 5002 attempt exhausts the sole candidate without attempting an audio-safe alternative playback path for the **same** manual mapping.
3. Acceptance/verification labels mix valid transport stream data, decoded video, and audio-track presence.

## R80.3 required behavior

1. Keep exact manual mapping, channel identity, KING365 candidate order, credentials and settings unchanged.
2. On failure of 5002, allow a **bounded**, same-candidate alternative playback trial only when the transport and audio rules permit; no permanent blind mode switch to DVB.
3. Separate phases with distinct evidence: data arrived, decoder video confirmed, audio track detected, audible sound **cannot** be automatically assumed.
4. Never mark final A/V success using `validated-ts-data` alone. If image/audio cannot be verified on hardware, retain `PENDING` and keep fallback recoverable.
5. Ensure every fallback is bounded (no retry loop), cancellation/zapping interrupts outdated trials, and SAT restore remains guaranteed when alternatives fail.
6. Do not change the released R80.2 update feed; build a separate R80.3 test artifact only after code-level regression tests and checksum controls.

## Test matrix before promotion

| Case | Expected |
| --- | --- |
| beIN 2/3 TOD_EVENT, 5002 fast success | Same player; no unnecessary retry |
| beIN 2/3, 5002 no video | Bound retries; safe alternative trial or restore SAT |
| Alternative TS gives data only | No false validated picture/audio success |
| Audible sound missing on direct/relay | Do not persist a broken player preference |
| CANAL+LIVE 2 with known valid DVB | No functional regression |
| Manual exact pin / backups | Same stream identity, no unexpected changes |
| Quick zap away during retry | Cancel stale verification and retry |
| Decoder failure / all IPTV candidates exhausted | Restore original SAT |
| Reload GUI, updated show on TOD channel | Caches invalidated at appropriate boundaries |

## Single receiver read-only command

```sh
wget -qO /tmp/audit_r803_player_readonly.py https://raw.githubusercontent.com/wacayoub/IPToSatPro/fix/r803-playback-verification-20261017/scripts/audit_r803_player_readonly.py && python3 /tmp/audit_r803_player_readonly.py
```

This emits only selected channel labels, player modes, failure categories, markers and installed code hash. It **does not install**, restart Enigma2, modify settings or export stream URLs, playlist endpoints or mapping contents.

## Release gate

Only promote to a new opt-in R80.3 candidate after we inspect actual R80.2 playback source, implement the change, run static/synthetic regression tests, and perform a focused real picture/audio check on the Vu+. No claimed complete repair before those criteria.
