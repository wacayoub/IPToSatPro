"""R75 acceptance: build real Enigma2 IPK, stages R74.11-.18, speed and safety."""
import ast
import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]


def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/file)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod


builder=load("r75build","build-r75-smart-index.py")
smart=load("r75patchtest","r75_smart_index_patch.py")


class R75Consolidated(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        target=Path(cls.tmp.name)/"R75.ipk"
        cls.details=builder.build(target)
        cls.data=target.read_bytes()
        pack=builder.base.b.b.base.pack
        cls.files=pack.members_from(pack.unpack_ar(cls.data)["data.tar.gz"])
        cls.control=pack.members_from(pack.unpack_ar(cls.data)["control.tar.gz"])
        cls.plugin=cls.files[builder.PLUGIN].decode()
        cls.core=cls.files[builder.CORE].decode()
        cls.monitor=cls.files[builder.MONITOR].decode()
        cls.updater=cls.files[builder.UPDATER].decode()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_real_versioned_installable_package(self):
        self.assertEqual(self.details["version"],builder.VERSION)
        self.assertTrue(self.details["player_unchanged"])
        self.assertFalse(self.details["production_published"])
        self.assertIn(("Version: "+builder.VERSION).encode(),self.control["control"])
        self.assertIn(('PLUGIN_VERSION = "'+builder.VERSION+'"'),self.plugin)
        self.assertIn(('CURRENT_VERSION = "'+builder.VERSION+'"'),self.updater)
        self.assertGreater(len(self.data),250000)
        self.assertEqual(len(self.details["steps"]),10)

    def test_all_critical_hotfixes_in_real_ipk(self):
        for marker in ("R7411_STAY_PREVIEW_PROVIDER_LANGUAGE_RESOLUTION",
                       "R7412_FAST_PREVIEW_SHORTLIST",
                       "R7413_PREVIEW_INLINE_NO_HIDE",
                       "R7414_PREVIEW_FAST_SEED_MANUAL_LOCK",
                       "R7415_FIRSTPAINT_GREEN_ANY_FOCUS",
                       "R7416_UNMAP_CRYPT_ACCESS"):
            self.assertIn(marker,self.plugin)
        for marker in ("R7417_FTA_SIGNAL_NATIVE_GUARD",
                       "R7418_BG_CANCEL_FUZZY",
                       "R75_SMART_NEGATIVE_CACHE"):
            self.assertIn(marker,self.monitor)
        for marker in ("R7418_BOUNDED_FUZZY","R75_SMART_INDEX_MEMO"):
            self.assertIn(marker,self.core)
        self.assertIn("AUDIO_SAFE_PLAYER",self.monitor)
        self.assertIn("R7417_FTA_SIGNAL_NATIVE_GUARD",self.monitor)
        self.assertIn("USER UNMAPPED",self.plugin)
        self.assertIn('"MANUAL LOCK"',self.plugin)

    def test_preview_and_automatic_policy_separate(self):
        self.assertIn("candidate_budget = 192 if self._r71_worker_deep else 24",self.plugin)
        self.assertIn('candidate_budget=96',self.monitor)
        self.assertIn('should_abort=lambda:',self.monitor)
        self.assertIn('def fast_preview_mega_matches(',self.core)
        self.assertIn('if isinstance(old, dict) and old.get("user_unmapped")',self.plugin)
        self.assertIn("_r7417_keep_sat(",self.monitor)

    def test_updater_points_to_verified_r75_staging_not_prod(self):
        self.assertIn(smart.UPDATER_URL,self.updater)
        self.assertNotIn('MANIFEST_URL = "https://raw.githubusercontent.com/wacayoub/IPToSatPro/main/update.json"',self.updater)
        self.assertIn("sha256",self.updater)
        self.assertIn("https://raw.githubusercontent.com",self.updater)

    def test_reconstructed_native_player_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            ipk=Path(td)/"baseline.ipk"
            builder.base.build(ipk)
            pk=builder.base.b.b.base.pack
            old=pk.members_from(pk.unpack_ar(ipk.read_bytes())["data.tar.gz"])
            for suffix in ("player.py","metadata_shadow.py"):
                path=builder.P+suffix
                if path in old:
                    self.assertEqual(self.files[path],old[path])

    def _nomination_functions(self):
        tree=ast.parse(self.core)
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="Catalog")
        methods={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
        named={}
        for n in ("_r7418_nominate_fuzzy","_r7418_nominate_fuzzy_uncached"):
            code=ast.fix_missing_locations(ast.Module(body=[methods[n]],type_ignores=[]))
            exec(compile(code,"r75-isolated.py","exec"),named)
        return named

    def test_memoized_nominees_reuse_and_bounded_size(self):
        methods=self._nomination_functions()
        calls=[]
        class Catalog:
            channels=[dict(name="station") for _ in range(30)]
            def _r7418_nominate_fuzzy_uncached(self,name,budget):
                calls.append((name,budget))
                return [dict(name=name,role="PRIMARY")]
        cat=Catalog()
        cat._r7418_nominate_fuzzy=methods["_r7418_nominate_fuzzy"].__get__(cat,Catalog)
        fn=cat._r7418_nominate_fuzzy
        # normalize_name is resolved in function global namespace.
        methods["_r7418_nominate_fuzzy"].__globals__["normalize_name"]=lambda s:s.strip().lower()
        first=fn(" Discovery Turbo Italy ",96)
        second=fn("Discovery Turbo Italy",96)
        self.assertEqual(len(calls),1)
        self.assertEqual(first,second)
        self.assertEqual(len(cat._r75_fuzzy_index_cache),1)
        # Capped cache cannot grow endlessly with normal remote browsing.
        for i in range(65):
            fn("Channel %d"%i,96)
        self.assertLessEqual(len(cat._r75_fuzzy_index_cache),48)
        self.assertIn(("Discovery Turbo Italy",96),calls)

    def test_negative_result_cache_auto_only_expiry(self):
        cls=next(n for n in ast.parse(self.monitor).body
                 if isinstance(n,ast.ClassDef) and n.name=="SatFallbackMonitor")
        methods={n.name:ast.get_source_segment(self.monitor,n)
                 for n in cls.body if isinstance(n,ast.FunctionDef)}
        queue=methods["_queue_background_smartmatch"]
        poll=methods["_smartmatch_poll"]
        self.assertIn('if stage=="fast":',queue)
        self.assertIn('id(catalog)',queue)
        self.assertIn('max_age=90s',queue)
        self.assertIn('id(self.catalog)',poll)
        self.assertIn('while len(cache)>64:',poll)
        self.assertIn('stage == "fuzzy"',poll)
        self.assertIn('MATCH_NEGATIVE_CACHE',queue)

    def test_code_compiles_and_no_credentials_in_artifact_metadata(self):
        for k,data in self.files.items():
            if k.endswith(".py"):
                compile(data,k,"exec")
        self.assertNotIn("/etc/enigma2/settings",self.plugin)
        self.assertNotIn("XtreamPassword",self.details)


if __name__=="__main__":
    unittest.main()
