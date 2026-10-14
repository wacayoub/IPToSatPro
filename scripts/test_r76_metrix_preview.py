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
        self.assertEqual(changed,{builder.PLUGIN,builder.UPDATER,builder.THEME})
        self.assertEqual(set(self.new)-set(self.old),{builder.NOTE})
        self.assertEqual(self.new[builder.base.MONITOR],self.old[builder.base.MONITOR])
        self.assertEqual(self.new[builder.base.CORE],self.old[builder.base.CORE])
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
        self.assertIn('self.skin = _theme_skin(R76_METRIX_HD if _r76_is_hd else R76_METRIX_FHD)',self.plugin)
        self.assertIn('from enigma import getDesktop',self.plugin)
        self.assertIn('("Metrix OpenATV R76 (default)", "metrix")',self.plugin)
        self.assertIn('r76_home_layout',self.plugin)
        self.assertIn('("classic","monitor","metrix")',self.plugin)

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
            self.assertEqual(set(x),set(y))
            diff={fn for fn in x if x[fn]!=y[fn]}
            if diff:changes[name]=diff
        self.assertEqual(changes.get("SatIPTVBridgeDashboard"),{"__init__","_refresh_monitor","_r723_select_home_layout","_r723_set_home_layout"})
        self.assertEqual(changes.get("SatIPTVBridgePreview"),{"__init__"})
        self.assertEqual(set(changes),{"SatIPTVBridgeDashboard","SatIPTVBridgePreview"})
        self.assertIn("R7413_PREVIEW_INLINE_NO_HIDE",self.plugin)

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
        self.assertIn("R76.2  •  METRIX PROFESSIONAL",self.plugin)
        self.assertIn("METRIX OPENATV  •  SAT / IPTV  •  LIVE STATUS",self.plugin)
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
            self.assertGreater(len([x for x in root if x.tag=="widget"]),20)

if __name__=="__main__":
    unittest.main()
