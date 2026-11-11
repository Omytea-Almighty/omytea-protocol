"""Meaningful rejection checks for the public reproduction boundary."""
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

import numpy as np
import xarray as xr

from reproduce import calculate_rpss, compare, unpack_verified


class AcceptanceTests(unittest.TestCase):
    def test_full_precision_not_display_rounding(self):
        self.assertTrue(compare({"model": 0.0004999}, {"model": 0}, 1)["accepted"])
        self.assertFalse(compare({"model": 0.00050001}, {"model": 0}, 1)["accepted"])

    def test_missing_both_sides_and_empty_are_rejected(self):
        result = compare({"a": 0, "b": 0}, {"a": 0, "c": 0}, 2)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["missing_computed"], ["c"])
        self.assertEqual(result["missing_reference"], ["b"])
        self.assertFalse(compare({}, {}, 0)["accepted"])
        self.assertFalse(compare({"a": 0}, {"a": 0}, 44)["accepted"])

    def test_nonfinite_is_rejected(self):
        for invalid in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ValueError):
                compare({"a": invalid}, {"a": 0}, 1)
            with self.assertRaises(ValueError):
                compare({"a": 0}, {"a": invalid}, 1)

    def test_uniform_baseline_and_empty_scoring_domain(self):
        mask = xr.DataArray([[1., 0.], [1., 0.]], dims=("latitude", "longitude"),
                            coords={"latitude": [45., -45.], "longitude": [0., 180.]})
        truth = np.zeros((5, 2, 2)); truth[2] = 1
        uniform = np.full((5, 2, 2), 0.2)
        self.assertAlmostEqual(calculate_rpss(uniform, truth, mask), 0.)
        self.assertAlmostEqual(calculate_rpss(truth, truth, mask), 1.)
        with self.assertRaises(ValueError):
            calculate_rpss(uniform, truth * np.nan, mask)
        ocean_only = np.full((5, 2, 2), np.nan); ocean_only[:, :, 1] = 0.2
        with self.assertRaisesRegex(ValueError, "entirely missing"):
            calculate_rpss(ocean_only, truth, mask)
        for invalid in (float("inf"), float("-inf")):
            bad = uniform.copy(); bad[0, 0, 0] = invalid
            with self.assertRaises(ValueError):
                calculate_rpss(bad, truth, mask)

    def test_input_tampering_missing_duplicate_and_unsafe_members(self):
        digest = hashlib.sha256(b"ok").hexdigest()
        manifest = {"files": [{"path": f"data/{i}", "bytes": 2, "sha256": digest} for i in range(96)]}
        for mode in ("valid", "tamper", "missing", "duplicate", "traversal", "symlink"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive = root / "inputs.tar.gz"
                with tarfile.open(archive, "w:gz") as stream:
                    for i in range(95 if mode == "missing" else 96):
                        member = tarfile.TarInfo(f"data/{i}")
                        payload = b"no" if mode == "tamper" and i == 0 else b"ok"
                        if i == 0 and mode == "traversal":
                            member.name = "../outside"
                        if i == 0 and mode == "symlink":
                            member.type, member.linkname = tarfile.SYMTYPE, "../../outside"
                        member.size = len(payload)
                        stream.addfile(member, io.BytesIO(payload))
                        if i == 0 and mode == "duplicate":
                            stream.addfile(member, io.BytesIO(payload))
                if mode == "valid":
                    unpack_verified(archive, manifest, root / "extracted")
                else:
                    with self.assertRaises(ValueError):
                        unpack_verified(archive, manifest, root / "extracted")
                self.assertFalse((root / "outside").exists())


if __name__ == "__main__":
    unittest.main()
