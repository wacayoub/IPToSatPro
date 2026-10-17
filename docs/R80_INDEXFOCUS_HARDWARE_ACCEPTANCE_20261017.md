# IPToSatPro R80 Index Focus — hardware acceptance (17 Oct 2026)

## Status: hardware-functional ACCEPTED, final publication NOT YET APPROVED

Production receiver: Vu+ Zero 4K / OpenATV 8.
Installed package: `enigma2-plugin-extensions-satiptvbridge`, version
`1.0.46-r80.1-indexfocus-hotpath-rc1`.

### Evidence (receiver output supplied by owner)

- Pinned RC1 package: 461,250 bytes; SHA-256
  `b6b1fe72ffbcbfaa398bd261c000f9361159a9e08f606a0af9d6da3d5ef04e5e`.
- Core SHA-256 installed after upgrade: `74cd89b8c6a41b4537fd758cedb3a07b2bc0f9a5c215063e4c45b99e5d92cd2a`;
  original source exact `795b3bb206ec9ca4a285db7a85f497af1037248837d5a299442cea10e608ee1b`.
- `opkg` upgrade successful (rc=0); private code/config backup:
  `/home/root/iptosatpro-r76-backups/r801-indexfocus-20261017T095700-11732`.
- Six tracked configuration/mapping files; all hashes unchanged after install.
- Original code changes limited to Preview optimization in `core.py`, plugin/updater version;
  82 package plugin assets unchanged and tsbridge service files byte-verified.
- After Enigma2 GUI restart, **owner reported**:
  - Preview Browser: OK (first-display time not measured).
  - Picture and sound: beIN/TOD, OSN, Moroccan channels OK.
  - SAT no-signal to IPTV fallback OK.
- Receiver has not reported crashes in these manual tests; no long-term uptime claim.
- No formal cold Preview P95 timing or test of all themes, 4K/HDR, or backup-stream permutations
  has been recorded in this acceptance.

### Release decision

**Freeze working R80.1 RC1. Do not add features or re-install experimental builds.**

Functional hardware acceptance is complete for the tested paths. Previously requested
quantitative cold Preview targets (P95 <= 1000 ms; score P95 <= 500 ms) are
**not certified** because the user did not time the first display. A numeric
log-only check can assess this without another installation; failing/absent
samples must not be called a performance pass.

A stable R80 final *may be prepared* from the exact validated RC1 payload,
with only version/control/manifest metadata changes and byte-exact player/UI
and matching code retained. Do not update `main/update.json`, advertise
performance gains, or declare universally certified hardware performance
before explicitly deciding release criteria and verifying the final artifact.

### Next and only necessary gate

One automatic, read-only log assessment for post-upgrade cold Preview timings,
or an explicit release decision that does not claim the unmet/unmeasured target.
No repetition of build-parity, 11-theme or general mapping audits unless a
user-visible regression appears.
