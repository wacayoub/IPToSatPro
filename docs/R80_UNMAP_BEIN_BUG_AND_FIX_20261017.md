# IPToSatPro R80.2 FINAL — UNMAP re-selects old beIN IPTV candidate

Status: **offline defect reproduced; targeted patch tested locally; not installed and not promoted to stable**.

## Observed incident

A user corrects a wrong beIN Sport SAT -> IPTV association with a new manual lock.
Playback sometimes stays black while IPToSatPro continues using a stale IPTV
candidate. UNMAP appears not to remove the old association completely.

## Exact source-level defects in R80.2 FINAL

- `plugin.py::_r7416_unmap_mapping` returned `(False, "")` when the SAT key had
  no active `channel_id` in `overrides.json`, although
  `manual_aliases.json` or `resolved_mappings.json` could still contain the
  obsolete source. Reproduced with alias-only fixture:
  `ORIGINAL_ALIAS_ONLY_UNMAP_RESULT (False, '')` and the old alias remained.
- Preview's BLUE -> UNMAP UI also checked only `overrides.json[channel_id]`
  and prevented UNMAP in the alias-only case.
- `plugin.py` wrote a per-SAT `user_unmapped=True` tombstone, but the
  R80.2 `monitor.py` had **zero references to `user_unmapped`**.
  Its normal fast match, async SmartMatch and retry paths could therefore
  re-select the same IPTV candidate immediately.
- Runtime direct-hot and pending playback plans could keep a previous manual
  mapping until the next clean SAT start.

## Scoped patch prepared offline

- Allow confirmed BLUE UNMAP on a SAT service even without an explicit manual
  fingerprint; write an idempotent tombstone and remove only that service's
  alias and learned mapping while preserving all other keys and private backup.
- In the active monitor, treat `user_unmapped=True` as a stop for automatic
  match/retry/play on that SAT service until the user explicitly saves a fresh
  manual GREEN lock.
- Drop pending/retry candidates for this service and refresh cached pinned
  identity before using an old direct mapping.
- Evict Preview's cached candidate list for the unmapped service, and render
  `UNMAPPED` accurately instead of a misleading manual-lock status.
- No match scoring changes, media player changes, fallback priorities or
  cross-channel mapping deletions.

## Offline proof

Seven targeted unit tests passed under Python 3.13.5 using the actual
hardware-validated R80 FINAL `plugin.py` and `monitor.py` sources (in
isolated temporary fixtures): alias-only deletion, verified one-key isolation,
tombstone idempotence, explicit auto-block, no effect on unrelated SAT,
stale pending candidate cancellation, and a saved beIN GREEN lock replacing
the old direct-hot source.

A strictly separated, **uninstalled**, hotfix candidate was assembled from
the user's exact published R80.2 FINAL package:
- Version: `1.0.46-r80.2.1-unmap-rc1`
- IPK size: `462254` bytes
- IPK SHA256:
  `08bcba2ad5982de9d55589bb5f0afe2c727e6e7a74cc2e90411cf7be2ca8a3e2`
- Frozen core SHA256 retained:
  `74cd89b8c6a41b4537fd758cedb3a07b2bc0f9a5c215063e4c45b99e5d92cd2a`
- Only `plugin.py`, `monitor.py`, `updater.py`, and expected control
  metadata were changed. The other 86 package data files are identical.
- The installer hook remains informational-only and exits cleanly.

**NO GO for immediate stable promotion** until the user explicitly approves a
guarded upgrade and a single beIN UNMAP -> manual GREEN -> re-zap functional
check on their receiver. Current `main` stays on working
`1.0.46-r80.2-final`.
