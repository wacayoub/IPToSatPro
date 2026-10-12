#!/usr/bin/env python3
"""R73.2 real IPK and 3-source synthetic anti-regression tests."""
import ast,base64,importlib.util, tempfile,time,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("build732",ROOT/"scripts/build-r73-preview.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)

class InstantCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.ipk=Path(cls.tmp.name)/"r732.ipk"
        cls.info=b.build(cls.ipk)
        cls.members=b.base.pack.members_from(b.base.pack.unpack_ar(cls.ipk.read_bytes())["data.tar.gz"])
        cls.old=b.base.pack.members_from(b.base.pack.unpack_ar(base64.b64decode(b.B64.read_bytes()))["data.tar.gz"])
        cls.psrc=cls.members[b.PLUGIN].decode()
        cls.csrc=cls.members[b.CORE].decode()
        sp=importlib.util.spec_from_file_location("core732",Path(cls.tmp.name)/"core.py")
        Path(cls.tmp.name,"core.py").write_text(cls.csrc)
        cls.core=importlib.util.module_from_spec(sp);sp.loader.exec_module(cls.core)
        cls.tree=ast.parse(cls.psrc)
        cls.cls=next(n for n in cls.tree.body if isinstance(n,ast.ClassDef) and n.name=="SatIPTVBridgePreview")
    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_one_shot_no_progressive_short_pass(self):
        self.assertIn("self.candidate_expand_timer.start(20, True)",self.psrc)
        self.assertNotIn("self.sat_change_timer.start(110, True)",self.psrc)
        self.assertIn("catalog.fast_preview_mega_matches(",self.psrc)
        self.assertIn("candidate_budget = 192",self.psrc)
        self.assertNotIn("catalog.fast_rank_matches_all_servers(\n                    sat_name, priorities",self.psrc)
        self.assertIn("self._r732_auto_rows[:48]",self.psrc)
        self.assertIn("self._r732_page_auto(step)",self.psrc)
        self.assertIn("MEGA SEARCH • calculating candidates once",self.psrc)

    def test_192_ready_preserves_three_sources_and_numbers(self):
        channels=[]
        for role in ("PRIMARY","BACKUP1","BACKUP2"):
            for i in range(64):
                channels.append(dict(name="beIN Sports 6 FHD FR",language="FR",market="FR",
                    server_role=role,server_label=role,server_priority=i%6,
                    url="http://192.0.2.1/%s/%d"%(role,i),group="beIN SPORTS",quality="FHD"))
            for i in range(4):
                channels.append(dict(name="beIN Sports 8 FHD FR",language="FR",market="FR",
                    server_role=role,server_label=role,server_priority=0,
                    url="http://192.0.2.1/%s/wrong/%d"%(role,i)))
        catalog=self.core.Catalog(channels)
        ctx={"confidence":"HIGH","market":"FR","market_preferences":["FR"],
             "language_priorities":["FR"],"match_threshold":60.0}
        t=time.perf_counter()
        rows=catalog.fast_preview_mega_matches("beIN Sports 6 FHD FR",["FR"],
                                context=ctx,per_server=64,topn=192)
        elapsed=1000*(time.perf_counter()-t)
        print("R732_BEIN_ONE_SHOT_MS",round(elapsed,2),"candidates",len(rows))
        self.assertEqual(len(rows),192)
        self.assertEqual({r[0]["server_role"] for r in rows},{"PRIMARY","BACKUP1","BACKUP2"})
        self.assertNotEqual(tuple(self.core._preview_numbers("beIN Sports 6 FHD FR")), tuple(self.core._preview_numbers("beIN Sports 8 FHD FR")))
        self.assertTrue(all(tuple(self.core._preview_numbers(r[0]["name"])) == tuple(self.core._preview_numbers("beIN Sports 6 FHD FR")) for r in rows))
        self.assertTrue(any(r[0].get("_r732_index_only") for r in rows))
        self.assertTrue(any(not r[0].get("_r732_index_only") for r in rows))
        t=time.perf_counter()
        again=catalog.fast_preview_mega_matches("beIN Sports 6 FHD FR",["FR"],
                                context=ctx,per_server=64,topn=192)
        print("R732_CACHE_HIT_MS",round((time.perf_counter()-t)*1000,2))
        self.assertEqual(len(again),192)

    def test_one_list_page_48_without_second_search(self):
        method=next(n for n in self.cls.body if isinstance(n,ast.FunctionDef) and n.name=="_r732_page_auto")
        mod=ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[]))
        ns={};exec(compile(mod,"fake_r732","exec"),ns)
        class Label:
            def __init__(self):self.value=None
            def setText(self,x):self.value=x
        class Fake:
            def __init__(self):
                self._r732_auto_rows=[{"name":"TEST %d"%i} for i in range(192)]
                self._r732_auto_page=0
                self.labels={"status":Label()}
            def __getitem__(self,x):return self.labels[x]
            def _render_source_list(self,keep_index=True):self.rendered=True
            def _set_focus(self,which):self.focus=which
        f=Fake()
        ns["_r732_page_auto"](f,1)
        self.assertEqual(f._r732_auto_page,1)
        self.assertEqual(len(f.channels),48)
        self.assertEqual(f.channels[0]["name"],"TEST 48")
        self.assertIn("192 total",f.labels["status"].value)
        ns["_r732_page_auto"](f,1)
        self.assertEqual(f.channels[0]["name"],"TEST 96")
        ns["_r732_page_auto"](f,1)
        self.assertEqual(f.channels[-1]["name"],"TEST 191")
        ns["_r732_page_auto"](f,1)
        self.assertEqual(f._r732_auto_page,3)

    def test_live_player_and_user_files_not_modified(self):
        for name,raw in self.old.items():
            if name not in (b.CORE,b.PLUGIN,b.UPDATER):
                self.assertEqual(self.members[name],raw,name)
        self.assertFalse(self.info["production_published"])
        self.assertFalse(self.info["receiver_tested"])
        self.assertTrue(self.info["player_unchanged"])
        self.assertEqual(self.info["candidate_search"],"one_shot_192_indexed_plus_full_catalogue_manual")

    def test_manual_full_catalogue_and_fta_survive(self):
        self.assertIn("catalog.manual_search(query, topn=limit, context=ctx)",self.psrc)
        self.assertIn('self._r731_show_fta = False',self.psrc)
        self.assertIn('self._r731_search_timer.callback.append(self._r731_poll_search)',self.psrc)

if __name__=="__main__":
    unittest.main()
