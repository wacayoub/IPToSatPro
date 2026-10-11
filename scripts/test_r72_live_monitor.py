#!/usr/bin/env python3
"""R72 beta regression suite for exact zipped Enigma2 source and screen."""
import ast, base64, hashlib, importlib.util, io, tempfile, unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image

sp=importlib.util.spec_from_file_location("r72",Path(__file__).with_name("build-r72-live-monitor.py"))
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)

class DummyLabel:
    def __init__(self):self.text=None
    def setText(self,t):self.text=str(t)
class DummyUi:
    def __init__(self):
        self.labels={}
        self._r711_lock_active=False
    def __getitem__(self,key):
        return self.labels.setdefault(key,DummyLabel())

class R72Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.temp.name)/"candidate.ipk"
        cls.metadata=b.build(cls.path)
        cls.data=b.pack.members_from(b.pack.unpack_ar(cls.path.read_bytes())["data.tar.gz"])
        cls.original=b.pack.members_from(b.pack.unpack_ar(base64.b64decode(b.B64.read_bytes()))["data.tar.gz"])
        cls.code=cls.data[b.PLUGIN].decode()
        tree=ast.parse(cls.code)
        dash=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=="SatIPTVBridgeDashboard")
        cls.methods={x.name:x for x in dash.body if isinstance(x,ast.FunctionDef)}

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_layout_stays_inside_1660_by_900_and_has_real_resolution_badges(self):
        root=ET.fromstring(b.skin())
        self.assertEqual(root.get("size"),"1660,900")
        components=[c for c in root if c.tag=="widget"]
        keys=[c.get("name") for c in components]
        self.assertEqual(len(keys),len(set(keys)))
        for required in ("r72_sat_name","r72_iptv_name","r72_sat_provider",
                         "r72_iptv_provider","r72_sat_signal","home_snr_bar",
                         "r72_mapping_status","r72_play_status","r72_res_val",
                         "r72_speed_val","r72_audio_lang_val","r72_audio_codec_val",
                         "r72_video_codec_val","r72_source_val","home_preview_action"):
            self.assertIn(required,keys)
        self.assertGreaterEqual(len(components),25)
        for item in components:
            x,y=map(int,item.get("position").split(","))
            w,h=map(int,item.get("size").split(","))
            self.assertLessEqual(x+w,1660)
            self.assertLessEqual(y+h,900)

    def test_background_generated_once(self):
        img=self.data[b.IMAGE]
        self.assertTrue(img.startswith(b"\x89PNG\r\n\x1a\n"))
        with Image.open(io.BytesIO(img)) as frame:
            self.assertEqual(frame.size,(1660,900))
        self.assertLess(len(img),160000)

    def test_no_runtime_changes_outside_dashboard_and_updater(self):
        self.assertEqual(set(self.data),set(self.original)|{b.IMAGE,b.CHANGELOG})
        for name,blob in self.original.items():
            if name not in (b.PLUGIN,b.UPDATER):
                with self.subTest(name=name):self.assertEqual(self.data[name],blob)
        prevtree=ast.parse(self.original[b.PLUGIN])
        prevclass=next(x for x in prevtree.body if isinstance(x,ast.ClassDef) and x.name=="SatIPTVBridgeDashboard")
        prevmethods={x.name:ast.dump(x,include_attributes=False) for x in prevclass.body if isinstance(x,ast.FunctionDef)}
        nowmethods={x.name:ast.dump(x,include_attributes=False) for x in self.methods.values()}
        self.assertEqual(set(prevmethods),set(nowmethods))
        changed={x for x in nowmethods if nowmethods[x]!=prevmethods[x]}
        self.assertEqual(changed,{"__init__","_refresh_monitor"})
        self.assertFalse(self.metadata["playback_changed"])
        self.assertFalse(self.metadata["receiver_verified"])

    def test_playing_status_and_quality_scenario_real_vs_claimed(self):
        # Execute the exact *compiled released* R72 display update block with
        # stub Label UI, not a rewritten heuristic. No Enigma2 APIs invoked.
        src=self.code
        start=src.index("        # R72: presentation only.")
        end=src.index('self["r72_source_val"].setText(',start)
        tail=src[end:]
        closing=tail.index('\n    def ',0)
        tail=src[start:end]+tail[:closing]
        params="self,snap,active,active_name,sat_name,sat,orbital,provider,snr_numeric,iw,ih,role,mode,timing,language"
        function="def evaluate("+params+"):\n"+tail
        scope={"presentation_name":lambda s:str(s),"self":None}
        exec(compile(function,"R72_TARGET_SNAPSHOT_BLOCK","exec"),scope)
        evaluate=scope["evaluate"]
        def run(**changes):
            case=dict(
                self=DummyUi(),
                snap={"first_image_locked":False,"quality_verified":False,
                      "sat_width":0,"sat_height":0,"sat_audio_languages":["FR"],
                      "server_label":"Primary France","quality":"4K",
                      "score":82.0},
                active=True,active_name="CANAL+ GOLF 4K",sat_name="CANAL+ GOLF HD",
                sat="Hotbird 13 E",orbital="13 E",provider="ABSAT",
                snr_numeric=78,iw=1920,ih=1080,role="PRIMARY",mode="DVB",
                timing=1460,language="FR")
            case.update(changes)
            evaluate(**case)
            return case["self"].labels
        rv=run()
        self.assertEqual(rv["r72_play_status"].text,"CANDIDATE")
        self.assertEqual(rv["r72_res_val"].text,"Claimed 4K")
        self.assertEqual(rv["r72_speed_val"].text,"Not measured")
        self.assertEqual(rv["r72_sat_signal"].text,"78%")
        self.assertEqual(rv["r72_audio_lang_val"].text,"FR (catalog)")
        playing=run(snap={"first_image_locked":True,"quality_verified":True,
                          "sat_width":1280,"sat_height":720,
                          "sat_audio_languages":["FR"],"server_label":"Primary",
                          "quality":"4K","score":92.5})
        self.assertEqual(playing["r72_play_status"].text,"PLAYING")
        self.assertIn("FHD",playing["r72_res_val"].text)
        self.assertIn("1920",playing["r72_res_val"].text)
        self.assertEqual(playing["r72_speed_val"].text,"1.46 s")
        self.assertEqual(playing["r72_audio_codec_val"].text,"Not available")
        self.assertEqual(playing["r72_video_codec_val"].text,"Not available")

    def test_reproducible_archive_and_prod_untouched(self):
        import json
        other=Path(self.temp.name)/"same.ipk"
        meta=b.build(other)
        self.assertEqual(self.path.read_bytes(),other.read_bytes())
        self.assertEqual(meta["sha256"],hashlib.sha256(other.read_bytes()).hexdigest())
        self.assertEqual(json.loads((b.ROOT/"update.json").read_text())["version"],"1.0.46-r70-final")
        self.assertFalse(meta["main_published"])

if __name__=="__main__":unittest.main()
