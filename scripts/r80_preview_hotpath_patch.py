#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R80 experimental, source-only Preview hot-path optimization.

Exact R76.15 scoring thresholds, candidates, policy, mappings and player kept.
One bounded pure fuzzy-ratio cache for Preview; one per-rank-call key cache
for the SECOND sort of already scored immutable row tuples.
Not a production installer. Offline parity and receiver tests are mandatory.
"""
import ast

TAG = "R80_PREVIEW_PURE_HOTPATH_V1"
MAX_RATIO_CACHE = 2048


def span(source, name, owner=None, min_lines=0):
    tree = ast.parse(source)
    if owner:
        cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == owner)
        funcs = [x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == name]
    else:
        funcs = [x for x in tree.body if isinstance(x, ast.FunctionDef)
                 and x.name == name and x.end_lineno - x.lineno >= min_lines]
    if len(funcs) != 1:
        raise AssertionError("Unexpected R80 function: %s / %d" % (name, len(funcs)))
    return funcs[0].lineno, funcs[0].end_lineno


def patch_method(source, name, owner, substitutions, min_lines=0):
    a, b = span(source, name, owner, min_lines)
    lines = source.splitlines(keepends=True)
    body = "".join(lines[a - 1:b])
    for old, new in substitutions:
        if body.count(old) != 1:
            raise AssertionError("R80 anchor mismatch in %s: %s count=%d" %
                                 (name, old[:70], body.count(old)))
        body = body.replace(old, new, 1)
    return "".join(lines[:a - 1]) + body + "".join(lines[b:])


def patch_core(source):
    if TAG in source:
        return source
    original = source

    # Preview-only SequenceMatcher.ratio is referentially transparent for the
    # two normalized strings, including reversed country/branding variants.
    # The non-Preview, live-zap ratio stays completely unchanged.
    source = patch_method(source, "match_score_details", None, [
        ('        _r7613_ratio = SequenceMatcher(None, sat_norm, ip_norm).ratio()',
         '        _r7613_ratio = (_r80_preview_ratio(sat_norm, ip_norm) if preview\n'
         '                       else SequenceMatcher(None, sat_norm, ip_norm).ratio())'),
        ('            ratio = _r7613_ratio if _r7613_ratio is not None else SequenceMatcher(None, sat_norm, ip_norm).ratio()',
         '            ratio = _r7613_ratio if _r7613_ratio is not None else (\n'
         '                _r80_preview_ratio(sat_norm, ip_norm) if preview\n'
         '                else SequenceMatcher(None, sat_norm, ip_norm).ratio())'),
    ], min_lines=300)

    # The ranked row tuples stay alive until return. Between the two calls
    # to rows.sort/out.sort, no row's ch, details or score is modified.
    # The second sort therefore reuses the EXACT tuple key computed for
    # each row by the original helper. Distinct tuples retain distinct ids.
    source = patch_method(source, "fast_rank_matches_all_servers", "Catalog", [
        ('        def key(item):', '        def _r80_original_key(item):'),
        ('        rows.sort(key=key, reverse=True)',
         '        # R80_PREVIEW_PURE_HOTPATH_V1: request-local memoized sort key.\n'
         '        _r80_key_cache = {}\n'
         '        def key(item):\n'
         '            row_id = id(item)\n'
         '            if row_id not in _r80_key_cache:\n'
         '                _r80_key_cache[row_id] = _r80_original_key(item)\n'
         '            return _r80_key_cache[row_id]\n'
         '        rows.sort(key=key, reverse=True)'),
    ])

    ratio_helper = (
        '# R80_PREVIEW_PURE_HOTPATH_V1: bounded, in-memory, immutable ratios only.\n'
        'from functools import lru_cache as _r80_lru_cache\n'
        '@_r80_lru_cache(maxsize=2048)\n'
        'def _r80_preview_ratio(left, right):\n'
        '    return SequenceMatcher(None, left, right).ratio()\n\n'
    )
    lineno, _ = span(source, "match_score_details", None, min_lines=300)
    lines = source.splitlines(keepends=True)
    source = "".join(lines[:lineno - 1]) + ratio_helper + "".join(lines[lineno - 1:])
    assert source != original
    compile(source, "core.py", "exec")
    return source
