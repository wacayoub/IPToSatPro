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
 else:pool=ast.walk(t)
 funcs=[n for n in pool if isinstance(n,ast.FunctionDef) and n.name==method]
 if cls is None and method=="match_score_details":
  # Real core has a later short policy wrapper; patch the 373-line scorer.
  funcs=[n for n in funcs if n.end_lineno-n.lineno>=100]
 assert len(funcs)==1,(cls,method,[(n.lineno,n.end_lineno) for n in funcs])
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
  ('''    def _fast_candidate_pool(self, sat_name, per_server=80, total_cap=None):''',
   '''    def _fast_candidate_pool(self, sat_name, per_server=80, total_cap=None, _r7613_preview_postings=False):'''),
  ('''            tighter = [ch for ch in base if wanted.intersection(set((ch.get("norm") or "").split())) == wanted]''',
   '''            if _r7613_preview_postings:
                # R7613_PREVIEW_SCORING_POSTINGS: Preview only, no live changes.
                other = [t for t in anchors[:3] if t != anchors[0]]
                postings = [set(id(x) for x in self._token_index.get(t, ())) for t in other]
                probable = [ch for ch in base if all(id(ch) in ids for ids in postings)]
                tighter = [ch for ch in probable
                           if wanted.issubset(set((ch.get("norm") or "").split()))]
                if not tighter:
                    tighter = [ch for ch in base
                               if wanted.issubset(set((ch.get("norm") or "").split()))]
            else:
                tighter = [ch for ch in base
                           if wanted.intersection(set((ch.get("norm") or "").split())) == wanted]''')
 ])
 # Activate postings only for Preview calls; live zap remains untouched.
 src=method_replace(src,"Catalog","_preview_nomination_pool",[
  ('''for ch in self._fast_candidate_pool(sat_name, per_server=max(36, per_server)):''',
   '''for ch in self._fast_candidate_pool(sat_name, per_server=max(36, per_server), _r7613_preview_postings=True):''')
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
