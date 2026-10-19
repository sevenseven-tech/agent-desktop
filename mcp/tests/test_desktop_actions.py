"""Unit tests for desktop_actions validators - pure, no X server needed.
Run inside the mcp image: /opt/dmcp/bin/python -m unittest /app/tests/test_desktop_actions.py
or locally with any python that can import the module (mcp SDK required)."""
import sys
import unittest

sys.path.insert(0, "/app")
sys.path.insert(0, __file__.rsplit("/tests/", 1)[0])  # allow running from repo checkout

import desktop_actions as da  # noqa: E402


class TestValidators(unittest.TestCase):
    def test_point_ok(self):
        self.assertEqual(da.validate_point(0, 0), (0, 0))
        self.assertEqual(da.validate_point(1919, 1079), (1919, 1079))

    def test_point_rejects(self):
        for bad in [(-1, 0), (0, -1), (99999, 0), (0, 99999), ("1", 2), (1.5, 2), (True, 2)]:
            with self.assertRaises(ValueError, msg=str(bad)):
                da.validate_point(*bad)

    def test_button(self):
        for b in (1, 2, 3):
            self.assertEqual(da.validate_button(b), b)
        for b in (0, 4, -1, "1", None):
            with self.assertRaises(ValueError, msg=str(b)):
                da.validate_button(b)

    def test_text(self):
        self.assertEqual(da.validate_text("hello world"), "hello world")
        self.assertEqual(da.validate_text("tab\there\nnl"), "tab\there\nnl")
        for bad in ["", "x" * (da.MAX_TYPE_LEN + 1), "bell\x07here", "nul\x00", None, 42]:
            with self.assertRaises(ValueError, msg=repr(bad)[:40]):
                da.validate_text(bad)

    def test_key(self):
        for ok in ["Return", "ctrl+s", "alt+F4", "ctrl+shift+t", "super", "KP_Enter", "a"]:
            self.assertEqual(da.validate_key(ok), ok)
        for bad in ["ctrl+s; rm -rf /", "key with space", "", "x" * 65, "$(id)", "ctrl+`"]:
            with self.assertRaises(ValueError, msg=bad):
                da.validate_key(bad)

    def test_window_id(self):
        for ok in ["0x1234abcd", "123456", "0X1"]:
            self.assertEqual(da.validate_window_id(ok), ok)
        for bad in ["", "0x", "abc", "1; xdotool key ctrl+alt+f12", "0x1234567890abcdef00"]:
            with self.assertRaises(ValueError, msg=bad):
                da.validate_window_id(bad)

    def test_url(self):
        self.assertEqual(da.validate_url("https://example.com/x?a=1&b=2"), "https://example.com/x?a=1&b=2")
        self.assertEqual(da.validate_url("http://localhost:8080"), "http://localhost:8080")
        for bad in ["ftp://example.com", "javascript:alert(1)", "https://a b", "", "https://" + "x" * 2048, None]:
            with self.assertRaises(ValueError, msg=repr(bad)[:40]):
                da.validate_url(bad)

    def test_scroll(self):
        self.assertEqual(da.validate_scroll(1), 1)
        self.assertEqual(da.validate_scroll(20), 20)
        for bad in [0, 21, -1, "3", None]:
            with self.assertRaises(ValueError, msg=str(bad)):
                da.validate_scroll(bad)


if __name__ == "__main__":
    unittest.main()
