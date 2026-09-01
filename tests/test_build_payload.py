import unittest

import typer

from jira_worklog_pkg.main import _build_payload


class TestBuildPayload(unittest.TestCase):

    def test_valid_date_with_comment(self):
        result = _build_payload("2024-01-15", 27000, "did some work")
        self.assertEqual(result, {
            "comment": "did some work",
            "started": "2024-01-15T00:00:00.000+0000",
            "timeSpentSeconds": 27000,
        })

    def test_valid_date_none_comment(self):
        result = _build_payload("2024-01-15", 3600, None)
        self.assertEqual(result["started"], "2024-01-15T00:00:00.000+0000")
        self.assertEqual(result["timeSpentSeconds"], 3600)
        self.assertEqual(result["comment"], "None")

    def test_seconds_cast_to_int(self):
        result = _build_payload("2024-06-01", 3600.0, "test")
        self.assertIsInstance(result["timeSpentSeconds"], int)

    def test_invalid_date_raises_abort(self):
        with self.assertRaises(typer.Abort):
            _build_payload("not-a-date", 3600, "test")

    def test_invalid_date_no_separators(self):
        with self.assertRaises(typer.Abort):
            _build_payload("20240115", 3600, "test")


if __name__ == '__main__':
    unittest.main()
