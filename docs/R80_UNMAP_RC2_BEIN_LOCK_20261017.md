# IPToSatPro R80.2.2 UNMAP RC2 — beIN Sports 3 locked FHD priority

**Experimental beta release only. Stable `main` is still `1.0.46-r80.2-final`.**

## Evidence from Vu+ receiver log (17 Oct 2026)

The user explicitly saved `MANUAL_CORRECT` for `AR BEIN SPORTS 3 FHD (50 FPS)`
but the playback engine logged:

- `MATCH_DIRECT source=MANUAL_LOCK ... mapped='AR BEIN SPORTS 3 FHD (50 FPS)'`.
- `CANDIDATE_SELECT ... iptv='AR BEIN SPORTS 3 HD (50 FPS)'`.
- `FAST_LOCK_PREWARM ... iptv='AR BEIN SPORTS 3 HD (50 FPS)'`.

The source code explains this mismatch: a recently failed pinned FHD is ranked
behind a previously successful HD when both share a normalized IPTV identity.
The log separately reports `No decoded IPTV video after 1.9 s` for the
selected FHD. RC2 cannot repair an unavailable or nondecoding upstream stream.

## Scoped change from UNMAP RC1

- Only for a persisted user-corrected GREEN mapping (`forced_correct=True`)
  matching the selected channel fingerprint, prioritize the **exact** IPTV
  channel before alternatives, including when its old health state is negative.
- Do not immediately retry the pinned source twice after a failure in the
  **same** SAT zap.
- For this explicit correction, allow BACKUP1/BACKUP2 only when their
  *claimed quality variant* is identical to that of the pinned stream
  (FHD never silently becomes HD). Respect all explicitly rejected
  fingerprints.
- Do not prewarm an old HD replica on the basis of a past FHD failure.
- Normal, legacy manual locks and SmartMatch/learned mappings keep the
  previous ordering. Prior UNMAP/tombstone fixes from RC1 are retained.
- No change to the frozen core, player, live video decoder, GUI themes,
  or private user mappings.

## Offline verification and release integrity

- 7 pre-existing UNMAP regression tests passed.
- 11 additional targeted RC2 tests passed, including reproducing the RC1
  bug and verifying RC2 exact pin precedence, rejected candidates, backup
  same-tier restriction, current-zap retry protection, and legacy behavior.
- Version: `1.0.46-r80.2.2-unmap-rc2`.
- Source RC1 SHA256:
  `08bcba2ad5982de9d55589bb5f0afe2c727e6e7a74cc2e90411cf7be2ca8a3e2`.
- Candidate IPK size: **463008** bytes.
- Candidate SHA256:
  `61acad0521f98ad8ea12c1d42e53d36d595ccd479874ee706a9ff52e69e9af4b`.
- Functional core SHA256 unchanged:
  `74cd89b8c6a41b4537fd758cedb3a07b2bc0f9a5c215063e4c45b99e5d92cd2a`.
- Changed runtime files: `monitor.py` (targeted logic),
  `plugin.py` and `updater.py` (version and isolated online feed).
  **86 of 89** package data files unchanged. Package post-install hook remains passive.
- The remote GitHub offline builder produces the byte-for-byte pinned IPK and
  commits it **only to this beta branch**; the stable feed is unchanged.

## One-time beta channel activation

`scripts/select_unmap_rc2_online_channel.py --enable` provides a
backup-protected, reversible opt-in for the beta online feed, supporting
an installed R80 FINAL or UNMAP RC1. After GUI restart, use the
normal IPToSatPro Online Update screen to view `r80.2.2-unmap-rc2`
and approve installation manually.

**Hardware gate:** confirm a single beIN Sports 3 manual FHD correction
and re-zap. If FHD fails to decode, check that only the corrected FHD
(or an explicitly compatible FHD backup) is attempted; do not confuse
a failing upstream stream with a mapping regression.
The separate Preview SAT-reference error is not addressed in this beta.

**Do not promote this RC2 beta to `main` until hardware evidence succeeds.**
