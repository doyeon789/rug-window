"""Win32 helpers that keep the rug window glued to the desktop.

The rug must sit above the desktop icons but below every other application
window. We get there by keeping the window at the bottom of the Z-order
(``HWND_BOTTOM``) and pushing it back down whenever Windows raises it.
"""


def hide_from_taskbar(hwnd: int) -> None:
    """Mark the window as a tool window so it has no taskbar button.

    Args:
        hwnd: Native handle of the top-level window.
    """
    raise NotImplementedError


def send_to_bottom(hwnd: int) -> None:
    """Move the window to the bottom of the Z-order without activating it.

    Args:
        hwnd: Native handle of the top-level window.
    """
    raise NotImplementedError
