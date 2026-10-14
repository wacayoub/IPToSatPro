#!/bin/sh
# IPToSat Pro r70 receiver smoke report (Vu+ Zero 4K / OpenATV 8.0.1).
# READ-ONLY diagnostic except an optional /tmp marker. Never prints URLs,
# credentials, full logs or channel names. Does not install or restart anything.
set -u

BASE=/etc/enigma2/SatIPTVBridge
P=/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge
LOG="$BASE/bridge.log"
MARK=/tmp/iptosat-r70-smoke-start
MODE="${1:-report}"

case "$MODE" in
mark)
    if [ ! -r "$LOG" ]; then
        echo "ERROR: $LOG missing or unreadable"
        exit 1
    fi
    wc -l < "$LOG" | tr -d ' ' > "$MARK"
    echo "Marker saved in /tmp (not in the IPTV configuration)."
    echo "Now zap between at least 20 LOCKED channels, including 4K, FHD and TOD; then run report."
    exit 0
    ;;
report)
    ;;
*)
    echo "Usage: sh $0 mark|report"
    exit 2
    ;;
esac

echo "=== IPToSat Pro read-only r70 receiver smoke report ==="
date
if command -v opkg >/dev/null 2>&1; then
    opkg status enigma2-plugin-extensions-satiptvbridge 2>/dev/null |
        grep -E '^(Package|Version|Status):'
fi
if [ -r "$P/plugin.py" ]; then
    grep -F 'PLUGIN_VERSION = ' "$P/plugin.py" | head -1
fi
if [ -r "$P/updater.py" ]; then
    grep -F 'CURRENT_VERSION = ' "$P/updater.py" | head -1
fi
if [ -r /proc/loadavg ]; then
    printf "loadavg: "
    cut -d ' ' -f 1-3 /proc/loadavg
fi
if [ -r /proc/meminfo ]; then
    grep -E '^(MemAvailable|MemFree):' /proc/meminfo | head -2
fi

echo "--- Metadata only: never display mappings or stream URLs ---"
if command -v python3 >/dev/null 2>&1; then
    python3 - "$BASE" <<'PY'
import json, os, sys
from pathlib import Path
base=Path(sys.argv[1])
for name, key in (("overrides.json", None),
                  ("r70-manual-locks.json", "locks"),
                  ("r70-history.json", "history")):
    p=base/name
    if not p.is_file():
        print("%s: not created" % name)
        continue
    try:
        if p.stat().st_size > 1024*1024:
            print("%s: exceeds diagnostic size limit" % name)
            continue
        d=json.loads(p.read_text(encoding="utf-8"))
        if key:
            d=d.get(key,{}) if isinstance(d,dict) else {}
        print("%s: %d records" % (name,len(d) if isinstance(d,dict) else 0))
    except Exception:
        print("%s: unreadable or malformed" % name)
PY
fi

if [ ! -r "$LOG" ]; then
    echo "bridge.log absent; no playback counters available."
    exit 0
fi
FIRST=0
if [ -r "$MARK" ]; then
    FIRST=$(cat "$MARK" 2>/dev/null)
    case "$FIRST" in *[!0-9]*|"") FIRST=0;; esac
fi
CURRENT=$(wc -l < "$LOG" | tr -d ' ')
case "$CURRENT" in *[!0-9]*|"") CURRENT=0;; esac
if [ "$CURRENT" -lt "$FIRST" ]; then
    echo "Log rotated since mark: starting count at zero."
    FIRST=0
fi
echo "Scanned log lines: $((CURRENT-FIRST)) (from marker line $FIRST)"
awk -v start="$FIRST" '
NR <= start { next }
{
  if (index($0," | IPTV_OK")) ok++
  if (index($0," | IPTV_FAIL")) fail++
  if (index($0," | PLAYER_LATE_VIDEO")) late++
  if (index($0," | PREVIEW_RANK_BG")) {
    rank++
    if (match($0,/elapsed=[0-9]+ms/)) {
      t=substr($0,RSTART+8,RLENGTH-10)+0
      if (t>2000) slow++
      if (t>maxrank) maxrank=t
    }
  }
  if (index($0," | SAT_TUNE_FAILED")) satfail++
  if (index($0," | FAIL_COOLDOWN")) cool++
  if (index($0," | QUALITY_DEGRADED")) lower++
  if (index($0," | IPTV_OK") && index($0,"actual=PENDING")) pending++
}
END {
 printf "IPTV_OK=%d IPTV_FAIL=%d late_video_events=%d\n",ok,fail,late
 printf "OK_with_pending_resolution=%d below_target_quality=%d\n",pending,lower
 printf "SAT_TUNE_FAILED=%d cooldowns=%d\n",satfail,cool
 printf "preview_rank_samples=%d slow_above_2s=%d max_rank_ms=%d\n",rank,slow,maxrank
 if (ok+fail==0) print "No IPTV sessions in marked window; test not yet conclusive."
 print "This report does NOT measure first displayed frame or prove silent/black video."
}
' "$LOG"
echo "Status: diagnostics only; keep r70 unpublished until receiver validation."
