# IPToSatPro R80.1 — consolidated release handoff (15 October 2026)

## Receiver audit follow-up: decisive incompatibility (15 October 2026)

**Final result: R80.0 Index Focus is NOT the byte-exact frozen R76.15/R80 RC1 runtime.**
The receiver independently reported:
- Installed `PLUGIN_VERSION` and `CURRENT_VERSION`: `1.0.46-r80.0-rc1-index-focus`.
- Local `core.py` size: 247187 bytes.
- Local `core.py` SHA256: `795b3bb206ec9ca4a285db7a85f497af1037248837d5a299442cea10e608ee1b`.
- Verified frozen R80 RC1 baseline `core.py` SHA256:
  `3666acc9bec02bfc917aa156897d3d321ec189ad6f8146211eac1a6375afdd09`.
- Non-invasive audit: `core_byte_identical_to_frozen_r7615_rc1=false`,
  `CORE_DIFFERS_REQUIRES_SOURCE_PARITY_AUDIT_NO_INSTALL`.
- Strict parity installer: `R800_STRICT_RUNTIME_PARITY BLOCKED reason=PYTHON_CONTENT_DIFFERS:core.py`,
  then `R800_CODE_DIFFERS` and `Receiver unchanged`.
- Backup: `BACKUP_VALID: /home/root/iptosatpro-r76-backups/20261015T215515`.

**Actionable decision: NO-GO for R80.1 on this receiver.**
Do not retry R80.1 `--install`, bypass checks, rebrand Index Focus as R80
RC1, or downgrade to R76.15. A separate, source-preserving candidate must
be based on the EXACT installed Index Focus `core.py` or its original .ipk,
which is not available in this GitHub release tree. Until that code is available
for full parity review, the only safe action is to retain installed R80.0.
The existing R80.1 IPK is NOT the compatible final release for this receiver.

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
  R80.0 compatibility checks (10 offline test cases).
  See https://github.com/wacayoub/IPToSatPro/actions/runs/38822312006

## Receiver installation status

The previously drafted single-command installation path was tested and
correctly refused because the Index Focus core is different. **Do not rerun it.**
The only remaining input for a real compatible build is the original installed
R80.0 Index Focus core/package. Until then, retain R80.0.

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
