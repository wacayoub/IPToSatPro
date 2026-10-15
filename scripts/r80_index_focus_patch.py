#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPToSatPro R80 RC1: nomination-only lazy guards, NO scoring/UI changes.

Eliminates work provably unnecessary for the decision being computed:
 * never extract an IPTV service number when SAT name has no service number;
 * never determine provider family if lexical/prefix match already accepted;
 * never calculate expensive prefixes if exact lexical overlap accepted.
The original candidate pool membership, result order and scoring stay fixed.
"""
import ast
import re

VERSION="1.0.46-r80.0-rc1-index-focus"
MARKER="R80_INDEX_LAZY_GUARDS"


def function_span(source,name):
    root=ast.parse(source)
    catalog=next(x for x in root.body if isinstance(x,ast.ClassDef) and x.name=="Catalog")
    funcs=[x for x in catalog.body if isinstance(x,ast.FunctionDef) and x.name==name]
    assert len(funcs)==1,(name,len(funcs))
    return funcs[0].lineno,funcs[0].end_lineno


def patch_core(src):
    if MARKER in src:
        return src
    start,end=function_span(src,"_preview_nomination_pool")
    ls=src.splitlines(keepends=True)
    s="".join(ls[start-1:end])
    # Only replace NUMERIC GUARD computations in preview nomination, not
    # other matching, scoring, or live-zap code.
    old_bein='''                cnums = tuple(ch.get("_preview_numbers") or _preview_numbers(cname))
                if sat_pnums and cnums and tuple(sat_pnums) != tuple(cnums):
                    continue'''
    new_bein='''                # R80_INDEX_LAZY_GUARDS: avoid parsing candidate service
                # numbers when SAT service itself has no number.
                if sat_pnums:
                    cnums = tuple(ch.get("_preview_numbers") or _preview_numbers(cname))
                    if cnums and tuple(sat_pnums) != tuple(cnums):
                        continue'''
    if s.count(old_bein)!=1:
        raise AssertionError("beIN numeric guard drift "+str(s.count(old_bein)))
    s=s.replace(old_bein,new_bein,1)
    old_provider='''                    cnums = tuple(ch.get("_preview_numbers") or _preview_numbers(cname))
                    if sat_pnums and cnums and tuple(sat_pnums) != tuple(cnums):
                        continue'''
    new_provider='''                    # R80_INDEX_LAZY_GUARDS: no unnecessary
                    # number normalization for unnumbered SAT services.
                    if sat_pnums:
                        cnums = tuple(ch.get("_preview_numbers") or _preview_numbers(cname))
                        if cnums and tuple(sat_pnums) != tuple(cnums):
                            continue'''
    if s.count(old_provider)!=1:
        raise AssertionError("provider numeric guard drift "+str(s.count(old_provider)))
    s=s.replace(old_provider,new_provider,1)
    old_prefix='''                    cnums = tuple(ch.get("_preview_numbers") or _preview_numbers(ch.get("name", "")))
                    if sat_pnums and cnums and tuple(sat_pnums) != tuple(cnums):
                        continue'''
    new_prefix='''                    if sat_pnums:
                        cnums = tuple(ch.get("_preview_numbers") or _preview_numbers(ch.get("name", "")))
                        if cnums and tuple(sat_pnums) != tuple(cnums):
                            continue'''
    if s.count(old_prefix)!=1:
        raise AssertionError("prefix numeric guard drift "+str(s.count(old_prefix)))
    s=s.replace(old_prefix,new_prefix,1)
    old_number='''                    cprefs = _preview_prefixes(cname)
                    cfam = str(ch.get("provider_family") or _iptv_provider_family("%s %s" % (cname, ch.get("group", ""))) or "").upper()
                    shared = bool(sat_ptokens.intersection(ctokens)) or bool(sat_prefixes.intersection(cprefs))
                    same_family = bool(sat_family and cfam and sat_family == cfam)
                    if not (shared or same_family):
                        continue'''
    new_number='''                    # R80_INDEX_LAZY_GUARDS: short-circuit identical
                    # OR condition, preserving order and strict family policy.
                    shared = bool(sat_ptokens.intersection(ctokens))
                    if not shared:
                        shared = bool(sat_prefixes.intersection(_preview_prefixes(cname)))
                    same_family = False
                    if not shared and sat_family:
                        cfam = str(ch.get("provider_family") or _iptv_provider_family("%s %s" % (cname, ch.get("group", ""))) or "").upper()
                        same_family = bool(cfam and sat_family == cfam)
                    if not (shared or same_family):
                        continue'''
    if s.count(old_number)!=1:
        raise AssertionError("number rescue guard drift "+str(s.count(old_number)))
    s=s.replace(old_number,new_number,1)
    patched="".join(ls[:start-1])+s+"".join(ls[end:])
    compile(patched,"core.py","exec")
    return patched
