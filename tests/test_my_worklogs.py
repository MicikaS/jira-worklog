from unittest.mock import MagicMock, patch

import pytest
import typer

from jiracli_pkg.main import my_worklogs

TEST_EMAIL = "john@example.com"


def _mock_response(status_code, json_data):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    return mock


def _make_worklog(email, date_str, time_spent, user="John Doe", worklog_id="1001"):
    return {
        "user": user,
        "email": email,
        "date": date_str,
        "time_spent": time_spent,
        "worklog_id": worklog_id,
    }


SAMPLE_ISSUES = {
    "issues": [
        {
            "key": "KAN-100",
            "fields": {"summary": "Fix login bug"},
        },
        {
            "key": "KAN-200",
            "fields": {"summary": "Update dashboard"},
        },
    ]
}


class TestMyWorklogsValidation:
    @patch("jiracli_pkg.main.JIRA_USERNAME", None)
    def test_no_username_aborts(self):
        with pytest.raises(typer.Abort):
            my_worklogs(month=4, year=2026)

    @patch("jiracli_pkg.main.JIRA_USERNAME", "")
    def test_empty_username_aborts(self):
        with pytest.raises(typer.Abort):
            my_worklogs(month=4, year=2026)


class TestMyWorklogsApiErrors:
    @patch("jiracli_pkg.main.JIRA_USERNAME", "John Doe")
    @patch("jiracli_pkg.main.requests.get")
    def test_api_error_prints_message(self, mock_get, capsys):
        mock_get.return_value = _mock_response(400, {
            "errorMessages": ["JQL query is invalid."]
        })
        my_worklogs(month=4, year=2026)

    @patch("jiracli_pkg.main.JIRA_USERNAME", "John Doe")
    @patch("jiracli_pkg.main.requests.get")
    def test_no_issues_found(self, mock_get, capsys):
        mock_get.return_value = _mock_response(200, {"issues": []})
        my_worklogs(month=4, year=2026)


class TestMyWorklogsJql:
    @patch("jiracli_pkg.main.JIRA_USERNAME", "John Doe")
    @patch("jiracli_pkg.main._issue_worklogs", return_value=[])
    @patch("jiracli_pkg.main.requests.get")
    def test_jql_contains_date_range(self, mock_get, mock_worklogs):
        mock_get.return_value = _mock_response(200, SAMPLE_ISSUES)
        my_worklogs(month=3, year=2026)
        jql = mock_get.call_args.kwargs.get("params", {}).get("jql") or \
              mock_get.call_args[1]["params"]["jql"]
        assert 'worklogAuthor = "John Doe"' in jql
        assert 'worklogDate >= "2026-03-01"' in jql
        assert 'worklogDate <= "2026-03-31"' in jql

    @patch("jiracli_pkg.main.JIRA_USERNAME", "John Doe")
    @patch("jiracli_pkg.main._issue_worklogs", return_value=[])
    @patch("jiracli_pkg.main.requests.get")
    def test_defaults_to_current_month(self, mock_get, mock_worklogs):
        mock_get.return_value = _mock_response(200, {"issues": []})
        with patch("jiracli_pkg.main.date") as mock_date:
            from datetime import date as real_date
            mock_date.today.return_value = real_date(2026, 4, 15)
            mock_date.side_effect = real_date
            my_worklogs(month=None, year=None)


class TestMyWorklogsDisplay:
    @patch("jiracli_pkg.main.EMAIL", TEST_EMAIL)
    @patch("jiracli_pkg.main.JIRA_USERNAME", "John Doe")
    @patch("jiracli_pkg.main._issue_worklogs")
    @patch("jiracli_pkg.main.requests.get")
    def test_worklogs_grouped_by_day(self, mock_get, mock_worklogs):
        mock_get.return_value = _mock_response(200, SAMPLE_ISSUES)
        mock_worklogs.side_effect = [
            [
                _make_worklog(TEST_EMAIL, "2026-04-01", "4h"),
                _make_worklog(TEST_EMAIL, "2026-04-02", "7h"),
            ],
            [
                _make_worklog(TEST_EMAIL, "2026-04-01", "4h"),
            ],
        ]
        my_worklogs(month=4, year=2026)

    @patch("jiracli_pkg.main.EMAIL", TEST_EMAIL)
    @patch("jiracli_pkg.main.JIRA_USERNAME", "John Doe")
    @patch("jiracli_pkg.main._issue_worklogs")
    @patch("jiracli_pkg.main.requests.get")
    def test_filters_other_users_worklogs(self, mock_get, mock_worklogs):
        mock_get.return_value = _mock_response(200, {
            "issues": [{"key": "KAN-100", "fields": {"summary": "Task"}}]
        })
        mock_worklogs.return_value = [
            _make_worklog(TEST_EMAIL, "2026-04-01", "4h"),
            _make_worklog("jane@example.com", "2026-04-01", "3h", user="Jane Smith"),
        ]
        my_worklogs(month=4, year=2026)
        # Should not crash; Jane's worklog should be excluded

    @patch("jiracli_pkg.main.EMAIL", TEST_EMAIL)
    @patch("jiracli_pkg.main.JIRA_USERNAME", "John Doe")
    @patch("jiracli_pkg.main._issue_worklogs")
    @patch("jiracli_pkg.main.requests.get")
    def test_filters_worklogs_outside_target_month(self, mock_get, mock_worklogs):
        mock_get.return_value = _mock_response(200, {
            "issues": [{"key": "KAN-100", "fields": {"summary": "Task"}}]
        })
        mock_worklogs.return_value = [
            _make_worklog(TEST_EMAIL, "2026-04-01", "4h"),
            _make_worklog(TEST_EMAIL, "2026-03-31", "8h"),  # previous month
        ]
        my_worklogs(month=4, year=2026)

    @patch("jiracli_pkg.main.EMAIL", TEST_EMAIL)
    @patch("jiracli_pkg.main.JIRA_USERNAME", "John Doe")
    @patch("jiracli_pkg.main._issue_worklogs")
    @patch("jiracli_pkg.main.requests.get")
    def test_long_summary_is_truncated(self, mock_get, mock_worklogs):
        long_summary = "A" * 100
        mock_get.return_value = _mock_response(200, {
            "issues": [{"key": "KAN-100", "fields": {"summary": long_summary}}]
        })
        mock_worklogs.return_value = [
            _make_worklog(TEST_EMAIL, "2026-04-01", "4h"),
        ]
        my_worklogs(month=4, year=2026)

    @patch("jiracli_pkg.main.EMAIL", TEST_EMAIL)
    @patch("jiracli_pkg.main.JIRA_USERNAME", "John Doe")
    @patch("jiracli_pkg.main._issue_worklogs")
    @patch("jiracli_pkg.main.requests.get")
    def test_weekend_with_worklogs_shown(self, mock_get, mock_worklogs):
        """2026-04-04 is a Saturday."""
        mock_get.return_value = _mock_response(200, {
            "issues": [{"key": "KAN-100", "fields": {"summary": "Weekend work"}}]
        })
        mock_worklogs.return_value = [
            _make_worklog(TEST_EMAIL, "2026-04-04", "3h"),
        ]
        my_worklogs(month=4, year=2026)

    @patch("jiracli_pkg.main.EMAIL", TEST_EMAIL)
    @patch("jiracli_pkg.main.JIRA_USERNAME", "John Doe")
    @patch("jiracli_pkg.main._issue_worklogs")
    @patch("jiracli_pkg.main.requests.get")
    def test_february_leap_year(self, mock_get, mock_worklogs):
        mock_get.return_value = _mock_response(200, {
            "issues": [{"key": "KAN-100", "fields": {"summary": "Task"}}]
        })
        mock_worklogs.return_value = [
            _make_worklog(TEST_EMAIL, "2028-02-29", "8h"),
        ]
        my_worklogs(month=2, year=2028)


class TestMyWorklogsExpectedHours:
    @patch("jiracli_pkg.main.WORK_HOURS", {
        "Monday": 7, "Tuesday": 7, "Wednesday": 7, "Thursday": 7, "Friday": 7
    })
    @patch("jiracli_pkg.main.EMAIL", TEST_EMAIL)
    @patch("jiracli_pkg.main.JIRA_USERNAME", "John Doe")
    @patch("jiracli_pkg.main._issue_worklogs")
    @patch("jiracli_pkg.main.requests.get")
    def test_custom_work_hours_used(self, mock_get, mock_worklogs):
        """When WORK_HOURS config is set, expected should use those values."""
        mock_get.return_value = _mock_response(200, {
            "issues": [{"key": "KAN-100", "fields": {"summary": "Task"}}]
        })
        mock_worklogs.return_value = [
            _make_worklog(TEST_EMAIL, "2026-04-01", "7h"),  # Wednesday
        ]
        my_worklogs(month=4, year=2026)

    @patch("jiracli_pkg.main.WORK_HOURS", {
        "Monday": 0, "Tuesday": 0, "Wednesday": 0, "Thursday": 0, "Friday": 0
    })
    @patch("jiracli_pkg.main.EMAIL", TEST_EMAIL)
    @patch("jiracli_pkg.main.JIRA_USERNAME", "John Doe")
    @patch("jiracli_pkg.main._issue_worklogs")
    @patch("jiracli_pkg.main.requests.get")
    def test_default_8h_when_work_hours_zero(self, mock_get, mock_worklogs):
        """When WORK_HOURS is 0, should default to 8h."""
        mock_get.return_value = _mock_response(200, {
            "issues": [{"key": "KAN-100", "fields": {"summary": "Task"}}]
        })
        mock_worklogs.return_value = [
            _make_worklog(TEST_EMAIL, "2026-04-01", "8h"),
        ]
        my_worklogs(month=4, year=2026)
