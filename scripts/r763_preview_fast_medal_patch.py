#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.3 fast Preview first paint and compact truth-in-labels candidate rows.

No player/media/network/monitor/mapping/cache persistence changes.
First-paint list is provisional and cannot cause an automatic lock.
All real scores still originate from the original background ranker.
"""
TAG="R763_FAST_INDEX_BEST_MEDAL"

SEED_HELPER='''# R763_FAST_INDEX_BEST_MEDAL
def _r763_preview_instant_index(sat_name, catalog, limit=24):
    """Show probable index hits while the existing background scorer is busy.

    Read only Catalog._exact keys/rows, not the underlying stream and not
    the full catalogue.  Only clear same-identity provisional suggestions;
    they remain REVIEW, 0-score, never used by unattended auto-mapping.
    """
    exact=_r7414_fast_exact_seed(sat_name,catalog)
    result=[dict(x) for x in exact]
    if len(result)>=limit or catalog is None:
        return result[:limit]
    import re as _r763_re
    from .core import normalize_name as _r763_normalize
    tokens=_r763_re.findall(r"[a-z0-9]+",_r763_normalize(sat_name or "").lower())
    noise={"tv","channel","hd","fhd","sd","uhd","4k","8k","1080p","1080i",
           "720p","2160p","h264","h265","hevc","live"}
    target=[t for t in tokens if t not in noise]
    if not target:
        return result[:limit]
    digits={t for t in target if t.isdigit()}
    groups=getattr(catalog,"_exact",None) or {}
    if not isinstance(groups,dict):
        return result[:limit]
    seen={str(row.get("url") or "") for row in result}
    roles={}
    for row in result:
        role=str(row.get("server_role") or "SERVER")
        roles[role]=roles.get(role,0)+1
    # Bounded indexed search: not Catalog.fast_preview_mega_matches().
    # In-memory keys, early pruning by overlap and exact numeric suffix.
    hits=[]
    for i,(key,rows) in enumerate(groups.items()):
        if i>=12000:
            break
        if not isinstance(key,str):
            continue
        candidate=set(_r763_re.findall(r"[a-z0-9]+",key.lower()))-noise
        if not candidate or (digits and not digits.issubset(candidate)):
            continue
        overlap=len(set(target)&candidate)
        required=2 if len(set(target))>=2 else 1
        if overlap<required:
            continue
        # Avoid showing unrelated names sharing generic terms.
        coverage=float(overlap)/len(set(target))
        if coverage<0.63:
            continue
        precision=float(overlap)/len(candidate)
        if precision<0.50:
            continue
        rank=(coverage,precision,-abs(len(candidate)-len(target)))
        hits.append((rank,key,rows))
    hits.sort(key=lambda a:a[0],reverse=True)
    for _rank,_key,rows in hits[:160]:
        if not isinstance(rows,(list,tuple)):
            continue
        for ch in rows[:40]:
            if not isinstance(ch,dict) or not ch.get("url"):
                continue
            fp=str(ch.get("url"))
            if fp in seen:
                continue
            role=str(ch.get("server_role") or "SERVER")
            if roles.get(role,0)>=8:
                continue
            roles[role]=roles.get(role,0)+1
            seen.add(fp)
            row=dict(ch)
            row["_manual_candidate"]=True
            row["_r763_fast_index"]=True
            row["_preview_score"]=0.0
            row["_preview_details"]={"review_reason":
                "INSTANT INDEX ONLY - unverified; background ranking pending"}
            result.append(row)
            if len(result)>=limit:
                return result
    return result


'''

# A single cheap firstpaint replacement in _load_selected_sat_candidates.
FIRST_OLD='''                first = _r7414_fast_exact_seed(self.sat_name, cat)'''
FIRST_NEW='''                first = _r763_preview_instant_index(self.sat_name, cat, limit=24)'''

# Original row text has already thrown away BEST OVERALL: it is only in
# state/tag metadata. Render explicit medal on the correct measured fp.
RENDER_OLD='''            quality = self._quality_record_text(ch)
            name = presentation_name(ch.get("name") or "IPTV")
            if len(name) > 31:
                name = name[:30] + "…"
            score=ch.get("_preview_score")
            score_text=("%.0f"%float(score)) if score not in (None,"") else "?"
            decision=self._candidate_decision(ch)
            observed=self._health_record(ch)
            measured=bool(observed.get("width") and observed.get("height"))
            state_text="REAL" if measured else "CAT"
            label="%s • %s" % (decision, score_text)
            text="[%s] %s • %s %s • %s • %s" % (
                _short_role(role), name[:32], state_text, quality[:13],
                server[:14], label)
            rows.append(self["source_list"].row(text[:112], state))'''

RENDER_NEW='''            # R763: short evidence labels; M=actually measured from
            # cached stream telemetry. C=unverified catalogue quality.
            name = presentation_name(ch.get("name") or "IPTV")
            if len(name) > 30:
                name = name[:29] + "…"
            observed=self._health_record(ch)
            measured=bool(observed.get("width") and observed.get("height"))
            if measured:
                try:
                    width=int(observed.get("width") or 0)
                    height=int(observed.get("height") or 0)
                    compact_quality="M:%dx%d" % (width,height)
                except Exception:
                    compact_quality="M:?"
            else:
                try:
                    quality_name=effective_quality_info(ch)[0] or "?"
                except Exception:
                    quality_name="?"
                compact_quality="C:%s" % str(quality_name)[:8].upper()
            if ch.get("_r763_fast_index") or ch.get("_r7414_seed"):
                score_label="IDX"
            else:
                score=ch.get("_preview_score")
                try: score_label="S%.0f" % float(score) if score is not None else "S?"
                except Exception: score_label="S?"
            # Do not call a candidate VERIFIED until OK actually checks it.
            decision_short={"USER REJECT":"REJ","REJECT":"REJ",
                            "REVIEW":"REV","MANUAL":"LOCK",
                            "ALLOWED":"SAFE","SAFE":"SAFE"}.get(decision,decision[:5])
            best_measured=bool(speed_count>=1 and overall_fp and cfp==overall_fp)
            medal="🎖 " if best_measured else ""
            best_marker="BEST " if best_measured else ""
            text="%s[%s] %s • %s • %s • %s • %s%s" % (
                medal,_short_role(role),name,compact_quality,
                server[:11],score_label,best_marker,decision_short)
            rows.append(self["source_list"].row(text[:112], state))'''


def once(src,old,new,name):
    n=src.count(old)
    if n!=1:
        raise AssertionError("R763 expected exactly one "+name+" anchor; found "+str(n))
    return src.replace(old,new,1)


def patch_plugin(src):
    if TAG in src:
        return src
    # Must not change the core smart-match threshold, auto-lock or player.
    src=once(src,"def _r7414_fast_exact_seed(sat_name, catalog):",
             SEED_HELPER+"def _r7414_fast_exact_seed(sat_name, catalog):",
             "instant seed helper")
    src=once(src,FIRST_OLD,FIRST_NEW,"first paint call")
    src=once(src,RENDER_OLD,RENDER_NEW,"candidate display")
    compile(src,"plugin.py","exec")
    return src

if __name__=="__main__":
    print("R763_PLUGIN_PATCH_READY")
