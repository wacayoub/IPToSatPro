#!/usr/bin/env python3
"""R76.14 Preview pure-parsing memoization on R76.13 (source only).

Original scoring code, tokenization logic, ranking, tie-breakers, and
manual-lock checks remain BYTE-FOR-BYTE unchanged inside function bodies.
Only bounded LRU decorators on immutable-output helper functions.
No cache files, persisted state, IPTV passwords or GUI interactions.
"""
import ast
import re

VERSION="1.0.46-r76.14-preview-parsecache-beta"
TAG="R7614_PREVIEW_PARSE_CACHE_IMMUTABLE"
CACHE_MAX=2048
PURE_FUNCTIONS=(
    "_r748_explicit_country",
    "normalize_preview_name",
    "_preview_lexical_tokens",
    "_preview_numbers",
    "_preview_identity_norm",
    "_preview_compact_key",
    "_preview_abbreviation_key",
)


def patch_core(source):
    if TAG in source:
        return source
    original=ast.parse(source)
    for name in PURE_FUNCTIONS:
        found=[x for x in ast.walk(original) if isinstance(x,ast.FunctionDef) and x.name==name]
        if len(found)!=1:
            raise AssertionError("unexpected R76.13 helper count: %s/%d"%(name,len(found)))
        if found[0].args.posonlyargs or found[0].args.kwarg or found[0].args.vararg:
            raise AssertionError("unbounded argument form in cached helper: "+name)
    # LRU cache returns immutable strings, numbers, booleans or tuples.
    # It is in-process only (never serialized with the frozen IPTV Catalog).
    start="def _r748_explicit_country(name):"
    if source.count(start)!=1:
        raise AssertionError("country helper signature changed")
    source=source.replace(start,
        "from functools import lru_cache as _r7614_cached\n"
        "# R7614_PREVIEW_PARSE_CACHE_IMMUTABLE — maximum 2048 name keys/helper.\n"
        "@_r7614_cached(maxsize=2048)\n"
        +start,1)
    for name in PURE_FUNCTIONS:
        if name=="_r748_explicit_country":
            continue
        # This inserts only a decorator. AST bodies must be exactly identical.
        patt=r"(?m)^(def "+re.escape(name)+r"\()"
        patched,count=re.subn(patt,
            "@_r7614_cached(maxsize=2048)\n"+r"\1",source,count=1)
        if count!=1:
            raise AssertionError("helper signature not found for "+name)
        source=patched
    actual=ast.parse(source)
    for name in PURE_FUNCTIONS:
        b=next(x for x in ast.walk(original) if isinstance(x,ast.FunctionDef) and x.name==name)
        a=next(x for x in ast.walk(actual) if isinstance(x,ast.FunctionDef) and x.name==name)
        # New decorator ONLY. No one changes helper code or match behavior.
        if ast.dump(ast.Module(body=b.body,type_ignores=[]),include_attributes=False)!=ast.dump(
            ast.Module(body=a.body,type_ignores=[]),include_attributes=False):
            raise AssertionError("cached pure helper body changed "+name)
    compile(source,"core.py","exec")
    return source
