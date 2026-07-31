import unittest

from jiracli_pkg.main import _is_iso_date_format


class TestIsoDateFormat(unittest.TestCase):

    def test_valid_date(self):
        self.assertTrue(_is_iso_date_format("2024-01-15"))

    def test_valid_end_of_month(self):
        self.assertTrue(_is_iso_date_format("2024-12-31"))

    def test_valid_first_day(self):
        self.assertTrue(_is_iso_date_format("2024-01-01"))

    def test_none_input(self):
        self.assertFalse(_is_iso_date_format(None))

    def test_empty_string(self):
        self.assertFalse(_is_iso_date_format(""))

    def test_wrong_separator(self):
        self.assertFalse(_is_iso_date_format("2024/01/15"))

    def test_incomplete_date(self):
        self.assertFalse(_is_iso_date_format("2024-01"))

    def test_invalid_month(self):
        self.assertFalse(_is_iso_date_format("2024-13-01"))

    def test_invalid_day(self):
        self.assertFalse(_is_iso_date_format("2024-01-32"))

    def test_no_leading_zeros(self):
        self.assertFalse(_is_iso_date_format("2024-1-5"))


if __name__ == '__main__':
    unittest.main()
