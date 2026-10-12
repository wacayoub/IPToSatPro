#!/usr/bin/env python3
"""R73.3 true compiled IPK tests, three sources, full one-shot and REVIEW safety."""
import ast,base64,importlib.util,tempfile,time,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r733_build",ROOT/"scripts/build-r73-preview.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)

class TurboTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.p=Path(cls.tmp.name)/"r733.ipk"
        cls.meta=b.build(cls.p)
        cls.members=b.base.pack.members_from(b.base.pack.unpack_ar(cls.p.read_bytes())["data.tar.gz"])
        cls.prev=b.base.pack.members_from(b.base.pack.unpack_ar(base64.b64decode(b.B64.read_bytes()))["data.tar.gz"])
        cls.psrc=cls.members[b.PLUGIN].decode()
        cls.csrc=cls.members[b.CORE].decode()
        loc=Path(cls.tmp.name)/"core.py"
        loc.write_text(cls.csrc,encoding="utf-8")
        sp=importlib.util.spec_from_file_location("core733",loc)
        cls.c=importlib.util.module_from_spec(sp);sp.loader.exec_module(cls.c)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def make_catalogue(self):
        rows=[]
        for role in ("PRIMARY","BACKUP1","BACKUP2"):
            for n in range(80):
                rows.append({"name":"beIN Sports 6 FHD FR",
                    "url":"http://192.0.2.1/%s/%d"%(role,n),"server_role":role,
                    "server_label":role,"server_priority":n%4,
                    "language":"FR","market":"FR","group":"beIN SPORTS","quality":"FHD"})
            rows.append({"name":"beIN Sports 8 FHD FR",
                "url":"http://192.0.2.1/wrong/"+role,"server_role":role,
                "market":"FR","language":"FR"})
            rows.append({"name":"Dubai Sports 6 FHD FR",
                "url":"http://192.0.2.1/brand/"+role,"server_role":role,
                "market":"FR","language":"FR"})
        return self.c.Catalog(rows)

    def test_192_prepared_once_and_review_overflow(self):
        cat=self.make_catalogue()
        ctx={"confidence":"HIGH","market":"FR","market_preferences":["FR"],
             "language_priorities":["FR"],"match_threshold":60.0}
        begin=time.perf_counter()
        rows=cat.fast_preview_mega_matches("beIN Sports 6 FHD FR",["FR"],
            context=ctx,per_server=64,topn=192)
        ms=(time.perf_counter()-begin)*1000
        self.assertEqual(len(rows),192)
        self.assertEqual({ch["server_role"] for ch,s,d in rows},
                         {"PRIMARY","BACKUP1","BACKUP2"})
        self.assertTrue(all("beIN Sports 6" in ch["name"] for ch,s,d in rows))
        full=[(ch,sc,det) for ch,sc,det in rows if not ch.get("_r732_index_only")]
        manual=[(ch,sc,det) for ch,sc,det in rows if ch.get("_r732_index_only")]
        self.assertEqual(len(full),18)
        self.assertEqual(len(manual),174)
        self.assertTrue(all(ch.get("_manual_candidate") is True for ch,sc,det in manual))
        self.assertTrue(all(sc==0.0 and "review_reason" in det for ch,sc,det in manual))
        self.assertTrue(all("manual" not in det for ch,sc,det in manual))
        stats=cat._r733_last_profile
        self.assertEqual(stats["scored"],18)
        self.assertEqual(stats["candidate_count"],192)
        self.assertGreater(stats["total_ms"],0)
        print("R733_192_ONE_SHOT",round(ms,2),"ms",stats)
        again=cat.fast_preview_mega_matches("beIN Sports 6 FHD FR",["FR"],
            context=ctx,per_server=64,topn=192)
        self.assertEqual(len(again),192)
        self.assertEqual(cat._r733_last_profile["cache"],1)

    def test_one_name_from_one_server_still_scores(self):
        cat=self.c.Catalog([{"name":"Ushuaia TV FHD FR","server_role":"PRIMARY",
                            "url":"http://192.0.2.1/1","language":"FR","market":"FR",
                            "group":"FRANCE"}])
        result=cat.fast_preview_mega_matches("Ushuaia TV FHD FR",["FR"],
               context={"confidence":"HIGH","market":"FR"},per_server=64,topn=192)
        self.assertEqual(len(result),1)
        self.assertFalse(result[0][0].get("_manual_candidate"))
        self.assertEqual(cat._r733_last_profile["scored"],1)

    def test_live_player_monitor_and_stores_untouched(self):
        for name,blob in self.prev.items():
            if name not in (b.PLUGIN,b.CORE,b.UPDATER):
                self.assertEqual(blob,self.members[name],name)
        self.assertEqual(self.meta["candidate_search"],"one_shot_192_turbo_18scored_plus_manual")
        self.assertFalse(self.meta["production_published"])
        self.assertFalse(self.meta["receiver_tested"])
        self.assertTrue(self.meta["player_unchanged"])

    def test_one_pass_without_progressive_loading(self):
        self.assertIn("catalog.fast_preview_mega_matches(",self.psrc)
        self.assertIn("candidate_budget = 192",self.psrc)
        self.assertIn("self._r732_auto_rows[:48]",self.psrc)
        self.assertIn("self._r732_page_auto(step)",self.psrc)
        self.assertIn("_r733_perf",self.psrc)
        self.assertIn("index=%dms scoring=%dms scored=%d cache=%d",self.psrc)
        self.assertIn("self._r731_show_fta = False",self.psrc)

    def test_score_override_does_not_make_unverified_candidates_safe(self):
        cat=self.make_catalogue()
        rows=cat.fast_preview_mega_matches("beIN Sports 6 FHD FR",["FR"],
             context={"confidence":"HIGH","market":"FR","match_threshold":60.0},
             per_server=64,topn=192)
        rejected=[(ch,d) for ch,sc,d in rows if ch.get("_manual_candidate")]
        self.assertTrue(rejected)
        self.assertTrue(all(d.get("review_reason") for ch,d in rejected))
        self.assertFalse(any(d.get("allow_reason") for ch,d in rejected))

if __name__=="__main__":
    unittest.main()
