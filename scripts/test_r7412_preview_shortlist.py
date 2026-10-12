"""R7412 regression tests using the genuine built R74 package.

Validate normal candidate cap, YELLOW deep search, R7411 provider/language/
resolution, Preview stay-open, protected mappings and rollback.
"""
import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
def mod(label,path):
    spec=importlib.util.spec_from_file_location(label,ROOT/"scripts"/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

r74=mod("r74builder7412","build-r74-unified.py")
r7411=mod("r7411patch7412","r7411_preview_persist_priority_hotfix.py")
r7412=mod("r7412patch","r7412_preview_fast_shortlist_hotfix.py")


class FastShortlistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        ipk=Path(cls.tmp.name)/"r74.ipk"
        cls.buildmeta=r74.build(ipk)
        container=r74.b.b.base.pack
        package=container.members_from(container.unpack_ar(ipk.read_bytes())["data.tar.gz"])
        cls.baseline=package[r74.PLUGIN].decode()
        cls.r7411,_=r7411.patch_plugin(cls.baseline)
        cls.patched,cls.status=r7412.patch(cls.r7411)
        cls.tree=ast.parse(cls.patched)
        cls.preview=next(n for n in cls.tree.body if isinstance(n,ast.ClassDef)
                         and n.name=="SatIPTVBridgePreview")
        cls.methods={n.name:n for n in cls.preview.body if isinstance(n,ast.FunctionDef)}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_real_r74_package_guarded_patch(self):
        self.assertEqual(self.status,"ready")
        self.assertEqual(r7412.patch(self.patched)[1],"already-installed")
        self.assertIn(r7412.TAG,self.patched)
        self.assertEqual(self.baseline.count(r7412.ORIGINAL),1)
        self.assertIn("R7411_STAY_PREVIEW_PROVIDER_LANGUAGE_RESOLUTION",self.patched)

    def test_normal_budget_24_and_full_manual_budget_192(self):
        method=ast.get_source_segment(self.patched,
                                      self.methods["_expand_selected_sat_candidates"])
        self.assertIn("candidate_budget = 192 if self._r71_worker_deep else 24",method)
        self.assertIn("candidate_per_server = 64 if self._r71_worker_deep else 8",method)
        self.assertIn("per_server=candidate_per_server, topn=candidate_budget",method)

    def test_full_bulk_auto_scan_not_capped(self):
        self.assertIn("per_server=64,topn=192",self.patched)
        self.assertIn("_r736_auto_map_single_sat(",self.patched)
        self.assertIn('return "MANUAL_PROTECTED",None',self.patched)

    def test_yellow_with_short_cache_queues_192(self):
        queued=[]
        ref="1:0:19:NEW:0:0"
        class Timer:
            def start(self,delay,one=True):queued.append(delay)
            def stop(self):pass
        class Fake:
            _closed_for_async=False
            _expand_worker=None
            _r732_auto_rows=[{"name":"First"}]
            _r71_deep_requested=False
            _r71_deep_target_ref=""
            _candidate_cache={ref:True}
            candidate_expand_timer=Timer()
            def _selected_sat_row(self):return {"ref":ref}
            def __getitem__(self,name):
                return SimpleNamespace(setText=lambda message:None)
        env={"sat_service_key":lambda value:value,
             "_preview_candidate_cache_drop":lambda value:None}
        fn=ast.fix_missing_locations(ast.Module(body=[self.methods["_all_sources"]],type_ignores=[]))
        exec(compile(fn,"test-yellow-actual-r74","exec"),env)
        f=Fake()
        env["_all_sources"](f)
        self.assertTrue(f._r71_deep_requested)
        self.assertEqual(f._r71_deep_target_ref,ref)
        self.assertEqual(queued,[10])
        self.assertNotIn(ref,f._candidate_cache)

    def test_preview_auto_selection_stays_inside_screen(self):
        self.assertIn("PREVIEW_STAY_OPEN",self.patched)
        self.assertNotIn(r7411.ORIGINAL_AUTO_CACHE,self.patched)
        self.assertNotIn(r7411.ORIGINAL_AUTO_FRESH,self.patched)
        self.assertIn("def _r737_show_video_fullscreen",self.patched)

    def test_old_plugin_rejected_without_priority_fix(self):
        with self.assertRaises(ValueError):
            r7412.patch(self.baseline)

    def test_apply_and_rollback(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"plugin.py"
            path.write_text(self.r7411)
            self.assertEqual(r7412.main(["--check","--target",str(path)]),0)
            self.assertEqual(path.read_text(),self.r7411)
            self.assertEqual(r7412.main(["--apply","--target",str(path)]),0)
            self.assertEqual(path.read_text(),self.patched)
            self.assertEqual(r7412.main(["--rollback","--target",str(path)]),0)
            self.assertEqual(path.read_text(),self.r7411)


if __name__=="__main__":
    unittest.main()
