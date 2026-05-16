"""
login_window.py — Native macOS WebKit login window for Cursor.

Opens cursor.com/settings in a native WKWebView, polls for the
WorkosCursorSessionToken cookie, and calls on_success(token) when found.

SECURITY NOTE:
  - This module makes NO outbound network calls of its own.
  - The WKWebView loads cursor.com directly — identical to opening Safari.
  - The token is extracted from the browser's cookie store locally.
  - The token is ONLY ever sent to cursor.com/api/usage-summary (see app.py).
  - No telemetry, no analytics, no third-party requests.
"""

from __future__ import annotations
from typing import Callable, Optional

import AppKit
import Foundation
import objc

try:
    import WebKit
    _HAS_WEBKIT = True
except ImportError:
    _HAS_WEBKIT = False


# ---------------------------------------------------------------------------
# Window delegate — detects manual window close (user cancels)
# ---------------------------------------------------------------------------

class _LoginDelegate(AppKit.NSObject):
    """NSWindowDelegate that fires on_cancel when the user closes the window."""

    @objc.python_method
    def set_callbacks(self, on_cancel: Optional[Callable]):
        self._on_cancel = on_cancel
        self._cancelled = False

    def windowWillClose_(self, notification):
        if not self._cancelled and self._on_cancel:
            self._on_cancel()

    @objc.python_method
    def mark_done(self):
        self._cancelled = True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_available() -> bool:
    """Returns True if WebKit bindings are available (pyobjc-framework-WebKit)."""
    return _HAS_WEBKIT


def open_login_window(
    on_success: Callable[[str], None],
    on_cancel: Optional[Callable] = None,
) -> None:
    """
    Opens a native WKWebView window pointing to cursor.com/settings.
    Polls the cookie store every 1.5 s; calls on_success(token) once found.
    Must be called from the main thread.
    """
    if not _HAS_WEBKIT:
        raise RuntimeError(
            "WebKit bindings not found. Install with: pip install pyobjc-framework-WebKit"
        )

    # --- Window ---
    frame = AppKit.NSMakeRect(0, 0, 980, 720)
    style = (
        AppKit.NSWindowStyleMaskTitled
        | AppKit.NSWindowStyleMaskClosable
        | AppKit.NSWindowStyleMaskResizable
        | AppKit.NSWindowStyleMaskMiniaturizable
    )
    win = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        frame, style, AppKit.NSBackingStoreBuffered, False
    )
    win.setTitle_("Cursor — přihlásit se")
    win.center()

    # --- WebView ---
    wk_config = WebKit.WKWebViewConfiguration.new()
    wk_view = WebKit.WKWebView.alloc().initWithFrame_configuration_(
        win.contentView().bounds(), wk_config
    )
    wk_view.setAutoresizingMask_(
        AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable
    )

    url = Foundation.NSURL.URLWithString_("https://cursor.com/settings")
    req = Foundation.NSURLRequest.requestWithURL_(url)
    wk_view.loadRequest_(req)

    win.setContentView_(wk_view)

    # --- Delegate ---
    delegate = _LoginDelegate.new()
    delegate.set_callbacks(on_cancel)
    win.setDelegate_(delegate)

    # --- Cookie poller ---
    cookie_store = wk_config.websiteDataStore().httpCookieStore()
    _timer_holder: list = []  # mutable ref so the block can stop the timer

    def _poll(timer):
        def _handle_cookies(cookies):
            for c in cookies:
                if c.name() == "WorkosCursorSessionToken" and c.value():
                    if _timer_holder:
                        _timer_holder[0].invalidate()
                    delegate.mark_done()
                    win.close()
                    on_success(c.value())

        cookie_store.getAllCookies_(_handle_cookies)

    timer = Foundation.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
        1.5, True, _poll
    )
    _timer_holder.append(timer)

    # Keep strong references so ARC doesn't collect them
    win._wk_view = wk_view
    win._delegate = delegate
    win._timer = timer

    win.makeKeyAndOrderFront_(None)
    AppKit.NSApp.activateIgnoringOtherApps_(True)
