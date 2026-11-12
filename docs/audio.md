# Audio

The SoundWire card is `mt8901-soundwire`, long name
`HP-HPOmniBookXLaptop14_ks000-8F22`. ALSA card 1. The codec is CS42L43 with
two CS35L56 amplifiers.

The upstream `soundwire-mtk.ko` machine `mtk_sdw_cs35l56_l0_cs42l43_l1`
expects four amplifiers on link 0. This board has two, unique ids 0 and 1,
plus the CS42L43 on link 1. `02-drivers/soundwire/match-two-amps.sh` changes that count in
the installed module and leaves a backup in `/var/lib/hp-omnibook/`. Reboot
after it runs. Reinstalling the module package restores the four-amp table.

`h7607a-hardware` can also ship `72-h7607a-no-microphone.rules` with mode
0600 on capture PCMs. PipeWire 1.6 then ignores the whole card, speakers
included. `03-system/input-audio/fix-hp-speakers.sh` installs
`03-system/input-audio/udev/72-h7607a-no-microphone.rules` and restores `root:audio` mode
0660. It restarts WirePlumber for `SUDO_USER` when that session bus exists.
Run `hp-audio-route.py` after that restart.

On this board, speaker PCM `hw:1,0` opens after:

- `O150 I032 Switch` and `O151 I033 Switch` on
- `PDI2 Demux` set to `DP2`

Headphone PCM is `hw:1,1`. The ASUS UCM speaker path `O152` / `PDI3` is the
wrong route here. `h7607a-hardware` still installs that UCM.

WirePlumber on the reference system keeps the card on the pro-audio profile.
That profile runs the UCM verb, which mutes the speaker amps, and it does not
run the Speaker sequence that would unmute them. `wpctl set-profile` takes a
numeric index. Index 0 is off. Passing the profile name by mistake saves the
card as off.

`03-system/input-audio/hp-audio-route.py` puts the card back on pro-audio, sets the HP
playback path, and re-asserts `Speaker Switch`, `AMP1 Speaker Switch`, and
`AMP2 Speaker Switch` after WirePlumber settles. It opens `hw:1,0` and
`hw:1,1` non-blocking and treats `EBUSY` as success so it does not steal the
device from PipeWire.

Install the script and the user service:

```bash
sudo install -m 0755 03-system/input-audio/hp-audio-route.py /usr/local/bin/hp-audio-route.py
mkdir -p ~/.config/systemd/user
cp 03-system/input-audio/systemd/hp-audio-route.service ~/.config/systemd/user/
systemctl --user enable --now hp-audio-route.service
```

Restarting WirePlumber reloads the card and mutes the amps again. Start the
user service after that, or run `hp-audio-route.py` once.

Capture PCMs `hw:1,7` through `hw:1,15`, other than the microphone path below,
and playback PCMs `hw:1,2` through `hw:1,6`, have no working DAI on this
machine. Leave them alone.

PipeWire logs a missing RTKit service until `rtkit` is installed and
`rtkit-daemon.service` is running. Install that package with the session
packages in [Installing](install.md).

## Microphone

`03-system/input-audio/hp-microphone.py` opens the internal microphone while it is running:
PDM2 through the CS42L43 decimators into DP1, then SoundWire DP12 / PDI7 into
UL1, exposed as a PipeWire source on `hw:mt8901soundwire,8`. Stopping the
process restores the capture controls it changed. It imports
`hp-audio-route.py` from the same directory.

```bash
sudo install -m 0755 03-system/input-audio/hp-audio-route.py 03-system/input-audio/hp-microphone.py /usr/local/bin/
mkdir -p ~/.config/systemd/user
cp 03-system/input-audio/systemd/hp-microphone.service ~/.config/systemd/user/
systemctl --user enable --now hp-microphone.service
```

The reference machine confirmed speech through this source. Gain is +18 dB
on the two decimators.

The CS35L56 amplifiers still want HP tuning firmware for board 8F22. See
[Limits](limits.md).
