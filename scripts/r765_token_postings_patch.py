#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.5: indexed postings first paint; smaller Preview-only rank pool and safer cache.

- On Vu+/Enigma2 GUI: reuse Catalog's PREBUILT inverted token postings, rather
  than scan up to 40,000 _exact name keys per SAT channel.
- If posting keys are available but nothing matches, return current exact seed
  and let the background ranker do the complete search. No GUI full key scan.
- When older Catalog lacks postings, preserve R76.4 _exact-name fallback.
- Preview-only top24 index nominations: examine up to 192 safe nominees
  rather than R73's at least 760; YELLOW/deep keeps 760+.
- Preserve all 18 existing full-score calls, safety thresholds, auto mapping
  and the native player; never label an index-only row SAFE.
- Keep 96 bounded context-aware cached result sets (was 48).
"""
TAG="R765_POSTINGS_FAST_FIRSTPAINT"

OLD_INDEX_START='''    hits=[]
    for i,(key,rows) in enumerate(groups.items()):'''
NEW_INDEX_START='''    # R765_POSTINGS_FAST_FIRSTPAINT: token postings already prepared by
    # Catalog when playlist loads. No full 40k-key name scan on GUI thread.
    hits=[]
    posting_index=getattr(catalog,"_token_index",None)
    if isinstance(posting_index,dict) and posting_index:
        anchors=[t for t in set(target) if t in posting_index and posting_index[t]]
        if anchors:
            rarest=min(anchors,key=lambda t:len(posting_index[t]))
            posting_rows=posting_index[rarest]
            for ch in posting_rows[:1800]:
                if not isinstance(ch,dict):
                    continue
                name=str(ch.get("norm") or ch.get("name") or "")
                key=name.lower()
                candidate=set(
                    (t[:-2] if t.endswith("tv") and len(t)>3 else t)
                    for t in _r763_re.findall(r"[a-z0-9]+",key)
                    if t not in noise)
                if not candidate or (digits and not digits.issubset(candidate)):
                    continue
                if target[-1] not in candidate:
                    continue
                overlap=len(set(target)&candidate)
                if overlap<(2 if len(set(target))>=2 else 1):
                    continue
                coverage=float(overlap)/len(set(target))
                precision=float(overlap)/len(candidate)
                if coverage<0.63 or precision<0.50:
                    continue
                rank=(coverage,precision,-abs(len(candidate)-len(target)))
                hits.append((rank,key,(ch,)))
            hits.sort(key=lambda a:a[0],reverse=True)
            # _token_index knows all IPTV server instances. Show as many
            # plausible P/B1/B2 sources as exist, without waiting for scores.
            for _rank,_key,rows in hits:
                for ch in rows:
                    if not ch.get("url"):
                        continue
                    fp=str(ch["url"])
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
                        break
                if len(result)>=limit:
                    break
            return result
        # Posting index exists: avoid scanning 40,000 names when there is
        # no indexed hit. Deferred worker still performs broader lookup.
        return result
    # Older/stub Catalog path: retain R76.4 exact-name scan compatibility.
    for i,(key,rows) in enumerate(groups.items()):'''

OLD_POOL='''        max_nominees = max(760, roles_cap * max(3, len(self.server_roles())) * 2)'''
NEW_POOL='''        # R765 only ordinary Preview (top24/8 per server); YELLOW/deep
        # keeps full R73.2/4 coverage for unusual aliases.
        max_nominees = (max(192, roles_cap * max(3, len(self.server_roles())) * 3)
                        if limit <= 24 and roles_cap <= 8 else
                        max(760, roles_cap * max(3, len(self.server_roles())) * 2))'''

OLD_CACHE='''        while len(order) > 48:'''
NEW_CACHE='''        # R765 retain more recent SAT identities without repeated scores.
        # Bound memory on low-RAM receiver; new Catalog naturally invalidates.
        while len(order) > 96:'''


def once(s,old,new,label):
    c=s.count(old)
    if c!=1:
        raise AssertionError("R765 source anchor drift %s count %s" % (label,c))
    return s.replace(old,new,1)


def patch_plugin(src):
    if TAG in src:return src
    src=once(src,OLD_INDEX_START,NEW_INDEX_START,"postings-first-paint")
    compile(src,"plugin.py","exec")
    return src


def patch_core(src):
    src=once(src,OLD_POOL,NEW_POOL,"preview-ranking-nominee-limit")
    src=once(src,OLD_CACHE,NEW_CACHE,"rank-cache-cap")
    compile(src,"core.py","exec")
    return src
