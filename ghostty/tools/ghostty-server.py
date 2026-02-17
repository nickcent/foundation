#!/usr/bin/env python3
"""Ghostty Control Panel — local server that reads/writes ~/.config/ghostty/config."""

import json
import os
import re
import shutil
import subprocess
import http.server
import time
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "ghostty" / "config"
HTML_PATH = Path(__file__).parent / "ghostty-control.html"
BACKUP_DIR = Path(__file__).parent / "backups"
PRESETS_PATH = Path(__file__).parent / "presets.json"
THEMES_DIR = Path("/Applications/Ghostty.app/Contents/Resources/ghostty/themes")
PORT = 7474


def parse_config():
    """Parse ghostty config into dict of active (uncommented) values."""
    cfg = {}
    if not CONFIG_PATH.exists():
        return cfg
    for line in CONFIG_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"')
            cfg[key] = val
    return cfg


def backup_config():
    """Snapshot current config before applying changes."""
    if not CONFIG_PATH.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / f"config-{ts}"
    shutil.copy2(CONFIG_PATH, dest)
    # Keep only last 20 backups
    backups = sorted(BACKUP_DIR.glob("config-*"), key=lambda p: p.stat().st_mtime)
    for old in backups[:-20]:
        old.unlink()
    return str(dest)


def list_backups():
    """List available config backups."""
    if not BACKUP_DIR.exists():
        return []
    backups = sorted(BACKUP_DIR.glob("config-*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": b.name, "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(b.stat().st_mtime))} for b in backups]


def restore_backup(name):
    """Restore a specific backup."""
    src = BACKUP_DIR / name
    if not src.exists():
        return False
    backup_config()  # Backup current before restoring
    shutil.copy2(src, CONFIG_PATH)
    return True


def update_config(state):
    """Update config file with new values, preserving structure."""
    if not CONFIG_PATH.exists():
        return False

    lines = CONFIG_PATH.read_text().splitlines()
    new_lines = []

    keys_to_set = {}
    keys_to_set["background-opacity"] = f"{state['opacity']:.2f}"
    keys_to_set["background-blur-radius"] = str(state["blur"])
    keys_to_set["foreground"] = state["fgColor"].lstrip("#")
    keys_to_set["font-size"] = str(state.get("fontSize", 16))

    if state.get("fontFamily"):
        keys_to_set["font-family"] = f'"{state["fontFamily"]}"'

    if state.get("useCustomBg"):
        keys_to_set["background"] = state["bgColor"].lstrip("#")

    theme_name = state.get("theme", "")
    keys_handled = set()

    for i, line in enumerate(lines):
        stripped = line.strip()

        if re.match(r'^#?\s*theme\s*=', stripped):
            m = re.search(r'theme\s*=\s*"?([^"]*)"?', stripped.lstrip("# "))
            if m and m.group(1).strip() == theme_name:
                new_lines.append(f' theme = "{theme_name}"')
            else:
                if not stripped.startswith("#"):
                    new_lines.append("# " + line)
                else:
                    new_lines.append(line)
            keys_handled.add("theme")
            continue

        matched_key = None
        for key in keys_to_set:
            if re.match(rf'^#?\s*{re.escape(key)}\s*=', stripped):
                matched_key = key
                break

        if matched_key:
            new_lines.append(f"{matched_key} = {keys_to_set[matched_key]}")
            keys_handled.add(matched_key)
        else:
            new_lines.append(line)

    for key, val in keys_to_set.items():
        if key not in keys_handled:
            new_lines.append(f"{key} = {val}")

    if "theme" not in keys_handled and theme_name:
        new_lines.append(f' theme = "{theme_name}"')

    CONFIG_PATH.write_text("\n".join(new_lines) + "\n")
    return True


def reload_ghostty():
    """Activate Ghostty, send Cmd+Shift+, to reload config, then return focus."""
    script = '''
        tell application "System Events"
            set frontApp to name of first application process whose frontmost is true
        end tell
        tell application "Ghostty" to activate
        delay 0.3
        tell application "System Events"
            keystroke "," using {command down, shift down}
        end tell
        delay 0.3
        tell application frontApp to activate
    '''
    try:
        subprocess.run(["osascript", "-e", script], timeout=5, capture_output=True)
        return True
    except Exception:
        return False


def get_theme_list():
    """Get themes from ghostty CLI."""
    try:
        result = subprocess.run(
            ["ghostty", "+list-themes"],
            capture_output=True, text=True, timeout=5
        )
        themes = []
        for line in result.stdout.splitlines():
            name = re.sub(r'\s*\((resources|custom)\)$', '', line.strip())
            if name:
                themes.append(name)
        return themes
    except Exception:
        return []


def get_font_list():
    """Get font families from ghostty CLI."""
    try:
        result = subprocess.run(
            ["ghostty", "+list-fonts"],
            capture_output=True, text=True, timeout=5
        )
        families = []
        for line in result.stdout.splitlines():
            if line and not line.startswith(" "):
                families.append(line.strip())
        return families
    except Exception:
        return []


def get_theme_colors(name):
    """Parse a theme file and return its color palette."""
    theme_file = THEMES_DIR / name
    if not theme_file.exists():
        return None
    colors = {}
    for line in theme_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            colors[key] = val
    return colors


def get_all_theme_colors():
    """Build a map of theme name -> preview colors (bg, fg, palette 0-7)."""
    result = {}
    if not THEMES_DIR.exists():
        return result
    for f in THEMES_DIR.iterdir():
        if f.is_file():
            colors = {}
            for line in f.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, val = line.partition("=")
                    colors[key.strip()] = val.strip()
            preview = {}
            if "background" in colors:
                preview["bg"] = colors["background"]
            if "foreground" in colors:
                preview["fg"] = colors["foreground"]
            # Grab palette 0-7 for swatch strip
            swatches = []
            for i in range(8):
                k = f"palette = {i}"
                # Theme files use "palette = N=#RRGGBB" format
                for line in f.read_text().splitlines():
                    if line.strip().startswith(f"palette = {i}="):
                        swatches.append(line.strip().split("=", 2)[2].strip())
                        break
            if swatches:
                preview["swatches"] = swatches
            if preview:
                result[f.name] = preview
    return result


def get_all_theme_colors_fast():
    """Optimized: parse all themes once, return preview data."""
    result = {}
    if not THEMES_DIR.exists():
        return result
    for f in THEMES_DIR.iterdir():
        if not f.is_file():
            continue
        text = f.read_text()
        preview = {}
        swatches = [None] * 8
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if key == "background":
                preview["bg"] = val
            elif key == "foreground":
                preview["fg"] = val
            elif key == "palette":
                # "palette = N=#RRGGBB" — val is "N=#RRGGBB"
                parts = val.split("=", 1)
                if len(parts) == 2:
                    try:
                        idx = int(parts[0].strip())
                        if 0 <= idx < 8:
                            swatches[idx] = parts[1].strip()
                    except ValueError:
                        pass
        swatch_list = [s for s in swatches if s]
        if swatch_list:
            preview["swatches"] = swatch_list
        if preview:
            result[f.name] = preview
    return result


def load_presets():
    """Load saved presets."""
    if PRESETS_PATH.exists():
        return json.loads(PRESETS_PATH.read_text())
    return {}


def save_presets(presets):
    """Save presets to disk."""
    PRESETS_PATH.write_text(json.dumps(presets, indent=2))


def get_macos_appearance():
    """Detect macOS dark/light mode."""
    try:
        result = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True, text=True, timeout=2
        )
        return "dark" if "Dark" in result.stdout else "light"
    except Exception:
        return "light"


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            self.serve_html()
        elif path == "/api/config":
            self.serve_config()
        elif path == "/api/config-raw":
            self.serve_config_raw()
        elif path == "/api/themes":
            self.send_json(get_theme_list())
        elif path == "/api/fonts":
            self.send_json(get_font_list())
        elif path == "/api/theme-colors":
            self.send_json(get_all_theme_colors_fast())
        elif path == "/api/backups":
            self.send_json(list_backups())
        elif path == "/api/presets":
            self.send_json(load_presets())
        elif path == "/api/appearance":
            self.send_json({"mode": get_macos_appearance()})
        else:
            self.send_error(404)

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/apply":
            self.handle_apply()
        elif path == "/api/restore":
            self.handle_restore()
        elif path == "/api/presets/save":
            self.handle_save_preset()
        elif path == "/api/presets/delete":
            self.handle_delete_preset()
        else:
            self.send_error(404)

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def serve_html(self):
        html = HTML_PATH.read_text()
        themes = get_theme_list()
        fonts = get_font_list()
        html = html.replace("THEME_LIST_PLACEHOLDER", json.dumps(themes))
        html = html.replace("FONT_LIST_PLACEHOLDER", json.dumps(fonts))
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def serve_config(self):
        cfg = parse_config()
        result = {}
        if "background-opacity" in cfg:
            result["opacity"] = float(cfg["background-opacity"])
        if "background-blur-radius" in cfg:
            result["blur"] = int(cfg["background-blur-radius"])
        if "background" in cfg:
            result["background"] = cfg["background"].lstrip("#")
        if "foreground" in cfg:
            result["foreground"] = cfg["foreground"].lstrip("#")
        if "theme" in cfg:
            result["theme"] = cfg["theme"]
        if "font-family" in cfg:
            result["fontFamily"] = cfg["font-family"].strip('"')
        if "font-size" in cfg:
            result["fontSize"] = int(cfg["font-size"])
        self.send_json(result)

    def serve_config_raw(self):
        text = CONFIG_PATH.read_text() if CONFIG_PATH.exists() else ""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(text.encode())

    def handle_apply(self):
        try:
            state = self.read_body()
            backup_path = backup_config()
            ok = update_config(state)
            if ok:
                reload_ghostty()
            self.send_json({"ok": ok, "backup": backup_path})
        except Exception as e:
            self.send_json({"ok": False, "error": str(e)})

    def handle_restore(self):
        try:
            body = self.read_body()
            name = body.get("name", "")
            if not name or "/" in name:
                self.send_json({"ok": False, "error": "Invalid backup name"})
                return
            ok = restore_backup(name)
            if ok:
                reload_ghostty()
            self.send_json({"ok": ok})
        except Exception as e:
            self.send_json({"ok": False, "error": str(e)})

    def handle_save_preset(self):
        try:
            body = self.read_body()
            name = body.get("name", "").strip()
            preset = body.get("preset", {})
            if not name:
                self.send_json({"ok": False, "error": "Name required"})
                return
            presets = load_presets()
            presets[name] = preset
            save_presets(presets)
            self.send_json({"ok": True})
        except Exception as e:
            self.send_json({"ok": False, "error": str(e)})

    def handle_delete_preset(self):
        try:
            body = self.read_body()
            name = body.get("name", "")
            presets = load_presets()
            if name in presets:
                del presets[name]
                save_presets(presets)
            self.send_json({"ok": True})
        except Exception as e:
            self.send_json({"ok": False, "error": str(e)})

    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


if __name__ == "__main__":
    server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Ghostty Control Panel running at http://localhost:{PORT}")
    print(f"Config: {CONFIG_PATH}")
    print(f"Backups: {BACKUP_DIR}")
    print(f"Presets: {PRESETS_PATH}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
