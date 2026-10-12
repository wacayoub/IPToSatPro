#!/usr/bin/env python3
"""20 real packaged Preview scorer checks: FR feeds, number safety and aliases.

Uses the complete Python module extracted from the staged IPK, not mocked scorer.
No IPTV networking or Enigma2 player; quality/audio decode needs receiver testing.
"""
import importlib.util
import pathlib
import tempfile
import unittest
import sys

HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("r73",HERE/"build-r73-preview.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class R73MatchScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        path=pathlib.Path(cls.tmp.name)/"r73.ipk"
        b.build(path)
        members=b.base.pack.members_from(b.base.pack.unpack_ar(path.read_bytes())["data.tar.gz"])
        src=pathlib.Path(cls.tmp.name)/"core.py"
        src.write_bytes(members[b.CORE])
        module_spec=importlib.util.spec_from_file_location("r73_real_core",src)
        cls.core=importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(cls.core)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_twenty_identity_and_feed_regressions(self):
        positive=[
           ("Ushuaia TV HD","FR: Ushuaia TV FHD"),
           ("CANAL+ Golf HD","FR: CANAL+ Golf FHD"),
           ("beIN Sports 6 HD","FR: beIN Sports 6 FHD"),
           ("OSN Cinema 1 HD","OSN Cinema 1 FHD"),
           ("Nat Geo HD","Nat Geo FHD"),
           ("Arryadia HD 1","Arryadia HD 1 FHD"),
           ("Alkass 2 HD","Alkass 2 FHD"),
           ("Digi 24","Digi 24 HD"),
        ]
        negative=[
           ("beIN Sports 6 HD","FR: beIN Sports 8 HD"),
           ("CANAL+ Sport 1 HD","FR: CANAL+ Sport 2 FHD"),
           ("TOD Event Sports 3","TOD Event Sports 7"),
           ("OSN Cinema 1","OSN Cinema 2"),
           ("Alkass 1 HD","Alkass 4 HD"),
           ("beIN Movies 2","beIN Movies 3"),
           ("Dubai Sports 1","Dubai Sports 2"),
           ("Arryadia HD 1","Arryadia HD 3"),
           ("MBC 1","MBC 2"),
           ("Eleven Sports 1","Eleven Sports 2"),
           ("Starzplay Sports 1","Starzplay Sports 2"),
           ("AD Sports 1","AD Sports 2"),
        ]
        self.assertEqual(len(positive)+len(negative),20)
        # Language / market policy deliberately disabled here: check pure identity
        # so a country bouquet cannot conceal a number-safety regression.
        context={"confidence":"LOW","language_priorities":[],"market_preferences":[]}
        for sat,iptv in positive:
            ch={"name":iptv,"group":"GENERAL","server_role":"PRIMARY",
                "server_priority":1,"url":"http://127.0.0.1/not-fetched"}
            with self.subTest(sat=sat,iptv=iptv,expected="plausible"):
                score,details=self.core.match_score_details(sat,ch,[],context,preview=True)
                self.assertFalse(str(details.get("reject_reason") or "").startswith("channel number identity mismatch"),
                                 (sat,iptv,score,details))
        for sat,iptv in negative:
            ch={"name":iptv,"group":"GENERAL","server_role":"BACKUP1",
                "server_priority":2,"url":"http://127.0.0.1/not-fetched"}
            with self.subTest(sat=sat,iptv=iptv,expected="number_reject"):
                score,details=self.core.match_score_details(sat,ch,[],context,preview=True)
                self.assertEqual(self.core.match_decision(score,details,60.0),"REJECT",
                                 (sat,iptv,score,details))
                self.assertIn("number",str(details.get("reject_reason") or ""),
                              (sat,iptv,score,details))

if __name__=="__main__":
    unittest.main()
