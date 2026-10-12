"""Real R74 compiled package + pure ranking regression tests for R74.11 hotfix.

Tests preview auto selection stays on the page, candidate priority, unchanged
monitor/relay and reversible install. No receiver or IPTV credentials required.
"""
import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "preview_r7411",ROOT/"scripts/r7411_preview_persist_priority_hotfix.py")
patcher=importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)


class PreviewPersistentPriorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        buildspec=importlib.util.spec_from_file_location(
            "build_r74_11_test",ROOT/"scripts/build-r74-unified.py")
        cls.builder=importlib.util.module_from_spec(buildspec)
        buildspec.loader.exec_module(cls.builder)
        cls.tmp=tempfile.TemporaryDirectory()
        output=Path(cls.tmp.name)/"r74.ipk"
        cls.builder.build(output)
        pack=cls.builder.b.b.base.pack
        members=pack.members_from(pack.unpack_ar(output.read_bytes())["data.tar.gz"])
        cls.original=members[cls.builder.PLUGIN].decode()
        cls.changed,cls.status=patcher.patch_plugin(cls.original)
        cls.monitor_original=members[cls.builder.MONITOR]
        cls.tree=ast.parse(cls.changed)
        cls.funcs={n.name:n for n in cls.tree.body if isinstance(n,ast.FunctionDef)}
        cls.preview=next(n for n in cls.tree.body if isinstance(n,ast.ClassDef)
                         and n.name=="SatIPTVBridgePreview")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.monitor=SimpleNamespace(
            current_sat_ref_string="sat",sat_audio_languages=["fra"],stream_health={})
        self.ns={
            "cfg":SimpleNamespace(match_threshold=SimpleNamespace(value=82)),
            "MONITOR":self.monitor,
            "channel_fingerprint":lambda ch:ch["id"],
            "match_decision":lambda score,det,threshold:(
                "REJECT" if det.get("reject_reason") else
                "REVIEW" if det.get("review_reason") else "SAFE"),
            "quality_fit_key":lambda *a:(1,1,0,0,0)
        }
        funcs=[self.funcs[name] for name in (
            "_r7411_resolution_rank","_r74_normalize_lang",
            "_r74_sat_original_languages","_r736_choose_best_safe")]
        exec(compile(ast.fix_missing_locations(ast.Module(body=funcs,type_ignores=[])),
                     "test-r7411-isolated","exec"),self.ns)

    def ch(self,id,provider=0,lang="FR",quality="HD",score=140,w=0,h=0):
        return (dict(id=id,name="Same channel "+quality,language=lang,
                     quality=quality,actual_width=w,actual_height=h,
                     server_priority=1),
                float(score),{"name":100,"provider_identity":provider})

    def choose(self,items):
        return self.ns["_r736_choose_best_safe"]("sat","Same channel HD",
            {"audio_language_set":["FR"]},items)

    def test_actual_r74_bundle_is_patched_without_drift(self):
        self.assertEqual(self.status,"ready")
        self.assertIn(patcher.TAG,self.changed)
        self.assertEqual(patcher.patch_plugin(self.changed)[1],"already-installed")
        self.assertEqual(self.original.count("_r738_queue_auto_open(self, raw,"),2)
        self.assertEqual(self.changed.count("_r738_queue_auto_open(self, raw,"),0)
        self.assertIn("PREVIEW_STAY_OPEN",self.changed)
        self.assertIn("def _r737_show_video_fullscreen",self.changed)
        self.assertIn("def _r738_queue_auto_open",self.changed)

    def test_provider_precedes_language_for_valid_candidates(self):
        # A provider match with unknown language wins over a nonmatching provider
        # with a known FR-language track; unknown is permitted, not invented.
        same=self.ch("same",provider=1,lang="",quality="HD",score=105)
        foreign=self.ch("foreign",provider=0,lang="FR",quality="4K",score=159)
        self.assertEqual(self.choose([foreign,same])[0]["id"],"same")

    def test_language_precedes_resolution_within_provider(self):
        french=self.ch("fr",provider=1,lang="FR",quality="HD",score=100)
        unknown=self.ch("unknown",provider=1,lang="",quality="4K",score=158)
        self.assertEqual(self.choose([unknown,french])[0]["id"],"fr")

    def test_higher_resolution_precedes_score_within_same_provider_language(self):
        full=self.ch("fhd",provider=1,lang="FR",quality="FHD",score=110)
        hd=self.ch("hd",provider=1,lang="FR",quality="HD",score=158)
        self.assertEqual(self.choose([hd,full])[0]["id"],"fhd")

    def test_measured_resolution_overrides_mislabelled_quality(self):
        fake4k=self.ch("fake",provider=1,lang="FR",quality="4K",w=1280,h=720)
        actualfhd=self.ch("real",provider=1,lang="FR",quality="FHD",w=1920,h=1080)
        self.assertEqual(self.choose([fake4k,actualfhd])[0]["id"],"real")

    def test_safety_always_beats_provider_and_resolution(self):
        wrong=self.ch("bad",provider=1,lang="FR",quality="4K",score=199)
        wrong=(wrong[0],wrong[1],dict(wrong[2],reject_reason="wrong channel"))
        safe=self.ch("safe",provider=0,lang="FR",quality="HD",score=100)
        self.assertEqual(self.choose([wrong,safe])[0]["id"],"safe")

    def test_dvb_confirmed_language_mismatch_not_auto_locked(self):
        bad=self.ch("bad",provider=1,lang="EN",quality="4K",score=155)
        good=self.ch("good",provider=0,lang="FR",quality="HD",score=106)
        self.assertEqual(self.choose([bad,good])[0]["id"],"good")

    def test_preview_list_uses_same_priorities(self):
        method=next(n for n in self.preview.body if isinstance(n,ast.FunctionDef)
                    and n.name=="_sort_candidates_with_cached_evidence")
        env=dict(self.ns)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),
                     "test-preview-list","exec"),env)
        monitor=self.monitor
        class Fake:
            sat_name="Same channel HD"
            sat_ref_string="sat"
            def _candidate_decision(self,ch):return "SAFE"
            def _health_record(self,ch):return {}
        rows=[]
        for ch,score,det in (
            self.ch("foreign",provider=0,lang="FR",quality="4K",score=151),
            self.ch("local",provider=1,lang="FR",quality="HD",score=111)):
            ch["_preview_score"]=score
            ch["_preview_details"]=det
            rows.append(ch)
        sorted_rows=env["_sort_candidates_with_cached_evidence"](
            Fake(),rows,context={"audio_language_set":["FR"]})
        self.assertEqual([r["id"] for r in sorted_rows],["local","foreign"])

    def test_safe_mapper_and_manual_protection_preserved(self):
        self.assertIn('return "MANUAL_PROTECTED",None',self.changed)
        self.assertIn("_r736_auto_map_single_sat(",self.changed)
        self.assertIn("AUTO_PLAY_START",self.changed)
        # Existing live auto play code remains available outside Preview.

    def test_preview_no_automatic_screen_close_from_selection(self):
        # The R73.8 helper retains a close(), but R74.11 never queues it from
        # a Preview cache hit or background matching completion.
        self.assertNotIn(patcher.ORIGINAL_AUTO_CACHE,self.changed)
        self.assertNotIn(patcher.ORIGINAL_AUTO_FRESH,self.changed)
        self.assertIn('source=CACHE auto=%s',self.changed)
        self.assertIn('source=RANKED auto=%s',self.changed)

    def test_local_check_apply_rollback(self):
        with tempfile.TemporaryDirectory() as folder:
            dest=Path(folder)/"plugin.py"
            dest.write_text(self.original)
            self.assertEqual(patcher.main(["--check","--target",str(dest)]),0)
            self.assertEqual(dest.read_text(),self.original)
            self.assertEqual(patcher.main(["--apply","--target",str(dest)]),0)
            self.assertEqual(dest.read_text(),self.changed)
            self.assertEqual(patcher.main(["--rollback","--target",str(dest)]),0)
            self.assertEqual(dest.read_text(),self.original)


if __name__=="__main__":
    unittest.main()
