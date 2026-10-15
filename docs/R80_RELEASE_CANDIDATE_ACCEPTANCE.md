# IPToSatPro R80 — Release candidate acceptance (15 October 2026)

## Actual state (not final)

R80 RC1 is the exact R76.15 executable implementation; no new ranking,
Preview UI, video/audio, mapping, scraper, matching heuristics or index cache
serialization behavior has been introduced in R80.

The first two R76.15 samples after installation were:
- 21:38:26: **nomination 8,462 ms**, scoring 3,150 ms, total 11,736 ms
- 21:40:31: **nomination 4,031 ms**, scoring 1,378 ms, total 6,002 ms

Prior R76.14 had nomination outliers up to 35,472 ms. These two newer
observations **do not prove** the long-tail problem is fixed.

## Final go / no-go

Run the read-only R80 audit after a proper Enigma2 GUI restart with
**at least 10 distinct SAT channels** sampled across beIN, OSN, Moroccan,
Canal+, Nat Geo, and ordinary numbered/generic names. The primary numeric
gate is:

- PREVIEW_STAGE numeric entries after the installation baseline: >= 10
- nomination P95 <= 3,000 ms, worst <= 5,000 ms
- no logged PREVIEW_RANK_BG errors
- no disappearing valid IPTV candidates compared with R76.15
- no long-loading GUI freeze, and no repeat-catalog-index rebuild on entering Preview

Independent receiver tests must confirm:
- manual/locked mappings survive installation, reboot and rollback;
  no user settings or mapping files are deleted
- SAT/region/provider priorities are appropriate for MENA; avoid selecting
  FR/DE/IT/PL feeds for the wrong Arabic satellite channel
- candidate names, server roles and ranking numbers remain consistent
- media picture and audio OK, including TOD events, 4K/HDR and fallback/no-signal
- user-chosen UI/theme is preserved; YELLOW deep search and manual action usable

*Never promote to stable on the basis of GitHub synthetic CI tests alone.*

## Safe deployment

- R80 RC1 install is strictly from installed **1.0.46-r76.15-preview-index-fast-beta**
- downloader defaults to `--check`; `--install` is explicit, SHA256-pinned
- persistent backup of prior plugin code and selected user mappings/settings
- passive opkg postinst; no cache migration, catalogue refresh or mapping mutation
- `--rollback` restores prior plugin *code only*, leaving latest mapping edits intact
- no changes to production `update.json` (still R70 final)
- testing branch: `release/r80-final-candidate-20261015`

## Remaining work before final R80

If the 10-channel index gate fails, keep R80 as a release candidate. Optimize
`Catalog._preview_nomination_pool` **only**, taking care not to change any
candidate identity, score, or position. Runtime phase measurements already
split nomination from scoring; additional instrumentation should identify
provider-family/number/fuzzy-prefix bucket outliers without printing channel
credentials or service URLs. Do not push an unmeasured optimization to stable.
