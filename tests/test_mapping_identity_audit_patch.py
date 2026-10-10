"""Actual pinned-core regression for TREK/Tipik audit patch, no receiver/IPK.

Runs all 100 existing SAT/OTT scoring cases against amended core as well as
the exact reported BE / FR labels, variant/number conflicts and stale v11 rows.
"""
import base64
import io
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "r70"))
sys.path.insert(0, str(ROOT / "tests"))
from mapping_identity_audit_patch import improve
from test_mapping_corpus_100 import _cases


def load_patched_core():
    raw = base64.b64decode((ROOT / "payload/r69-beta.b64").read_bytes())
    with tempfile.TemporaryDirectory() as td:
        ipk = Path(td) / "published-r69.ipk"
        ipk.write_bytes(raw)
        archive = subprocess.check_output(["ar", "p", str(ipk), "data.tar.gz"])
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        src = tar.extractfile(
            "./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/core.py"
        ).read().decode()
    patched = improve(src)
    compile(patched, "patched-core.py", "exec")
    ns = {"__name__": "audit_patched_core"}
    exec(patched, ns)
    return ns


C = load_patched_core()


def classify(sat, iptv, group="FRANCE", provider="Unknown"):
    ctx = C["infer_sat_context"](
        sat, provider, orbital_position=130, user_languages=["AR", "FR", "EN"]
    )
    row = {"name": iptv, "url": "fake://unit-test", "group": group}
    score, details = C["match_score_details"](
        sat, row, ["AR", "FR", "EN"], ctx, "best"
    )
    return C["match_decision"](score, details, 82.0), score, details, ctx


class RealReportedCases(unittest.TestCase):
    def test_all_reported_normalizations(self):
        n = C["normalize_name"]
        for raw in ("BE TIPIK HD", "BE TIPIK FHD", "BE: Tipik 4K",
                    "BE RTBF TIPIK", "BE TIPIK"):
            self.assertEqual(n(raw), "tipik", raw)
        for raw in ("FR TREK FHD", "FR TREK HD", "VIP: TREK HD"):
            self.assertEqual(n(raw), "trek", raw)

    def test_trek_is_french_sat_brand_not_generic_13e_italian(self):
        result, score, detail, ctx = classify("TREK", "FR TREK FHD")
        self.assertEqual(ctx["market"], "FR")
        self.assertEqual(ctx["confidence"], "HIGH")
        self.assertEqual(result, "SAFE")
        self.assertFalse(detail["reject_reason"])
        self.assertFalse(detail["review_reason"])

    def test_fr_trek_variants_are_allowed(self):
        for name in ("FR TREK FHD", "FR TREK HD", "VIP: TREK HD", "FR: TREK HEVC"):
            with self.subTest(name=name):
                decision, score, details, ctx = classify("TREK", name)
                self.assertEqual(decision, "SAFE", (name, score, details))

    def test_belgian_tipik_is_not_mislabeled_french_by_provider_group(self):
        for name in ("BE TIPIK HD", "BE TIPIK FHD", "BE: Tipik 4K", "BE RTBF TIPIK"):
            with self.subTest(name=name):
                decision, score, details, ctx = classify("Tipik", name)
                self.assertEqual(ctx["market"], "BE")
                self.assertEqual(decision, "SAFE", (name, score, details))

    def test_other_country_trek_is_not_assumed_equivalent(self):
        decision, score, details, ctx = classify("TREK", "BE: TREK HD")
        self.assertEqual(decision, "REJECT")
        self.assertIn("market", details["reject_reason"])

    def test_distinct_services_not_admitted(self):
        for sat, iptv in (
            ("TREK", "STAR TREK RAW"),
            ("TREK", "GLOBAL TREKKER HD"),
            ("Tipik", "BE TIPIK VISION HD"),
            ("Tipik", "BE-VIP: TIPIK (13) RAW"),
        ):
            with self.subTest(sat=sat, iptv=iptv):
                decision, score, details, ctx = classify(sat, iptv)
                self.assertEqual(decision, "REJECT", (sat, iptv, score, details))

    def test_generic_be_brand_word_not_a_country_prefix(self):
        self.assertEqual(C["market_from_text"]("BE HAPPY TV"), "")
        self.assertEqual(C["market_from_text"]("BE MOVIES"), "")
        self.assertEqual(C["normalize_name"]("BE MOVIES"), "be cinema")

    def test_old_v11_rows_re_enrich_during_new_catalog_construction(self):
        old = {
            "name": "BE TIPIK FHD", "norm": "be tipik",
            "market": "FR", "market_source": "group", "_e": 11,
            "claimed_quality_rank": 500, "url": "fake://old",
            "quality_rank": 500, "group": "FRANCE",
        }
        catalog = C["Catalog"]([old])
        self.assertEqual(catalog.channels[0]["norm"], "tipik")
        self.assertEqual(catalog.channels[0]["market"], "BE")
        self.assertEqual(set(catalog._exact), {"tipik"})

    def test_original_100_native_scoring_scenarios_unchanged(self):
        count = 0
        for sat, ch, ctx, language, intended, label in _cases:
            with self.subTest(label=label, sat=sat, name=ch["name"]):
                score, details = C["match_score_details"](
                    sat, ch, [language], ctx, "best"
                )
                decision = C["match_decision"](score, details, 82.0)
                self.assertIn(decision, ("SAFE", "ALLOWED") if intended else ("REJECT",))
                count += 1
        self.assertEqual(count, 100)

    def test_patch_rejects_second_application(self):
        # Exact anchoring is a release safety guard, not an idempotent rewrite.
        # The first application already happened at import time.
        src = inspect_core_source()
        with self.assertRaises(AssertionError):
            improve(improve(src))


def inspect_core_source():
    raw = base64.b64decode((ROOT / "payload/r69-beta.b64").read_bytes())
    with tempfile.TemporaryDirectory() as td:
        ipk = Path(td) / "published-r69.ipk"
        ipk.write_bytes(raw)
        archive = subprocess.check_output(["ar", "p", str(ipk), "data.tar.gz"])
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        return tar.extractfile(
            "./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/core.py"
        ).read().decode()


if __name__ == "__main__":
    unittest.main()
