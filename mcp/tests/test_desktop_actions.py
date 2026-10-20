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


class TestXga(unittest.TestCase):
    """CU_XGA geometry: xga_fit + map_xga_to_native are pure; the mapping must
    use the same fit as the screenshot or clicks land off-target."""

    def test_fit_landscape(self):
        self.assertEqual(da.xga_fit(1920, 1080), (1024, 576))
        self.assertEqual(da.xga_fit(2560, 1080), (1024, 432))
        self.assertEqual(da.xga_fit(1280, 1024), (960, 768))

    def test_fit_exact_and_upscale(self):
        self.assertEqual(da.xga_fit(1024, 768), (1024, 768))
        self.assertEqual(da.xga_fit(800, 600), (1024, 768))  # upscale to box
        self.assertEqual(da.xga_fit(400, 300), (1024, 768))

    def test_fit_always_inside_box(self):
        for w, h in [(1920, 1080), (7680, 4320), (1024, 768), (3840, 2160), (600, 900)]:
            sw, sh = da.xga_fit(w, h)
            self.assertLessEqual(sw, da.XGA_W, f"{w}x{h} -> {sw}x{sh}")
            self.assertLessEqual(sh, da.XGA_H, f"{w}x{h} -> {sw}x{sh}")

    def test_map_center_and_origin(self):
        # 1920x1080 fits to 1024x576; center of screenshot space -> center of screen
        self.assertEqual(da.map_xga_to_native(512, 288, 1920, 1080), (960, 540))
        self.assertEqual(da.map_xga_to_native(0, 0, 1920, 1080), (0, 0))

    def test_map_bottom_right_clamped(self):
        # fit corner maps to (near) native corner, never past the edge
        for nw, nh in [(1920, 1080), (2560, 1080), (1280, 1024)]:
            sw, sh = da.xga_fit(nw, nh)
            nx, ny = da.map_xga_to_native(sw - 1, sh - 1, nw, nh)
            self.assertTrue(0 <= nx <= nw - 1, f"{nw}x{nh} corner x={nx}")
            self.assertTrue(0 <= ny <= nh - 1, f"{nw}x{nh} corner y={ny}")

    def test_map_roundtrip_proportional(self):
        # a point at fraction f of screenshot space lands at ~f of native
        nw, nh = 2560, 1440
        sw, sh = da.xga_fit(nw, nh)
        nx, ny = da.map_xga_to_native(sw // 2, sh // 2, nw, nh)
        self.assertLessEqual(abs(nx - nw / 2), 2)
        self.assertLessEqual(abs(ny - nh / 2), 2)


if __name__ == "__main__":
    unittest.main()
