# Cursor Usage Menu Bar — průvodce pro agenta

## Co to je

Lehká macOS aplikace v řádku nabídek: dvě procenta (Auto / Named modely), dny do obnovy a on-demand USD. Po kliknutí kompaktní menu s detaily.

## Rychlý start

```bash
pip3 install -r requirements.txt
python3 app.py
```

Instalace včetně LaunchAgent: `bash install.sh`

## Kde co měnit

- **Ikona v menu baru** → `build_status_icon`, `_apply_icon` v `app.py`
- **Obsah dropdown menu** → `_do_fetch` / `_apply_pending`, položky `item_*`
- **Přihlášení** → `login_window.py`, menu „Přihlásit se přes web…“
- **Interval obnovy** → `REFRESH_INTERVALS`, `load_refresh_interval` / `save_refresh_interval`
- **Dokumentace pro uživatele** → `README.md`

## Testování

1. Spustit `python3 app.py` — ikona v menu baru, bez ikony v Docku.
2. Menu → Obnovit — data se načtou (vyžaduje platný token).
3. Bez tokenu: ikona `⌨ ?`, přihlášení přes web nebo ruční token.

## Časté úkoly

| Úkol | Postup |
|------|--------|
| Nová položka v menu | Přidat `rumps.MenuItem` v `__init__`, aktualizovat v `_apply_pending` |
| Změna API polí | `parse_data()` — mapování z JSON `usage-summary` |
| Oprava auto-start | Zkontrolovat plist v `~/Library/LaunchAgents/`, log `/tmp/cursor-usage-menubar.log` |
| Release na GitHub | Commit na `main`, push `origin main` |

## Omezení

- Pouze macOS 12+.
- Vyžaduje běžící proces (menu bar app = daemon).
- Nepřidávat síťové volání mimo `cursor.com`.
