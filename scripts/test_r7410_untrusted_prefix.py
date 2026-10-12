#!/usr/bin/env python3
"""R74.10: wrong IPTV country prefix is untrusted display metadata, not a ban.

Read the real IPK core built by the release workflow. No fake matcher functions.
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r7410_build",ROOT/"scripts/build-r74-unified.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class PrefixUntrusted(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        ipk=Path(cls.tmp.name)/"r7410.ipk"
        cls.meta=b.build(ipk)
        files=b.b.b.base.pack.members_from(b.b.b.base.pack.unpack_ar(ipk.read_bytes())["data.tar.gz"])
        source=Path(cls.tmp.name)/"real_core.py";source.write_bytes(files[b.CORE])
        sp=importlib.util.spec_from_file_location("real_r7410_core",source)
        cls.c=importlib.util.module_from_spec(sp);sp.loader.exec_module(cls.c)
        cls.source=files[b.CORE].decode()
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def score(self,sat,name,market=None,context=None,preview=True,role="BACKUP2"):
        ch={"name":name,"group":"TV CHANNELS","server_role":role,
            "server_priority":3,"market":market or self.c.market_from_text(name),
            "market_source":"name","url":"http://localhost/not-a-real-stream.ts"}
        c=context or {"confidence":"HIGH",
                       "market_preferences":[self.c.market_from_text(sat)],
                       "language_priorities":[]}
        return self.c.match_score_details(sat,ch,[],c,preview=preview)

    def test_tlc_austria_mislabeled_de_stays_visible(self):
        for preview in (True,False):
            score,d=self.score("TLC HD Austria","DE: TLC HD",preview=preview)
            self.assertEqual(d.get("prefix_evidence"),"UNVERIFIED_LABEL",(score,d))
            self.assertEqual(d.get("name"),100.0,(score,d))
            self.assertEqual(self.c.match_decision(score,d,82),"REVIEW",(score,d))
            self.assertIn("country prefix DE",d["review_reason"])
            self.assertFalse(d["reject_reason"],(score,d))

    def test_tlc_correct_at_label_remains_safe_and_higher_than_de(self):
        for preview in (True,False):
            good,dgood=self.score("TLC HD Austria","AT: TLC HD",preview=preview)
            bad,dbad=self.score("TLC HD Austria","DE: TLC HD",preview=preview)
            self.assertEqual(self.c.match_decision(good,dgood,82),"SAFE",(good,dgood))
            self.assertEqual(self.c.match_decision(bad,dbad,82),"REVIEW",(bad,dbad))
            self.assertGreater(good,bad,(good,bad))
            self.assertFalse(dgood.get("prefix_evidence"))

    def test_countries_are_low_trust_all_server_roles(self):
        scenarios=[
            ("TLC HD Germany","AT TLC HD"),
            ("TLC HD France","DE TLC HD"),
            ("TLC HD Spain","FR TLC HD"),
            ("TLC HD Austria","AU TLC HD"),
            ("TRACE URBAN Africa","AL TRACE URBAN"),
        ]
        for sat,ip in scenarios:
            for role in ("PRIMARY","BACKUP1","BACKUP2"):
                with self.subTest(sat=sat,ip=ip,role=role):
                    score,d=self.score(sat,ip,role=role)
                    self.assertEqual(d.get("prefix_evidence"),"UNVERIFIED_LABEL",(score,d))
                    self.assertEqual(self.c.match_decision(score,d,82),"REVIEW",(score,d))

    def test_iptv_name_tag_cannot_claim_sat_audio_language(self):
        # A possibly wrongly labelled DE prefix is NOT decoded audio evidence.
        c={"confidence":"HIGH","market_preferences":["AT"],
           "audio_language_set":["FR"],"audio_language_target":"FR",
           "language_priorities":["FR"]}
        score,d=self.score("TLC HD Austria","DE TLC HD",context=c)
        self.assertEqual(self.c.match_decision(score,d,82),"REVIEW",(score,d))
        self.assertFalse(d.get("reject_reason"),(score,d))

    def test_correct_country_keeps_original_sat_audio_policy(self):
        c={"confidence":"HIGH","market_preferences":["AT"],
           "audio_language_set":["FR"],"audio_language_target":"FR",
           "language_priorities":["FR"]}
        score,d=self.score("TLC HD Austria","AT TLC HD",context=c)
        self.assertNotEqual(d.get("prefix_evidence"),"UNVERIFIED_LABEL")
        self.assertNotEqual(self.c.match_decision(score,d,82),"REJECT")

    def test_real_variant_and_number_still_hard_rejected(self):
        bad=[("TLC 1 HD Austria","DE TLC 2 HD"),
             ("TLC HD Austria","DE TLC EXTRA HD"),
             ("TLC HD Austria","DE TLC JUNIOR HD"),
             ("FILMBOX ONE Austria","DE FILMBOX TWO")]
        for sat,ip in bad:
            with self.subTest(sat=sat,ip=ip):
                score,d=self.score(sat,ip)
                self.assertEqual(self.c.match_decision(score,d,82),"REJECT",(score,d))

    def test_wrong_brand_is_not_country_equivalence(self):
        score,d=self.score("TLC HD Austria","DE DISCOVERY HD")
        self.assertNotEqual(d.get("prefix_evidence"),"UNVERIFIED_LABEL")
        self.assertNotEqual(self.c.match_decision(score,d,82),"SAFE")

    def test_unscored_or_wrong_prefix_cannot_auto_lock(self):
        self.assertIn('if country_prefix_warning:',self.source)
        self.assertIn('details["review_reason"]=(',self.source)
        self.assertIn('prefix_fit=(2 if country_relation=="MATCH"',self.source)
        self.assertIn('self._fast_cache_key("mega-r7410"',self.source)
        self.assertTrue(self.meta["untrusted_iptv_prefix"])
        self.assertFalse(self.meta["receiver_tested"])

if __name__=="__main__":
    unittest.main()
