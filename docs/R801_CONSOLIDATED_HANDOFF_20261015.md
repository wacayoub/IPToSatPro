# IPToSatPro R80.1 — consolidated release handoff (15 October 2026)

## Verified receiver state supplied by owner
- Receiver: Vu+ Zero 4K, OpenATV 8.
- Installed plugin and opkg metadata: `1.0.46-r80.0-rc1-index-focus`.
- Engine markers present: R7612, R7613, R7614, R7615.
- R80 Preview hot-path marker absent (expected; R80.1 not installed).
- Existing plugin-code backup archive checks as intact at
  `/home/root/iptosatpro-r76-backups/20261015T215515`.
- R80.1 payload has pinned SHA256
  `210fe7de203353b71f02829f4f2b31acc582dfc663ce7bc8971425e0ecd2f173`,
  size 461044 bytes.
- Owner's cold ranking samples remain slow: 2.119–6.302 seconds measured
  PREVIEW_STAGE; max scoring 4304ms, rescue 1815ms, sorting 692ms.
- Earlier attempts correctly refused unknown installed version; no plugin or
  settings were modified.

## What this candidate fixes in the delivery chain
- The R80.1 install guard recognizes R76.15, R80 Final RC1, and the
  installed R80.0 Index Focus.
- **For R80.0 Index Focus only**, the install guard obtains a git-SHA-pinned
  read-only comparator. It verifies the exact frozen R80 Final RC1 package
  hash and checks every on-disk Python module and packaged resource against
  that reference, allowing only exact known changes to version and manifest
  strings. A different core, extra Python code, missing asset, modified UI
  resource, or failed HTTPS audit blocks installation.
- It never rewrites/patches the installed Index Focus code to defeat the gate.
- Installer retains strict checks for already-installed/inconsistent R80.1,
  persistent preinstall code/settings backup and code-only rollback, with no
  automatic Enigma2 restart or changes to the stable online update channel.
- SHA256-pinned R80.1 package payload is unchanged.
- CI on commit `e11d85483b2dedbcb5baadb3fdc4d24f0e42bc9d` passed
  shell syntax, 9 receiver-installer regression tests and the strict
  R80.0 compatibility checks (11 offline test cases).
  See https://github.com/wacayoub/IPToSatPro/actions/runs/38822312006

## Single bounded receiver action (optional, experimental)
```sh
wget -qO /tmp/download-r801-preview-hotpath.sh https://raw.githubusercontent.com/wacayoub/IPToSatPro/e11d85483b2dedbcb5baadb3fdc4d24f0e42bc9d/download-r801-preview-hotpath.sh && sh /tmp/download-r801-preview-hotpath.sh --install
```

- If it prints `R800_CODE_DIFFERS` or an audit failure, STOP. Retain R80.0.
  That is not a repairable version-string mismatch, and using opkg force to
  bypass it risks losing actual Index Focus optimizations or UI resources.
- If it prints `R801_BETA_INSTALL_OK`, reboot only Enigma2 GUI through
  OpenATV menu and evaluate cold Preview behavior on at least 10 different
  satellite channels. Confirm audio/video, auto-lock/manual mapping,
  preserved themes and fallback/timeshift.
- If reverting, the installed script supports `--rollback` (plugin CODE
  only; opkg metadata may still report R80.1). The backup is a code snapshot
  and **does not demonstrate a genuine opkg package transaction rollback**.

## Release decision
**NO-GO for production final.** Passing offline GitHub CI cannot demonstrate
receiver code compatibility or receiver speed / AV parity. R80.0 Index Focus
remains the only currently verified running receiver version; the R80.1
candidate has not been physically benchmarked, and its pure hot-path memoization
does not guarantee the cold latency goal (P95 total <=1000ms, score <=500ms,
rescue <=200ms, sort <=200ms, all measured on >=10 uncached channels).
Do not change production update.json or publish a stable R80 release.

Do not repeat prior version-only installation trials; the compatibility gate
now provides the definitive answer in one bounded receiver invocation.
