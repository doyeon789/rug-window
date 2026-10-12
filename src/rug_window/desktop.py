"""Win32 helpers that keep the rug window glued to the desktop.

The rug must sit above the desktop icons but below every other application
window. ``HWND_BOTTOM`` is not enough: the desktop (``Progman``) is itself a
top-level window, so the rug could end up behind it. Instead we insert the rug
directly in front of ``Progman`` and stop clicks from raising it.

Only things Qt cannot do live here. Taskbar hiding uses ``Qt.Tool`` instead.

Windows only. The window helpers need a real native handle, so call them
after the widget is shown (``winId()`` is valid). Qt may re-apply window
styles while showing a window, so calling them earlier can be silently undone.

pywin32 reports Win32 failures as ``pywintypes.error``, which is not an
``OSError``. The helpers convert those failures to ``OSError`` so callers
handle one exception type.
"""

import ctypes
from ctypes import wintypes

import pywintypes
import win32con
import win32gui
import win32process

_SWP_ZORDER_ONLY = win32con.SWP_NOACTIVATE | win32con.SWP_NOMOVE | win32con.SWP_NOSIZE


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

    Assumes the desktop icons (``SHELLDLL_DefView``) live under ``Progman``.
    On some setups (older Windows 10 builds, wallpaper slideshow) they live in
    a ``WorkerW`` window in front of ``Progman`` instead, and the rug would end
    up behind the icons. Not handled yet.

    Args:
        hwnd: Native handle of the top-level window.

    Raises:
        OSError: If ``FindWindow`` returns 0 because ``Progman`` does not
            exist, or if a Win32 call fails.
    """
    _require_window(hwnd)
    progman = win32gui.FindWindow("Progman", None)
    if not progman:
        raise OSError("Progman window not found")
    try:
        insert_after = win32con.HWND_NOTOPMOST
        candidate = win32gui.GetWindow(progman, win32con.GW_HWNDPREV)
        while candidate:
            if candidate != hwnd and not _is_topmost(candidate):
                insert_after = candidate
                break
            candidate = win32gui.GetWindow(candidate, win32con.GW_HWNDPREV)
        win32gui.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, _SWP_ZORDER_ONLY)
    except pywintypes.error as exc:
        raise OSError(f"Could not place window above the desktop: {exc}") from exc


def disable_activation(hwnd: int) -> None:
    """Stop clicks from activating the window and raising it to the front.

    Reads the extended style, ORs in ``WS_EX_NOACTIVATE``, and writes it back,
    so the styles Qt already set (e.g. for translucency) are kept.

    Args:
        hwnd: Native handle of the top-level window.

    Raises:
        OSError: If reading or writing the window style fails.
    """
    # GetWindowLong/SetWindowLong return 0 instead of raising on a bad handle,
    # so check the handle first.
    _require_window(hwnd)
    try:
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(
            hwnd, win32con.GWL_EXSTYLE, style | win32con.WS_EX_NOACTIVATE
        )
    except pywintypes.error as exc:
        raise OSError(f"Could not disable window activation: {exc}") from exc


def _require_window(hwnd: int) -> None:
    if not win32gui.IsWindow(hwnd):
        raise OSError(f"Not a valid window handle: {hwnd:#x}")


def _is_topmost(hwnd: int) -> bool:
    style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    return bool(style & win32con.WS_EX_TOPMOST)


def set_click_through(hwnd: int, enabled: bool) -> None:
    """Let mouse clicks pass through the window to what is underneath.

    Toggles ``WS_EX_TRANSPARENT`` in the extended style (read, change one
    bit, write). The full-screen rug window turns this on wherever the cursor
    is not over the rug, so the desktop stays usable.

    Args:
        hwnd: Native handle of the top-level window.
        enabled: True to let clicks through, False to receive them.

    Raises:
        OSError: If reading or writing the window style fails.
    """
    _require_window(hwnd)
    try:
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if enabled:
            style |= win32con.WS_EX_TRANSPARENT
        else:
            style &= ~win32con.WS_EX_TRANSPARENT
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)
    except pywintypes.error as exc:
        raise OSError(f"Could not change click-through: {exc}") from exc


_LVM_GETITEMCOUNT = 0x1004
_LVM_GETITEMRECT = 0x100E
_LVIR_BOUNDS = 0
_PROCESS_ACCESS = 0x0008 | 0x0010 | 0x0020 | 0x0400  # VM_OPERATION/READ/WRITE, QUERY
_MEM_COMMIT_RESERVE = 0x1000 | 0x2000
_MEM_RELEASE = 0x8000
_PAGE_READWRITE = 0x04


def desktop_icon_rects() -> list[tuple[int, int, int, int]]:
    """Return the screen rectangle of every desktop icon (icon plus label).

    The icon positions live inside Explorer's process, in its desktop list
    view. A ``LVM_GETITEMRECT`` message writes its answer into memory the
    caller points to, and that memory must be in Explorer's process. So we
    borrow a small block there (``VirtualAllocEx``), ask for each icon's
    rectangle into it, and read it back (``ReadProcessMemory``).

    Coordinates are physical pixels relative to the desktop list view, which
    covers the primary screen from its top-left corner.

    Returns:
        ``(left, top, right, bottom)`` per icon. Empty if the desktop list view
        cannot be found (for example, icons hosted under ``WorkerW``).

    Raises:
        OSError: If Explorer's memory cannot be accessed.
    """
    progman = win32gui.FindWindow("Progman", None)
    defview = win32gui.FindWindowEx(progman, 0, "SHELLDLL_DefView", None)
    list_view = win32gui.FindWindowEx(defview, 0, "SysListView32", None)
    if not list_view:
        return []
    count = win32gui.SendMessage(list_view, _LVM_GETITEMCOUNT, 0, 0)
    _, pid = win32process.GetWindowThreadProcessId(list_view)

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.VirtualAllocEx.restype = ctypes.c_void_p
    kernel32.VirtualAllocEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.c_size_t,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    kernel32.VirtualFreeEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.c_size_t,
        wintypes.DWORD,
    ]
    for name in ("ReadProcessMemory", "WriteProcessMemory"):
        getattr(kernel32, name).argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
        ]

    process = kernel32.OpenProcess(_PROCESS_ACCESS, False, pid)
    if not process:
        raise OSError(ctypes.get_last_error(), "Could not open Explorer process")
    rect = wintypes.RECT()
    size = ctypes.sizeof(rect)
    remote = kernel32.VirtualAllocEx(
        process, None, size, _MEM_COMMIT_RESERVE, _PAGE_READWRITE
    )
    if not remote:
        kernel32.CloseHandle(process)
        raise OSError(ctypes.get_last_error(), "Could not allocate in Explorer")
    rects = []
    try:
        for index in range(count):
            # LVM_GETITEMRECT reads which rectangle to return from .left.
            rect.left = _LVIR_BOUNDS
            if not kernel32.WriteProcessMemory(
                process, remote, ctypes.byref(rect), size, None
            ):
                raise OSError(ctypes.get_last_error(), "WriteProcessMemory failed")
            if not win32gui.SendMessage(list_view, _LVM_GETITEMRECT, index, remote):
                continue
            if not kernel32.ReadProcessMemory(
                process, remote, ctypes.byref(rect), size, None
            ):
                raise OSError(ctypes.get_last_error(), "ReadProcessMemory failed")
            rects.append((rect.left, rect.top, rect.right, rect.bottom))
    finally:
        kernel32.VirtualFreeEx(process, remote, 0, _MEM_RELEASE)
        kernel32.CloseHandle(process)
    return rects
