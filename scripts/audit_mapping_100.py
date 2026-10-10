#!/usr/bin/env python3
"""100-point mapping audit matrix: evidence accounting, NOT 100 fabricated live tests."""
from pathlib import Path
import json, collections, csv, io
ROOT=Path(__file__).resolve().parents[1]
groups=json.loads("{\"01. SAT catalogue & scan\":[\"TV lamedb counted per orbital\",\"SAT DVB reference is stable and canonical\",\"8W 240 TV services inventoried\",\"Crypted flag sourced from CAID/static data\",\"FTA services visible in separate list\",\"beIN SPORTS 6 in 8W roster\",\"SAT channel index cursor restored\",\"No phantom duplicate SAT refs\",\"SAT 7W/8W distinction correct\",\"SAT without signal included only in allowed mode\"],\"02. Preview cache & lock\":[\"LOCKED badge equals saved mapping\",\"Locked source appears in right candidate panel\",\"Complete-empty cache can be invalidated\",\"Stale lock fingerprint detected\",\"Global Preview cache token changes on provider refresh\",\"First paint cannot permanently freeze 0 candidates\",\"Partial cache cannot overwrite complete valid result\",\"Pinned candidate not removed by top-36 truncation\",\"Old SAT result cannot repaint next channel\",\"Source list preserves chosen index across refresh\"],\"03. Manual mapping integrity\":[\"Saved lock never silently overwritten\",\"Mapping survives GUI reboot\",\"Mappings source fingerprint lookup resolves\",\"Legacy mapping without provider metadata handled\",\"Provider stream rotation repairs stale fingerprint\",\"PRIMARY/B1/B2 identity remains distinct\",\"Unmatched mapping source shown as unavailable not 0 valid\",\"Manual rejected candidate never auto-selected\",\"SAT mapping exact-ref key collision checked\",\"Manual/learned/session mapping policy separated\"],\"04. Candidate discovery\":[\"Fast exact index returns exact beIN number\",\"Every configured provider role indexed\",\"All Sources pagination reaches every row\",\"Live fallback can use backup candidates after pinned failure\",\"TREK FR/HD decorations normalize correctly\",\"Candidate pool doesn't starve rare backup\",\"Negative cache expires for missing candidates\",\"Index lookups do not require fresh network scan\",\"Automatic candidates respond to changed server catalogue\",\"beIN SPORTS 6 sources appear in right Preview pane\"],\"05. Identity & safety\":[\"beIN SPORTS 1 is not TOD EVENT 7 by default\",\"Channel number 1 is distinct from 2 and 3\",\"beIN SPORTS 6 is not generic beIN UHD\",\"Market/language conflicting feed rejected\",\"UHD 4K not forced into FHD SAT by default\",\"Unknown resolution not assumed 4K\",\"Audio language identity before auto-lock\",\"No wrongly merged SAT/OTT event feeds\",\"Candidate hard rejection remains final\",\"No automatic persisted REVIEW lock\"],\"06. Async events & lifecycle\":[\"Late IPTV_OK cancels pending rescue\",\"Late success blocks SAT restoration\",\"Rescue timer cannot apply after zap change\",\"One recovery search per zap generation\",\"Saved mapping remains while background ranker runs\",\"Worker never touches Enigma2 GUI\",\"Worker timeout has deterministic safe outcome\",\"GUI teardown cancels pending timers\",\"No callback can overwrite winning IPTV picture\",\"No stale completion can restart already verified player\"],\"07. Playback & audio\":[\"5002 failure can try 4097 when appropriate\",\"TOD 4K ServiceApp audio route considered\",\"beIN 4K has confirmed audible sound\",\"Native TS-ready distinguished from video decoded\",\"Hardware PTS/video dimensions independently validated\",\"TOD Events 1–14 preserve audio tracks\",\"No dual player extra work on first-mode success\",\"UHD stream truly 3840x2160 when selected\",\"Timeshift/play-pause remains native compatible\",\"EOF retry never loops indefinitely\"],\"08. Performance & memory\":[\"Preview first paint p50 below 150 ms\",\"Preview full rank p95 below 1 s\",\"No AUTO_RESCUE_TIMEOUT on healthy indexed catalog\",\"Zap locked median below 2 s when stream healthy\",\"CPU responsive on 5000 IPTV items\",\"RAM bounded across 100 SAT zaps\",\"No multiple heavy rank workers at same time\",\"Candidate processing bounded per server\",\"Background ranker yields CPU to Enigma2\",\"No 12 s cooldown on a recoverable alternate\"],\"09. User actions & status\":[\"LOCKED means source playable or status distinguished\",\"NO SOURCE not shown during pending expansion\",\"Unmeasured candidate has honest label\",\"GREEN requires verified selected identity\",\"YELLOW can browse all candidates\",\"BLUE auto-test honors user choice\",\"User can disable automatic fallback\",\"Source/server role visible for each candidate\",\"Current SAT remains on left when IPTV fails\",\"Log explains reject versus missing versus timeout\"],\"10. Release safeguards & validation\":[\"OpenATV 8.0.1 physical zap tested\",\"Vu+ Zero 4K cold boot tested\",\"No Enigma2 crash from PAT event callback\",\"Native original monitor AST preserved\",\"Every protection test green offline\",\"Real beIN 1–8 playback validation\",\"Real TREK and at least 10 non-sports validation\",\"Playback+audio regression matrix verified\",\"Rollback backup command proven on receiver\",\"No next IPK or Online Update before full gate\"]}")
observed=json.loads("{\"02-02\":\"Screenshot beIN SPORTS 6: mapping locked, candidate panel NO SOURCE.\",\"04-10\":\"Screenshot beIN SPORTS 6: 0 BEST / NO SOURCE.\",\"06-01\":\"At 20:57 IPTV_FAIL -> AUTO_RESCUE_START -> delayed IPTV_OK on the same source.\",\"06-02\":\"At 20:57 AUTO_RESCUE_START and IPTV_OK coexist; ranker later timed out and restored SAT.\",\"08-03\":\"At 20:57:40 and 20:58:12 AUTO_RESCUE_TIMEOUT observed.\",\"09-01\":\"Screenshot: LOCKED badge while no source is shown.\",\"09-02\":\"Screenshot: NO SOURCE while title says candidate expansion pending.\",\"07-03\":\"User reports beIN 4K image with no audio, not verified resolved.\",\"07-08\":\"At 20:57 beIN 4K target UHD but observed 1920x1080/FHD.\"}")
staged=json.loads("{\"02-02\":\"Staged source reconciliation on locked cached Preview row; requires receiver test.\",\"02-03\":\"Staged invalidation of a complete empty cache tied to stale manual lock.\",\"02-04\":\"Staged fingerprint lookup / stale lock differentiation; not yet packaged.\",\"06-01\":\"Staged cancel when playback_locked after late decoded video.\",\"06-02\":\"Staged guard against restoring SAT after winning IPTV.\",\"06-09\":\"Staged late-first-frame owner guard and cancellation.\"}")
static=json.loads("{\"01-01\":\"plugin.py:_preview_sat_service_rows uses lamedb TV rows.\",\"01-04\":\"plugin.py checks lamedb and Enigma2 native access evidence.\",\"02-01\":\"plugin.py:_sat_status reads saved manual overrides.\",\"02-05\":\"plugin.py:_preview_catalog_token/cache sync exists.\",\"02-07\":\"plugin.py:_preview_candidate_cache_put preserves complete results.\",\"02-08\":\"plugin.py:_poll_expanded_candidates preserves selected outside top-36.\",\"03-01\":\"monitor.py:MANUAL_LOCK is exact user-authoritative source.\",\"03-06\":\"core.py preserves distinct server identities/fingerprints.\",\"03-08\":\"monitor.py and Preview filter user-rejected candidates.\",\"03-10\":\"monitor.py separates manual/learned/session direct mappings.\",\"04-01\":\"core.py has fast exact index and number-aware candidate pooling.\",\"04-02\":\"core.py all-server matching supports roles.\",\"04-03\":\"r70_preview_patch.py pagination controls all-source listings.\",\"04-05\":\"core.normalize_name strips FR/HD decoration.\",\"04-08\":\"core.py fast rank uses built indexes; no network in matching.\",\"05-02\":\"core.py compares significant channel numbers.\",\"05-04\":\"monitor.py checks market and language match_decision.\",\"05-05\":\"monitor.py QUALITY_4K_GUARD keeps normal SAT from UHD auto upscale.\",\"05-06\":\"monitor.py UHD_UNKNOWN_SKIP protects UHD identity.\",\"05-09\":\"core.match_decision filters hard rejects.\",\"05-10\":\"preview_autotest_rc4 stops for manual GREEN lock.\",\"06-03\":\"auto_recovery_rc7 compares SAT ref/token in poll.\",\"06-04\":\"auto_recovery_rc7 stores one attempted SAT ref.\",\"06-06\":\"auto_recovery_rc7 worker uses pure catalog ranking and only returns result.\",\"06-08\":\"auto_recovery_rc7 cancel on stop-probe / stop-all timers.\",\"07-01\":\"TOD player plan 5002 then 4097 implemented.\",\"07-04\":\"monitor.py:_record_health distinguishes TS-ready vs decoded-video.\",\"07-07\":\"player_recovery_rc5 only adds a failure-mode alternate.\",\"07-10\":\"monitor.py has bounded retry/cooldown.\",\"08-07\":\"Preview refuses overlapping expansion worker.\",\"08-08\":\"core fast all-server candidate cap exists.\",\"09-04\":\"Preview GREEN locks selected candidate, no automatic saves in rc4.\",\"09-05\":\"All Sources is bound to YELLOW.\",\"09-06\":\"Auto-test bound to BLUE/3 on selected SAT.\",\"09-07\":\"Settings allows opt-out.\",\"10-04\":\"Baseline checker asserts original monitor function AST unmodified.\",\"10-05\":\"Offline CI tests exist for safety, preview, FTA and player.\"}")
checks=[]
for g,(group,entries) in enumerate(groups.items(),1):
    assert len(entries)==10
    for i,description in enumerate(entries,1):
        cid="%02d-%02d"%(g,i)
        if cid in staged:
            status="PATCH_STAGED_NOT_RECEIVER_VERIFIED"
            evidence=staged[cid]
        elif cid in observed:
            status="OBSERVED_PROBLEM"
            evidence=observed[cid]
        elif cid in static:
            status="CODE_SAFEGUARD_PRESENT_ONLY"
            evidence=static[cid]
        else:
            status="NEEDS_REAL_RECEIVER_TEST"
            evidence="Not confirmed by source code or user logs; receiver measurement required."
        checks.append({"id":cid,"group":group,"check":description,"status":status,"evidence":evidence})
assert len(checks)==100
# Guarantee staged fixes and code checks exist before calling any offline audit green.
sources={name:(ROOT/"r70"/name).read_text() for name in
  ("auto_recovery_rc7.py","r70_preview_patch.py",
   "tod_audio_recovery_rc6.py","preview_autotest_rc4.py")}
required=["AUTO_RESCUE_CANCEL_LATE_OK","_r70_rc7_reconciled","_preview_candidate_cache_drop",
          "playback_locked","_accept_verified_video","fast_rank_matches_all_servers"]
for token in required:
    if not any(token in text for text in sources.values()):
        raise AssertionError("Missing audit source evidence: "+token)
total=collections.Counter(row["status"] for row in checks)
print("100-POINT AUDIT:",dict(total))
lines=["# IPToSat Pro mapping & Preview — audit of 100 checkpoints",
       "",
       "> Important: this is a 100-control audit, not a claim of 100 real receiver tests.",
       "> Code presence does not mean functional success. Any observed failure blocks release.",
       ""]
lines.append("**Status counts:** "+", ".join("%s: %d"%(k,v) for k,v in sorted(total.items())))
lines.append("")
last=None
for r in checks:
    if r["group"]!=last:
        lines+=["## "+r["group"],""]
        last=r["group"]
    lines.append("- **"+r["id"]+"** "+r["check"]+" — `"+r["status"]+"`. "+r["evidence"])
lines+=["","**RELEASE GATE: BLOCKED** until zero critical observed failures, no staged-only guards, and hardware validation on Vu+ Zero 4K/OpenATV 8.0.1."]
out=ROOT/"audit";out.mkdir(exist_ok=True)
(out/"MAPPING_100_RESULTS.md").write_text("\n".join(lines)+"\n")
with (out/"MAPPING_100_RESULTS.csv").open("w",newline="") as h:
    w=csv.DictWriter(h,fieldnames=("id","group","check","status","evidence"))
    w.writeheader();w.writerows(checks)
print("WROTE",out/"MAPPING_100_RESULTS.md")
print("RELEASE_BLOCKED",bool(total.get("OBSERVED_PROBLEM") or total.get("PATCH_STAGED_NOT_RECEIVER_VERIFIED") or total.get("NEEDS_REAL_RECEIVER_TEST")))
