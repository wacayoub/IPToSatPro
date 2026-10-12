# R73.8 SAFE Auto Play — staged beta

Branch-only experimental change; not merged into main or the production update.json.

- Automatically passes a selected SAFE/ALLOWED IPTV candidate through the existing Enigma2 monitored player after a Preview-generated AUTO mapping.
- Also handles previously saved AUTO mappings, with a one-minute protection window so manual corrections stay accessible.
- Rejects stale SAT references, user zaps, manual locks, background-only/non-current services, duplicate requests and working DVB video.
- Preserves monitor.py, player, timeshift, user settings and saved mappings byte-for-byte inside the package.
- Preview candidate detailed-scoring budget 18 -> 36 (shared P/B1/B2 indexing remains bounded).
- GitHub Actions tests and checksum-staged beta are prerequisites for field testing.

Opt-in beta script (once published): `download-r738-safe-beta.sh`.

Do not install until the manifest and payload files exist on this branch. A receiver test is still necessary.
