#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.11: eliminate cold O(all IPTV) decorated index on the ACTUAL normal path.

R76.9 normal Preview calls Catalog.fast_rank_matches_all_servers -> 
Catalog._preview_nomination_pool, NOT fast_preview_mega_matches.
The latter received R76.10's thresholds, leaving this unconditional
_ensure_preview_decorated_index() call intact and potentially very slow.

Normal Preview uses the decorated index only if already built; initial results
still come from identity, token, provider and compact indexes, and full YELLOW/
deep search retains the original decorated-index rebuild.

No video/audio, live SmartMatch, mappings or ranking score changes.
"""
TAG="R7611_NORMAL_PREVIEW_NO_COLD_DECORATED_SCAN"
OLD='''        preview_index = self._ensure_preview_decorated_index()
        # Exact identity after stripping Preview-only provider decorations.'''
NEW='''        # R7611_NORMAL_PREVIEW_NO_COLD_DECORATED_SCAN: the normal 48/16
        # Preview MUST NOT build a whole-playlist decorated index on first use.
        # Reuse the already populated index when available; YELLOW/deep
        # retains _ensure_preview_decorated_index() in mega-ranking.
        preview_index = getattr(self, "_preview_decorated_exact", None)
        if not (isinstance(preview_index, dict) and
                bool(getattr(self, "_preview_decorated_ready", False))):
            preview_index = {}
        # Exact identity after stripping Preview-only provider decorations.'''


def patch_core(src):
    if TAG in src:
        return src
    import ast
    tree=ast.parse(src)
    catalog=next((n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="Catalog"),None)
    if catalog is None:
        raise AssertionError("Catalog class missing")
    normal=next((n for n in catalog.body if isinstance(n,ast.FunctionDef) and n.name=="_preview_nomination_pool"),None)
    if normal is None:
        raise AssertionError("R7611 normal Preview nomination method missing")
    lines=src.splitlines(keepends=True)
    body="".join(lines[normal.lineno-1:normal.end_lineno])
    if body.count(OLD)!=1 or src.count(OLD)!=1:
        raise AssertionError("R7611 normal preview index anchor changed")
    changed=body.replace(OLD,NEW,1)
    src="".join(lines[:normal.lineno-1])+changed+"".join(lines[normal.end_lineno:])
    compile(src,"core.py","exec")
    assert TAG in src
    return src


if __name__=="__main__":
    print("R7611_NORMAL_PREVIEW_NO_COLD_DECORATED_SCAN_PATCH_READY")
