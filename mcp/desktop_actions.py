#!/usr/bin/env python3
"""desktop-mcp: desktop-action MCP tools (screenshot/click/type/key/scroll/list_windows/activate_window/open_url).

Serves Streamable HTTP on 127.0.0.1:8932 (loopback only - the auth proxy on
8931 is the only thing that talks to it, same as playwright-mcp on 8930).
X11 work is shelled out to xdotool/imagemagick with list-args (no shell),
DISPLAY=:1. Argument validation is pure functions so it is unit-testable
without an X server (tests/test_desktop_actions.py).
"""
import base64
import os
import re
import subprocess

from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent

DISPLAY = os.environ.get("DISPLAY", ":1")
SCREEN_W, SCREEN_H = 7680, 4320  # generous sanity ceiling for coordinates
MAX_TYPE_LEN = 8192
KEY_RE = re.compile(r"^[a-zA-Z0-9_+:<>.-]{1,64}$")
URL_RE = re.compile(r"^https?://[^\s]{1,2048}$")

mcp = FastMCP(
    "desktop-actions",
    instructions=(
        "X11 desktop actions for the container display :1. Coordinates are "
        "pixels from the top-left of the screen (see screenshot). Use "
        "list_windows + activate_window to steer focus; open_url opens a URL "
        "in the desktop browser."
    ),
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

def validate_point(x, y):
    # bool is a subclass of int - reject it explicitly (True as a coordinate is a bug, not a value)
    if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, int) or not isinstance(y, int):
        raise ValueError("x and y must be integers")
    if not (0 <= x <= SCREEN_W and 0 <= y <= SCREEN_H):
        raise ValueError(f"coordinate ({x},{y}) outside screen bounds {SCREEN_W}x{SCREEN_H}")
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


# ---------- MCP tools ----------

@mcp.tool()
def screenshot() -> ImageContent:
    """Capture the whole desktop as a PNG image."""
    r = subprocess.run(
        ["import", "-window", "root", "png:-"], env=_env(), capture_output=True, timeout=20
    )
    if r.returncode != 0 or not r.stdout.startswith(b"\x89PNG"):
        raise RuntimeError(f"screenshot failed: {r.stderr[:200]!r}")
    return ImageContent(content=base64.b64encode(r.stdout).decode(), mimeType="image/png")


@mcp.tool()
def click(x: int, y: int, button: int = 1, double: bool = False) -> str:
    """Move the pointer to (x, y) and click. button: 1 left, 2 middle, 3 right."""
    x, y = validate_point(x, y)
    button = validate_button(button)
    r = _run(["xdotool", "mousemove", str(x), str(y), "click", "--repeat", "2" if double else "1", str(button)])
    if r.returncode != 0:
        raise RuntimeError(f"click failed: {r.stderr[:200]}")
    return f"clicked {'double ' if double else ''}button {button} at ({x},{y})"


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
    """Scroll the wheel at (x, y). direction: 'up' or 'down'."""
    x, y = validate_point(x, y)
    amount = validate_scroll(amount)
    if direction not in ("up", "down"):
        raise ValueError("direction must be 'up' or 'down'")
    button = "4" if direction == "up" else "5"
    r = _run(["xdotool", "mousemove", str(x), str(y), "click", "--repeat", str(amount), str(button)])
    if r.returncode != 0:
        raise RuntimeError(f"scroll failed: {r.stderr[:200]}")
    return f"scrolled {direction} x{amount} at ({x},{y})"


@mcp.tool()
def list_windows() -> str:
    """List visible windows as 'id | title' lines (id feeds activate_window)."""
    r = _run(["xdotool", "search", "--onlyvisible", "--name", ""])
    if r.returncode != 0:
        raise RuntimeError(f"list_windows failed: {r.stderr[:200]}")
    lines = []
    for wid in r.stdout.split():
        name = _run(["xdotool", "getwindowname", wid])
        title = name.stdout.strip().replace("\n", " ") if name.returncode == 0 else "?"
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
    """Open a URL in the desktop browser (xdg-open / $BROWSER)."""
    url = validate_url(url)
    browser = os.environ.get("BROWSER") or "xdg-open"
    subprocess.Popen([browser, url], env=_env(),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"opening {url}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
