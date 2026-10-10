"""Known gap repros: these intentionally document existing wrong dispositions.

Tests are expected failures, NOT fixes or passing playback validation.
They use real pinned core.py, and demonstrate why synthetic 100/100 did not
cover TREK on Hotbird nor Belgian BE: prefixed Tipik.
"""
import base64
import io
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
raw=base64.b64decode((ROOT/"payload/r69-beta.b64").read_bytes())
with tempfile.TemporaryDirectory() as td:
    ipk=Path(td)/"base.ipk";ipk.write_bytes(raw)
    gzip_data=subprocess.check_output(["ar","p",str(ipk),"data.tar.gz"])
with tarfile.open(fileobj=io.BytesIO(gzip_data),mode="r:gz") as tar:
    core_bytes=tar.extractfile("./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/core.py").read()
scope={"__name__":"audit_core"}
exec(compile(core_bytes,"pinned_core.py","exec"),scope)


class KnownMappingGaps(unittest.TestCase):
    @unittest.expectedFailure
    def test_trek_hotbird_fr_exact_should_not_need_preview(self):
        c=scope["infer_sat_context"]("TREK","Unknown",orbital_position=130,
                                      user_languages=["AR","FR","EN"])
        ch={"name":"FR TREK FHD","group":"FRANCE","url":"fake://trek"}
        score,details=scope["match_score_details"]("TREK",ch,["AR","FR","EN"],c)
        self.assertGreaterEqual(score,82)
        # This currently produces REVIEW even with exact normalized identity.
        self.assertEqual(scope["match_decision"](score,details,82),"SAFE")

    @unittest.expectedFailure
    def test_tipik_belgian_prefix_same_identity_should_be_reviewable(self):
        c=scope["infer_sat_context"]("Tipik","Unknown",orbital_position=130,
                                      user_languages=["AR","FR","EN"])
        ch={"name":"BE: Tipik 4K","group":"BELGIUM","url":"fake://tipik"}
        score,details=scope["match_score_details"]("Tipik",ch,["AR","FR","EN"],c)
        # Native core incorrectly sees "BE" as part of identity; hard rejects.
        self.assertIn(scope["match_decision"](score,details,82),("REVIEW","SAFE"))

    def test_why_trek_is_review(self):
        c=scope["infer_sat_context"]("TREK","Unknown",orbital_position=130,
                                      user_languages=["AR","FR","EN"])
        score,details=scope["match_score_details"]("TREK",{
            "name":"FR TREK FHD","group":"FRANCE","url":"fake://trek"},
            ["AR","FR","EN"],c)
        self.assertEqual(score,87.0)
        self.assertIn("ambiguous SAT market hint IT",details["review_reason"])
        self.assertEqual(scope["match_decision"](score,details,82),"REVIEW")

    def test_why_tipik_is_rejected(self):
        c=scope["infer_sat_context"]("Tipik","Unknown",orbital_position=130,
                                      user_languages=["AR","FR","EN"])
        score,details=scope["match_score_details"]("Tipik",{
            "name":"BE: Tipik 4K","group":"BELGIUM","url":"fake://tipik"},
            ["AR","FR","EN"],c)
        self.assertEqual(score,1.0)
        self.assertIn("identity confidence below safe floor",details["reject_reason"])

if __name__=="__main__":
    unittest.main()
