#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Acceptance on REAL R76.8 packaged scorer; no Enigma decoder simulated."""
import ast,importlib.util,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r768_build",ROOT/"scripts"/"build-r76-metrix-preview.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)

class RegionalPriority(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work=tempfile.TemporaryDirectory()
        p=Path(cls.work.name)/"r768.ipk"
        cls.meta=b.build(p)
        parts=b.pack.members_from(b.pack.unpack_ar(p.read_bytes())["data.tar.gz"])
        cls.source=parts[b.base.CORE].decode()
        src=Path(cls.work.name)/"actual_core.py";src.write_text(cls.source)
        spec=importlib.util.spec_from_file_location("r768_actual",src)
        cls.c=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.c)
        cls.parts=parts
    @classmethod
    def tearDownClass(cls):
        cls.work.cleanup()

    def score(self,iptv,ctx,sat="Discovery HD",role="BACKUP2"):
        ch={"name":iptv,"group":"CHANNELS","server_role":role,
            "server_priority":1,"market":self.c.market_from_text(iptv),
            "market_source":"name","url":"http://127.0.0.1/no-stream.ts"}
        return self.c.match_score_details(sat,ch,[],ctx,preview=True)

    def mena(self,reason="sat:AR"):
        return {"market_preferences":["AR"],"confidence":"HIGH",
                "reason":reason,"language_priorities":["AR"],
                "global_fallback":False}

    def test_discovery_fr_uk_de_are_visible_but_not_safe(self):
        ctx=self.mena()
        names=("FR: DISCOVERY HEVC","UK: DISCOVERY","DE: DISCOVERY HD",
               "DE: DISCOVERY HEVC HD","FR: DISCOVERY CHANNEL HD",
               "ES: DISCOVERY HD","IT: DISCOVERY HD","PT: DISCOVERY HD")
        for name in names:
            with self.subTest(name=name):
                original=self.c._r768_original_match_score_details(
                    "Discovery HD",
                    {"name":name,"market":self.c.market_from_text(name),
                     "market_source":"name","group":"CHANNELS",
                     "server_role":"BACKUP2","server_priority":1,
                     "url":"http://127.0.0.1/no-stream.ts"},
                    [],ctx,preview=True)
                new,details=self.score(name,ctx)
                if original[1].get("reject_reason"):
                    self.assertEqual(new,original[0])
                else:
                    self.assertLess(new,original[0])
                    self.assertEqual(details.get("regional_priority"),"SECONDARY")
                    self.assertEqual(self.c.match_decision(new,details,82.0),"REVIEW")

    def test_ar_osn_kept_first_and_no_overrides_or_player_changes(self):
        ctx=self.mena("provider:AR, sat:AR")
        arabic,da=self.score("AR OSN DISCOVERY CHANNEL HD",ctx)
        foreign,df=self.score("FR: DISCOVERY CHANNEL HD",ctx)
        self.assertGreater(arabic,foreign)
        self.assertNotIn(self.c.match_decision(arabic,da,82.0),("REJECT","REVIEW"))
        self.assertEqual(self.c.match_decision(foreign,df,82.0),"REVIEW")
        self.assertEqual(df.get("regional_evidence"),"CHANNEL_OR_PROVIDER")
        self.assertEqual(self.parts[b.base.MONITOR],
                         self._baseline()[b.base.MONITOR])
        self.assertEqual(self.parts.get(b.P+"player.py"),self._baseline().get(b.P+"player.py"))

    def _baseline(self):
        if not hasattr(self,"_old"):
            dest=Path(self.work.name)/"r75.ipk"
            b.base.build(dest)
            self._old=b.pack.members_from(b.pack.unpack_ar(dest.read_bytes())["data.tar.gz"])
        return self._old

    def test_orbital_hint_is_not_real_audio_proof(self):
        ctx=self.mena()
        a,details=self.score("FR: DISCOVERY CHANNEL HD",ctx)
        self.assertEqual(details.get("regional_evidence"),"SATELLITE_HINT")
        self.assertEqual(details.get("region_score_adjustment"),-22.0)
        ctx["audio_language_set"]=["FR"]
        bscore,bd=self.score("FR: DISCOVERY CHANNEL HD",ctx)
        self.assertGreater(bscore,a)
        self.assertEqual(bd.get("region_score_adjustment"),-6.0)

    def test_no_global_or_low_confidence_penalty(self):
        for ctx in ({"confidence":"LOW","market_preferences":["AR"]},
                    {"confidence":"HIGH","market_preferences":["AR"],
                     "global_fallback":True,"reason":"sat:AR"}):
            s,d=self.score("FR: DISCOVERY CHANNEL HD",ctx)
            old,_=self.c._r768_original_match_score_details(
                "Discovery HD",{"name":"FR: DISCOVERY CHANNEL HD",
                "market":"FR","market_source":"name","group":"CHANNELS",
                "server_role":"BACKUP2","server_priority":1,
                "url":"http://127.0.0.1/no-stream.ts"},[],ctx,preview=True)
            self.assertEqual(s,old)
            self.assertNotIn("region_score_adjustment",d)

    def test_european_sat_and_country_safety_preserved(self):
        context={"confidence":"HIGH","market_preferences":["DE","AR"],
                 "reason":"name:DE, sat:AR"}
        for name in ("DE: DISCOVERY HD","DE: DISCOVERY HEVC HD"):
            s,d=self.score(name,context,sat="Discovery HD")
            self.assertNotIn("region_score_adjustment",d)
        sat="TLC HD Austria"
        ctx={"confidence":"HIGH","market_preferences":["AT"],
             "reason":"name:AT"}
        s,d=self.score("AT: TLC HD",ctx,sat=sat)
        self.assertFalse(d.get("reject_reason"),(s,d))
        self.assertNotIn("region_score_adjustment",d)

    def test_wrong_identity_and_number_still_reject(self):
        ctx=self.mena()
        for iptv in ("FR: DISNEY CHANNEL HD","DE: DISCOVERY 2",
                     "FR: DISCOVERY JUNIOR","UK: BBC ONE HD"):
            score,d=self.score(iptv,ctx)
            self.assertEqual(self.c.match_decision(score,d,82),"REJECT",
                             (iptv,score,d))

    def test_prefix_vip_not_country(self):
        ctx=self.mena()
        s,d=self.score("VIP: DISCOVERY CHANNEL",ctx)
        self.assertNotIn("region_score_adjustment",d)

    def test_fast_nomination_has_contextual_region_before_exact(self):
        self.assertIn("R768_CONTEXT_REGION_PRIORITY",self.source)
        start=self.source.index("regional_priority=1")
        end=self.source.index("return (exact, regional_priority,",start)
        self.assertLess(start,end)
        self.assertIn('market_source=="name"',self.source)
        self.assertIn("R766_COLD_RANK_FAST",self.source)

if __name__=="__main__":unittest.main()
