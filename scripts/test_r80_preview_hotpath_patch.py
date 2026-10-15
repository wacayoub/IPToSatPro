#!/usr/bin/env python3
"""R80 offline source and behavioral parity; fabricated rows only.

Never accesses receiver IPTV services, mapped profiles or server credentials.
"""
import ast
import difflib
import functools
import importlib.util
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load("r80_base", "build-r7615-preview-index.py")
patch = load("r80_hotpath", "r80_preview_hotpath_patch.py")


def functions(source):
    tree = ast.parse(source)
    catalog = next(x for x in tree.body
                   if isinstance(x, ast.ClassDef) and x.name == "Catalog")
    nodes = {"Catalog." + x.name: ast.dump(x, include_attributes=False)
             for x in catalog.body if isinstance(x, ast.FunctionDef)}
    fns = [x for x in tree.body if isinstance(x, ast.FunctionDef)
           and x.name == "match_score_details"]
    for i, fn in enumerate(fns):
        nodes["match_score_details_%d" % i] = ast.dump(fn, include_attributes=False)
    return nodes


def key_snippet(source):
    start, end = patch.span(source, "fast_rank_matches_all_servers", "Catalog")
    lines = source.splitlines()
    body = "\n".join(lines[start - 1:end])
    identifier = ("        def _r80_original_key(item):"
                  if patch.TAG in source else "        def key(item):")
    a = body.index(identifier)
    final = "        rows.sort(key=key, reverse=True)"
    b = body.index(final, a) + len(final)
    return textwrap.dedent(body[a:b])


def rank_fixture(source, channels):
    context = {"confidence": "HIGH", "match_threshold": 82.0}
    counters = {"context": 0, "quality": 0}
    def bands(ch, det, context):
        counters["context"] += 1
        return (int(ch.get("market", 0)), int(ch.get("language", 0)), 0)
    def qfit(ch, sat, ctx):
        counters["quality"] += 1
        return int(ch.get("quality", 0))
    class Cat:
        _context_rank_bands = staticmethod(bands)
    rows = [(ch, float(ch["score"]), dict(ch["details"])) for ch in channels]
    env = {"self": Cat(), "sat_name": "BEIN SPORTS 1", "context": context,
           "rows": rows, "match_decision": lambda score, det, threshold:
           "SAFE" if score >= threshold else "REVIEW",
           "quality_fit_key": qfit, "_stream_penalty": lambda ch: 0}
    exec(compile(key_snippet(source), "extracted_key.py", "exec"), env)
    # The production method re-sorts the shortlisted output.
    env["out"] = rows[:min(7, len(rows))]
    exec("out.sort(key=key, reverse=True)", env)
    return ([(ch["name"], ch["server_role"]) for ch, _, _ in rows],
            [(ch["name"], ch["server_role"]) for ch, _, _ in env["out"]],
            counters)


class R80HotpathParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as temp:
            pkg = Path(temp) / "r7615.ipk"
            meta = base.build(pkg)
            assert meta["sha256"] == "c3991af773c6700c1aac0652f5027b27b4e1a91ff0820bf25e801e8d8488c468"
            members = base.pack.members_from(base.pack.unpack_ar(pkg.read_bytes())["data.tar.gz"])
            cls.before = members[base.CORE].decode("utf8")
        cls.after = patch.patch_core(cls.before)

    def test_only_preview_sort_and_first_score_function_change(self):
        a, b = functions(self.before), functions(self.after)
        self.assertEqual(a.keys(), b.keys())
        self.assertEqual({key for key in a if a[key] != b[key]},
                         {"Catalog.fast_rank_matches_all_servers",
                          "match_score_details_0"})
        self.assertEqual(patch.patch_core(self.after), self.after)
        self.assertIn("R80_PREVIEW_PURE_HOTPATH_V1", self.after)
        # Native live-zapping and all user/player functions retain their AST.
        self.assertIn("else SequenceMatcher(None, sat_norm, ip_norm).ratio()", self.after)

    def test_exact_rank_and_second_sort_parity(self):
        channels = []
        roles = ("PRIMARY", "BACKUP1", "BACKUP2")
        for i in range(57):
            channels.append({
                "name": "BEIN SPORTS %d" % (i % 19),
                "server_role": roles[i % 3],
                "score": 70 + (i % 27),
                "details": {
                    "name": float(10 + i % 23), "equivalence": float(i % 3),
                    "variant": float(i % 5), "provider_identity": bool(i % 4)},
                "market": i % 3, "language": i % 5, "quality": i % 4,
                "server_priority": (i % 3) + 1})
        before = rank_fixture(self.before, channels)
        after = rank_fixture(self.after, channels)
        self.assertEqual(before[:2], after[:2])
        self.assertGreater(before[2]["context"], after[2]["context"])
        self.assertEqual(after[2]["context"], len(channels))
        self.assertEqual(after[2]["quality"], len(channels))

    def test_ratio_values_identical_for_prefixes_country_and_aliases(self):
        tree = ast.parse(self.after)
        fn = next(x for x in tree.body
                  if isinstance(x, ast.FunctionDef) and x.name == "_r80_preview_ratio")
        node = ast.Module(body=[fn], type_ignores=[])
        ast.fix_missing_locations(node)
        env = {"SequenceMatcher": difflib.SequenceMatcher,
               "_r80_lru_cache": functools.lru_cache}
        exec(compile(node, "ratio.py", "exec"), env)
        cached = env["_r80_preview_ratio"]
        names = [
            ("bein sports 1", "bein sports 1"),
            ("tve la 1", "la 1"),
            ("osn cinema", "osn cinema hd"),
            ("tlc at", "tlc austria"),
            ("filmbox one", "one filmbox"),
            ("fr disney channel", "de disney channel"),
            ("nat geo abu dhabi", "natgeo ad"),
            ("ushuaia tv", "ushuaia hd")]
        for _ in range(30):
            for left, right in names:
                expected = difflib.SequenceMatcher(None, left, right).ratio()
                self.assertEqual(cached(left, right), expected)
        self.assertGreater(cached.cache_info().hits, 200)
        self.assertLessEqual(cached.cache_info().currsize, patch.MAX_RATIO_CACHE)


if __name__ == "__main__":
    unittest.main()
