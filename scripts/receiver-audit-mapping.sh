#!/bin/sh
# IPToSat Pro read-only mapping diagnostic, Vu+ Zero 4K / OpenATV 8.0.1.
# Does not read provider credentials or stream URLs. Nothing installed.
set -u
echo '=== IPToSat mapping diagnostic (READ ONLY) ==='
echo '=== Installed packages ==='
opkg list-installed 2>/dev/null | grep -Ei 'iptosat|satiptvbridge|serviceapp|enigma2 ' | head -30 || true
echo '=== Plugin version strings ==='
P=/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge
if [ -f "$P/plugin.py" ]; then
    grep -E '^PLUGIN_VERSION[ =]' "$P/plugin.py" | head -1
else
    echo 'plugin.py unavailable'
fi
echo '=== System clock / DVB database ==='
date 2>/dev/null || true
ls -lh /etc/enigma2/lamedb* 2>/dev/null || true
echo '=== Current mapping source counts (no IDs/URLs revealed) ==='
python3 - <<'PY'
import os,json
root='/etc/enigma2/SatIPTVBridge'
if not os.path.isdir(root):
    print('Mapping directory not found')
else:
    for file in sorted(os.listdir(root)):
        if not file.endswith('.json'):
            continue
        try:
            p=os.path.join(root,file)
            if os.path.getsize(p)>8*1024*1024:
                continue
            if not any(x in file.lower() for x in ('override','mapping','reject','health')):
                continue
            obj=json.load(open(p,encoding='utf8'))
            count=len(obj) if isinstance(obj,(dict,list)) else 0
            print('%s: %d entries'%(file,count))
        except Exception:
            print('%s: unreadable or different schema'%file)
PY
echo '=== Candidate/index/Preview issues (safe logs) ==='
F=/etc/enigma2/SatIPTVBridge/bridge.log
if [ -r "$F" ]; then
    grep -E 'PREVIEW_RANK_BG|PREVIEW_ROSTER|PREVIEW_SAT_COST|AUTO_RESCUE_|MATCH_BG_ERR|MATCH_BG_DONE|NO_MATCH|MATCH_PLAN|MATCH_DIRECT|IPTV_OK|IPTV_FAIL|CANDIDATE_NEXT|RESTORE_SAT' "$F" | tail -100
else
    echo 'No readable bridge.log'
fi
echo '=== Enigma crash traces recent, if any ==='
for f in /home/root/logs/enigma2*.log; do
    [ -f "$f" ] || continue
    grep -E 'Traceback|AttributeError|TypeError|PREVIEW_RANK_BG|SatIPTVBridge' "$f" | tail -12
done
echo '=== End read-only diagnostic ==='
