"""Run from the addon root: python tests/fetch-tools.test.py"""
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import Mock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "Tools"))
import build_names_lua as build
import fetch_descriptions as descriptions
import fetch_names as names


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="enpanel-api-test-")
        self.root = pathlib.Path(self.temp.name)
        assert self.root.resolve().parent == pathlib.Path(tempfile.gettempdir()).resolve()
        self.addCleanup(self.temp.cleanup)
        (self.root / "Data/cache").mkdir(parents=True)

    def write_cache(self, filename, rows):
        path = self.root / "Data/cache" / filename
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return path

    def run_names(self, response):
        api = Mock()
        api.search.return_value = response
        with patch.object(names, "CACHE", self.root / "Data/cache"), \
             patch.object(names, "Api", return_value=api), \
             patch.object(sys, "argv", ["fetch_names.py", "--kind", "spell", "--max-id", "1"]), \
             contextlib.redirect_stdout(io.StringIO()):
            return names.main()

    def test_failed_search_does_not_report_complete(self):
        with self.assertRaisesRegex(RuntimeError, "search failed"):
            self.run_names(None)

    def test_truncated_search_does_not_report_complete(self):
        with self.assertRaisesRegex(RuntimeError, "truncated"):
            self.run_names({"results": [], "resultCountCapped": True})

    def run_descriptions(self, response):
        self.write_cache("names_spell.jsonl", [{"id": 133, "name": "Fireball"}])
        with patch.object(descriptions, "CACHE", self.root / "Data/cache"), \
             patch.object(descriptions, "get_token", return_value="fixture-token"), \
             patch.object(descriptions.urllib.request, "urlopen", side_effect=response), \
             patch.object(descriptions.time, "sleep"), \
             patch.object(sys, "argv", ["fetch_descriptions.py", "--kind", "spell", "--retry-empty"]), \
             contextlib.redirect_stdout(io.StringIO()):
            return descriptions.main()

    def test_empty_description_is_retried(self):
        path = self.write_cache("desc_spell.jsonl", [{"id": 133, "text": ""}])
        result = self.run_descriptions(lambda *a, **kw: io.BytesIO(b'{"description":"Hurls a fiery ball."}'))
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8").splitlines()[-1])["text"], "Hurls a fiery ball.")

    def test_failed_description_does_not_become_a_negative_cache_entry(self):
        failure = urllib.error.HTTPError("https://example.invalid", 503, "Unavailable", {}, None)
        self.assertEqual(self.run_descriptions(failure), 1)
        self.assertEqual((self.root / "Data/cache/desc_spell.jsonl").read_text(encoding="utf-8"), "")

    def test_description_404_is_an_explicit_empty_result(self):
        missing = urllib.error.HTTPError("https://example.invalid", 404, "Missing", {}, None)
        self.assertEqual(self.run_descriptions(missing), 0)
        rows = (self.root / "Data/cache/desc_spell.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(json.loads(rows[0]), {"id": 133, "text": ""})

    def test_rebuild_uses_latest_cached_record_once_and_keeps_lf(self):
        self.write_cache("names_spell.jsonl", [
            {"id": 133, "name": "Old name"}, {"id": 133, "name": 'New "name"'},
        ])
        self.write_cache("desc_spell.jsonl", [
            {"id": 133, "text": "Outdated"}, {"id": 133, "text": ""},
            {"id": 585, "text": "Smite"},
        ])
        out = self.root / "output"
        for args in ([], ["--desc"]):
            with patch.object(build, "ROOT", self.root), \
                 patch.object(sys, "argv", ["build_names_lua.py", "--kind", "spell", "--out", str(out), *args]), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(build.main(), 0)
        data = (out / "NamesSpell.lua").read_bytes()
        self.assertEqual(data.count(b"[133]"), 1)
        self.assertIn(b'New \\"name\\"', data)
        self.assertNotIn(b"\r", data)
        self.assertNotIn(b"[133]", (out / "DescSpell.lua").read_bytes())

    def test_credentials_can_be_read_from_explicit_path(self):
        path = self.root / "fixture.env"
        path.write_text("BLIZZARD_CLIENT_ID=fixture-id\nBLIZZARD_CLIENT_SECRET=fixture-secret\n", encoding="utf-8")
        self.assertEqual(names.load_keys(path), ("fixture-id", "fixture-secret"))


if __name__ == "__main__":
    unittest.main()
