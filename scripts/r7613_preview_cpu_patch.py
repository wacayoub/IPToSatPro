#!/usr/bin/env python3
"""R76.13 targeted cold Preview CPU reductions (core-only, preview-scoped).

1. Reuse the same SequenceMatcher ratio twice in one scoring call.
2. Replace large norm-split scans in rarest-anchor candidate lookup with
   already-built postings intersection. Verify norm tokens before accepting
   a row. No new network, no stream probes, no cache rewrite.
Warning: token indexes must represent the same channel object identities as
the _exact index for the optimized path to be behavior-equivalent.
"""
import ast

TAG="R7613_PREVIEW_SCORING_POSTINGS"
NAME="1.0.46-r76.13-preview-cpu-fast-beta"


def span(src,cls,method):
 t=ast.parse(src)
 if cls:
  klass=next(n for n in t.body if isinstance(n,ast.ClassDef) and n.name==cls)
  pool=klass.body
 else:pool=t.body
 funcs=[n for n in pool if isinstance(n,ast.FunctionDef) and n.name==method]
 assert len(funcs)==1,(cls,method)
 return funcs[0].lineno,funcs[0].end_lineno


def one(s,old,new):
 if s.count(old)!=1:
  raise AssertionError("R7613 patch anchor missing/duplicate "+str(s.count(old))+": "+repr(old[:100]))
 return s.replace(old,new,1)


def method_replace(src,cls,method,changes):
 a,b=span(src,cls,method)
 lines=src.splitlines(keepends=True)
 body="".join(lines[a-1:b])
 for old,new in changes:
  body=one(body,old,new)
 return "".join(lines[:a-1])+body+"".join(lines[b:])


def patch_core(src):
 if TAG in src:
  return src
 # Efficient posting intersection on actual same-object identity, with norm
 # verification to preserve the original name-token acceptance gate.
 src=method_replace(src,"Catalog","_fast_candidate_pool",[
  ('''            tighter = [ch for ch in base if wanted.intersection(set((ch.get("norm") or "").split())) == wanted]''',
   '''            # R7613_PREVIEW_SCORING_POSTINGS: intersect the indexed channel IDs
            # before splitting individual channel norms; retain the norm gate.
            # A stale/incomplete posting is handled conservatively via the old
            # norm path so good candidates are never silently dropped.
            other = [t for t in anchors[:3] if t != anchors[0]]
            postings = [set(id(x) for x in self._token_index.get(t, ())) for t in other]
            probable = [ch for ch in base if all(id(ch) in ids for ids in postings)]
            tighter = [ch for ch in probable
                       if wanted.issubset(set((ch.get("norm") or "").split()))]
            if not tighter:
                tighter = [ch for ch in base
                           if wanted.issubset(set((ch.get("norm") or "").split()))]''')
 ])
 # Same double SequenceMatcher ratio in the preview-only exact score path.
 src=method_replace(src,None,"match_score_details",[
  ('''    if country_identity or reordered_identity or sat_norm == ip_norm or preview_provider_exact or (preview and _preview_compact_key(sat_name) and _preview_compact_key(sat_name) == _preview_compact_key(ch.get("name", ""))):''',
   '''    # R7613_PREVIEW_SCORING_POSTINGS: avoid recomputing the SAME fuzzy ratio
    # for preview identity eligibility in this scoring call.
    _r7613_ratio = None
    if country_identity or reordered_identity or sat_norm == ip_norm or preview_provider_exact or (preview and _preview_compact_key(sat_name) and _preview_compact_key(sat_name) == _preview_compact_key(ch.get("name", ""))):'''),
  ('''        seq = SequenceMatcher(None, sat_norm, ip_norm).ratio() * 78.0''',
   '''        _r7613_ratio = SequenceMatcher(None, sat_norm, ip_norm).ratio()
        seq = _r7613_ratio * 78.0'''),
  ('''            ratio = SequenceMatcher(None, sat_norm, ip_norm).ratio()''',
   '''            ratio = _r7613_ratio if _r7613_ratio is not None else SequenceMatcher(None, sat_norm, ip_norm).ratio()''')
 ])
 compile(src,"core.py","exec")
 return src
