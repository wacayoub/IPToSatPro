#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76 finalization acceptance on the ACTUAL rebuilt R76 Enigma2 IPK.

Software-only tests cannot prove Vu+ Zero 4K hardware/video decoder behavior.
"""
import ast
import hashlib
import importlib.util
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

builder=load("r76builder","build-r76-metrix-preview.py")
layout=builder.layout


def literal(tree,name):
    node=next(x for x in tree.body if isinstance(x,ast.Assign)
              and any(isinstance(t,ast.Name) and t.id==name for t in x.targets))
    return ast.literal_eval(node.value)


class R76Acceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        folder=Path(cls.temp.name)
        cls.dest=folder/"r76.ipk"
        cls.meta=builder.build(cls.dest)
        cls.before=folder/"r75.ipk"
        builder.base.build(cls.before)
        cls.old=builder.pack.members_from(builder.pack.unpack_ar(
            cls.before.read_bytes())["data.tar.gz"])
        cls.new=builder.pack.members_from(builder.pack.unpack_ar(
            cls.dest.read_bytes())["data.tar.gz"])
        cls.plugin=cls.new[builder.PLUGIN].decode()
        cls.old_plugin=cls.old[builder.PLUGIN].decode()
        cls.theme=cls.new[builder.THEME].decode()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_actual_ipk_reproducible_and_staged(self):
        self.assertEqual(self.meta["version"],builder.VERSION)
        self.assertFalse(self.meta["receiver_tested"])
        self.assertFalse(self.meta["production_published"])
        self.assertEqual(hashlib.sha256(self.dest.read_bytes()).hexdigest(),self.meta["sha256"])
        with tempfile.TemporaryDirectory() as tmp:
            second=Path(tmp)/"repeat.ipk"
            builder.build(second)
            self.assertEqual(self.dest.read_bytes(),second.read_bytes())

    def test_all_package_files_protected(self):
        changed={p for p in self.old if self.old[p]!=self.new[p]}
        self.assertEqual(changed,{builder.PLUGIN,builder.UPDATER,builder.THEME,builder.base.CORE})
        self.assertEqual(set(self.new)-set(self.old),{builder.NOTE,builder.HOME_THEMES})
        self.assertEqual(self.new[builder.base.MONITOR],self.old[builder.base.MONITOR])
        self.assertNotEqual(self.new[builder.base.CORE],self.old[builder.base.CORE])
        for suffix in ("player.py","metadata_shadow.py"):
            path=builder.P+suffix
            if path in self.old:self.assertEqual(self.old[path],self.new[path])
        for p,blob in self.new.items():
            if p.endswith(".py"):compile(blob,p,"exec")

    def test_metrix_is_default_theme_and_bounded_hd_fhd(self):
        tree=ast.parse(self.plugin)
        fhd=literal(tree,"R76_METRIX_FHD")
        hd=literal(tree,"R76_METRIX_HD")
        layout.validate_skin(fhd,set(layout.HOME_WIDGETS))
        layout.validate_skin(hd,set(layout.HOME_WIDGETS),hd=True)
        self.assertIn('THEME_HD if _r76_is_hd else THEME_FHD',self.plugin)
        self.assertIn('from enigma import getDesktop',self.plugin)
        self.assertIn('from .home_themes_r767 import THEME_CHOICES',self.plugin)
        self.assertIn('r76_home_layout',self.plugin)
        self.assertIn('_r76_layout == "classic"',self.plugin)

    def test_home_max_real_information(self):
        home=ET.fromstring(literal(ast.parse(self.plugin),"R76_METRIX_FHD"))
        names={x.attrib["name"] for x in home if x.tag=="widget"}
        for n in ("r72_sat_signal","home_snr_bar","r72_iptv_name",
                  "r72_iptv_provider","r72_mapping_status","r72_play_status",
                  "r72_res_val","r72_speed_val","r72_audio_lang_val",
                  "r72_audio_codec_val","r72_video_codec_val","r72_source_val",
                  "home_selected_info","home_iptv_detail","home_status",
                  "r76_system_label","r76_mapping_label","r76_epg_label","r76_catalog_label"):
            self.assertIn(n,names)
        self.assertIn('self["r72_video_codec_val"].setText("Not available")',self.plugin)
        self.assertIn('snap.get("sat_snr")',self.plugin)
        self.assertIn('snap.get("first_image_locked")',self.plugin)
        self.assertIn('with open("/proc/stat","r")',self.plugin)
        self.assertIn('with open("/proc/meminfo","r")',self.plugin)
        self.assertIn('_r76_event.getEventName()',self.plugin)
        self.assertIn('and not _r76_map.get("user_unmapped")',self.plugin)
        self.assertIn('_r76_now - self._r76_extras_last >= 12.0',self.plugin)

    def test_neodark_preview_b_hd_fhd_and_legacy_keys(self):
        tree=ast.parse(self.theme)
        hi=literal(tree,"PREVIEW_R74_FHD")
        low=literal(tree,"PREVIEW_R76_HD")
        layout.validate_skin(hi,set(layout.PREVIEW_WIDGETS))
        layout.validate_skin(low,set(layout.PREVIEW_WIDGETS),hd=True)
        for xml in (hi,low):
            root=ET.fromstring(xml)
            names={x.attrib["name"] for x in root if x.tag=="widget"}
            self.assertEqual(names,layout.PREVIEW_CLASSIC_NAMES)
            self.assertNotIn("r76_video",names)
            self.assertEqual(root.attrib["backgroundColor"],"#090F18")
        self.assertNotIn("VideoWindow(decoder=",self.plugin)
        self.assertNotIn('self["r76_video"]',self.plugin)
        self.assertIn('NEO DARK CLASSIC',self.plugin)

    def test_preview_video_not_autoplay_on_navigation(self):
        before=ast.parse(self.old_plugin)
        after=ast.parse(self.plugin)
        def defs(tree):
            return {n.name:n for n in tree.body if isinstance(n,ast.ClassDef)}
        original=defs(before); updated=defs(after)
        self.assertEqual(set(original),set(updated))
        # No method body may change aside from dashboard/preview constructors and
        # Preview already-OK-only presentation callback (zero media policy changes).
        changes={}
        for name in original:
            x={n.name:ast.dump(n,include_attributes=False) for n in original[name].body
               if isinstance(n,ast.FunctionDef)}
            y={n.name:ast.dump(n,include_attributes=False) for n in updated[name].body
               if isinstance(n,ast.FunctionDef)}
            self.assertEqual(set(y)-set(x), {"_r767_open_group"} if name=="SatIPTVBridgeDashboard" else set())
            self.assertEqual(set(x)-set(y),set())
            diff={fn for fn in x if x[fn]!=y[fn]}
            if diff:changes[name]=diff
        self.assertEqual(changes.get("SatIPTVBridgeDashboard"),{"__init__","_refresh_monitor","open_settings","_r711_tools_choice","_r723_select_home_layout","_r723_set_home_layout"})
        self.assertEqual(changes.get("SatIPTVBridgePreview"),{"__init__","_render_source_list","_load_selected_sat_candidates"})
        self.assertEqual(set(changes),{"SatIPTVBridgeDashboard","SatIPTVBridgePreview"})
        self.assertIn("R7413_PREVIEW_INLINE_NO_HIDE",self.plugin)

    def test_r763_candidates_index_starts_without_scoring(self):
        self.assertIn("R763_FAST_INDEX_BEST_MEDAL", self.plugin)
        self.assertIn("def _r763_preview_instant_index", self.plugin)
        self.assertIn("first = _r763_preview_instant_index(self.sat_name, cat, limit=24)", self.plugin)
        self.assertIn("self.candidate_expand_timer.start(20, True)", self.plugin)
        self.assertIn("catalog.fast_preview_mega_matches(", self.plugin)
        # The early rows remain marked as provisional REVIEW, and never auto map.
        self.assertIn('row["_manual_candidate"]=True', self.plugin)
        self.assertIn('row["_r763_fast_index"]=True', self.plugin)
        self.assertIn('"INSTANT INDEX ONLY - unverified; background ranking pending"', self.plugin)
        self.assertNotIn("_r763_instant_auto_lock", self.plugin)

    def test_r763_medal_is_evidence_gated_and_quality_compact(self):
        self.assertIn('medal="🎖 " if best_measured else ""', self.plugin)
        self.assertIn('speed_count>=1 and overall_fp and cfp==overall_fp', self.plugin)
        self.assertIn('compact_quality="M:%dx%d"', self.plugin)
        self.assertIn('compact_quality="C:%s"', self.plugin)
        self.assertIn('score_label="IDX"', self.plugin)
        self.assertIn('decision_short={"USER REJECT":"REJ"', self.plugin)
        self.assertIn('BEST ', self.plugin)
        self.assertNotIn('REAL MESURE', self.plugin[self.plugin.index('def _render_source_list(self, keep_index=True):'):self.plugin.index('def _format_epg_event',self.plugin.index('def _render_source_list(self, keep_index=True):'))])

    def test_preview_candidate_displays_original_iptv_prefix(self):
        # Execute the name expression from the ACTUAL rebuilt package's
        # Preview method, not a separate reimplementation of the formatter.
        tree=ast.parse(self.plugin)
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef)
                 and n.name=="SatIPTVBridgePreview")
        render=next(n for n in cls.body if isinstance(n,ast.FunctionDef)
                    and n.name=="_render_source_list")
        assignments=[
            node for node in ast.walk(render)
            if isinstance(node,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=="name" for t in node.targets)
            and 'ch.get(' in ast.unparse(node.value)
        ]
        self.assertEqual(len(assignments),1)
        expression=assignments[0].value
        self.assertNotIn("presentation_name",ast.unparse(expression))
        for expected in ("FR: DISNEY CHANNEL HD","DE: DISNEY CHANNEL",
                         "UK: BBC ONE HD","VIP: CANAL+","4K: ELEVEN SPORTS",
                         "ES: LA 1 HD","PT: DISNEY CHANNEL"):
            result=eval(compile(ast.Expression(expression),"<iptv label>","eval"),
                        {},{"ch":{"name":expected}})
            self.assertEqual(result,expected)
        # Blank and multiline inputs should be safe for an Enigma2 list.
        result=eval(compile(ast.Expression(expression),"<iptv label>","eval"),
                    {},{"ch":{"name":"FR: DISNEY\nCHANNEL HD"}})
        self.assertEqual(result,"FR: DISNEY CHANNEL HD")

    def test_r763_index_synthetic_latency_and_no_wrong_identity(self):
        # Execute exact patched helper against a stub indexed catalogue, not IPTV streams.
        import sys,types,time
        code=ast.parse(self.plugin)
        fn=next(n for n in code.body if isinstance(n,ast.FunctionDef)
                and n.name=="_r763_preview_instant_index")
        module=ast.Module(body=[fn],type_ignores=[])
        base="r763_testpack"
        pkg=types.ModuleType(base);pkg.__path__=[]
        core=types.ModuleType(base+".core")
        core.normalize_name=lambda s: str(s).lower().strip()
        sys.modules[base]=pkg
        sys.modules[base+".core"]=core
        try:
            ns={"__package__":base,"_r7414_fast_exact_seed":lambda name,cat:[]}
            exec(compile(module,"candidate_helper.py","exec"),ns)
            groups={"other channel %04d"%i:[] for i in range(6500)}
            groups["osn movies family"]=[
                {"name":"OSN Movies Family","url":"http://host/tv/1",
                 "server_role":"PRIMARY"}]
            groups["osn movies comedy"]=[
                {"name":"OSN Movies Comedy","url":"http://host/tv/2",
                 "server_role":"PRIMARY"}]
            cat=type("CatalogStub",(),{"_exact":groups})()
            before=time.perf_counter()
            got=ns["_r763_preview_instant_index"]("OSNtv Movies Family",cat,24)
            elapsed=time.perf_counter()-before
            self.assertLess(elapsed,0.5)
            self.assertEqual([c["name"] for c in got],["OSN Movies Family"])
            self.assertTrue(got[0]["_manual_candidate"])
            self.assertTrue(got[0]["_r763_fast_index"])
            self.assertEqual(got[0]["_preview_score"],0.0)
        finally:
            sys.modules.pop(base+".core",None)
            sys.modules.pop(base,None)

    def test_openatv_has_no_inline_video_window_or_callback(self):
        """Never introduce an onLayoutFinish lambda or second video window."""
        self.assertNotIn('self.onLayoutFinish.append(lambda',self.plugin)
        self.assertNotIn('self.onLayoutFinish.append(self["r76_video"]',self.plugin)
        self.assertNotIn('self["r76_video"]',self.plugin)

    def test_preview_list_fills_both_panels_safely(self):
        hi=ET.fromstring(literal(ast.parse(self.theme),"PREVIEW_R74_FHD"))
        wd={x.attrib["name"]:x for x in hi if x.tag=="widget"}
        def rect(n):
            x,y=map(int,wd[n].attrib["position"].split(","))
            w,h=map(int,wd[n].attrib["size"].split(","))
            return x,y,x+w,y+h
        def separate(a,b):
            x,y,r,d=rect(a);u,v,s,t=rect(b)
            return r<=u or s<=x or d<=v or t<=y
        self.assertTrue(separate("sat_list","source_list"))
        self.assertTrue(separate("source_list","key_green"))
        self.assertTrue(separate("verify","key_red"))
        self.assertEqual(rect("sat_list")[1],rect("source_list")[1])
        self.assertEqual(rect("sat_list")[3],rect("source_list")[3])
        self.assertGreater(rect("source_list")[3]-rect("source_list")[1],420)

    def test_metrix_home_real_tv_spacing_and_brand(self):
        hi=ET.fromstring(literal(ast.parse(self.plugin),"R76_METRIX_FHD"))
        w={el.get("name"):el for el in hi if el.tag=="widget"}
        def rect(name):
            x,y=map(int,w[name].get("position").split(","))
            dx,dy=map(int,w[name].get("size").split(","))
            return (x,y,x+dx,y+dy)
        sat=rect("r72_sat_name")
        iptv=rect("r72_iptv_name")
        tiles=[rect(x) for x in ("r72_res_val","r72_speed_val","r72_audio_lang_val")]
        self.assertLess(sat[3],iptv[1])
        self.assertLess(iptv[3],tiles[0][1])
        self.assertGreaterEqual(sat[0],420)
        self.assertGreaterEqual(rect("key_red")[1],800)
        self.assertIn('self["version"] = Label("R76.7.1  •  "+_r76_layout.replace("_"," ").upper())',self.plugin)
        self.assertIn("SAT / IPTV  •  LIVE STATUS  •  HOME THEMES",self.plugin)
        self.assertNotIn('self["subtitle"] = Label("R72  •  SATELLITE',self.plugin)

    def test_remote_actions_and_mapping_logic_unchanged(self):
        # Compare all AST class methods; this also protects color action maps,
        # mapping choice code, UI timers, software decoder routing and candidate
        # actions against accidental R76 changes.
        self.assertIn('"green": self.open_preview_sources',self.plugin)
        self.assertIn('"yellow": self.open_updater',self.plugin)
        self.assertIn('"blue": self.open_logs',self.plugin)
        self.assertIn('"menu": self.open_settings',self.plugin)
        self.assertIn('"ok": self.open_preview_sources',self.plugin)
        self.assertIn('if isinstance(old, dict) and old.get("user_unmapped")',self.plugin)
        self.assertNotIn("clear_overrides(",builder.layout.patch_plugin.__code__.co_consts.__repr__())
        self.assertEqual(self.old[builder.base.MONITOR],self.new[builder.base.MONITOR])

    def test_updater_never_auto_downgrades_to_r75(self):
        updater=self.new[builder.UPDATER].decode()
        self.assertIn('CURRENT_VERSION = "'+builder.VERSION+'"',updater)
        self.assertIn('staging/r76-metrix-preview.update.json',updater)
        self.assertNotIn(builder.base.p75.UPDATER_URL,updater)

    def test_skin_does_not_depend_on_external_picture_resources(self):
        for raw in (literal(ast.parse(self.plugin),"R76_METRIX_FHD"),
                    literal(ast.parse(self.theme),"PREVIEW_R74_FHD")):
            root=ET.fromstring(raw)
            self.assertEqual(len([x for x in root if x.tag=="ePixmap"]),0)
            self.assertGreaterEqual(len([x for x in root if x.tag=="widget"]),20)

if __name__=="__main__":
    unittest.main()
