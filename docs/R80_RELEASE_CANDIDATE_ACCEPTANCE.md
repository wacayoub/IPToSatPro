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

### Additional real R76.15 observations (15 October 2026)
User-provided PREVIEW_STAGE and PREVIEW_RANK_BG log samples, 21:59–22:09:
- 8 uncached samples: wall elapsed average **4,018 ms**, worst **6,325 ms**
- normal nomination **49–71 ms**, one outlier **546 ms**
- scoring **1,215–4,304 ms**, rescue up to **1,815 ms**
- sorting up to **692 ms**
- 2 cache hits: wall elapsed **87 ms** each, core profile total **1 ms**

These are only 8 cold samples and may repeat SAT channels, so they are
insufficient for the formal >=10 distinct-channel acceptance protocol;
nevertheless cold scoring and rescue clearly exceed the R80 target.

## Final go / no-go

Run the read-only R80 audit after a proper Enigma2 GUI restart with
**at least 10 distinct SAT channels** sampled across beIN, OSN, Moroccan,
Canal+, Nat Geo, and ordinary numbered/generic names. The primary numeric
gate is:

- PREVIEW_STAGE numeric entries after the installation baseline: >= 10
- at least 10 **uncached** samples, sampled manually on >=10 different SAT channels
- nomination P95 <= 3,000 ms, worst <= 5,000 ms
- **cold scoring P95 <= 500 ms, rescue P95 <= 200 ms, sort P95 <= 200 ms**
- **cold total P95 <= 1,000 ms**; these are engineering targets pending hardware validation
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

If any 10-channel cold-path gate fails, keep R80 as a release candidate.
The new log evidence prioritizes `Catalog.fast_rank_matches_all_servers`
scoring and rescue phases, not only `Catalog._preview_nomination_pool`.
First locate repeated pure calculations in the exact packaged R76.15 code;
then implement only semantics-preserving changes, with reference-versus-patched
candidate identity, score, order and manual-lock parity tests.
Do not cap away valid candidates, bypass MENA/provider-country protections,
weaken deep YELLOW search, or alter on-device player, settings or mappings.
Never push an unmeasured optimization to production.

The read-only audit checks numeric phases but does NOT prove the samples
came from distinct SAT channels; that must be confirmed manually without
recording or publishing private channel/server details.
