import unittest

from jiracli_pkg.main import _is_valid_time_format, _time_to_seconds


class TestTimeFunctions(unittest.TestCase):

    def test_valid_time_formats(self):
        self.assertTrue(_is_valid_time_format("7h"))
        self.assertTrue(_is_valid_time_format("15m"))
        self.assertTrue(_is_valid_time_format("7.5h"))
        self.assertTrue(_is_valid_time_format("2h30m"))
        self.assertTrue(_is_valid_time_format("7.5h20m"))

    def test_invalid_time_formats(self):
        self.assertFalse(_is_valid_time_format("7"))
        self.assertFalse(_is_valid_time_format("abc"))
        self.assertFalse(_is_valid_time_format("5.5"))
        self.assertFalse(_is_valid_time_format(""))

    def test_time_to_seconds(self):
        self.assertEqual(_time_to_seconds("7h"), (25200, 7.0))
        self.assertEqual(_time_to_seconds("30m"), (1800, 0.5))
        self.assertEqual(_time_to_seconds("7h30m"), (27000, 7.5))
        self.assertEqual(_time_to_seconds("7.5h"), (27000, 7.5))
        self.assertEqual(_time_to_seconds("2h45m"), (9900, 2.75))


if __name__ == '__main__':
    unittest.main()
