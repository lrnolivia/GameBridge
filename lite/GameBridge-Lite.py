#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import importlib.util
import io
import queue
import sys
import threading
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gdk, Gio

APP_ID = "com.loew.gamebridgelite"
HERE = Path(__file__).resolve().parent
ENGINE_PATH = HERE / "gamebridge_core.py"


def load_engine():
    spec = importlib.util.spec_from_file_location("gamebridge_engine", ENGINE_PATH)
    if not spec or not spec.loader:
        raise RuntimeError(f"Could not load GameBridge core: {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


GB = load_engine()


CSS = b"""
window { font-size: 12px; }

.big-symbol {
    font-size: 22px;
    font-weight: 700;
    margin: 0;
}
.working-symbol { color: #57DCEB; }
.success-symbol { color: #59C98A; }
.error-symbol { color: #FF7E87; }
.warning-symbol { color: #FFE16B; }

.page-title {
    font-size: 28px;
    font-weight: 650;
    margin-top: 2px;
    margin-bottom: 0;
}
.subtitle {
    font-size: 11px;
    opacity: 0.64;
    margin-bottom: 8px;
}
.phase-label {
    font-size: 13px;
    font-weight: 650;
    margin-top: 3px;
    margin-bottom: 1px;
}
.phase-cyan { color: #57DCEB; }
.phase-magenta { color: #FF6AAD; }
.phase-yellow { color: #FFE16B; }
.phase-sienna { color: #DB805A; }
.phase-green { color: #6DDB9C; }
.phase-red { color: #FF7E87; }
.detail {
    font-size: 11px;
    opacity: 0.76;
    margin-top: 1px;
}

.info-card {
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,0.10);
    background-color: rgba(255,255,255,0.035);
    padding: 10px 12px;
}
.info-key {
    font-size: 10px;
    opacity: 0.58;
}
.info-value {
    font-size: 12px;
    font-weight: 600;
}
.safety-value { color: #6DDB9C; }

progressbar {
    background: transparent;
    background-color: transparent;
    border: none;
    box-shadow: none;
    padding: 0;
    margin-top: 4px;
    margin-bottom: 3px;
}
progressbar trough {
    min-height: 13px;
    border-radius: 999px;
    border: none;
    box-shadow: none;
    background-color: rgba(255,255,255,0.10);
}
progressbar progress {
    min-height: 13px;
    border-radius: 999px;
    border: none;
    box-shadow: none;
    background-image: linear-gradient(to right, #35D0E2, #FF4F9A, #FFD84A);
}
progressbar.phase-cyan progress {
    background-image: linear-gradient(to right, #22BFD3, #57DCEB);
}
progressbar.phase-green progress {
    background-image: linear-gradient(to right, #3BAE72, #6DDB9C);
}
progressbar.phase-yellow progress {
    background-image: linear-gradient(to right, #F0BE32, #FFE16B);
}
progressbar.phase-red progress {
    background-image: linear-gradient(to right, #E05560, #FF7E87);
}
progressbar text { font-size: 11px; font-weight: 700; }

button {
    min-height: 26px;
    padding: 4px 14px;
    border-radius: 8px;
    font-size: 11px;
}
button.primary { font-weight: 700; }

expander { font-size: 11px; }
.console {
    font-family: monospace;
    font-size: 10px;
    padding: 8px;
}
.console-frame {
    border-radius: 9px;
    border: 1px solid rgba(255,255,255,0.10);
    background-color: rgba(27,28,32,0.82);
}
.dialog-heading {
    font-size: 16px;
    font-weight: 650;
    margin-bottom: 4px;
}
"""


class GameBridgeLite(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.window = None
        self.session = None
        self.busy = False
        self._pulse_id = 0
        self._spinner_id = 0
        self._spinner_frame = 0
        self._console_queue = queue.SimpleQueue()
        self._console_flush_id = 0
        self._settings_dialog = None

    def setup_color_scheme(self):
        try:
            self.interface_settings = Gio.Settings.new("org.gnome.desktop.interface")
            self.interface_settings.connect("changed::color-scheme", self.on_color_scheme_changed)
            self.apply_color_scheme()
        except Exception:
            pass

    def apply_color_scheme(self):
        try:
            scheme = self.interface_settings.get_string("color-scheme")
        except Exception:
            scheme = "default"
        settings = Gtk.Settings.get_default()
        if settings is not None:
            try:
                settings.set_property("gtk-application-prefer-dark-theme", scheme == "prefer-dark")
            except Exception:
                pass

    def on_color_scheme_changed(self, *_):
        self.apply_color_scheme()

    def do_activate(self):
        self.setup_color_scheme()
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.session = GB.initial_session(None, None)

        self.window = Gtk.ApplicationWindow(application=self)
        try:
            self.window.set_icon_name(APP_ID)
        except Exception:
            pass
        self.window.set_title("GameBridge Lite")
        self.window.set_default_size(620, 470)
        self.window.set_resizable(True)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        outer.set_margin_top(18)
        outer.set_margin_bottom(18)
        outer.set_margin_start(24)
        outer.set_margin_end(24)
        self.window.set_child(outer)

        self.symbol = Gtk.Label(label="◇")
        self.symbol.add_css_class("big-symbol")
        self.symbol.add_css_class("success-symbol")
        outer.append(self.symbol)

        title = Gtk.Label(label="GameBridge Lite")
        title.add_css_class("page-title")
        outer.append(title)

        subtitle = Gtk.Label(label="PLAYER NAME · REVIEW + SYNC")
        subtitle.add_css_class("subtitle")
        outer.append(subtitle)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("info-card")
        outer.append(card)

        self.name_value = self._info_row(card, "NAME TO USE", "—")
        self.folder_value = self._info_row(card, "GAMES FOLDER", "—")
        safety = self._info_row(card, "SAFETY", "IDs · saves · binaries untouched")
        safety.add_css_class("safety-value")

        self.status_label = Gtk.Label(label="Ready")
        self.status_label.add_css_class("phase-label")
        self.status_label.add_css_class("phase-green")
        self.status_label.set_wrap(True)
        self.status_label.set_justify(Gtk.Justification.CENTER)
        outer.append(self.status_label)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_fraction(0.0)
        self.progress.set_text("")
        self.progress.set_hexpand(True)
        outer.append(self.progress)

        self.detail_label = Gtk.Label(label="Review supported player-name settings before syncing.")
        self.detail_label.add_css_class("detail")
        self.detail_label.set_wrap(True)
        self.detail_label.set_justify(Gtk.Justification.CENTER)
        outer.append(self.detail_label)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        buttons.set_halign(Gtk.Align.CENTER)
        outer.append(buttons)

        self.review_button = Gtk.Button(label="Review Games")
        self.review_button.connect("clicked", self.on_review)
        buttons.append(self.review_button)

        self.fix_button = Gtk.Button(label="Sync Player Names")
        self.fix_button.add_css_class("primary")
        self.fix_button.connect("clicked", self.on_fix)
        buttons.append(self.fix_button)

        self.settings_button = Gtk.Button(label="Settings")
        self.settings_button.connect("clicked", self.on_settings)
        buttons.append(self.settings_button)

        self.console_expander = Gtk.Expander(label="Show results")
        self.console_expander.set_expanded(False)
        self.console_expander.connect("notify::expanded", self.on_console_expanded)
        outer.append(self.console_expander)

        self.console_scroll = Gtk.ScrolledWindow()
        self.console_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.console_scroll.set_min_content_height(150)
        self.console_scroll.set_max_content_height(260)
        self.console_scroll.add_css_class("console-frame")

        self.console_view = Gtk.TextView()
        self.console_view.set_editable(False)
        self.console_view.set_cursor_visible(False)
        self.console_view.set_monospace(True)
        self.console_view.set_wrap_mode(Gtk.WrapMode.NONE)
        self.console_view.add_css_class("console")
        self.console_buffer = self.console_view.get_buffer()
        self.console_scroll.set_child(self.console_view)
        self.console_expander.set_child(self.console_scroll)

        self.refresh_session_labels()
        self.window.present()

    def _info_row(self, parent, key, value):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        key_label = Gtk.Label(label=key)
        key_label.add_css_class("info-key")
        key_label.set_xalign(0)
        key_label.set_size_request(94, -1)
        row.append(key_label)
        value_label = Gtk.Label(label=value)
        value_label.add_css_class("info-value")
        value_label.set_xalign(0)
        value_label.set_hexpand(True)
        value_label.set_ellipsize(3)  # Pango.EllipsizeMode.END numeric enum
        value_label.set_selectable(True)
        row.append(value_label)
        parent.append(row)
        return value_label

    def refresh_session_labels(self):
        if not self.session:
            return
        self.name_value.set_text(self.session.player_name or "Not set")
        self.folder_value.set_text(str(self.session.root) if self.session.root else "Not detected")

    def set_phase(self, text, css="phase-cyan", detail=None):
        for name in ("phase-cyan", "phase-magenta", "phase-yellow", "phase-sienna", "phase-green", "phase-red"):
            self.status_label.remove_css_class(name)
            self.progress.remove_css_class(name)
        self.status_label.add_css_class(css)
        self.progress.add_css_class(css)
        self.status_label.set_text(text)
        if detail is not None:
            self.detail_label.set_text(detail)

    def set_symbol(self, symbol, css):
        for name in ("working-symbol", "success-symbol", "error-symbol", "warning-symbol"):
            self.symbol.remove_css_class(name)
        self.symbol.add_css_class(css)
        self.symbol.set_text(symbol)

    def set_busy(self, busy):
        self.busy = busy
        for button in (self.review_button, self.fix_button, self.settings_button):
            button.set_sensitive(not busy)
        if busy:
            self.set_symbol("◐", "working-symbol")
            self.progress.set_fraction(0.18)
            self.progress.set_text("Working…")
            self._spinner_frame = 0
            if not self._spinner_id:
                self._spinner_id = GLib.timeout_add(120, self._animate_spinner)
            if not self._pulse_id:
                self._pulse_id = GLib.timeout_add(90, self._pulse_progress)
        else:
            if self._spinner_id:
                GLib.source_remove(self._spinner_id)
                self._spinner_id = 0
            if self._pulse_id:
                GLib.source_remove(self._pulse_id)
                self._pulse_id = 0

    def _animate_spinner(self):
        frames = ("◐", "◓", "◑", "◒")
        self.symbol.set_text(frames[self._spinner_frame % len(frames)])
        self._spinner_frame += 1
        return self.busy

    def _pulse_progress(self):
        if not self.busy:
            return False
        self.progress.pulse()
        return True

    def console(self, text):
        for line in str(text).splitlines() or [""]:
            self._console_queue.put(line)
        if not self._console_flush_id:
            GLib.idle_add(self._start_console_pump)

    def _start_console_pump(self):
        if not self._console_flush_id:
            self._console_flush_id = GLib.timeout_add(40, self._flush_console_queue)
        return False

    def _flush_console_queue(self):
        lines = []
        for _ in range(250):
            try:
                lines.append(self._console_queue.get_nowait())
            except queue.Empty:
                break
        if lines:
            end = self.console_buffer.get_end_iter()
            self.console_buffer.insert(end, "\n".join(lines) + "\n")
            self._scroll_console_bottom()
        if self.busy or not self._console_queue.empty():
            return True
        self._console_flush_id = 0
        return False

    def _scroll_console_bottom(self):
        adj = self.console_scroll.get_vadjustment()
        if adj:
            adj.set_value(max(adj.get_lower(), adj.get_upper() - adj.get_page_size()))
        return False

    def clear_console(self):
        self.console_buffer.set_text("")

    def on_console_expanded(self, expander, *_):
        expander.set_label("Hide results" if expander.get_expanded() else "Show results")
        if expander.get_expanded():
            GLib.idle_add(self._scroll_console_bottom)

    @staticmethod
    def _capture(fn, *args, **kwargs):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            result = fn(*args, **kwargs)
        return result, buf.getvalue()

    def validate_root(self):
        if not self.session.root or not Path(self.session.root).is_dir():
            self.set_symbol("!", "warning-symbol")
            self.set_phase("Choose your games folder", "phase-yellow", "Open Settings and select the Game Library folder.")
            self.on_settings()
            return None
        return Path(self.session.root)

    def validate_fix_session(self):
        root = self.validate_root()
        if root is None:
            return None
        if not self.session.player_name:
            self.set_symbol("!", "warning-symbol")
            self.set_phase("Choose a player name", "phase-yellow", "Open Settings and choose a Steam account or enter a name.")
            self.on_settings()
            return None
        return root, self.session.player_name

    def on_review(self, *_):
        if self.busy:
            return
        root = self.validate_root()
        if root is None:
            return
        self.clear_console()
        self.console_expander.set_expanded(True)
        self.set_phase("Reviewing games…", "phase-cyan", "Read-only scan. No files will be changed.")
        self.set_busy(True)
        threading.Thread(target=self._review_worker, args=(root,), daemon=True).start()

    def _review_worker(self, root):
        try:
            results, output = self._capture(GB.audit_library, root, False)
            self.console(output)
            lines = []
            lines.append(f"{'GAME':<42} {'CURRENT NAME':<28} STATUS")
            lines.append("─" * 82)
            desired = (self.session.player_name or "").casefold()
            for row in results:
                if not row.player_names:
                    current = "—"
                    status = "NOT FOUND"
                elif len(row.player_names) > 1:
                    current = " · ".join(row.player_names[:2])
                    status = "MIXED"
                else:
                    current = row.player_names[0]
                    cf = current.casefold()
                    if desired and cf == desired:
                        status = "LOCAL"
                    elif GB.is_supported_source_value(current):
                        status = "SUPPORTED"
                    else:
                        status = "CUSTOM"
                game = row.game[:40]
                current = current[:26]
                lines.append(f"{game:<42} {current:<28} {status}")
            lines.append("")
            lines.append(f"Games found: {len(results)}")
            lines.append(f"Name found: {sum(1 for r in results if r.player_names)}")
            lines.append(f"No name found: {sum(1 for r in results if not r.player_names)}")
            self.console("\n".join(lines))
            GLib.idle_add(self._review_done, len(results))
        except Exception as exc:
            self.console(f"ERROR: {exc}")
            GLib.idle_add(self._failed, f"Review failed: {exc}")

    def _review_done(self, count):
        self.set_busy(False)
        self.set_symbol("✓", "success-symbol")
        self.set_phase("Review complete", "phase-green", f"Checked {count} game folder{'s' if count != 1 else ''}. Nothing was changed.")
        self.progress.set_fraction(1.0)
        self.progress.set_text("Read-only review complete")
        return False

    def on_fix(self, *_):
        if self.busy:
            return
        validated = self.validate_fix_session()
        if validated is None:
            return
        root, player_name = validated
        self.clear_console()
        self.console_expander.set_expanded(True)
        self.set_phase("Finding supported player-name values…", "phase-cyan", "Scanning only recognized identity fields in small text/config files.")
        self.set_busy(True)
        threading.Thread(target=self._scan_fix_worker, args=(root, player_name), daemon=True).start()

    def _scan_fix_worker(self, root, player_name):
        try:
            changes, output = self._capture(GB.scan_library, root, player_name, False)
            self.console(output)
            if not changes:
                GLib.idle_add(self._nothing_to_fix)
                return
            grouped = {}
            for change in changes:
                grouped.setdefault(change.game, 0)
                grouped[change.game] += 1
            self.console("MATCHES\n" + "─" * 52)
            for game in sorted(grouped, key=str.casefold):
                self.console(f"{game}: {grouped[game]} config(s)")
            self.console(f"\nReplacement: {player_name}")
            self.console("Backups: automatic before every write")
            self.console("Protected: Steam IDs · saves · binaries · assets")
            GLib.idle_add(self._confirm_fix, root, player_name, changes)
        except Exception as exc:
            self.console(f"ERROR: {exc}")
            GLib.idle_add(self._failed, f"Scan failed: {exc}")

    def _nothing_to_fix(self):
        self.set_busy(False)
        self.set_symbol("✓", "success-symbol")
        self.set_phase("No player-name updates found", "phase-green", "All recognized player-name settings are already compatible.")
        self.progress.set_fraction(1.0)
        self.progress.set_text("No changes needed")
        return False

    def _confirm_fix(self, root, player_name, changes):
        self.set_busy(False)
        self.set_symbol("!", "warning-symbol")
        self.set_phase("Ready to sync player names", "phase-yellow", f"{len(changes)} config(s) match a supported compatibility value.")
        self.progress.set_fraction(0.55)
        self.progress.set_text(f"{len(changes)} config(s) ready")

        dialog = Gtk.Window(transient_for=self.window, modal=True)
        dialog.set_title("Sync player names?")
        dialog.set_default_size(430, 210)
        dialog.set_resizable(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(22)
        box.set_margin_bottom(18)
        box.set_margin_start(22)
        box.set_margin_end(22)
        dialog.set_child(box)

        title = Gtk.Label(label="Sync player names?")
        title.add_css_class("dialog-heading")
        title.set_xalign(0)
        box.append(title)

        body = Gtk.Label(
            label=(
                f"GameBridge will update {len(changes)} config(s) to use “{player_name}”.\n\n"
                "Every modified config is backed up first. Steam IDs, saves, binaries, and assets are not changed."
            )
        )
        body.set_wrap(True)
        body.set_xalign(0)
        box.append(body)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        buttons.set_halign(Gtk.Align.END)
        box.append(buttons)

        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", self._cancel_fix, dialog)
        buttons.append(cancel)

        apply_button = Gtk.Button(label="Sync Names")
        apply_button.add_css_class("primary")
        apply_button.connect("clicked", self._start_confirmed_fix, dialog, root, player_name, changes)
        buttons.append(apply_button)

        dialog.present()
        return False

    def _cancel_fix(self, _button, dialog):
        dialog.close()
        self.set_symbol("◇", "success-symbol")
        self.set_phase("No files changed", "phase-green", "The proposed updates were cancelled.")
        self.progress.set_fraction(0.0)
        self.progress.set_text("")

    def _start_confirmed_fix(self, _button, dialog, root, player_name, changes):
        dialog.close()
        self.set_phase("Backing up + syncing…", "phase-cyan", "Applying only the reviewed player-name updates.")
        self.set_busy(True)
        threading.Thread(target=self._apply_worker, args=(root, player_name, changes), daemon=True).start()

    def _apply_worker(self, root, player_name, changes):
        try:
            result, output = self._capture(GB.apply_changes, root, changes, player_name)
            self.console(output)
            verified, failed, backup_root = result
            GLib.idle_add(self._apply_done, verified, failed, str(backup_root))
        except Exception as exc:
            self.console(f"ERROR: {exc}")
            GLib.idle_add(self._failed, f"Fix failed: {exc}")

    def _apply_done(self, verified, failed, backup_root):
        self.set_busy(False)
        if failed:
            self.set_symbol("!", "warning-symbol")
            self.set_phase("Finished with warnings", "phase-yellow", f"Verified {verified} config(s); {failed} verification failure(s). Backup: {backup_root}")
            self.progress.set_fraction(1.0)
            self.progress.set_text("Completed with warnings")
        else:
            self.set_symbol("✓", "success-symbol")
            self.set_phase("Player names synced", "phase-green", f"Verified {verified} config(s). Backup: {backup_root}")
            self.progress.set_fraction(1.0)
            self.progress.set_text("Backup + verification complete")
        return False

    def _failed(self, message):
        self.set_busy(False)
        self.set_symbol("×", "error-symbol")
        self.set_phase("Something went wrong", "phase-red", message)
        self.progress.set_fraction(1.0)
        self.progress.set_text("Failed")
        self.console_expander.set_expanded(True)
        return False

    def on_settings(self, *_):
        if self.busy or self._settings_dialog:
            return

        rows = [r for r in GB.detect_steam_identities() if GB.steam_login_name(r)]
        libs = GB.discover_libraries()

        dialog = Gtk.Window(transient_for=self.window, modal=True)
        dialog.set_title("GameBridge Settings")
        dialog.set_default_size(520, 330)
        dialog.set_resizable(False)
        self._settings_dialog = dialog
        dialog.connect("close-request", self._settings_closed)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer.set_margin_top(18)
        outer.set_margin_bottom(18)
        outer.set_margin_start(20)
        outer.set_margin_end(20)
        dialog.set_child(outer)

        heading = Gtk.Label(label="Settings")
        heading.add_css_class("dialog-heading")
        heading.set_xalign(0)
        outer.append(heading)

        name_label = Gtk.Label(label="Name to use")
        name_label.set_xalign(0)
        outer.append(name_label)

        self.profile_dropdown = Gtk.DropDown.new_from_strings(
            [GB.steam_login_name(r) + ((" · " + r.persona_name) if r.persona_name and r.persona_name != GB.steam_login_name(r) else "") for r in rows]
            + ["Enter a different name…"]
        )
        selected = len(rows)
        if self.session.identity:
            for i, row in enumerate(rows):
                if row.steam_id == self.session.identity.steam_id:
                    selected = i
                    break
        self.profile_dropdown.set_selected(selected)
        outer.append(self.profile_dropdown)

        self.manual_entry = Gtk.Entry()
        self.manual_entry.set_placeholder_text("Local Profile Name")
        self.manual_entry.set_text(self.session.player_name if not self.session.identity and self.session.player_name else "")
        self.manual_entry.set_visible(selected == len(rows))
        self.profile_dropdown.connect("notify::selected", lambda *_: self.manual_entry.set_visible(self.profile_dropdown.get_selected() == len(rows)))
        outer.append(self.manual_entry)

        folder_label = Gtk.Label(label="Games folder")
        folder_label.set_xalign(0)
        outer.append(folder_label)

        folder_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        outer.append(folder_box)
        self.folder_entry = Gtk.Entry()
        self.folder_entry.set_hexpand(True)
        self.folder_entry.set_text(str(self.session.root) if self.session.root else (str(libs[0]) if libs else ""))
        self.folder_entry.set_placeholder_text("/var/mnt/.../Game Library")
        folder_box.append(self.folder_entry)
        browse = Gtk.Button(label="Browse…")
        browse.connect("clicked", self._choose_folder)
        folder_box.append(browse)

        hint = Gtk.Label(label="GameBridge re-detects Steam accounts and likely game libraries each time Settings opens.")
        hint.add_css_class("detail")
        hint.set_wrap(True)
        hint.set_xalign(0)
        outer.append(hint)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        controls.set_halign(Gtk.Align.END)
        controls.set_margin_top(8)
        outer.append(controls)
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda *_: dialog.close())
        controls.append(cancel)
        save = Gtk.Button(label="Save")
        save.add_css_class("primary")
        save.connect("clicked", self._save_settings, rows)
        controls.append(save)

        dialog.present()

    def _settings_closed(self, *_):
        self._settings_dialog = None
        return False

    def _choose_folder(self, *_):
        chooser = Gtk.FileChooserNative(
            title="Choose Game Library folder",
            transient_for=self._settings_dialog,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            accept_label="Choose",
            cancel_label="Cancel",
        )
        current = Path(self.folder_entry.get_text()).expanduser()
        if current.is_dir():
            try:
                chooser.set_current_folder(Gio.File.new_for_path(str(current)))
            except Exception:
                pass
        chooser.connect("response", self._folder_chosen)
        chooser.show()

    def _folder_chosen(self, chooser, response):
        if response == Gtk.ResponseType.ACCEPT:
            f = chooser.get_file()
            if f and f.get_path():
                self.folder_entry.set_text(f.get_path())
        chooser.destroy()

    def _save_settings(self, _button, rows):
        idx = self.profile_dropdown.get_selected()
        if idx < len(rows):
            row = rows[idx]
            self.session.player_name = GB.steam_login_name(row)
            self.session.identity = row
            self.session.player_name_source = "Steam AccountName · loginusers.vdf"
        else:
            name = self.manual_entry.get_text().strip()
            self.session.player_name = name or None
            self.session.identity = None
            self.session.player_name_source = "manual override" if name else "not detected"

        folder = self.folder_entry.get_text().strip()
        self.session.root = Path(folder).expanduser() if folder else None
        self.refresh_session_labels()
        self.set_symbol("◇", "success-symbol")
        self.set_phase("Settings saved", "phase-green", "Ready to review games or fix recognized supported player-name values.")
        self.progress.set_fraction(0.0)
        self.progress.set_text("")
        self._settings_dialog.close()


def main():
    return GameBridgeLite().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
