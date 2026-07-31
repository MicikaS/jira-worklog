import json
import os
import tempfile
import unittest
from unittest.mock import patch

import typer

from jiracli_pkg.main import _try_log_time_from_csv_file, _get_status_file_path


class TestCsvParsing(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def _write_csv(self, filename, lines):
        path = os.path.join(self.tmpdir, filename)
        with open(path, "w") as f:
            f.write("\n".join(lines))
        return path

    def _cleanup_status(self, csv_path):
        status_path = _get_status_file_path(csv_path)
        if status_path.exists():
            status_path.unlink()

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_non_csv_extension_raises(self):
        path = self._write_csv("data.txt", ["Monday,TEST-1,7h,2024-01-15,0"])
        with self.assertRaises(ValueError) as ctx:
            _try_log_time_from_csv_file(path)
        self.assertIn("not a CSV", str(ctx.exception))

    @patch("jiracli_pkg.main._submit_worklog", return_value=True)
    def test_valid_csv_all_succeed(self, mock_submit):
        path = self._write_csv("work.csv", [
            "Working Day,Issue,Time (Hours),Date,Overtime",
            "Monday,TEST-1,7h,2024-01-15,0",
            "Tuesday,TEST-1,7h,2024-01-16,0",
        ])
        try:
            _try_log_time_from_csv_file(path)
            self.assertEqual(mock_submit.call_count, 2)
            # Status file should be marked complete
            status_path = _get_status_file_path(path)
            with open(status_path) as f:
                status = json.load(f)
            self.assertTrue(status["complete"])
        finally:
            self._cleanup_status(path)

    @patch("jiracli_pkg.main._submit_worklog", return_value=True)
    def test_header_row_skipped(self, mock_submit):
        path = self._write_csv("work.csv", [
            "Working Day,Issue,Time (Hours),Date,Overtime",
            "Monday,TEST-1,7h,2024-01-15,0",
        ])
        try:
            _try_log_time_from_csv_file(path)
            self.assertEqual(mock_submit.call_count, 1)
        finally:
            self._cleanup_status(path)

    @patch("jiracli_pkg.main._submit_worklog", return_value=True)
    def test_comment_row_skipped(self, mock_submit):
        path = self._write_csv("work.csv", [
            "Monday,TEST-1,7h,2024-01-15,0",
            "# this is a comment",
            "Tuesday,TEST-1,7h,2024-01-16,0",
        ])
        try:
            _try_log_time_from_csv_file(path)
            self.assertEqual(mock_submit.call_count, 2)
        finally:
            self._cleanup_status(path)

    @patch("jiracli_pkg.main._submit_worklog", return_value=True)
    def test_already_logged_csv_raises(self, mock_submit):
        path = self._write_csv("work.csv", [
            "Monday,TEST-1,7h,2024-01-15,0",
        ])
        # Create a status file marking it complete
        status_path = _get_status_file_path(path)
        with open(status_path, "w") as f:
            json.dump({"logged_rows": [0], "complete": True}, f)
        try:
            with self.assertRaises(ValueError) as ctx:
                _try_log_time_from_csv_file(path)
            self.assertIn("already logged", str(ctx.exception))
        finally:
            self._cleanup_status(path)

    @patch("jiracli_pkg.main._submit_worklog", side_effect=typer.Abort())
    def test_partial_failure_reports_failed_rows(self, mock_submit):
        path = self._write_csv("work.csv", [
            "Monday,TEST-1,7h,2024-01-15,0",
        ])
        try:
            with self.assertRaises(ValueError) as ctx:
                _try_log_time_from_csv_file(path)
            self.assertIn("failed to log", str(ctx.exception))
        finally:
            self._cleanup_status(path)

    @patch("jiracli_pkg.main._submit_worklog", return_value=True)
    def test_resume_skips_already_logged_rows(self, mock_submit):
        path = self._write_csv("work.csv", [
            "Monday,TEST-1,7h,2024-01-15,0",
            "Tuesday,TEST-1,7h,2024-01-16,0",
        ])
        # Pre-create status with row 0 already logged
        status_path = _get_status_file_path(path)
        with open(status_path, "w") as f:
            json.dump({"logged_rows": [0], "complete": False}, f)
        try:
            _try_log_time_from_csv_file(path)
            # Only row 1 should be submitted
            self.assertEqual(mock_submit.call_count, 1)
            call_args = mock_submit.call_args
            self.assertEqual(call_args.kwargs["date"], "2024-01-16")
        finally:
            self._cleanup_status(path)

    @patch("jiracli_pkg.main._submit_worklog", return_value=True)
    def test_invalid_working_day_raises(self, mock_submit):
        path = self._write_csv("work.csv", [
            "Caturday,TEST-1,7h,2024-01-15,0",
        ])
        try:
            with self.assertRaises(ValueError) as ctx:
                _try_log_time_from_csv_file(path)
            self.assertIn("working day", str(ctx.exception).lower())
        finally:
            self._cleanup_status(path)

    @patch("jiracli_pkg.main._submit_worklog", return_value=True)
    def test_empty_rows_skipped(self, mock_submit):
        path = self._write_csv("work.csv", [
            "Monday,TEST-1,7h,2024-01-15,0",
            ",,,,,",
            "Tuesday,TEST-1,7h,2024-01-16,0",
        ])
        try:
            _try_log_time_from_csv_file(path)
            self.assertEqual(mock_submit.call_count, 2)
        finally:
            self._cleanup_status(path)


if __name__ == '__main__':
    unittest.main()
