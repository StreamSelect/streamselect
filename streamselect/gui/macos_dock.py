"""macOS: leave the Dock while only the menu-bar item runs ("Tray Mode" TQ14).

Qt has no call for this, so it is one Objective-C message through ``ctypes``:
``[NSApp setActivationPolicy:]`` with Regular (Dock icon) or Accessory (menu
bar only). Any failure is logged and ignored: the Dock icon staying is harmless.
"""

from __future__ import annotations

import ctypes
import ctypes.util

from loguru import logger

from streamselect.core import runtime_env

_REGULAR = 0
_ACCESSORY = 1


def show_in_dock(visible: bool) -> None:
    """Put the app in the Dock (*visible*) or take it out. No-op off macOS."""
    if not runtime_env.is_macos():
        return
    try:
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        send_ptr = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
        get = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(send_ptr)
        set_policy = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p,
                                      ctypes.c_long)(send_ptr)
        activate = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p,
                                    ctypes.c_bool)(send_ptr)
        app = get(objc.objc_getClass(b"NSApplication"), objc.sel_registerName(b"sharedApplication"))
        set_policy(app, objc.sel_registerName(b"setActivationPolicy:"),
                   _REGULAR if visible else _ACCESSORY)
        if visible:
            activate(app, objc.sel_registerName(b"activateIgnoringOtherApps:"), True)
    except Exception as exc:
        logger.warning("Could not change the Dock icon: {}", exc)
