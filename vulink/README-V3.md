# VuLink V3 — ChatGPT ↔ Vu+ Zero 4K (GitHub Private Relay)

**Release candidate developer preview** — not yet receiver/Cloud-GitHub end-to-end validated. Source is publicly auditable under feature branch; the *relay repository containing requests/replies MUST be PRIVATE and separate*.

## Architecture

- **ChatGPT GitHub connector** (already connected in the user's chat) can post a structured request comment to a private GitHub device issue, and read the reply comments. It does **not** open an SSH/FTP terminal or connect directly to the decoder.
- **VuLink V3** keeps an outbound HTTPS connection to GitHub's REST API from the Vu+ and polls the private device issue every ~25 seconds. No router port forwarding, inbound connections or public endpoints.
- **No forwarding of personal secrets:** output restricted to whitelisted diagnostic/measurements; no raw logs, IPTV URLs, mapping contents, passwords, file listing or serial numbers.
- **Read-only permitted automatically:** get_diagnostic, preview_performance, audit_python. **Backup** requires physical GREEN authorization on the Vu+ (YELLOW denies), and remains stored privately on the receiver. No arbitrary shell or FTP and no remote editing in RC1.

## One-time setup (requires explicit user action)

1. On GitHub, create a **new private repository** named \`wacayoub/VuLink-Relay\`. Enable Issues. Never reuse a public IPToSatPro repo for requests or replies. If you choose another private repo, enter that repo name during setup.
2. In GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens, create a token restricted to **only that private repository**, with **Issues: Read and write** and Metadata: Read. Set a short expiry and rotate periodically. **Do not paste the token into ChatGPT**, GitHub issues, a screenshot, or the local browser's HTTP QR page.
3. Make sure your ChatGPT GitHub connector is explicitly granted access to the same private relay repository (GitHub App installation permissions may need updating).
4. On the Vu+ root shell, verify the beta safely:
   \`\`\`sh
   wget -qO /tmp/install-vulink-v3.sh https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/vulink-v3-github-relay/vulink/install.sh
   sh /tmp/install-vulink-v3.sh --check
   sh /tmp/install-vulink-v3.sh --install
   \`\`\`
5. One-time hidden token configuration on the **receiver's root SSH session**:
   \`\`\`sh
   python3 /usr/lib/enigma2/python/Plugins/Extensions/VuLink/v3_setup.py
   \`\`\`
   Enter \`wacayoub/VuLink-Relay\` and the token **when prompted**. The script checks the repository is private and restricts its local 0600 configuration file to root.
6. Restart **only Enigma2 GUI** from OpenATV, then open **Plugins → VuLink Pro V3 - ChatGPT Connect**. The TV should display "GitHub PRIVE CONNECTE" and the device issue number after GitHub responds. Start relay on GUI boot; the local QR web page remains an optional independent feature.

Once configured, the user can ask in this ChatGPT chat to check the Vu+ remotely. The assistant uses the connected GitHub integration to locate the **private device issue**, post a request, poll the issue comments for a matching VULINK_V3_RESULT, and summarize the response. The user no longer needs to download and attach every report.

## Machine-readable message format

Post a **GitHub issue comment** to the device registration issue:

\`\`\`text
VULINK_V3_REQUEST
{"protocol":"vulink-v3.1","device_id":"0123456789abcdef","request_id":"run-unique-20261014","created_at":"2026-10-14T14:00:00Z","operation":"preview_performance"}
\`\`\`

The device accepts only these **exact five fields**, a known device id, the repository owner's GitHub author login, a request id of 8–64 safe characters, and a timestamp no older than 10 minutes (or over 60 seconds in the future).

The response is added as another comment:

\`\`\`text
VULINK_V3_RESULT
{"protocol":"vulink-v3.1","device_id":"...","request_id":"...","operation":"preview_performance","status":"completed","completed_at":"...","result":{"available":true,"stage_metrics":{}}}
\`\`\`

For backup_iptosat, the first response is \`awaiting_tv_approval\`; user presses GREEN or YELLOW on the physical TV remote within 180 seconds, then agent posts completed/denied. Backups are never attached to GitHub or exposed over HTTP.

The device issue is created automatically in the **private** relay repository by the Vu+ after first setup; do not guess its number. GitHub latency varies; expected poll interval ~25 sec plus API latency.

## Scope and limitations

- V3 RC1 proves the **software relay path in local simulations**, not a live ChatGPT→GitHub→Vu+ run. It requires the one-time private repo, scoped token, GitHub connector permission and actual receiver boot test.
- **No SSH or FTP access inside ChatGPT.** To enable code changes later, extend the allowlist with checksum-pinned signed patches, backup + TV confirmation + rollback; do not open a shell or accept user-supplied file paths and commands through comments.
- All requests/replies stay private **only if the relay repository is private and GitHub authorizations are restricted**. GitHub can access relay data and acts as the intermediary.
- If disconnected GitHub/network, the agent retries; no router ports should be opened. To revoke, revoke the PAT in GitHub and remove \`/etc/enigma2/VuLink/v3-relay.json\` from Vu+.
- To rollback VuLink plugin code: \`sh /tmp/install-vulink-v3.sh --rollback\`, then restart Enigma2 GUI. The root-only relay configuration file is **not automatically deleted** during rollback.
