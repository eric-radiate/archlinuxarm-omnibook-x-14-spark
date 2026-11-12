#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Install the OmniBook top bar from this directory into the user's config.
#
# Copies Waybar, SwayNC, hypridle, panel scripts, and the battery-alert timer.
# Re-running overwrites those files. Hyprland blocks that are already present
# are left alone. Hyprland itself is not restarted.
#
#   bash 04-desktop/install-hyprbar.sh
set -euo pipefail

if [[ $EUID -eq 0 ]]; then
  echo "Run as your user: bash $0" >&2
  exit 1
fi

src="$(cd "$(dirname "$0")" && pwd)"
[[ -f "$src/waybar/config.jsonc" ]] || {
  echo "missing $src/waybar/config.jsonc" >&2
  exit 1
}

sudo pacman -S --needed --noconfirm \
  waybar hypridle swaync power-profiles-daemon-n1x brightnessctl \
  python-gobject gtk3 kitty blueman pavucontrol wireplumber \
  adwaita-fonts libnotify

python3 - "$src" "$HOME" <<'PY'
import shutil
import sys
from pathlib import Path

src, home = Path(sys.argv[1]), Path(sys.argv[2])
count = 0
for path in src.rglob("*"):
    if (
        not path.is_file()
        or path.suffix in {".pyc", ".md"}
        or path.name == "install-hyprbar.sh"
        or "__pycache__" in path.parts
    ):
        continue
    rel = path.relative_to(src)
    dest = home / ".config" / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_bytes()
    if b"@HOME@" in text:
        text = text.replace(b"@HOME@", str(home).encode())
        dest.write_bytes(text)
    else:
        shutil.copy2(path, dest)
    if path.suffix in {".sh", ".py"}:
        dest.chmod(0o755)
    count += 1
print(f"installed {count} files under {home / '.config'}")
PY

python3 - "$HOME/.config/hypr/hyprland.lua" "$HOME" <<'PY'
import sys
from pathlib import Path

path, home = Path(sys.argv[1]), sys.argv[2]
if not path.exists():
    raise SystemExit(f"missing {path}; start Hyprland once so it creates the config, then re-run")
text = path.read_text()
original = text

stock = """hl.monitor({
    output   = \"\",
    mode     = \"preferred\",
    position = \"auto\",
    scale    = \"auto\",
})"""
panel = """-- HP internal panel; do not auto-enable NVIDIA phantom outputs.
hl.monitor({
    output   = \"eDP-1\",
    mode = \"2880x1800@120.00\",
    position = \"0x0\",
    scale = 1.5,
})
hl.monitor({ output = \"HDMI-A-1\", disabled = true })
for i = 1, 12 do
    hl.monitor({ output = \"Unknown-\" .. i, disabled = true })
end"""
if 'output   = "eDP-1"' not in text and 'output = "eDP-1"' not in text:
    if stock not in text:
        raise SystemExit("hyprland.lua has no eDP-1 monitor and no stock monitor block to replace")
    text = text.replace(stock, panel, 1)

if "mouse_move_enables_dpms" not in text:
    text += """

hl.config({
    misc = {
        mouse_move_enables_dpms = true,
        key_press_enables_dpms = true,
    },
})
"""

if "-- BEGIN fix-hyprbar" not in text:
    block = """
-- BEGIN fix-hyprbar
hl.on(\"hyprland.start\", function ()
    hl.exec_cmd(\"sh -c 'pidof waybar >/dev/null || exec waybar'\")
    hl.exec_cmd(\"sh -c 'pidof hypridle >/dev/null || exec hypridle'\")
    hl.exec_cmd(\"sh -c 'pidof swaync >/dev/null || exec swaync'\")
end)
-- END fix-hyprbar

"""
    anchor = "---- ENVIRONMENT VARIABLES ----"
    if anchor in text:
        text = text.replace(anchor, block + anchor, 1)
    else:
        text += "\n" + block

presence = f"{home}/.config/hypr/hp-presence.sh"
if "-- BEGIN hp-presence" not in text:
    text += f"""
-- BEGIN hp-presence
hl.on(\"hyprland.start\", function ()
    hl.exec_cmd(\"{presence}\")
end)
-- END hp-presence
"""

if "elan2513:00-04f3:4664" not in text:
    text += """
hl.device({
    name      = \"elan2513:00-04f3:4664\",
    output    = \"eDP-1\",
    transform = 0,
})
"""

if "touchdevice" not in text:
    text += """
hl.config({
    input = {
        touchdevice = {
            output = \"eDP-1\",
            transform = 0,
        },
    },
})
"""

rotate = f"{home}/.config/hypr/rotate-panel.sh"
if "rotate-panel.sh" not in text:
    text += f"""
hl.bind(mainMod .. \" + O\", hl.dsp.exec_cmd(\"{rotate} landscape\"))
hl.bind(mainMod .. \" + SHIFT + O\", hl.dsp.exec_cmd(\"{rotate} portrait\"))
"""

if text != original:
    path.write_text(text)
    print(f"updated {path}")
else:
    print(f"{path} already has the panel blocks")
PY

systemctl --user daemon-reload
systemctl --user enable --now swaync.service
systemctl --user enable --now hp-battery-alert.timer

if systemctl cat power-profiles-daemon.service >/dev/null 2>&1; then
  sudo systemctl enable --now power-profiles-daemon.service
fi

if [[ -n ${WAYLAND_DISPLAY:-} ]]; then
  if pgrep -x waybar >/dev/null; then
    kill "$(pgrep -x waybar)" || true
    sleep 0.3
  fi
  setsid -f waybar >/tmp/waybar-install.log 2>&1 || true
  if pgrep -f "$HOME/.config/hypr/hp-presence.sh" >/dev/null; then
    pkill -f "$HOME/.config/hypr/hp-presence.sh" || true
    sleep 0.3
  fi
  setsid -f "$HOME/.config/hypr/hp-presence.sh" >/tmp/hp-presence.out 2>&1 || true
fi

echo "hyprbar installed"
