#!/usr/bin/env python3
"""HP panel settings with supported modes, persistence, and timed rollback."""
import contextlib
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path.home() / '.config'
HYPR = ROOT / 'hypr/hyprland.lua'
BAR = ROOT / 'waybar/config.jsonc'
LAYOUT = ROOT / 'waybar/display-layout.json'
RUNTIME = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
PENDING = RUNTIME / 'hp-display-preview.json'
PATTERN = re.compile(r'hl\.monitor\(\{\s*output\s*=\s*"eDP-1"\s*,.*?\}\)', re.S)
SCALES = [1.5, 1.6, 1.8, 2.0, 2.25, 2.4]


def atomic_write(path, text):
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd, name = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(text)
            f.flush()
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextlib.contextmanager
def locked():
    with (RUNTIME / 'hp-display.lock').open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def monitor():
    monitors = json.loads(subprocess.check_output(['hyprctl', 'monitors', '-j'], timeout=3))
    return next(m for m in monitors if m['name'] == 'eDP-1' and not m['disabled'])


def block(text):
    match = PATTERN.search(text)
    if not match:
        raise RuntimeError('Cannot find the internal panel settings in hyprland.lua')
    return match.group()


def bar_layout(scale):
    c = json.loads(BAR.read_text())
    base = json.loads(LAYOUT.read_text())
    compact = 2880 / scale < 1350
    c['modules-left'] = [m for m in base['left'] if m != 'hyprland/window'] if compact else base['left']
    c['modules-center'] = ['custom/gpu'] if compact else base['center']
    atomic_write(BAR, json.dumps(c, indent=2) + '\n')
    subprocess.run(['pkill', '-USR2', '-x', 'waybar'], check=False)


def event(kind, **details):
    path = Path.home() / '.local/state/hp-display-events.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as f:
        f.write(json.dumps({'time': time.time(), 'event': kind, **details}) + '\n')


def preview(scale, mode):
    m = monitor()
    modes = [x.removesuffix('Hz') for x in m['availableModes']]
    if scale not in SCALES or mode not in modes:
        raise ValueError('Choose a supported scale and display mode')
    with locked():
        if PENDING.exists():
            raise RuntimeError('A display preview is already running; keep or revert it first')
        text = HYPR.read_text()
        before = block(text)
        after = re.sub(r'mode\s*=\s*"[^"]+"', f'mode = "{mode}"', before)
        after = re.sub(r'scale\s*=\s*[0-9.]+', f'scale = {scale:g}', after)
        token = uuid.uuid4().hex
        state = {'token': token, 'before': before, 'after': after,
                 'scale_before': m['scale'], 'scale_after': scale,
                 'deadline': time.time() + 30}
        atomic_write(PENDING, json.dumps(state))
        # Pass immutable identity and deadline: an older watchdog must never
        # adopt or roll back a newer preview.
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--watchdog',
                          token, str(state['deadline'])], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        bar_layout(scale)
        atomic_write(HYPR, text.replace(before, after, 1))
        event('preview', token=token, scale=scale, mode=mode)
        return token


def restore_state(state):
    text = HYPR.read_text()
    if block(text) == state['after']:
        atomic_write(HYPR, text.replace(state['after'], state['before'], 1))
        bar_layout(state['scale_before'])
    PENDING.unlink(missing_ok=True)


def revert(expected_token=None, reason='reverted'):
    with locked():
        if not PENDING.exists():
            return False
        state = json.loads(PENDING.read_text())
        if expected_token is not None and state['token'] != expected_token:
            return False
        restore_state(state)
        event(reason, token=state['token'], scale=state['scale_before'])
        return True


def keep(expected_token=None):
    with locked():
        if not PENDING.exists():
            return False
        state = json.loads(PENDING.read_text())
        if expected_token is not None and state['token'] != expected_token:
            return False
        if time.time() >= state['deadline']:
            restore_state(state)
            event('expired', token=state['token'])
            return False
        # Commit under the same lock used by rollback. Once removed, no timer
        # for this preview can restore the previous settings.
        PENDING.unlink()
        event('saved', token=state['token'], scale=state['scale_after'])
        return True


def gui():
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, Gio, GLib

    class Settings(Gtk.Application):
        def __init__(self):
            super().__init__(application_id='local.hp.DisplaySettings', flags=Gio.ApplicationFlags.FLAGS_NONE)
            self.window = None
            self.token = None
            self.dialog = None
            self.timer = None

        def do_activate(self):
            if self.window:
                self.window.present()
                return
            m = monitor()
            self.window = Gtk.ApplicationWindow(application=self, title='Display Settings')
            self.window.set_default_size(430, 300)
            self.window.set_resizable(False)
            self.window.connect('delete-event', self.close)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin=22)
            self.window.add(box)
            heading = Gtk.Label(xalign=0)
            heading.set_markup('<big><b>Built-in display</b></big>')
            box.pack_start(heading, False, False, 0)
            hint = Gtk.Label(label='Choose how large text and apps appear.\nHigher scale makes everything larger.', xalign=0)
            box.pack_start(hint, False, False, 0)
            self.size = Gtk.ComboBoxText()
            for s in SCALES:
                label = ' (original)' if s == 2 else ''
                self.size.append(str(s), f'{s:g}×{label}  ·  {round(2880/s)} × {round(1800/s)} workspace')
            self.size.set_active_id(str(float(m['scale'])))
            if self.size.get_active() < 0:
                self.size.set_active_id('2.0')
            self.mode = Gtk.ComboBoxText()
            for raw in m['availableModes']:
                value = raw.removesuffix('Hz')
                res, hz = value.split('@')
                self.mode.append(value, f'{res} at {float(hz):g} Hz')
            self.mode.set_active(0 if m['refreshRate'] > 90 else 1)
            for title, widget in [('Text and app size', self.size), ('Resolution / refresh rate', self.mode)]:
                box.pack_start(Gtk.Label(label=title, xalign=0), False, False, 0)
                box.pack_start(widget, False, False, 0)
            self.message = Gtk.Label(label='Changes are saved when you choose Keep changes.', xalign=0)
            self.message.set_line_wrap(True)
            box.pack_start(self.message, False, False, 0)
            buttons = Gtk.Box(spacing=10)
            self.undo = Gtk.Button(label='Revert')
            self.undo.connect('clicked', self.undo_clicked)
            self.undo.set_sensitive(False)
            self.apply = Gtk.Button(label='Apply')
            self.apply.connect('clicked', self.apply_clicked)
            self.apply.get_style_context().add_class('suggested-action')
            buttons.pack_end(self.apply, False, False, 0)
            buttons.pack_end(self.undo, False, False, 0)
            box.pack_start(buttons, False, False, 0)
            self.window.show_all()

        def apply_clicked(self, button):
            try:
                self.token = preview(float(self.size.get_active_id()), self.mode.get_active_id())
                self.apply.set_sensitive(False)
                self.undo.set_sensitive(True)
                self.size.set_sensitive(False)
                self.mode.set_sensitive(False)
                self.dialog = Gtk.MessageDialog(transient_for=self.window, modal=True,
                    message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.NONE,
                    text='Keep these display settings?')
                self.dialog.add_button('Revert', Gtk.ResponseType.NO)
                self.dialog.add_button('Keep changes', Gtk.ResponseType.YES)
                self.dialog.set_default_response(Gtk.ResponseType.YES)
                self.dialog.connect('response', self.confirmed)
                self.dialog.show_all()
                self.tick()
                self.timer = GLib.timeout_add_seconds(1, self.tick)
            except Exception as error:
                self.message.set_text(str(error))

        def confirmed(self, dialog, response):
            if self.token is None:
                return
            token = self.token
            if response == Gtk.ResponseType.YES:
                saved = keep(token)
                self.finish('Display settings saved.' if saved else
                            'Preview expired; the previous settings were restored.')
            else:
                revert(token)
                self.finish('Previous display settings restored.')

        def tick(self):
            if self.token is None:
                return False
            try:
                state = json.loads(PENDING.read_text())
            except FileNotFoundError:
                self.finish('Previous display settings restored.')
                return False
            if state['token'] != self.token:
                self.finish('A different display preview is active.')
                return False
            remaining = max(0, int(state['deadline'] - time.time()))
            self.dialog.format_secondary_text(
                f'Choose Keep changes to save.\nAutomatically reverting in {remaining} seconds.')
            return True

        def finish(self, text):
            self.token = None
            if self.timer:
                GLib.source_remove(self.timer)
                self.timer = None
            if self.dialog:
                self.dialog.destroy()
                self.dialog = None
            self.apply.set_sensitive(True)
            self.undo.set_sensitive(False)
            self.size.set_sensitive(True)
            self.mode.set_sensitive(True)
            self.message.set_text(text)
            GLib.timeout_add(500, self.refresh)

        def refresh(self):
            m = monitor()
            self.size.set_active_id(str(float(m['scale'])))
            for raw in m['availableModes']:
                value = raw.removesuffix('Hz')
                res, hz = value.split('@')
                if abs(float(hz) - m['refreshRate']) < 0.1:
                    self.mode.set_active_id(value)
                    break
            return False

        def undo_clicked(self, button):
            if self.token:
                revert(self.token)
                self.finish('Previous display settings restored.')

        def close(self, *args):
            if self.token:
                revert(self.token)
            return False

    Settings().run([])


if __name__ == '__main__':
    command = sys.argv[1] if len(sys.argv) > 1 else '--gui'
    if command == '--status':
        try:
            m = monitor()
            print(json.dumps({'text': 'screen', 'tooltip': f"{m['width']} × {m['height']} at {m['refreshRate']:g} Hz\nScale {m['scale']:g}×\nClick to change text size, resolution and refresh rate"}))
        except Exception:
            print(json.dumps({'text': 'screen', 'tooltip': 'Open display settings'}))
    elif command == '--preview':
        preview(float(sys.argv[2]), sys.argv[3])
    elif command == '--keep':
        keep()
    elif command == '--revert':
        revert()
    elif command == '--watchdog':
        token, deadline = sys.argv[2], float(sys.argv[3])
        time.sleep(max(0, deadline - time.time()))
        revert(token, reason='automatic_revert')

    else:
        gui()
