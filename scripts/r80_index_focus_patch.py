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
    # Match EXACT numeric-guard syntax, preserving whatever indentation
    # appears in the compiled Enigma2 packet. This intentionally changes
    # only the three Preview nomination guards, not the scorer.
    numeric = re.compile(
        r'(?m)^(?P<pad> +)cnums = (?P<expr>tuple\(ch\.get\("_preview_numbers"\) or _preview_numbers\([^\n]+\)\))\n'
        r'(?P=pad)if sat_pnums and cnums and tuple\(sat_pnums\) != tuple\(cnums\):\n'
        r'(?P=pad)    continue')
    def lazy_nums(match):
        pad=match.group("pad")
        return (pad+"# R80_INDEX_LAZY_GUARDS: don't parse IPTV service numbers\n"
                +pad+"# when the SAT service has none.\n"
                +pad+"if sat_pnums:\n"
                +pad+"    cnums = "+match.group("expr")+"\n"
                +pad+"    if cnums and tuple(sat_pnums) != tuple(cnums):\n"
                +pad+"        continue")
    s,n=re.subn(numeric,lazy_nums,s)
    if n!=3:
        raise AssertionError("numeric lazy guard count expected 3, got "+str(n))
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
