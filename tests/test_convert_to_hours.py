import unittest

from jira_worklog_pkg.utils import convert_to_hours


class TestConvertToHours(unittest.TestCase):

    def test_hours_only(self):
        self.assertEqual(convert_to_hours("7h"), 7.0)

    def test_minutes_only(self):
        self.assertAlmostEqual(convert_to_hours("30m"), 0.5)

    def test_hours_and_minutes(self):
        self.assertAlmostEqual(convert_to_hours("2h 30m"), 2.5)

    def test_days(self):
        self.assertEqual(convert_to_hours("1d"), 24.0)

    def test_weeks(self):
        self.assertEqual(convert_to_hours("1w"), 168.0)

    def test_combined(self):
        self.assertAlmostEqual(convert_to_hours("1d 2h 30m"), 26.5)

    def test_weeks_and_days(self):
        self.assertEqual(convert_to_hours("1w 2d"), 216.0)


if __name__ == '__main__':
    unittest.main()
