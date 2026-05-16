#!/usr/bin/env python3
"""
Cursor Usage Menu Bar App
Zobrazuje aktuální stav plan & usage z cursor.com v menu baru macOS.
Ikona: dvě procenta nad sebou + USD vedle. Menu: jen zbývající dny.
"""

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional

import rumps
import AppKit
import login_window as _login_window

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_PATH = os.path.expanduser(
    "~/Library/Application Support/cursor-usage/config.json"
)
CURSOR_COOKIES_DB = os.path.expanduser(
    "~/Library/Application Support/Cursor/Partitions/cursor-browser/Cookies"
)
REFRESH_INTERVAL_DEFAULT = 300
REFRESH_INTERVALS = [
    (60,   "1 minuta"),
    (300,  "5 minut"),
    (900,  "15 minut"),
    (1800, "30 minut"),
    (3600, "60 minut"),
]
BASE_URL = "https://cursor.com"


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(data: dict) -> None:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)


def load_token() -> Optional[str]:
    return _load_config().get("session_token") or None


def save_token(token: str) -> None:
    data = _load_config()
    data["session_token"] = token
    _save_config(data)


def load_refresh_interval() -> int:
    val = _load_config().get("refresh_interval", REFRESH_INTERVAL_DEFAULT)
    valid = [s for s, _ in REFRESH_INTERVALS]
    return val if val in valid else REFRESH_INTERVAL_DEFAULT


def save_refresh_interval(seconds: int) -> None:
    data = _load_config()
    data["refresh_interval"] = seconds
    _save_config(data)


def _decrypt_mac_cookie(encrypted_value: bytes) -> str:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    result = subprocess.run(
        ["security", "find-generic-password", "-w", "-s", "Cursor Safe Storage"],
        capture_output=True, text=True,
    )
    password = result.stdout.strip() or "peanuts"
    key = PBKDF2HMAC(
        algorithm=hashes.SHA1(), length=16, salt=b"saltysalt",
        iterations=1003, backend=default_backend(),
    ).derive(password.encode("utf-8"))
    payload = encrypted_value[3:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(b" " * 16), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted = decryptor.update(payload) + decryptor.finalize()
    return decrypted[:-decrypted[-1]].decode("utf-8")


def try_read_token_from_cursor_cookies() -> Optional[str]:
    if not os.path.exists(CURSOR_COOKIES_DB):
        return None
    tmp = tempfile.mktemp(suffix=".db")
    try:
        shutil.copy2(CURSOR_COOKIES_DB, tmp)
        conn = sqlite3.connect(tmp)
        row = conn.execute(
            "SELECT value, encrypted_value FROM cookies "
            "WHERE name = 'WorkosCursorSessionToken' LIMIT 1"
        ).fetchone()
        conn.close()
        if not row:
            return None
        value, encrypted = row
        if value:
            return value
        if encrypted:
            return _decrypt_mac_cookie(encrypted)
    except Exception:
        return None
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def fetch_usage_summary(token: str) -> dict:
    req = urllib.request.Request(
        f"{BASE_URL}/api/usage-summary",
        headers={
            "Cookie": f"WorkosCursorSessionToken={token}",
            "User-Agent": "cursor-usage-menubar/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Menu bar ikona — kreslená přes NSImage (moderní přístup, bez setView_)
# Layout:  auto%  | days
#          named% | $od
# ---------------------------------------------------------------------------

_FONT_SIZE = 8.5
_GAP_PX   = 2.0   # mezera mezi dvěma řádky
_SEP_PX   = 5.0   # horizontální mezera mezi sloupci
_PAD_R    = 3.0   # pravý padding

def _icon_attrs():
    font = AppKit.NSFont.monospacedDigitSystemFontOfSize_weight_(
        _FONT_SIZE, AppKit.NSFontWeightMedium
    )
    return font, {
        AppKit.NSFontAttributeName: font,
        AppKit.NSForegroundColorAttributeName: AppKit.NSColor.controlTextColor(),
    }


def _text_w(text: str, attrs: dict) -> float:
    return AppKit.NSString.stringWithString_(text).sizeWithAttributes_(attrs).width


def build_status_icon(auto_pct: float, api_pct: float,
                      od_str: str, days_str: str) -> AppKit.NSImage:
    """
    Vrátí NSImage s dvouřádkovým layoutem.
    Kreslí se s flipped=True (y=0 nahoře) aby odpovídalo souřadnicovému
    systému NSStatusBarButton.
    """
    font, attrs = _icon_attrs()
    H = AppKit.NSStatusBar.systemStatusBar().thickness()
    cap_h = font.capHeight()

    auto_s  = f"{auto_pct:.0f}%" if auto_pct >= 1 or auto_pct == 0 else "<1%"
    api_s   = f"{api_pct:.0f}%"  if api_pct  >= 1 or api_pct  == 0 else "<1%"

    aw = _text_w(auto_s,  attrs)
    bw = _text_w(api_s,   attrs)
    dw = _text_w(days_str, attrs) if days_str else 0
    ow = _text_w(od_str,  attrs)

    pct_col   = max(aw, bw)
    right_col = max(dw, ow)
    W = pct_col + _SEP_PX + right_col + _PAD_R

    # Vertikální centrování — blok dvou řádků uprostřed H
    # (kreslíme s flipped=True: y=0 je nahoře)
    block_h     = 2 * cap_h + _GAP_PX
    top_of_block = (H - block_h) / 2.0   # y od vrchu k hornímu řádku

    # Pro drawAtPoint_ ve flipped systému: point = levý horní roh textu
    # (baseline není relevantní — AppKit ve flipped kreslí od top-left)
    y_top = top_of_block
    y_bot = top_of_block + cap_h + _GAP_PX

    def draw_handler(rect):
        # procenta — zarovnaná doprava
        AppKit.NSString.stringWithString_(auto_s).drawAtPoint_withAttributes_(
            AppKit.NSMakePoint(pct_col - aw, y_top), attrs)
        AppKit.NSString.stringWithString_(api_s).drawAtPoint_withAttributes_(
            AppKit.NSMakePoint(pct_col - bw,  y_bot), attrs)
        # pravý sloupec — horizontálně vycentrováno
        rx = pct_col + _SEP_PX
        if days_str:
            AppKit.NSString.stringWithString_(days_str).drawAtPoint_withAttributes_(
                AppKit.NSMakePoint(rx + (right_col - dw) / 2, y_top), attrs)
        AppKit.NSString.stringWithString_(od_str).drawAtPoint_withAttributes_(
            AppKit.NSMakePoint(rx + (right_col - ow) / 2, y_bot), attrs)
        return True

    img = AppKit.NSImage.imageWithSize_flipped_drawingHandler_(
        AppKit.NSMakeSize(W, H), True, draw_handler
    )
    img.setTemplate_(True)   # automaticky invertuje pro tmavý menu bar
    return img


def _apply_icon(button, auto_pct: float, api_pct: float,
                od_str: str, days_str: str = "") -> None:
    """Nastaví ikonu na NSStatusBarButton (main thread)."""
    try:
        img = build_status_icon(auto_pct, api_pct, od_str, days_str)
        button.setImage_(img)
        button.setImagePosition_(AppKit.NSImageOnly)
        button.setTitle_("")
    except Exception as e:
        try:
            button.setTitle_(f"{auto_pct:.0f}% {api_pct:.0f}%")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Data → display
# ---------------------------------------------------------------------------

def days_remaining(end_str: str) -> int:
    try:
        end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return max(0, (end - now).days)
    except Exception:
        return -1


def parse_data(data: dict) -> dict:
    """Extrahuje relevantní hodnoty z API odpovědi."""
    ind = data.get("individualUsage", {})
    plan = ind.get("plan", {})
    on_demand = ind.get("onDemand", {})

    auto_pct = plan.get("autoPercentUsed", 0)
    api_pct = plan.get("apiPercentUsed", 0)
    total_pct = plan.get("totalPercentUsed", 0)
    od_used = on_demand.get("used", 0) or 0
    od_limit = on_demand.get("limit")

    end_str = data.get("billingCycleEnd", "")
    days = days_remaining(end_str)
    membership = data.get("membershipType", "?").replace("_", " ")

    used = plan.get("used", 0)
    limit = plan.get("limit")

    return dict(
        auto_pct=auto_pct,
        api_pct=api_pct,
        total_pct=total_pct,
        od_used=od_used,
        od_limit=od_limit,
        days=days,
        membership=membership,
        used=used,
        limit=limit,
        billing_end=end_str,
    )


def _pct_bar(pct: float, width: int = 8) -> str:
    filled = round(min(pct, 100) / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _fmt_date(date_str: str) -> str:
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%d.%m.%Y")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class CursorUsageApp(rumps.App):
    def __init__(self):
        super().__init__("⌨", quit_button=rumps.MenuItem("Ukončit"))

        self.token: Optional[str] = None
        self._notified_missing_token = False
        self._notified_over_limit = False

        # Pending UI update z background vlákna → aplikuje main-thread timer
        self._pending: Optional[dict] = None  # {'line1','line2','info','update_time'} nebo {'error','plain'}

        def static(text):
            item = rumps.MenuItem(text)
            item.set_callback(None)
            return item

        self.item_days     = static("Načítám…")
        self.item_plan     = static("")
        self.item_auto     = static("")
        self.item_named    = static("")
        self.item_ondemand = static("")
        self.item_total    = static("")
        self.item_updated  = static("")

        self.refresh_item        = rumps.MenuItem("Obnovit", callback=self.manual_refresh)
        self.login_item          = rumps.MenuItem("Přihlásit se přes web…", callback=self._open_login_window)
        self.set_token_item      = rumps.MenuItem("Zadat token ručně…", callback=self.prompt_token)
        self.open_dashboard_item = rumps.MenuItem("Otevřít dashboard", callback=self._open_dashboard)

        # Submenu pro interval obnovy
        self._interval_items = {}
        current_interval = load_refresh_interval()
        interval_menu = rumps.MenuItem("Obnovovat každých…")
        for secs, label in REFRESH_INTERVALS:
            item = rumps.MenuItem(
                ("✓ " if secs == current_interval else "   ") + label,
                callback=self._set_interval,
            )
            item._interval_secs = secs
            self._interval_items[secs] = item
            interval_menu.add(item)

        self.menu = [
            self.item_days,
            self.item_plan,
            None,
            self.item_auto,
            self.item_named,
            self.item_ondemand,
            self.item_total,
            None,
            self.item_updated,
            None,
            self.refresh_item,
            self.open_dashboard_item,
            interval_menu,
            None,
            self.login_item,
            self.set_token_item,
        ]

        self._status_button = None  # NSStatusBarButton
        self._refresh_interval = load_refresh_interval()

        self.token = load_token()
        if not self.token:
            self.token = try_read_token_from_cursor_cookies()
            if self.token:
                save_token(self.token)

        self._start_timers()

    # ------------------------------------------------------------------
    # Timers

    def _start_timers(self):
        self._fetch_timer = rumps.Timer(self._on_fetch_timer, self._refresh_interval)
        self._fetch_timer.start()

        # UI timer — každou sekundu aplikuje pending update na main thread
        self._ui_timer = rumps.Timer(self._apply_pending, 1)
        self._ui_timer.start()

        # Okamžitý první fetch
        threading.Thread(target=self._do_fetch, daemon=True).start()

    def _on_fetch_timer(self, _):
        threading.Thread(target=self._do_fetch, daemon=True).start()

    # ------------------------------------------------------------------
    # Background fetch (nikdy nemění UI přímo)

    def _do_fetch(self):
        if not self.token:
            self._pending = {"plain": "⌨ ?", "info": "Token chybí – klikni na 'Přihlásit se přes web…'"}
            if not self._notified_missing_token:
                self._notified_missing_token = True
                rumps.notification("Cursor Usage", "Token není nastaven",
                                   "Klikni na ikonu → 'Přihlásit se přes web…'")
            return

        try:
            data = fetch_usage_summary(self.token)
            d = parse_data(data)
            od_str   = f"${d['od_used']:.2f}" if d["od_used"] else "$0"
            days_str = f"{d['days']}d" if d["days"] >= 0 else ""

            auto_bar  = _pct_bar(d["auto_pct"])
            named_bar = _pct_bar(d["api_pct"])

            od_line = f"${d['od_used']:.2f}"
            if d["od_limit"] and d["od_limit"] > 0:
                od_line += f" / ${d['od_limit']:.2f}"

            if d["auto_pct"] < 100 and d["api_pct"] < 100:
                self._notified_over_limit = False  # reset pro příští cyklus

            if (d["auto_pct"] >= 100 or d["api_pct"] >= 100) and not self._notified_over_limit:
                self._notified_over_limit = True
                which = "Auto" if d["auto_pct"] >= 100 else "Named"
                rumps.notification("Cursor Usage", f"Limit překročen — {which} modely",
                                   "Zkontroluj svůj plán na cursor.com/dashboard/usage")

            self._pending = {
                "auto_pct":   d["auto_pct"],
                "api_pct":    d["api_pct"],
                "od_str":     od_str,
                "days_str":   days_str,
                "item_days":  f"⏳  Zbývá {d['days']} dní do obnovy" if d["days"] >= 0 else "",
                "item_plan":  f"📋  {d['membership'].title()}   •   {_fmt_date(d['billing_end'])}",
                "item_auto":  f"🤖  Auto:     {auto_bar}  {d['auto_pct']:.1f} %",
                "item_named": f"✏️   Named:   {named_bar}  {d['api_pct']:.1f} %",
                "item_ondemand": f"💳  On-demand:  {od_line}",
                "item_total": f"📊  Celkem:   {d['used']:,} / {d['limit']:,}" if d["limit"] else "",
                "update_time": datetime.now().strftime("%H:%M"),
            }
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                msg = "Token vypršel – klikni na 'Přihlásit se přes web…'"
                if not self._notified_missing_token:
                    self._notified_missing_token = True
                    rumps.notification("Cursor Usage", "Token vypršel",
                                       "Klikni na ikonu → 'Přihlásit se přes web…'")
            else:
                msg = f"Chyba HTTP {e.code}"
            self._pending = {"plain": "⌨ !", "info": msg}
        except Exception as e:
            self._pending = {"plain": "⌨ !", "info": f"Chyba: {e}"}

    # ------------------------------------------------------------------
    # Main-thread UI update (voláno z rumps.Timer → hlavní vlákno)

    def _apply_pending(self, _):
        if self._pending is None:
            return
        p = self._pending
        self._pending = None

        # Lazy init: získej NSStatusBarButton
        if self._status_button is None:
            try:
                self._status_button = self._nsapp.nsstatusitem.button()
            except Exception:
                pass

        if "auto_pct" in p:
            if self._status_button is not None:
                _apply_icon(self._status_button, p["auto_pct"], p["api_pct"],
                            p["od_str"], p.get("days_str", ""))
            else:
                self.title = f"{p['auto_pct']:.0f}% {p['api_pct']:.0f}% {p['od_str']}"
            self.item_days.title     = p.get("item_days", "")
            self.item_plan.title     = p.get("item_plan", "")
            self.item_auto.title     = p.get("item_auto", "")
            self.item_named.title    = p.get("item_named", "")
            self.item_ondemand.title = p.get("item_ondemand", "")
            self.item_total.title    = p.get("item_total", "")
            self.item_updated.title  = f"Aktualizováno: {p['update_time']}"
        elif "plain" in p:
            if self._status_button is not None:
                try:
                    self._status_button.setTitle_(p["plain"])
                    self._status_button.setImage_(None)
                    self._status_button.setImagePosition_(AppKit.NSNoImage)
                except Exception:
                    self.title = p["plain"]
            else:
                self.title = p["plain"]
            self.item_days.title = p.get("info", "")
            self.item_plan.title = self.item_auto.title = self.item_named.title = ""
            self.item_ondemand.title = self.item_total.title = ""

    # ------------------------------------------------------------------

    def _set_interval(self, sender):
        secs = sender._interval_secs
        self._refresh_interval = secs
        save_refresh_interval(secs)
        # Aktualizuj zaškrtnutí v submenu
        for s, item in self._interval_items.items():
            label = dict(REFRESH_INTERVALS)[s]
            item.title = ("✓ " if s == secs else "   ") + label
        # Restartuj fetch timer s novým intervalem
        self._fetch_timer.stop()
        self._fetch_timer = rumps.Timer(self._on_fetch_timer, secs)
        self._fetch_timer.start()
        threading.Thread(target=self._do_fetch, daemon=True).start()

    def manual_refresh(self, _):
        threading.Thread(target=self._do_fetch, daemon=True).start()

    def _open_login_window(self, _):
        """Opens a native WKWebView window — user logs in to cursor.com."""
        if not _login_window.is_available():
            rumps.alert(
                title="WebKit není dostupný",
                message=(
                    "Nainstaluj WebKit bindings:\n\n"
                    "pip install pyobjc-framework-WebKit\n\n"
                    "Nebo použij 'Zadat token ručně…'."
                ),
            )
            return

        def _on_success(token: str):
            self.token = token
            self._notified_missing_token = False
            save_token(token)
            threading.Thread(target=self._do_fetch, daemon=True).start()
            rumps.notification("Cursor Usage", "Přihlášení úspěšné", "Token byl uložen.")

        def _on_cancel():
            pass  # user closed window without logging in

        _login_window.open_login_window(_on_success, _on_cancel)

    def prompt_token(self, _):
        """Fallback: manually paste the WorkosCursorSessionToken."""
        win = rumps.Window(
            message=(
                "Vlož WorkosCursorSessionToken:\n\n"
                "1. Otevři cursor.com/settings v prohlížeči\n"
                "2. DevTools → Application → Cookies → cursor.com\n"
                "3. Zkopíruj hodnotu WorkosCursorSessionToken"
            ),
            title="Zadat token ručně",
            default_text=self.token or "",
            ok="Uložit",
            cancel="Zrušit",
            dimensions=(500, 80),
        )
        response = win.run()
        if response.clicked and response.text.strip():
            self.token = response.text.strip()
            self._notified_missing_token = False
            save_token(self.token)
            threading.Thread(target=self._do_fetch, daemon=True).start()

    def _open_dashboard(self, _):
        subprocess.Popen(["open", "https://cursor.com/dashboard/usage"])


# ---------------------------------------------------------------------------

def _hide_from_dock() -> None:
    """Menu bar only — no Python icon in the Dock."""
    AppKit.NSApplication.sharedApplication().setActivationPolicy_(
        AppKit.NSApplicationActivationPolicyAccessory
    )


if __name__ == "__main__":
    _hide_from_dock()
    CursorUsageApp().run()
