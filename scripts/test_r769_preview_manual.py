#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.9 QA on real IPK: 48/16 Preview parity, safe context, protected files."""
import ast,importlib.util,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("r769builder",ROOT/"scripts/build-r76-metrix-preview.py")
b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
class PreviewManualParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work=tempfile.TemporaryDirectory()
        new=Path(cls.work.name)/"new.ipk";old=Path(cls.work.name)/"r75.ipk"
        cls.meta=b.build(new)
        b.base.build(old)
        cls.files=b.pack.members_from(b.pack.unpack_ar(new.read_bytes())["data.tar.gz"])
        cls.old=b.pack.members_from(b.pack.unpack_ar(old.read_bytes())["data.tar.gz"])
        cls.code=cls.files[b.PLUGIN].decode()
        cls.tree=ast.parse(cls.code)
    @classmethod
    def tearDownClass(cls):cls.work.cleanup()
    def method(self,name):
        cls=next(x for x in self.tree.body if isinstance(x,ast.ClassDef) and x.name=="SatIPTVBridgePreview")
        return next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name==name)
    def test_worker_normal_uses_same_ranker_and_limits_as_manual(self):
        code=ast.get_source_segment(self.code,self.method("_expand_selected_sat_candidates"))
        self.assertIn("candidate_budget = 192 if self._r71_worker_deep else 48",code)
        self.assertIn("candidate_per_server = 64 if self._r71_worker_deep else 16",code)
        self.assertIn("catalog.fast_rank_matches_all_servers(",code)
        self.assertIn("catalog.fast_preview_mega_matches(",code)
        self.assertIn("if self._r71_worker_deep:",code)
        self.assertIn("sat_name, ctx = _r769_preview_sat_context(raw, self.session)",code)
        self.assertIn('threading.Thread(target=worker, name="IPToSatPreviewRank")',code)
    def test_original_manual_and_automap_are_untouched(self):
        self.assertIn("R769_PREVIEW_MANUAL_PARITY",self.code)
        self.assertEqual(self.files[b.base.MONITOR],self.old[b.base.MONITOR])
        self.assertEqual(self.files[b.base.CORE],b.r768.patch_core(b.r766.patch_core(b.r765.patch_core(self.old[b.base.CORE].decode()))).encode())
        self.assertEqual(set(x for x in self.old if self.old[x]!=self.files[x]),
                         {b.PLUGIN,b.UPDATER,b.THEME,b.base.CORE})
        self.assertEqual(set(self.files)-set(self.old),{b.NOTE,b.HOME_THEMES})
        self.assertEqual(self.files.get(b.P+"player.py"),self.old.get(b.P+"player.py"))
        # Original Manual Mapping class unchanged by R76.9.
        old_tree=ast.parse(self.old[b.PLUGIN].decode())
        def cls(t):
            n=next(c for c in t.body if isinstance(c,ast.ClassDef) and c.name=="SatIPTVBridgeAlternatives")
            return ast.dump(n,include_attributes=False)
        self.assertEqual(cls(old_tree),cls(self.tree))
    def test_same_sat_context_reused_but_never_cross_sat(self):
        helper=next(x for x in self.tree.body if isinstance(x,ast.FunctionDef)
                    and x.name=="_r769_preview_sat_context")
        func=compile(ast.Module(body=[helper],type_ignores=[]),"helper.py","exec")
        state={"calls":0,"live_ref":"SAT_A"}
        def static(raw):
            return "Discovery HD",raw,{"provider":"Unknown","market":"AR","confidence":"HIGH"}
        def live(sess):
            state["calls"]+=1
            return "AR OSN DISCOVERY CHANNEL HD",state["live_ref"],{"provider":"OSN","market":"AR",
                   "market_preferences":["AR"],"language_priorities":["AR"]}
        env={"_match_context_for_sat_ref":static,"_match_context_for_current":live,
             "sat_service_key":lambda s:s,
             "clean_display_name":lambda s:s.strip()}
        exec(func,env)
        f=env["_r769_preview_sat_context"]
        name,ctx=f("SAT_A",object())
        self.assertEqual(name,"AR OSN DISCOVERY CHANNEL HD")
        self.assertEqual(ctx["provider"],"OSN")
        self.assertEqual(ctx["market_preferences"],["AR"])
        state["live_ref"]="SAT_B"
        name,ctx=f("SAT_A",object())
        self.assertEqual(name,"Discovery HD")
        self.assertEqual(ctx["provider"],"Unknown")
        self.assertNotIn("market_preferences",ctx)
        self.assertEqual(state["calls"],2)
    def test_preview_right_list_is_manual_mapping_style(self):
        render=ast.get_source_segment(self.code,self.method("_render_source_list"))
        order=ast.get_source_segment(self.code,self.method("_sort_candidates_with_cached_evidence"))
        # Ranked results use the same tier and identity/quality tie-breakers as
        # Manual Mapping; receiver data is labelled REAL only when measured.
        for token in ('"MANUAL":5', '"SAFE":4', '"ALLOWED":3', '"REVIEW":2',
                      "quality_fit_key(", '"provider_identity"', "identity_band"):
            self.assertIn(token,order)
        self.assertIn('rows.sort(key=key,reverse=True)',order)
        for token in ('score_label="%.1f"%score',"market[:3]","language[:3]",
                      '"REAL %dx%d"','"DECLARED "',"self._source_tag(",
                      'name = " ".join(str(ch.get("name")'):
            self.assertIn(token,render)
        self.assertNotIn("presentation_name(",render)
        # Existing PreviewList widgets, callbacks and video preview stay intact.
        self.assertIn('self["source_list"].setList(rows)',render)
        self.assertIn('self["source_list"].moveToIndex(idx)',render)

    def test_no_live_context_scan_with_known_static_provider(self):
        helper=next(x for x in self.tree.body if isinstance(x,ast.FunctionDef)
                    and x.name=="_r769_preview_sat_context")
        env={"_match_context_for_sat_ref":lambda s:("Sky One",s,{"provider":"Sky"}),
             "_match_context_for_current":lambda s:1/0,
             "sat_service_key":lambda s:s,"clean_display_name":lambda s:s}
        exec(compile(ast.Module(body=[helper],type_ignores=[]),"helper.py","exec"),env)
        name,c=env["_r769_preview_sat_context"]("SAT_1",None)
        self.assertEqual((name,c["provider"]),("Sky One","Sky"))
    def test_preview_initial_and_deep_routes_stay_intact(self):
        load=ast.get_source_segment(self.code,self.method("_load_selected_sat_candidates"))
        worker=ast.get_source_segment(self.code,self.method("_expand_selected_sat_candidates"))
        self.assertIn("_r763_preview_instant_index(self.sat_name, cat, limit=24)",load)
        self.assertIn("candidate_budget = 192 if self._r71_worker_deep else 48",worker)
        self.assertFalse(self.meta["receiver_tested"])
        self.assertFalse(self.meta["production_published"])
if __name__=="__main__":unittest.main()
