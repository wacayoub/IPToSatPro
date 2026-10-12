#!/usr/bin/env python3
"""R74.9 package tests: FilmBox One / ONE FILMBOX is strict exact reordering.

Use the actual built R74.9 core module and existing match_score_details rather
than mocking rankings. No network, no receiver claims or manual mapping edits.
"""
import importlib.util,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r749_builder",ROOT/"scripts/build-r74-unified.py")
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class ReorderedFilmBoxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        out=Path(cls.tmp.name)/"r749.ipk"
        cls.meta=builder.build(out)
        files=builder.b.b.base.pack.members_from(builder.b.b.base.pack.unpack_ar(out.read_bytes())["data.tar.gz"])
        py=Path(cls.tmp.name)/"actual_core.py";py.write_bytes(files[builder.CORE])
        sp=importlib.util.spec_from_file_location("actual_r749_core",py)
        cls.core=importlib.util.module_from_spec(sp);sp.loader.exec_module(cls.core)
        cls.src=files[builder.CORE].decode()
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def calc(self,sat,iptv,preview=True,role="BACKUP1",context=None):
        ch={"name":iptv,"group":"MOVIES","server_role":role,
            "server_priority":2,"url":"http://127.0.0.1/unused.ts"}
        c=context if context is not None else {"confidence":"LOW","language_priorities":[],
                                                "market_preferences":[]}
        return self.core.match_score_details(sat,ch,[],c,preview=preview)

    def test_filmbox_one_vs_one_filmbox_safe_on_preview_and_automatic(self):
        for preview in (True,False):
            score,details=self.calc("FilmBox One","ONE: FILMBOX",preview=preview)
            self.assertEqual(details.get("name_order_alias"),"SAME_WORDS_DIFFERENT_ORDER",
                             (score,details,preview))
            self.assertEqual(details.get("name"),100.0,(score,details))
            self.assertEqual(self.core.match_decision(score,details,82.0),"SAFE",(score,details))

    def test_actual_label_variations(self):
        pairs=[("FilmBox One","ONE: FILMBOX"),
               ("FILMBOX ONE HD","ONE FILMBOX FHD"),
               ("FILMBOX ONE","ONE - FILMBOX HD"),
               ("FILMBOX 1 HD","ONE FILMBOX FHD"),
               ("FILMBOX ONE","1 FILMBOX"),
               ("Sky Action Movies","Movies Sky Action"),
               ("FilmBox Premium","Premium FilmBox")]
        for sat,iptv in pairs:
            with self.subTest(sat=sat,iptv=iptv):
                self.assertTrue(self.core._r749_reordered_identity(sat,iptv),
                                (self.core.normalize_preview_name(sat),
                                 self.core.normalize_preview_name(iptv)))
                score,details=self.calc(sat,iptv)
                self.assertEqual(details.get("name"),100.0,(sat,iptv,score,details))
                self.assertFalse(details.get("reject_reason"),(sat,iptv,details))

    def test_different_service_number_is_rejected(self):
        negatives=[("FilmBox One","TWO FILMBOX"),
                   ("FilmBox One","ONE FILMBOX 2"),
                   ("FilmBox 2","ONE FILMBOX"),
                   ("beIN Sports 6","8 SPORTS BEIN"),
                   ("FILMBOX 1","FILMBOX 10")]
        for sat,iptv in negatives:
            with self.subTest(sat=sat,iptv=iptv):
                self.assertFalse(self.core._r749_reordered_identity(sat,iptv))
                score,details=self.calc(sat,iptv)
                self.assertEqual(self.core.match_decision(score,details,82),"REJECT",
                                 (sat,iptv,score,details))

    def test_different_brand_or_edition_is_not_alias(self):
        negatives=[("FilmBox One","FILMBOX EXTRA"),
                   ("FilmBox One","ONE FILMBOX PREMIUM"),
                   ("FilmBox One","ONE FILMBOX FAMILY"),
                   ("FilmBox One","FILMBOX STARS"),
                   ("FilmBox One","ONE CINEMA")]
        for sat,iptv in negatives:
            with self.subTest(sat=sat,iptv=iptv):
                self.assertFalse(self.core._r749_reordered_identity(sat,iptv))
                _score,details=self.calc(sat,iptv)
                self.assertNotEqual(details.get("name_order_alias"),"SAME_WORDS_DIFFERENT_ORDER")

    def test_generic_and_one_token_non_matches(self):
        for a,b in (("BBC","BBC"),("One","1"),("HD 1","1 HD"),("CHANNEL 1","1 CHANNEL"),
                     ("FILMBOX ONE","FILMBOX ONE")):
            with self.subTest(a=a,b=b):
                self.assertFalse(self.core._r749_reordered_identity(a,b))

    def test_source_role_does_not_affect_safe_identity(self):
        for role in ("PRIMARY","BACKUP1","BACKUP2"):
            score,details=self.calc("FilmBox One","ONE: FILMBOX",role=role)
            self.assertEqual(details.get("name_order_alias"),
                             "SAME_WORDS_DIFFERENT_ORDER",(role,details))
            self.assertEqual(self.core.match_decision(score,details,82),"SAFE")

    def test_country_conflicts_still_rejected(self):
        # Existing R74.8 country safety wins over token-order equivalence.
        a,b="TLC Germany","AT: TLC HD"
        score,details=self.calc(a,b)
        self.assertNotEqual(details.get("name_order_alias"),"SAME_WORDS_DIFFERENT_ORDER")
        self.assertFalse(self.core._r749_reordered_identity(a,b))

    def test_reordering_in_pre_rank_and_score_and_cache_epoch(self):
        self.assertIn("reordered=_r749_reordered_identity(sat_name,name)",self.src)
        self.assertIn("or reordered))",self.src)
        self.assertIn('self._fast_cache_key("mega-r7410"',self.src)
        self.assertIn("reordered_identity=_r749_reordered_identity(sat_name,ch.get(\"name\",\"\"))",self.src)
        self.assertTrue(self.meta["reordered_name_matcher"])
        self.assertFalse(self.meta["receiver_tested"])
        self.assertFalse(self.meta["production_published"])

if __name__=="__main__": unittest.main()
