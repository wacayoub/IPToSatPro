#!/usr/bin/env python3
"""R74.8 tests on the exact staged IPK matcher, not mocked normalization."""
import importlib.util,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r748b",ROOT/"scripts/build-r74-unified.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class CountryCodeMatcher(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        out=Path(cls.tmp.name)/"r748.ipk"
        cls.meta=b.build(out)
        fs=b.b.b.base.pack.members_from(b.b.b.base.pack.unpack_ar(out.read_bytes())["data.tar.gz"])
        src=Path(cls.tmp.name)/"real_r748_core.py";src.write_bytes(fs[b.CORE])
        spec=importlib.util.spec_from_file_location("real_r748_core",src)
        cls.c=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.c)
        cls.src=fs[b.CORE].decode()
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def sample(self,name,role="PRIMARY"):
        return {"name":name,"group":"CHANNELS","market":self.c.market_from_text(name),
                "market_source":"name","server_role":role,"server_priority":1,
                "url":"http://127.0.0.1/offline-test.ts"}
    def score(self,sat,iptv,role="PRIMARY",preview=True):
        ctx=self.c.infer_sat_context(sat,"",192,user_languages=[],
                                     audio_languages=[],epg_text="")
        return self.c.match_score_details(sat,self.sample(iptv,role),[],
                                           ctx,preview=preview)
    def test_tlc_austria_and_iptv_at_is_safe_name_identity(self):
        sat,iptv="TLC HD Austria","AT: TLC HD"
        self.assertEqual(self.c._r748_country_relation(sat,iptv)[0],"MATCH")
        self.assertEqual(self.c.market_from_text(sat),"AT")
        self.assertEqual(self.c.market_from_text(iptv),"AT")
        score,details=self.score(sat,iptv)
        self.assertEqual(details.get("country_alias_match"),"AT")
        self.assertFalse(details.get("reject_reason"),(score,details))
        self.assertEqual(self.c.match_decision(score,details,82.0),"SAFE",
                         (score,details))
    def test_tlc_germany_to_de_prefix(self):
        score,details=self.score("TLC HD Germany","DE TLC HD","BACKUP1")
        self.assertEqual(details.get("country_alias_match"),"DE")
        self.assertFalse(details.get("reject_reason"),(score,details))
    def test_multiple_country_aliases(self):
        scenarios=[
            ("TLC HD Austria","AT: TLC HD","AT"),
            ("TLC HD Österreich","AT: TLC HD","AT"),
            ("TLC HD Germany","DE TLC HD","DE"),
            ("TLC HD France","FR: TLC HD","FR"),
            ("TLC HD Spain","ES TLC HD","ES"),
            ("TLC HD United Kingdom","UK: TLC HD","UK"),
            ("TLC HD Albania","AL: TLC HD","AL"),
            ("TRACE URBAN Africa","AF: TRACE URBAN","AF"),
            ("TLC HD Italy","IT: TLC HD","IT"),
            ("TLC HD Portugal","PT TLC HD","PT"),
            ("TLC HD Netherlands","NL: TLC HD","NL"),
            ("TLC HD Poland","PL: TLC HD","PL"),
            ("TLC HD Switzerland","CH TLC HD","CH"),
            ("TLC HD Belgium","BE TLC HD","BE"),
            ("TLC HD Greece","GR TLC HD","GR"),
            ("TLC HD Turkey","TR TLC HD","TR"),
            ("TLC HD Romania","RO TLC HD","RO"),
            ("TLC HD Croatia","HR TLC HD","HR"),
            ("TLC HD Czechia","CZ TLC HD","CZ"),
            ("TLC HD Sweden","SE TLC HD","SE"),
            ("TLC HD Norway","NO TLC HD","NO"),
            ("TLC HD Algeria","DZ TLC HD","DZ"),
            ("TLC HD Morocco","MA TLC HD","MA"),
            ("TLC HD Tunisia","TN TLC HD","TN"),
            ("TLC HD Australia","AU TLC HD","AU"),
            ("TLC HD New Zealand","NZ TLC HD","NZ"),
        ]
        for sat,iptv,code in scenarios:
            with self.subTest(sat=sat,iptv=iptv):
                self.assertEqual(self.c._r748_country_relation(sat,iptv),
                                 ("MATCH",code,code))
                score,details=self.score(sat,iptv)
                self.assertEqual(details.get("country_alias_match"),code,(score,details))
                self.assertFalse(details.get("reject_reason"),(score,details))
    def test_wrong_market_label_visible_review_but_never_automatic(self):
        pairs=[
            ("TLC HD Austria","DE: TLC HD"),
            ("TLC HD Austria","AU: TLC HD"),
            ("TLC HD Germany","AT: TLC HD"),
            ("TRACE URBAN Africa","AL: TRACE URBAN"),
        ]
        for sat,iptv in pairs:
            with self.subTest(sat=sat,iptv=iptv):
                self.assertEqual(self.c._r748_country_relation(sat,iptv)[0],"CONFLICT")
                score,details=self.score(sat,iptv)
                self.assertEqual(self.c.match_decision(score,details,82),"REVIEW")
                self.assertIn("country",details.get("review_reason","").lower())
                self.assertEqual(details.get("prefix_evidence"),"UNVERIFIED_LABEL")
                self.assertFalse(details.get("reject_reason"),(score,details))
    def test_real_service_numbers_and_variants_unchanged(self):
        positives=[("TLC 1 HD Austria","AT TLC 1 HD"),
                   ("TLC 2 HD Germany","DE TLC 2 HD")]
        negatives=[("TLC 1 HD Austria","AT TLC 2 HD"),
                   ("TLC Junior HD Austria","AT TLC HD")]
        for sat,iptv in positives:
            with self.subTest(sat=sat,iptv=iptv):
                self.assertEqual(self.c._r748_country_relation(sat,iptv)[0],"MATCH")
        for sat,iptv in negatives:
            with self.subTest(sat=sat,iptv=iptv):
                self.assertNotEqual(self.c._r748_country_relation(sat,iptv)[0],"MATCH")
                score,d=self.score(sat,iptv)
                self.assertNotIn(self.c.match_decision(score,d,82.0),("SAFE","ALLOWED"),
                                 (score,d))
    def test_public_brand_france_two_not_stripped(self):
        self.assertEqual(self.c._r748_explicit_country("France 2 HD")[0],"")
        self.assertEqual(self.c._r748_explicit_country("At The Races HD")[0],"")
        self.assertEqual(self.c._r748_explicit_country("BBC Arabic")[0],"")
    def test_abbreviations_not_country_language(self):
        self.assertEqual(self.c._r748_explicit_country("AR BEIN SPORTS 1")[0],"AR")
        self.assertEqual(self.c._r748_explicit_country("AF: TRACE URBAN")[0],"AF")
        self.assertEqual(self.c._r748_explicit_country("AT TLC HD")[0],"AT")
        self.assertEqual(self.c._r748_explicit_country("AU TLC HD")[0],"AU")
        self.assertEqual(self.c._r748_explicit_country("TLC HD Austria")[0],"AT")
        self.assertEqual(self.c._r748_explicit_country("TLC HD Australia")[0],"AU")
    def test_auto_scorer_and_preview_scorer_both_receive_country_identity(self):
        for preview in (True,False):
            score,details=self.score("TLC HD Austria","AT: TLC HD",preview=preview)
            self.assertEqual(details.get("country_alias_match"),"AT",
                             (score,details,preview))
            self.assertFalse(details.get("reject_reason"),(score,details,preview))
    def test_all_server_index_uses_country_identity(self):
        self.assertIn("country_relation,_sat_code,_ip_code=_r748_country_relation(sat_name,name)",self.src)
        self.assertIn('country_relation=="MATCH"',self.src)
        self.assertIn('country_relation in ("MATCH","CONFLICT")',self.src)
        self.assertIn('prefix_fit=(2 if country_relation=="MATCH"',self.src)
        self.assertTrue(self.meta["country_alias_matcher"])
        self.assertFalse(self.meta["receiver_tested"])
if __name__=="__main__":unittest.main()
