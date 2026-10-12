"""Win32 helpers that keep the rug window glued to the desktop.

The rug must sit above the desktop icons but below every other application
window. ``HWND_BOTTOM`` is not enough: the desktop (``Progman``) is itself a
top-level window, so the rug could end up behind it. Instead we insert the rug
directly in front of ``Progman`` and stop clicks from raising it.

Only things Qt cannot do live here. Taskbar hiding uses ``Qt.Tool`` instead.

Windows only. Both functions need a real native handle, so call them after the
widget is shown (``winId()`` is valid). Qt may re-apply window styles while
showing a window, so calling them earlier can be silently undone.
"""


def place_above_desktop(hwnd: int) -> None:
    """Insert the window directly in front of the desktop in the Z-order.

    Finds ``Progman``, takes the window just in front of it
    (``GW_HWNDPREV``), and places this window right behind that one. If no
    window is in front of ``Progman``, the window goes to ``HWND_TOP``, which
    is then directly in front of ``Progman`` anyway.

    Args:
        hwnd: Native handle of the top-level window.

    Raises:
        OSError: If the ``Progman`` window cannot be found.
    """
    raise NotImplementedError


def disable_activation(hwnd: int) -> None:
    """Stop clicks from activating the window and raising it to the front.

    Adds ``WS_EX_NOACTIVATE`` to the existing extended style.

    Args:
        hwnd: Native handle of the top-level window.
    """
    raise NotImplementedError
