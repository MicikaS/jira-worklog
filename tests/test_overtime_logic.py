import unittest
from unittest.mock import patch, MagicMock

import typer

from jiracli_pkg.main import _submit_worklog


class TestSubmitWorklogLimits(unittest.TestCase):
    """Test hour-limit validation in _submit_worklog."""

    def _mock_post(self, status_code=201, json_data=None):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = json_data or {"timeSpent": "2h"}
        return mock_resp

    @patch("jiracli_pkg.main.requests.post")
    @patch("jiracli_pkg.main._get_total_hours_on_date", return_value=None)
    def test_no_username_aborts(self, mock_hours, mock_post):
        with self.assertRaises(typer.Abort):
            _submit_worklog("TEST-1", "2h", "2024-01-15", None, False)

    @patch("jiracli_pkg.main.requests.post")
    @patch("jiracli_pkg.main._get_total_hours_on_date", return_value=5.0)
    def test_regular_under_limit_succeeds(self, mock_hours, mock_post):
        mock_post.return_value = self._mock_post()
        result = _submit_worklog("TEST-1", "2h", "2024-01-15", None, False)
        self.assertTrue(result)
        mock_post.assert_called_once()

    @patch("jiracli_pkg.main.requests.post")
    @patch("jiracli_pkg.main._get_total_hours_on_date", return_value=5.0)
    def test_regular_over_8h_aborts(self, mock_hours, mock_post):
        with self.assertRaises(typer.Abort):
            _submit_worklog("TEST-1", "4h", "2024-01-15", None, False)

    @patch("jiracli_pkg.main.requests.post")
    @patch("jiracli_pkg.main._get_total_hours_on_date", return_value=10.0)
    def test_overtime_under_13h_succeeds(self, mock_hours, mock_post):
        mock_post.return_value = self._mock_post()
        result = _submit_worklog("TEST-1", "2h", "2024-01-15", None, True)
        self.assertTrue(result)

    @patch("jiracli_pkg.main.requests.post")
    @patch("jiracli_pkg.main._get_total_hours_on_date", return_value=10.0)
    def test_overtime_over_13h_aborts(self, mock_hours, mock_post):
        with self.assertRaises(typer.Abort):
            _submit_worklog("TEST-1", "4h", "2024-01-15", None, True)

    @patch("jiracli_pkg.main.WORK_HOURS", {"Monday": 7, "Tuesday": 0, "Wednesday": 0, "Thursday": 0, "Friday": 0})
    @patch("jiracli_pkg.main.requests.post")
    @patch("jiracli_pkg.main._get_total_hours_on_date", return_value=0.0)
    def test_work_hours_exceeded_aborts(self, mock_hours, mock_post):
        # 2024-01-15 is a Monday
        with self.assertRaises(typer.Abort):
            _submit_worklog("TEST-1", "8h", "2024-01-15", None, False)

    @patch("jiracli_pkg.main.WORK_HOURS", {"Monday": 7, "Tuesday": 0, "Wednesday": 0, "Thursday": 0, "Friday": 0})
    @patch("jiracli_pkg.main.requests.post")
    @patch("jiracli_pkg.main._get_total_hours_on_date", return_value=0.0)
    def test_work_hours_exceeded_with_overtime_succeeds(self, mock_hours, mock_post):
        mock_post.return_value = self._mock_post()
        result = _submit_worklog("TEST-1", "8h", "2024-01-15", None, True)
        self.assertTrue(result)

    @patch("jiracli_pkg.main.requests.post")
    @patch("jiracli_pkg.main._get_total_hours_on_date", return_value=0.0)
    def test_api_failure_returns_false(self, mock_hours, mock_post):
        mock_post.return_value = self._mock_post(status_code=400, json_data={"errorMessages": ["Bad request"]})
        result = _submit_worklog("TEST-1", "2h", "2024-01-15", None, False)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
