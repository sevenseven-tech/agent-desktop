#!/usr/bin/env python3
"""desktop-mcp: desktop-action MCP tools (screenshot/click/type/key/scroll/list_windows/activate_window/open_url).

Serves Streamable HTTP on 127.0.0.1:8932 (loopback only - the auth proxy on
8931 is the only thing that talks to it, same as playwright-mcp on 8930).
X11 work is shelled out to xdotool/imagemagick with list-args (no shell),
DISPLAY=:1. Argument validation is pure functions so it is unit-testable
without an X server (tests/test_desktop_actions.py).
"""
import os
import re
import subprocess

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.types import Image

DISPLAY = os.environ.get("DISPLAY", ":1")
SCREEN_W, SCREEN_H = 7680, 4320  # generous sanity ceiling for coordinates
MAX_TYPE_LEN = 8192
KEY_RE = re.compile(r"^[a-zA-Z0-9_+:<>.-]{1,64}$")
URL_RE = re.compile(r"^https?://[^\s]{1,2048}$")

# Pixel-based computer-use models (Anthropic computer-use style) perform best
# on XGA screenshots. With CU_XGA on, screenshot() fits the desktop into a
# 1024x768 box and click/scroll take coordinates in THAT screenshot space,
# auto-mapped back to native display pixels. Default off: coordinates stay
# native, behavior identical to pre-#19.
CU_XGA = os.environ.get("CU_XGA", "").strip().lower() in ("1", "true", "yes")
XGA_W, XGA_H = 1024, 768

_INSTRUCTIONS = (
    "X11 desktop actions for the container display :1. Coordinates are "
    "pixels from the top-left of the screen (see screenshot). Use "
    "list_windows + activate_window to steer focus; open_url opens a URL "
    "in the desktop browser."
)
if CU_XGA:
    _INSTRUCTIONS += (
        " CU_XGA mode: screenshots are scaled to fit 1024x768; give "
        "click/scroll coordinates in SCREENSHOT space - they are mapped to "
        "native resolution automatically."
    )

mcp = FastMCP(
    "desktop-actions",
    instructions=_INSTRUCTIONS,
    host="127.0.0.1",
    port=8932,
    streamable_http_path="/mcp",
)


def _env():
    e = dict(os.environ)
    e["DISPLAY"] = DISPLAY
    return e


def _run(args, timeout=10):
    return subprocess.run(args, env=_env(), capture_output=True, text=True, timeout=timeout)


# ---------- pure validators (unit-tested) ----------

def xga_fit(w, h):
    """Screenshot size for a native (w, h) display in CU_XGA mode: fit inside
    the 1024x768 box, aspect preserved, small screens upscaled - same semantics
    as ImageMagick '-resize 1024x768'. Pure; used by both screenshot() and the
    coordinate mapping so the two never disagree."""
    scale = min(XGA_W / w, XGA_H / h)
    return max(1, round(w * scale)), max(1, round(h * scale))


def map_xga_to_native(x, y, native_w, native_h):
    """Map a (x, y) point from CU_XGA screenshot space to native display
    pixels using the same fit geometry as xga_fit(); clamped in-bounds.
    May differ from the actual JPEG size by <=1 px due to ImageMagick
    rounding - irrelevant for pointer placement."""
    sw, sh = xga_fit(native_w, native_h)
    nx = min(native_w - 1, max(0, round(x * native_w / sw)))
    ny = min(native_h - 1, max(0, round(y * native_h / sh)))
    return nx, ny


def native_geometry():
    """Native display size (W, H) from xdotool; raises if unreadable."""
    r = _run(["xdotool", "getdisplaygeometry"])
    m = re.fullmatch(r"(\d{2,5})\s+(\d{2,5})", r.stdout.strip()) if r.returncode == 0 else None
    if not m:
        raise RuntimeError(f"CU_XGA on but display geometry unreadable: {r.stderr[:120]!r}")
    return int(m.group(1)), int(m.group(2))


def validate_point(x, y, max_x=SCREEN_W, max_y=SCREEN_H):
    # bool is a subclass of int - reject it explicitly (True as a coordinate is a bug, not a value)
    if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, int) or not isinstance(y, int):
        raise ValueError("x and y must be integers")
    if not (0 <= x <= max_x and 0 <= y <= max_y):
        raise ValueError(f"coordinate ({x},{y}) outside screen bounds {max_x}x{max_y}")
    return x, y


def validate_button(button):
    if button not in (1, 2, 3):
        raise ValueError("button must be 1 (left), 2 (middle) or 3 (right)")
    return button


def validate_text(text):
    if not isinstance(text, str) or not text:
        raise ValueError("text must be a non-empty string")
    if len(text) > MAX_TYPE_LEN:
        raise ValueError(f"text too long (max {MAX_TYPE_LEN})")
    if any(ord(c) < 32 and c not in "\n\t" for c in text):
        raise ValueError("text contains control characters")
    return text


def validate_key(key):
    if not isinstance(key, str) or not KEY_RE.fullmatch(key):
        raise ValueError("key must be an xdotool keysym combo like 'ctrl+s' or 'Return'")
    return key


def validate_window_id(window_id):
    s = str(window_id).strip()
    if not re.fullmatch(r"0[xX][0-9a-fA-F]{1,16}|\d{1,16}", s):
        raise ValueError("window_id must be a window id from list_windows")
    return s


def validate_url(url):
    if not isinstance(url, str) or len(url) > 2048 or not URL_RE.fullmatch(url):
        raise ValueError("url must start with http:// or https:// (max 2048 chars)")
    return url


def validate_scroll(amount):
    if not isinstance(amount, int) or not (1 <= amount <= 20):
        raise ValueError("amount must be an integer 1..20")
    return amount


def _resolve_point(x, y):
    """Validate a user-supplied point and return (native_x, native_y).
    CU_XGA off: point is native. CU_XGA on: point is CU_XGA screenshot
    space (bounds = fit box) and gets mapped to native pixels."""
    if not CU_XGA:
        return validate_point(x, y)
    nw, nh = native_geometry()
    sw, sh = xga_fit(nw, nh)
    validate_point(x, y, max_x=sw, max_y=sh)
    return map_xga_to_native(x, y, nw, nh)


# ---------- MCP tools ----------

@mcp.tool()
def screenshot() -> Image:
    """Capture the whole desktop as a JPEG image.

    JPEG + downscale, not PNG: MCP clients cap single SSE events (httpx2 /
    SDK 2.x hard-limit 1 MiB) and a PNG of a busy webpage at native res
    exceeds it (~1.2 MB observed), which kills the call with 'SSE stream
    ended without a response'. Target stays well under the cap.

    CU_XGA mode: fits the image into 1024x768 instead (aspect preserved)
    for pixel-based computer-use models; click/scroll then expect
    coordinates in this scaled space and map them automatically."""
    if CU_XGA:
        r = subprocess.run(
            ["import", "-window", "root", "-resize", f"{XGA_W}x{XGA_H}",
             "-quality", "85", "jpg:-"],
            env=_env(), capture_output=True, timeout=20,
        )
        if r.returncode != 0 or not r.stdout.startswith(b"\xff\xd8"):
            raise RuntimeError(f"screenshot failed: {r.stderr[:200]!r}")
        return Image(data=r.stdout, format="jpeg")
    r = subprocess.run(
        ["import", "-window", "root", "-resize", "1600x>", "-quality", "85", "jpg:-"],
        env=_env(), capture_output=True, timeout=20,
    )
    if r.returncode != 0 or not r.stdout.startswith(b"\xff\xd8"):
        raise RuntimeError(f"screenshot failed: {r.stderr[:200]!r}")
    if len(r.stdout) > 700_000:  # still huge -> re-encode smaller
        r2 = subprocess.run(
            ["convert", "jpg:-", "-resize", "1280x>", "-quality", "70", "jpg:-"],
            input=r.stdout, capture_output=True, timeout=20,
        )
        if r2.returncode == 0 and r2.stdout.startswith(b"\xff\xd8") and len(r2.stdout) < len(r.stdout):
            r = r2
    return Image(data=r.stdout, format="jpeg")


@mcp.tool()
def click(x: int, y: int, button: int = 1, double: bool = False) -> str:
    """Move the pointer to (x, y) and click. button: 1 left, 2 middle, 3 right.
    In CU_XGA mode (x, y) is in screenshot space; otherwise native pixels."""
    nx, ny = _resolve_point(x, y)
    button = validate_button(button)
    r = _run(["xdotool", "mousemove", str(nx), str(ny), "click", "--repeat", "2" if double else "1", str(button)])
    if r.returncode != 0:
        raise RuntimeError(f"click failed: {r.stderr[:200]}")
    mapped = f" from screenshot-space ({x},{y})" if CU_XGA else ""
    return f"clicked {'double ' if double else ''}button {button} at ({nx},{ny}){mapped}"


@mcp.tool()
def type_text(text: str) -> str:
    """Type text into the currently focused window."""
    text = validate_text(text)
    r = _run(["xdotool", "type", "--clearmodifiers", "--delay", "12", text], timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"type failed: {r.stderr[:200]}")
    return f"typed {len(text)} chars"


@mcp.tool()
def key(combo: str) -> str:
    """Press a key or chord, e.g. 'Return', 'ctrl+s', 'alt+F4', 'ctrl+shift+t'."""
    combo = validate_key(combo)
    r = _run(["xdotool", "key", "--clearmodifiers", combo])
    if r.returncode != 0:
        raise RuntimeError(f"key failed: {r.stderr[:200]}")
    return f"pressed {combo}"


@mcp.tool()
def scroll(x: int, y: int, amount: int = 3, direction: str = "down") -> str:
    """Scroll the wheel at (x, y). direction: 'up' or 'down'.
    In CU_XGA mode (x, y) is in screenshot space; otherwise native pixels."""
    nx, ny = _resolve_point(x, y)
    amount = validate_scroll(amount)
    if direction not in ("up", "down"):
        raise ValueError("direction must be 'up' or 'down'")
    button = "4" if direction == "up" else "5"
    r = _run(["xdotool", "mousemove", str(nx), str(ny), "click", "--repeat", str(amount), str(button)])
    if r.returncode != 0:
        raise RuntimeError(f"scroll failed: {r.stderr[:200]}")
    mapped = f" from screenshot-space ({x},{y})" if CU_XGA else ""
    return f"scrolled {direction} x{amount} at ({nx},{ny}){mapped}"


@mcp.tool()
def list_windows() -> str:
    """List visible windows as 'id | title' lines (id feeds activate_window)."""
    r = _run(["xdotool", "search", "--onlyvisible", "--name", ""])
    if r.returncode != 0:
        raise RuntimeError(f"list_windows failed: {r.stderr[:200]}")
    lines = []
    for wid in r.stdout.split():
        name = _run(["xdotool", "getwindowname", wid])
        title = name.stdout.strip().replace("\n", " ") if name.returncode == 0 else ""
        if title:  # skip unnamed override-redirect/desktop windows
            lines.append(f"{wid} | {title}")
    return "\n".join(lines) if lines else "no visible windows"


@mcp.tool()
def activate_window(window_id: str) -> str:
    """Focus/raise a window by id from list_windows."""
    wid = validate_window_id(window_id)
    r = _run(["xdotool", "windowactivate", "--sync", wid], timeout=15)
    if r.returncode != 0:
        raise RuntimeError(f"activate_window failed: {r.stderr[:200]}")
    return f"activated window {wid}"


@mcp.tool()
def open_url(url: str) -> str:
    """Open a URL as a new tab in the RUNNING browser. Uses CDP (the live
    logged-in instance); falls back to xdg-open/$BROWSER when CDP is down.
    (Launching $BROWSER directly would spawn a SECOND instance on another
    profile - invisible to CDP and to the agent's browser tools.)"""
    url = validate_url(url)
    r = _run(["curl", "-sf", "-m", "5", "-X", "PUT", f"http://127.0.0.1:9222/json/new?{url}"])
    if r.returncode == 0:
        return f"opened {url} as a new tab in the running browser (CDP)"
    browser = os.environ.get("BROWSER") or "xdg-open"
    subprocess.Popen([browser, url], env=_env(),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"CDP unavailable, opened {url} via {browser}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
