"""
The taskbar icon (owner, 2026-10-12): the installed Cadet Foundry runs with no window, so closing the browser tab
doesn't stop it and nothing showed that it was running. Now an icon sits in the notification area (bottom right of the
taskbar) while it runs: hover says it's running and where it saves, a click opens it, right-click has Open and Quit.

Windows only, standard library only (ctypes and Windows' own Shell_NotifyIcon) -- nothing extra is bundled.
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    user32, shell32, kernel32 = ctypes.windll.user32, ctypes.windll.shell32, ctypes.windll.kernel32
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                    ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                    ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]

    class NOTIFYICONDATAW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                    ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                    ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                    ("szInfo", wintypes.WCHAR * 256), ("uVersion", wintypes.UINT), ("szInfoTitle", wintypes.WCHAR * 64),
                    ("dwInfoFlags", wintypes.DWORD), ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", wintypes.HICON)]

    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = LRESULT
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                       wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                                  wintypes.UINT]
    user32.CreatePopupMenu.restype = wintypes.HMENU
    user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                      wintypes.HWND, wintypes.LPVOID]
    user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE

WM_DESTROY, WM_CLOSE, WM_NULL = 0x0002, 0x0010, 0x0000
WM_TRAY = 0x0400 + 20
WM_LBUTTONUP, WM_RBUTTONUP = 0x0202, 0x0205
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x1, 0x2, 0x4, 0x10
TPM_RIGHTBUTTON, TPM_RETURNCMD = 0x2, 0x100
MF_STRING, MF_SEPARATOR = 0x0, 0x800
ID_OPEN, ID_QUIT = 1, 2
ICON = Path(__file__).resolve().parent.parent / "web" / "icon.ico"


class Tray:
    """One icon. start() returns once it's showing (or failed); stop() removes it."""

    def __init__(self, on_open, on_quit, tip: str, hint: str = ""):
        self.on_open, self.on_quit, self.tip, self.hint = on_open, on_quit, tip[:127], hint
        self.hwnd = None
        self._icon = None
        self._taskbar_created = None
        self.ok = False
        self._ready = threading.Event()
        self._proc = None                                  # kept alive: ctypes callbacks must not be collected

    # ── the window that receives the icon's clicks ──────────────────────────
    def _data(self, flags: int) -> "NOTIFYICONDATAW":
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd, nid.uID, nid.uFlags, nid.uCallbackMessage = self.hwnd, 1, flags, WM_TRAY
        nid.hIcon = self._icon
        nid.szTip = self.tip
        return nid

    def _menu(self) -> None:
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING, ID_OPEN, "Open Cadet Foundry")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, ID_QUIT, "Quit Cadet Foundry")
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self.hwnd)              # so the menu closes when you click elsewhere
        cmd = user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_RETURNCMD, pt.x, pt.y, 0, self.hwnd, None)
        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(menu)
        self._command(cmd)

    def _command(self, cmd: int) -> None:
        if cmd == ID_OPEN:
            self.on_open()
        elif cmd == ID_QUIT:
            self.on_quit()

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAY:
            event = lparam & 0xFFFF
            if event == WM_LBUTTONUP:
                self.on_open()
            elif event == WM_RBUTTONUP:
                self._menu()
            return 0
        if msg == self._taskbar_created:                   # Windows Explorer restarted: put the icon back
            shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._data(NIF_MESSAGE | NIF_ICON | NIF_TIP)))
            return 0
        if msg == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._data(0)))
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _run(self) -> None:
        try:
            hinst = kernel32.GetModuleHandleW(None)
            self._proc = WNDPROC(self._wndproc)
            wc = WNDCLASSW()
            wc.lpfnWndProc, wc.hInstance, wc.lpszClassName = self._proc, hinst, f"CadetFoundryTray{os.getpid()}"
            user32.RegisterClassW(ctypes.byref(wc))
            self._taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")
            self.hwnd = user32.CreateWindowExW(0, wc.lpszClassName, "Cadet Foundry", 0, 0, 0, 0, 0, None, None, hinst, None)
            size = user32.GetSystemMetrics(49)              # SM_CXSMICON: the tray's own icon size
            self._icon = user32.LoadImageW(None, str(ICON), 1, size, size, 0x10) if ICON.exists() else None
            if not self._icon:
                self._icon = user32.LoadIconW(None, ctypes.c_void_p(32512))   # IDI_APPLICATION
            nid = self._data(NIF_MESSAGE | NIF_ICON | NIF_TIP | (NIF_INFO if self.hint else 0))
            if self.hint:                                  # a one-time "it's down here" balloon
                nid.szInfoTitle, nid.szInfo, nid.dwInfoFlags = "Cadet Foundry is running", self.hint[:255], 0x1
            self.ok = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)))
        except Exception:                                   # no tray (a server edition, a locked-down PC): run without
            self.ok = False
        finally:
            self._ready.set()
        if not self.ok:
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def start(self) -> bool:
        if sys.platform != "win32":
            return False
        threading.Thread(target=self._run, daemon=True, name="tray").start()
        self._ready.wait(5)
        return self.ok

    def set_tip(self, tip: str) -> None:
        if self.ok and self.hwnd:
            self.tip = tip[:127]
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._data(NIF_TIP)))

    def stop(self) -> None:
        if self.ok and self.hwnd:
            user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
            self.ok = False
