"""Win32 helpers that keep the rug window glued to the desktop.

The rug must sit above the desktop icons but below every other application
window. ``HWND_BOTTOM`` is not enough: the desktop (``Progman``) is itself a
top-level window, so the rug could end up behind it. Instead we insert the rug
directly in front of ``Progman`` and stop clicks from raising it.

Only things Qt cannot do live here. Taskbar hiding uses ``Qt.Tool`` instead.

Windows only. Both functions need a real native handle, so call them after the
widget is shown (``winId()`` is valid). Qt may re-apply window styles while
showing a window, so calling them earlier can be silently undone. ``main``
owns these calls.

pywin32 reports Win32 failures as ``pywintypes.error``, which is not an
``OSError``. Both functions convert those failures to ``OSError`` so callers
handle one exception type.
"""


def place_above_desktop(hwnd: int) -> None:
    """Insert the window directly in front of the desktop in the Z-order.

    Finds ``Progman`` and walks forward through the Z-order
    (``GW_HWNDPREV``), skipping this window and any window with
    ``WS_EX_TOPMOST``. Inserting behind a topmost window would make this window
    topmost too, so it would float above every app. This window is then placed
    right behind the first normal window found. If there is none, every window
    in front of ``Progman`` is topmost, and ``HWND_NOTOPMOST`` puts this window
    in front of all non-topmost windows, which is directly in front of
    ``Progman``.

    Uses ``SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE`` so the call changes only
    the Z-order and does not steal focus.

    Args:
        hwnd: Native handle of the top-level window.

    Raises:
        OSError: If ``FindWindow`` returns 0 because ``Progman`` does not
            exist, or if a Win32 call fails.
    """
    raise NotImplementedError


def disable_activation(hwnd: int) -> None:
    """Stop clicks from activating the window and raising it to the front.

    Reads the extended style, ORs in ``WS_EX_NOACTIVATE``, and writes it back,
    so the styles Qt already set (e.g. for translucency) are kept.

    Args:
        hwnd: Native handle of the top-level window.

    Raises:
        OSError: If reading or writing the window style fails.
    """
    raise NotImplementedError
