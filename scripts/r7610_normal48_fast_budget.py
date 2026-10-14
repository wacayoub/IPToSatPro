#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.10 candidate fix: R76.9 Preview's 48/16 was misclassified as DEEP.

R76.9 increased normal Manual-equivalent Preview from 24/8 to 48/16.
Two older core optimizations still use 24/8 as the normal fast-path bound:
- decorated index: empty cache triggers whole-catalogue build at limit>24;
- nominee limit: 48/16 triggers a 760+ rather than 192-row candidate pool.

Treat up to 48 candidates / 16 per server as normal ONLY in these two
performance gates; retain the exact scoring, verification, reject decisions,
sort, Manual Mapping, 192/64 DEEP mode, service and playback behavior.
A bounded fast nomination can miss aliases: YELLOW/DEEP remains available.
"""
TAG = "R7610_NORMAL48_FAST_BUDGET"
OLD_DECORATED = 'if limit > 24 else {})'
NEW_DECORATED = 'if limit > 48 else {})'
OLD_POOL = 'if limit <= 24 and roles_cap <= 8 else'
NEW_POOL = 'if limit <= 48 and roles_cap <= 16 else'


def patch_core(source):
    if TAG in source:
        return source
    for old, new, label in (
        (OLD_DECORATED, NEW_DECORATED, "decorated index fallback"),
        (OLD_POOL, NEW_POOL, "bounded nominee pool"),
    ):
        n = source.count(old)
        if n != 1:
            raise AssertionError("R7610 core %s anchor count=%d" % (label, n))
        source = source.replace(old, new, 1)
    # Add distinct version tag without affecting execution.
    source = '# ' + TAG + '\n' + source
    compile(source, "core.py", "exec")
    return source


if __name__ == "__main__":
    print("R7610_NORMAL48_FAST_BUDGET_SOURCE_READY")
