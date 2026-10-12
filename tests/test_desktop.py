"""Tests for the Win32 helpers in ``rug_window.desktop``.

Each test runs against a real, hidden top-level Win32 window, so it needs
Windows.
"""

import sys
from collections.abc import Iterator

import pytest

if sys.platform != "win32":
    pytest.skip("Win32-only helpers", allow_module_level=True)

import win32api
import win32con
import win32gui

from rug_window.desktop import disable_activation

# A style bit Qt or Windows might already have set, which must survive.
EXISTING_STYLE = win32con.WS_EX_TOOLWINDOW
_WINDOW_CLASS = "RugWindowTestWindow"


@pytest.fixture(scope="module")
def window_class() -> Iterator[str]:
    """Register a minimal window class once for this module."""
    wc = win32gui.WNDCLASS()
    wc.lpszClassName = _WINDOW_CLASS
    wc.lpfnWndProc = win32gui.DefWindowProc
    wc.hInstance = win32api.GetModuleHandle(None)
    win32gui.RegisterClass(wc)
    yield _WINDOW_CLASS
    win32gui.UnregisterClass(_WINDOW_CLASS, wc.hInstance)


@pytest.fixture
def hwnd(window_class: str) -> Iterator[int]:
    """Create a hidden top-level window that already has ``EXISTING_STYLE``."""
    handle = win32gui.CreateWindowEx(
        EXISTING_STYLE,
        window_class,
        "rug-window test",
        win32con.WS_OVERLAPPED,
        0,
        0,
        100,
        100,
        0,
        0,
        win32api.GetModuleHandle(None),
        None,
    )
    yield handle
    win32gui.DestroyWindow(handle)


def _ex_style(hwnd: int) -> int:
    return win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)


def test_disable_activation_keeps_existing_style_bits(hwnd: int) -> None:
    disable_activation(hwnd)

    assert _ex_style(hwnd) & EXISTING_STYLE


def test_disable_activation_sets_noactivate(hwnd: int) -> None:
    disable_activation(hwnd)

    assert _ex_style(hwnd) & win32con.WS_EX_NOACTIVATE


def test_disable_activation_twice_gives_same_style(hwnd: int) -> None:
    disable_activation(hwnd)
    style_after_once = _ex_style(hwnd)

    disable_activation(hwnd)

    assert _ex_style(hwnd) == style_after_once
