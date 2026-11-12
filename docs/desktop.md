# Desktop bar

Optional Hyprland bar for this panel. It is not part of the hardware boot
path. `iio-hyprland` is not used.

`04-desktop/` holds the Waybar config, its status scripts, SwayNC, hypridle, the
panel helpers, and a user timer that warns on a low battery. Paths in the
tree use `@HOME@`. `04-desktop/install-hyprbar.sh` copies them into
`~/.config` and fills in the home directory. Re-running that script
overwrites those copied files. It does not restart Hyprland. Blocks already
present in `hyprland.lua` are left as they are.

```bash
bash 04-desktop/install-hyprbar.sh
```

The installer also adds this panel setup when `hyprland.lua` does not already
have it:

- `eDP-1` at `2880x1800@120.00`, scale 1.5
- `HDMI-A-1` and `Unknown-1` through `Unknown-12` disabled, so NVIDIA phantom
  outputs stay off
- ELAN touch device `elan2513:00-04f3:4664` mapped to `eDP-1`
- Super+O and Super+Shift+O for landscape and portrait
- Waybar, hypridle, and SwayNC started with Hyprland

Walk-away blanking is `04-desktop/hypr/hp-presence.sh`. It reads the HP 5MP
camera's HID human-presence sensor (`in_proximity0_raw` on an IIO device named
`prox`) and calls `dpms.sh`. The distance and attention channels stay at
their unknown sentinels, so the script ignores them.

The backlight module uses the NVIDIA device `nvidia_0`. The battery module
uses `BAT0`, which appears after the ACPI override in [ACPI](acpi.md). The
power button cycles `power-profiles-daemon-n1x`.
