#!/usr/bin/env python3
"""Offline release-bundle checks; no original receiver IPK required."""
import base64
import hashlib
import json
import unittest
from unittest.mock import patch

import prepare_r80_final_offline as engine
import prepare_r80_release_bundle_offline as bundle
from test_r80_final_offline import synthetic


class R80BundleTests(unittest.TestCase):
    def test_bundle_matches_repacked_ipk_and_does_not_publish(self):
        fake, core = synthetic()
        def synthetic_only_transform(src):
            return engine.transform(src, expected_size=len(fake),
                                    expected_sha=engine.digest(fake),
                                    expected_core=engine.digest(core))
        with patch.object(bundle, "TESTED_SHA", engine.digest(fake)):
            with patch.object(bundle, "transform", synthetic_only_transform):
                files, audit, manifest = bundle.build_bundle(fake)
        self.assertEqual(set(files), {bundle.IPK_NAME, bundle.PART_NAME,
                                     bundle.MANIFEST_NAME, "SHA256SUMS.txt"})
        ipk = files[bundle.IPK_NAME]
        self.assertEqual(base64.b64decode(files[bundle.PART_NAME]), ipk)
        self.assertEqual(hashlib.sha256(ipk).hexdigest(), manifest["sha256"])
        self.assertEqual(json.loads(files[bundle.MANIFEST_NAME]), manifest)
        self.assertEqual(manifest["version"], engine.FINAL)
        self.assertEqual(manifest["parts"], [bundle.PAYLOAD_URL])
        self.assertEqual(manifest["production_published"], False)
        self.assertEqual(manifest["final_binary_receiver_tested"], False)
        self.assertEqual(manifest["source_hardware_functionally_validated"], True)
        self.assertTrue(audit["unchanged_operational_payload"])

    def test_pinned_real_ipk_is_required(self):
        fake, _ = synthetic()
        with self.assertRaisesRegex(ValueError, "TESTED_INPUT_PACKAGE_MISSING_OR_SHA_MISMATCH"):
            bundle.build_bundle(fake)


if __name__ == "__main__":
    unittest.main()
