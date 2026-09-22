"""Downloader boundaries: fixed origin, unchanged bytes, no credential transport."""
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from download_inputs import NoRedirect, fetch_file, validate_entry


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.entry = {"path": "forecasts/20251127/team/model/file.nc",
                      "source_url": "https://data.ecmwf.int/ai-weatherquest/by_fc_date/20251127/team/model/file.nc",
                      "bytes": 2, "sha256": hashlib.sha256(b"ok").hexdigest()}

    def test_origin_path_and_redirect(self):
        validate_entry(self.entry)
        for change in ({"source_url": "http://127.0.0.1/file"},
                       {"source_url": self.entry["source_url"] + "?token=secret"},
                       {"path": "../outside"}, {"bytes": 4_000_001}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_entry({**self.entry, **change})
        with self.assertRaises(ValueError):
            NoRedirect().redirect_request(None, None, 302, None, None, "http://127.0.0.1")

    def test_changed_bytes_never_written(self):
        for payload in (b"ok", b"no", b"o", b"okay"):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                with patch("download_inputs.urllib.request.build_opener") as factory:
                    factory.return_value.open.return_value = io.BytesIO(payload)
                    if payload == b"ok":
                        fetch_file(self.entry, root)
                        self.assertEqual((root / self.entry["path"]).read_bytes(), b"ok")
                    else:
                        with self.assertRaises(ValueError):
                            fetch_file(self.entry, root)
                        self.assertFalse((root / self.entry["path"]).exists())


if __name__ == "__main__":
    unittest.main()
