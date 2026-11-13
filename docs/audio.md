# Audio

The SoundWire card is `mt8901-soundwire`, long name
`HP-HPOmniBookXLaptop14_ks000-8F22`. ALSA card 1. The codec is CS42L43 with
two CS35L56 amplifiers.

The upstream `soundwire-mtk.ko` machine `mtk_sdw_cs35l56_l0_cs42l43_l1`
expects four amplifiers on link 0. This board has two, unique ids 0 and 1,
plus the CS42L43 on link 1. `02-drivers/soundwire/match-two-amps.sh` changes that count in
the exact reviewed unsigned legacy module. It checks complete input/output
hashes, saves the module and previous initramfs under
`/var/lib/hp-omnibook/transactions/`, rebuilds the pinned preset and extracts
the result to verify the embedded module. A failed build or verification
restores the previous files. Recovery uses `lib/hp_boot.py restore` as
described in [ACPI recovery](acpi.md). Reboot after it succeeds. Reinstalling
the package restores the four-amp table.

This workaround has not been run through a new physical installation during
the repository review. The existing two-amp module itself was used by the
reference machine. On current Omarchy, use its source patch
`1061-soundwire-mediatek-add-the-HP-OmniBook-X-14-topology.patch`, which adds a
separate two-amp topology and keeps the four-amp entry. Do not run this binary
workaround on an Omarchy module or a signed replacement.

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

## Speaker tuning

The reference machine produced speaker audio while the CS35L56 amps reported
missing OEM firmware. On 2026-11-12, an owner-created HP Cloud Recovery USB
was inspected read-only on another computer. Its Windows image contains the
8F22-specific tuning and matching DSP firmware 3.13.5. The driver metadata
confirms the board and the left/right SoundWire mapping.

On 2026-11-13 the reference HP booted the combined #25 sleep kernel with the
HP identity source patch and the locally acquired OEM files. Both amplifiers
loaded firmware **3.13.5**, their separate link/UID tunings, and factory
calibration. The owner confirmed correct left/right playback and heard the
stereo test well at 45% PipeWire volume. This is a functional listening test;
no controlled tuned/ROM comparison or protection measurement was performed.

See [Speaker tuning](speaker-tuning.md) for file hashes, the required
`103c8f22-spkid0` qualifier, source build steps and private staging. Run
`python3 03-system/check/check-hp-audio.py` after boot to check both amps.
Firmware binaries are not included in this tree.

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

Capture was checked again on the combined boot on 2026-11-13. A local
speech-recognition check recovered the requested phrase three times from a
20-second sample. The speech interval had no clipped PCM samples. This is a
functional capture test, not an acoustic-quality or noise-rejection rating.
Recordings and transcripts stay private.

The CS35L56 speaker tuning is separate from this CS42L43 microphone route.
