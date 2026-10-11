#!/usr/bin/env python3
"""IPToSatPro performance audit, Python stdlib only; reads logs, never changes receiver.

Usage:
  python3 /tmp/r727-speed-audit.py
  python3 /tmp/r727-speed-audit.py /etc/enigma2/SatIPTVBridge/bridge.log
  python3 /tmp/r727-speed-audit.py --self-test

No URLs, credentials, usernames, Xtream IDs, tokens or full raw log lines printed.
Distinguishes validated MPEG-TS bytes from actually decoded video.
"""
import sys,re,statistics
from collections import Counter

DEFAULT="/etc/enigma2/SatIPTVBridge/bridge.log"
def field(s,key):
    m=re.search(r"(?:^|\s)"+re.escape(key)+r"=(?:'([^']*)'|([^\s]+))",s)
    return (m.group(1) if m.group(1) is not None else m.group(2)) if m else ""
def events(rows):
    out=[]
    for line in rows:
        try:
            ts,kind,payload=(part.strip() for part in line.rstrip("\n").split("|",2))
        except ValueError:
            continue
        kind=kind.strip()
        if kind not in ("IPTV_OK","IPTV_FAIL","MATCH_BG_DONE","RETRY_PLAYER","MATCH_BG_REUSE",
                        "NO_MATCH","PLAYER_VERIFIED_REUSE","PLAYER_FAST_REUSE"):
            continue
        out.append((kind,payload))
    return out

def audit(rows):
    ev=events(rows)
    ok=[];matching=[];fail=Counter();retries=Counter()
    for kind,text in ev:
        sat=field(text,"sat") or "Unknown"
        if kind=="IPTV_OK":
            try:latency=int(field(text,"latency").rstrip("ms"))
            except Exception:continue
            label=field(text,"iptv")[:49]
            evidence=field(text,"evidence")
            ok.append((latency,sat,label,evidence,field(text,"mode"),field(text,"role")))
        elif kind=="MATCH_BG_DONE":
            try:cost=int(field(text,"cost").rstrip("ms"))
            except Exception:continue
            matching.append((cost,sat,field(text,"stage"),field(text,"candidates")))
        elif kind=="IPTV_FAIL":
            fail[(sat,field(text,"reason")[:58])]+=1
        elif kind=="RETRY_PLAYER":
            retries["player"]+=1
    print("=== IPToSatPro: SLOW-ZAP AUDIT (read only) ===")
    print("IPTV_OK:",len(ok),"| IPTV_FAIL:",sum(fail.values()),"| Player retries:",retries["player"])
    for title,rows in (("All IPTV acceptance times",ok),
                       ("First decoded frame / resolution only",[x for x in ok if x[3]!="validated-ts-data"]),
                       ("TS-ready only (NOT verified decoded video)",[x for x in ok if x[3]=="validated-ts-data"])):
        latencies=[x[0] for x in rows]
        if latencies:
            print("%s: n=%d median=%.2fs slowest=%.2fs"%
                  (title,len(rows),statistics.median(latencies)/1000,max(latencies)/1000))
        else:print("%s: n=0"%title)
    print("=== Slowest accepted IPTV (>=3s; top 10) ===")
    for latency,sat,label,evidence,mode,role in sorted(
            (x for x in ok if x[0]>=3000),reverse=True)[:10]:
        print("%.2fs | SAT=%s | IPTV=%s | evidence=%s | player=%s role=%s"%
              (latency/1000,sat[:44],label,evidence,mode,role))
    print("=== Longest SmartMatch CPU work (>=1s; top 10) ===")
    for cost,sat,stage,candidates in sorted(
            (x for x in matching if x[0]>=1000),reverse=True)[:10]:
        print("%.2fs | SAT=%s | stage=%s candidates=%s"%
              (cost/1000,sat[:48],stage,candidates))
    print("=== Most frequent playback errors (top 5) ===")
    for (sat,reason),num in fail.most_common(5):
        print("%d | SAT=%s | %s"%(num,sat[:44],reason))
    print("Interpretation: TS-ready <=2s does NOT prove first decoded video <=2s.")
    print("Only measurements; no automatic changes or credentials printed.")

def test():
    sample=[
        "2026-10-11 19:54:45 | IPTV_OK | candidate=1/8 attempt=1 mode=5002 role=PRIMARY sat='Animal Planet Europe HD' iptv='AR ANIMAL PLANET ARABIA HD' actual=1280x720/HD latency=24002ms evidence=resolution",
        "2026-10-11 19:58:06 | IPTV_OK | candidate=1/1 attempt=1 mode=dvb role=BACKUP2 sat='Digi 24' iptv='RO: DIGI 24 HD' actual=PENDING latency=1202ms evidence=validated-ts-data",
        "2026-10-11 19:50:29 | MATCH_BG_DONE | sat='Digi 24' stage=fuzzy cost=9784ms rows=32 candidates=0",
        "2026-10-11 19:11:16 | IPTV_FAIL | candidate=1/3 attempt=1 mode=dvb sat='ACASA' iptv='RO ACASA FHD' reason=IPTV stream reached EOF",
    ]
    parsed=events(sample)
    assert len(parsed)==4 and field(parsed[0][1],"latency")=="24002ms"
    assert field(parsed[1][1],"evidence")=="validated-ts-data"
    assert field(parsed[2][1],"cost")=="9784ms"
    audit(sample)
    print("SELF_TEST_OK")

if __name__=="__main__":
    if "--self-test" in sys.argv:test()
    else:
        path=sys.argv[1] if len(sys.argv)>1 else DEFAULT
        try:
            with open(path,"r",encoding="utf-8",errors="replace") as f:
                audit(f)
        except Exception as e:
            print("Cannot read diagnostic log:",type(e).__name__,str(e))
            sys.exit(1)
