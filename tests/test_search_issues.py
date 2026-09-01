from unittest.mock import MagicMock, patch

from jira_worklog_pkg.main import search_issues


def _mock_response(status_code, json_data):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    return mock


class TestSearchIssuesDisplay:
    @patch("jira_worklog_pkg.main.requests.get")
    def test_no_results(self, mock_get, capsys):
        mock_get.return_value = _mock_response(200, {"issues": []})
        search_issues("nonexistent")

    @patch("jira_worklog_pkg.main.requests.get")
    def test_multiple_results(self, mock_get):
        mock_get.return_value = _mock_response(200, {
            "issues": [
                {
                    "key": "KAN-100",
                    "fields": {
                        "summary": "Fix login bug",
                        "status": {"name": "In Progress"},
                        "assignee": {"displayName": "John Doe"},
                    }
                },
                {
                    "key": "KAN-101",
                    "fields": {
                        "summary": "Update dashboard",
                        "status": {"name": "Done"},
                        "assignee": None,
                    }
                },
            ]
        })
        search_issues("bug")

    @patch("jira_worklog_pkg.main.requests.get")
    def test_long_summary_is_truncated(self, mock_get):
        long_summary = "A" * 100
        mock_get.return_value = _mock_response(200, {
            "issues": [
                {
                    "key": "KAN-200",
                    "fields": {
                        "summary": long_summary,
                        "status": {"name": "Open"},
                        "assignee": {"displayName": "Jane"},
                    }
                }
            ]
        })
        search_issues("test")

    @patch("jira_worklog_pkg.main.requests.get")
    def test_api_error(self, mock_get):
        mock_get.return_value = _mock_response(400, {
            "errorMessages": ["JQL query is invalid."]
        })
        search_issues("bad query")


class TestSearchJqlConstruction:
    @patch("jira_worklog_pkg.main.requests.get")
    def test_jql_contains_search_text(self, mock_get):
        mock_get.return_value = _mock_response(200, {"issues": []})
        search_issues("login bug")
        call_kwargs = mock_get.call_args
        jql = call_kwargs.kwargs.get("params", {}).get("jql") or call_kwargs[1]["params"]["jql"]
        assert 'text ~ "login bug"' in jql

    @patch("jira_worklog_pkg.main.requests.get")
    def test_max_results_passed(self, mock_get):
        mock_get.return_value = _mock_response(200, {"issues": []})
        search_issues("test", max_results=5)
        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1]["params"]
        assert params["maxResults"] == "5"