import pytest
import typer

from jiracli_pkg.main import _validate_issue_key


class TestValidIssueKeys:
    def test_standard_key(self):
        assert _validate_issue_key("KAN-247") == "KAN-247"

    def test_two_letter_project(self):
        assert _validate_issue_key("AB-1") == "AB-1"

    def test_long_project_key(self):
        assert _validate_issue_key("PROJECT123-99") == "PROJECT123-99"

    def test_underscore_in_project(self):
        assert _validate_issue_key("MY_PROJECT-5") == "MY_PROJECT-5"

    def test_lowercase_is_uppercased(self):
        assert _validate_issue_key("kan-247") == "KAN-247"

    def test_mixed_case_is_uppercased(self):
        assert _validate_issue_key("Kan-247") == "KAN-247"

    def test_whitespace_is_stripped(self):
        assert _validate_issue_key("  KAN-247  ") == "KAN-247"

    def test_lowercase_with_whitespace(self):
        assert _validate_issue_key(" kan-247 ") == "KAN-247"


class TestInvalidIssueKeys:
    def test_empty_string(self):
        with pytest.raises(typer.Abort):
            _validate_issue_key("")

    def test_whitespace_only(self):
        with pytest.raises(typer.Abort):
            _validate_issue_key("   ")

    def test_numeric_project(self):
        with pytest.raises(typer.Abort):
            _validate_issue_key("123-456")

    def test_missing_number(self):
        with pytest.raises(typer.Abort):
            _validate_issue_key("KAN")

    def test_trailing_dash(self):
        with pytest.raises(typer.Abort):
            _validate_issue_key("KAN-")

    def test_non_numeric_id(self):
        with pytest.raises(typer.Abort):
            _validate_issue_key("KAN-abc")

    def test_leading_dash(self):
        with pytest.raises(typer.Abort):
            _validate_issue_key("-KAN-1")

    def test_spaces_in_key(self):
        with pytest.raises(typer.Abort):
            _validate_issue_key("K AN-1")

    def test_no_dash(self):
        with pytest.raises(typer.Abort):
            _validate_issue_key("KAN247")
