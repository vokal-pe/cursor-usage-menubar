# Agent guide — cursor-usage-menubar

## What this is

macOS menu bar utility for **personal** Cursor.com usage (Auto %, Named %, on-demand $, days until renewal). Open source, MIT.

## Before changing code

1. Read `.cursor/rules/project.mdc`.
2. Do not add outbound URLs except `cursor.com`.
3. Never log or commit session tokens.
4. Test UI changes on macOS main thread (`rumps.Timer` for updates from background fetch).

## Common tasks

| Task | Where |
|------|--------|
| Change icon layout | `build_status_icon()`, `_apply_icon()` in `app.py` |
| Change dropdown menu | `CursorUsageApp.__init__`, `_do_fetch` pending keys |
| Refresh interval | `REFRESH_INTERVALS`, `load_refresh_interval()` |
| Login flow | `login_window.py`, menu item „Přihlásit se přes web…“ |
| Install / autostart | `install.sh`, `com.petrvokal.cursor-usage-menubar.plist` |

## Release checklist

- [ ] `python3 -c "import ast; ast.parse(open('app.py').read())"`
- [ ] Manual run: icon + menu + login
- [ ] No secrets in `git diff`
- [ ] Update README if user-facing behavior changes
- [ ] Push to `main` on GitHub
