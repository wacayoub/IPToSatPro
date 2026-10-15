#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.15: speed up ONLY existing Preview candidate nomination, not scoring/GUI.

1) Fast-anchor filtering: skip building huge extra token-id postings,
   verify directly against original name tokens. Same rule as pre-R76.13,
   no candidate loss through stale token indexes.
2) Provider-family rescue: if *every* SAT providerless token has an indexed
   lexical prefix and coverage/provider indexes are ready, the already-built
   prefix index is a safe superset filter. Scan provider rows in original
   order; skip costly candidate normalization for impossible prefixes.
   Otherwise fall back to the exact R76.14 provider scan.

No channel cap reduction, no new indexes, no metadata rewriting, no player
changes, no mappings changes, no network requests.
"""
import ast

VERSION="1.0.46-r76.15-preview-index-fast-beta"
TAG="R7615_NOMINATION_INDEX_ONLY"


def span(src,method):
    t=ast.parse(src)
    cls=next(x for x in t.body if isinstance(x,ast.ClassDef) and x.name=="Catalog")
    funcs=[x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name==method]
    assert len(funcs)==1,(method,len(funcs))
    return funcs[0].lineno,funcs[0].end_lineno


def patch_method(src,method,pairs):
    a,b=span(src,method)
    lines=src.splitlines(keepends=True)
    block="".join(lines[a-1:b])
    for old,new in pairs:
        if block.count(old)!=1:
            raise AssertionError("R7615 anchor in "+method+" count="+str(block.count(old))+": "+repr(old[:120]))
        block=block.replace(old,new,1)
    return "".join(lines[:a-1])+block+"".join(lines[b:])


def patch_core(src):
    if TAG in src:
        return src
    old_fast='''            if _r7613_preview_postings:
                # R7613_PREVIEW_SCORING_POSTINGS: Preview only, no live changes.
                other = [t for t in anchors[:3] if t != anchors[0]]
                postings = [set(id(x) for x in self._token_index.get(t, ())) for t in other]
                probable = [ch for ch in base if all(id(ch) in ids for ids in postings)]
                tighter = [ch for ch in probable
                           if wanted.issubset(set((ch.get("norm") or "").split()))]
                if not tighter:
                    tighter = [ch for ch in base
                               if wanted.issubset(set((ch.get("norm") or "").split()))]
            else:'''
    new_fast='''            if _r7613_preview_postings:
                # R7615_NOMINATION_INDEX_ONLY: no giant posting-id sets.
                # Exact original norm-token gate; don't hide valid matches.
                tighter = [ch for ch in base
                           if wanted.issubset(set((ch.get("norm") or "").split()))]
            else:'''
    src=patch_method(src,"_fast_candidate_pool",[(old_fast,new_fast)])
    # A strict prefix-superset check; do NOT silently exclude 2-letter/numeric
    # services or generic aliases, which have no guaranteed lexical posting.
    old_provider='''            for ch in provider_index.get(sat_family, ()):
                if len(out) >= cap: return out
                cname = ch.get("name", "")'''
    new_provider='''            # R7615_NOMINATION_INDEX_ONLY: indexed superset for
            # provider rescues, only with complete coverage/provider indexes.
            # Original provider order and per-server limits are unchanged.
            _r7615_provider_rows = provider_index.get(sat_family, ())
            _r7615_allowed_ids = None
            if (len(_r7615_provider_rows) > 256
                    and getattr(self, "_preview_coverage_ready", False)
                    and getattr(self, "_preview_provider_ready", False)
                    and sat_provider_tokens and sat_provider_prefixes
                    and all(len(t) >= 4 and t not in _GENERIC_IDENTITY_TOKENS
                            for t in sat_provider_tokens)):
                _r7615_allowed_ids = set()
                for _r7615_prefix in sat_provider_prefixes:
                    for _r7615_row in prefix_index.get(_r7615_prefix, ()):
                        _r7615_allowed_ids.add(id(_r7615_row))
                if not _r7615_allowed_ids:
                    # Frozen index might be missing/old: fail open, never
                    # turn a missing prefix bucket into zero candidates.
                    _r7615_allowed_ids = None
            for ch in _r7615_provider_rows:
                if len(out) >= cap: return out
                if (_r7615_allowed_ids is not None
                        and id(ch) not in _r7615_allowed_ids):
                    continue
                cname = ch.get("name", "")'''
    src=patch_method(src,"_preview_nomination_pool",[(old_provider,new_provider)])
    compile(src,"core.py","exec")
    return src
