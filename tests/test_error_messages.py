import unittest
from unittest.mock import MagicMock

import requests

from jira_worklog_pkg.main import _get_error_messages


class TestGetErrorMessages(unittest.TestCase):

    def _make_response(self, status_code, json_data=None, text="", raise_json_error=False):
        response = MagicMock(spec=requests.Response)
        response.status_code = status_code
        response.text = text
        if raise_json_error:
            response.json.side_effect = requests.exceptions.JSONDecodeError("", "", 0)
        else:
            response.json.return_value = json_data or {}
        return response

    def test_json_with_error_messages(self):
        response = self._make_response(404, {"errorMessages": ["Issue not found"]})
        self.assertEqual(_get_error_messages(response), ["Issue not found"])

    def test_json_with_multiple_error_messages(self):
        response = self._make_response(400, {"errorMessages": ["Error 1", "Error 2"]})
        self.assertEqual(_get_error_messages(response), ["Error 1", "Error 2"])

    def test_json_without_error_messages(self):
        response = self._make_response(400, {"other": "data"})
        self.assertEqual(_get_error_messages(response), ["Request failed with status 400."])

    def test_json_with_empty_error_messages(self):
        response = self._make_response(400, {"errorMessages": []})
        self.assertEqual(_get_error_messages(response), ["Request failed with status 400."])

    def test_non_json_response(self):
        response = self._make_response(502, text="<html>Bad Gateway</html>", raise_json_error=True)
        result = _get_error_messages(response)
        self.assertEqual(len(result), 1)
        self.assertIn("502", result[0])
        self.assertIn("Bad Gateway", result[0])

    def test_non_json_long_text_truncated(self):
        long_text = "x" * 500
        response = self._make_response(500, text=long_text, raise_json_error=True)
        result = _get_error_messages(response)
        self.assertLessEqual(len(result[0]), 300)


if __name__ == '__main__':
    unittest.main()
