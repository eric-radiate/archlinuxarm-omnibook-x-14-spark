# CS35L56 speaker tuning from HP recovery media

Matching OEM speaker files have been located for the HP OmniBook X Laptop
14-ks000, board **8F22**. This is a record of the recovery media and its driver
metadata, initially checked on 2026-11-12 Pacific time on another computer.
On **2026-11-13**, the owner supplied that USB for a separate local extraction
and Linux trial on the HP. Both amps now load the matching firmware and
tuning, apply calibration and produce the correct stereo channels. No
firmware, extracted INF text, catalog or recording is included in this tree.

The existing [speaker route](audio.md) produced audio on ROM firmware 3.4.4
with `FIRMWARE_MISSING` on 2026-11-02. The later functional playback test does
not measure loudness, bass response or protection behavior. No controlled
tuned/ROM comparison has been performed.

## Recovery source

The owner created the USB with the official
[HP Cloud Recovery Tool](https://apps.microsoft.com/detail/9mtks9pr7r3n),
entering product number **E4KN9AV** as printed on the laptop, without a suffix.
The USB was then mounted read-only on another Linux computer. Recovery was
not booted or run on the laptop to perform this inspection.

| Item | Observed value |
| --- | --- |
| USB filesystem label | `HP_RECOVERY` |
| Recovery image ID in `Info.txt` | `26WW1NIZR03` |
| Recovery opcode in `Info.txt` | `ABA` |
| Factory Windows image | `PRELOAD/BASE.SWM` through `PRELOAD/BASE36.SWM`, 36 parts |
| Split-image GUID | `8b727f1fa470334684c6a3bf50410525` |
| Windows image | ARM64, build `28000.3086`, `CoreSingleLanguage`, `en-US` |
| Audio package | Cirrus Logic SoundWire Audio Driver `1.0.690.3159` |
| HP package part number | `P019GW-B2X` |
| CVA board identity | `SysId01=0x8F22`, HP OmniBook X 14 inch Laptop Next Gen AI PC |
| INF subsystem identity | `SUBSYS_8F22103C` |
| CS35L56 DSP firmware | `3.13.5` |

The recovery opcode is image metadata, not an instruction to invent a
`#ABA` suffix for the product number. The package's CVA has an empty
`SoftpaqNumber` field; this inspection did not establish a public SoftPaq
download URL.

All 36 split parts had the same GUID and a complete part-number sequence.
`wimlib-imagex verify` successfully checked the split Windows image,
`sources/boot.wim` and `PRELOAD/Build.WIM`, including their file-data hashes.
This checks archive consistency; it does not prove a successful factory
restore, independently authenticate a Windows catalog signature, or test Linux
audio. The [HP Cloud Recovery instructions](https://support.hp.com/us-en/document/ish_4511095-4511141-16)
describe USB creation and factory recovery as separate steps.

## Package and driver metadata

The audio package is present under this path inside the Windows image:

```text
/SWSETUP/DRV/Audio/Cirrus/NKLCirrus_99GWB2/1.0.690.3159/
```

Its `P019GWB2.cva` identifies board 8F22. The installed extension driver and
speaker files are also present under:

```text
/Windows/System32/DriverStore/FileRepository/xucsmeext_8f22_fdl.inf_arm64_bf13798af99513c5/
```

The file `XuCsMeExt_8F22_FDL.inf` identifies Cirrus hardware and subsystem
`8F22103C`. It selects DSP firmware 3.13.5 together with the tuning in
`tn/35L56/8F22/dflt`. The following paths are relative to that DriverStore
directory:

| Role | Original relative path | Bytes | SHA-1 recorded in the WIM |
| --- | --- | ---: | --- |
| Shared DSP firmware | `fw/35L56/3.13.5/dflt/b0_dflt_35l56_3.13.5.wmfw` | 35,804 | `c3f42a03f8935ded0035b66ae0a14189af251348` |
| Right speaker, link 0 UID 0 | `tn/35L56/8F22/dflt/b0_dflt_8f22_rw_l0u0.bin` | 11,444 | `5fc7b77cbf72d2188b5c9cb22d8d9a227ed001dd` |
| Left speaker, link 0 UID 1 | `tn/35L56/8F22/dflt/b0_dflt_8f22_lw_l0u1.bin` | 11,444 | `19d9cedc1305ab8e67a52a9277dbed8787650b35` |

These are archive hash records, not a redistribution license or a substitute
for checking the applicable package terms. Keep the firmware and coefficients
as a matching set. Files for the ASUS ProArt or another HP board do not provide
this board's tuning.

The later extracted bytes were also checked with SHA-256; exact sizes and
hashes are in [pins/hp-speaker-firmware.json](../pins/hp-speaker-firmware.json).
The WMDR files contain an older `8e73` project filename internally. HP's
8F22 extension INF explicitly selects the supplied 8F22 files recorded here;
an internal text string is not a reason to substitute another board's tuning.

## SoundWire mapping and expected Linux names

The HP INF maps **UID 0 to the right speaker** and **UID 1 to the left speaker**
on link 0. Its Windows section names use `AMP1` for the right and `AMP0` for
the left. Those section numbers are not Linux ALSA control prefixes.

For the two-amp machine table reviewed here, Linux `AMP1` is UID 0 and Linux
`AMP2` is UID 1. With system ID `103c8f22` and speaker ID 0, the expected
filenames under `/usr/lib/firmware/cirrus/` are:

| Original file | Link/UID filename | Legacy ALSA-prefix filename |
| --- | --- | --- |
| `b0_dflt_35l56_3.13.5.wmfw` | `cs35l56-b0-dsp1-misc-103c8f22-spkid0.wmfw` | Same shared filename |
| `b0_dflt_8f22_rw_l0u0.bin` | `cs35l56-b0-dsp1-misc-103c8f22-spkid0-l0u0.bin` | `cs35l56-b0-dsp1-misc-103c8f22-spkid0-amp1.bin` |
| `b0_dflt_8f22_lw_l0u1.bin` | `cs35l56-b0-dsp1-misc-103c8f22-spkid0-l0u1.bin` | `cs35l56-b0-dsp1-misc-103c8f22-spkid0-amp2.bin` |

The link/UID filenames above were verified on the reference HP. No legacy
`amp1`/`amp2` aliases were needed: the B0 driver first tries its ALSA prefix,
then falls back to `l0u0`/`l0u1`. Both amps report speaker ID **0**, so the
`-spkid0` part is required. An initial trial omitted it and stayed on ROM;
tracing the real requests identified the mismatch. The corrected files were
verified inside the combined initramfs before rebooting.

Confirm the actual identity and requested names on any other driver or BIOS.
Vendor kernels can differ from their nominal upstream version. The
[kernel CS35L56 documentation](https://docs.kernel.org/sound/codecs/cs35l56.html)
explains firmware naming, the link/UID qualifier introduced in 6.16, and the
need for firmware and coefficient versions to match. `patched=0` at initial
probe is normal; completed load messages are needed to establish success.

The same HP package also contains CS42L43 and DTS files. They are separate
from these three CS35L56 files. This record does not propose changing the
CS42L43 microphone or headphone configuration.

## Inspect an owner's recovery USB without installing firmware

Use `wimlib-imagex` from the distribution's `wimlib` tools. Identify the USB
with `lsblk -f` and mount its `HP_RECOVERY` partition read-only. Do not use the
recovery installer for this inspection. Set the path to the actual mountpoint:

```bash
hp_recovery_root="/run/media/$USER/HP_RECOVERY"
findmnt --target "$hp_recovery_root" -o SOURCE,TARGET,FSTYPE,OPTIONS
wimlib-imagex info "$hp_recovery_root/PRELOAD/BASE.SWM"
wimlib-imagex verify "$hp_recovery_root/PRELOAD/BASE.SWM" \
  --ref="$hp_recovery_root/PRELOAD/BASE*.SWM"
wimlib-imagex verify "$hp_recovery_root/sources/boot.wim"
wimlib-imagex verify "$hp_recovery_root/PRELOAD/Build.WIM"
```

Check that the mount options include `ro`. The following lists only the
extension driver's directory and file metadata; it does not extract firmware:

```bash
wimlib-imagex dir "$hp_recovery_root/PRELOAD/BASE.SWM" 1 \
  --path=/Windows/System32/DriverStore/FileRepository/xucsmeext_8f22_fdl.inf_arm64_bf13798af99513c5 \
  --detailed --ref="$hp_recovery_root/PRELOAD/BASE*.SWM"
```

The DriverStore folder name, image ID and version above identify the inspected
media. A later recovery release may change them; inspect its own CVA and INF
rather than treating a similar filename as an exact match. See the upstream
[wimlib directory-listing reference](https://wimlib.net/man1/wimdir.html).

## Verified Linux result

The #25 combined boot reports, for both amps:

- Firmware `3.13.5`, with 41 algorithms.
- Shared `103c8f22-spkid0.wmfw` and the respective `l0u0.bin` / `l0u1.bin` loaded.
- `Calibration applied`.
- Tuning PID `0x103135`, TID `0x5a0618`; right SID `0x24100a`, left SID `0x24110a`.

The owner confirmed correct left/right speech playback at 30% PipeWire volume
and heard the test well at 45%. The internal microphone also captured an
intelligible repeated test phrase. Sanitized results and the source/module
identity are in [pins/audio-results.json](../pins/audio-results.json).

Check a running reference system without changing it:

```bash
python3 03-system/check/check-hp-audio.py
```

The first `fw:3.4.4 (patched=0)` line is the initial ROM probe; it remains in
a successful boot log. Require the later completed firmware, tuning and
calibration messages for **both** amps. A bare `fw_patched` flag or matching
module name is insufficient. Logs do not establish audible playback.

## Stage locally supplied files

Acquire the extension directory from the owner's recovery media outside this
repository, under the applicable terms. The optional extraction below reads
only that directory, not the full Windows image, and needs no root once the
USB is mounted read-only:

```bash
hp_audio_extract="$HOME/hp-audio-private/extracted"
mkdir -p -m 700 "$hp_audio_extract"
wimlib-imagex extract "$hp_recovery_root/PRELOAD/BASE.SWM" 1 \
  /Windows/System32/DriverStore/FileRepository/xucsmeext_8f22_fdl.inf_arm64_bf13798af99513c5 \
  --ref="$hp_recovery_root/PRELOAD/BASE*.SWM" \
  --dest-dir="$hp_audio_extract" --no-acls --no-attributes
python3 02-drivers/soundwire/stage-hp-firmware.py \
  "$hp_audio_extract/xucsmeext_8f22_fdl.inf_arm64_bf13798af99513c5" \
  "$HOME/hp-audio-private/staged"
```

The stager checks all three SHA-256 values before creating output and writes
private copies with the observed Linux names. It refuses output inside this
repository. It neither downloads nor installs firmware and changes no boot,
device, mixer or sleep setting. A different recovery revision needs its own
review; similarly named files are not automatically accepted.

## HP machine-driver identity patch

The original MediaTek legacy machine driver assigns an OEM subsystem ID only
for the ASUS. [hp-audio-identity.patch](../02-drivers/soundwire/hp-audio-identity.patch)
adds an exact HP product/board/vendor/F.05 match and sets `103c:8f22` before
registering the card. The codec adds its observed speaker-ID qualifier.
The existing ASUS match is preserved. This is GPL kernel source, separate
from the MIT staging helper and proprietary local firmware inputs.

Use the `audio-source.c` from [Josie's pinned source record](https://github.com/pfeifferj/archlinuxarm-proart-p16/blob/3484cc008a9ee00b34c086c729e28e935cbc3430/02-drivers/audio/payload/provenance/hardware/audio-source.c),
SHA-256 `4a3e4318ede455010a0e92eb776bcad22a7b3a5582d5bd75edfa5a33abf264e0`.
An offline build, outside this repository, follows the tested native GCC
16.1.1 build against the pinned vendor headers:

```bash
hp_audio_work="$HOME/hp-audio-private/module"
mkdir -m 700 "$hp_audio_work"
install -m 0644 /path/to/audio-source.c "$hp_audio_work/mt8901-acp-sdw-legacy-mach.c"
printf '%s  %s\n' \
  4a3e4318ede455010a0e92eb776bcad22a7b3a5582d5bd75edfa5a33abf264e0 \
  "$hp_audio_work/mt8901-acp-sdw-legacy-mach.c" | sha256sum --check --strict
patch --fuzz=0 "$hp_audio_work/mt8901-acp-sdw-legacy-mach.c" \
  < 02-drivers/soundwire/hp-audio-identity.patch
printf '%s\n' 'obj-m += mt8901-acp-sdw-legacy-mach.o' > "$hp_audio_work/Makefile"
make -j2 -C /usr/src/linux-headers-7.0.0-1022-nvidia \
  M="$hp_audio_work" CC=gcc HOSTCC=gcc CONFIG_DEBUG_INFO_BTF_MODULES= modules
python3 01-platform/sleep/verify-modules.py /path/to/sleep-work/build/Module.symvers \
  "$hp_audio_work/mt8901-acp-sdw-legacy-mach.ko"
```

The empty per-module BTF option follows the retained private driver's
no-coupled-BTF convention; it does not disable BTF on the kernel or its stock
modules. All 38 imported-symbol CRCs were checked against the exact #25 build.
A matching release string alone is insufficient. The tested source version is
`9834795298B30A6CAE8BF85`; binary hashes can depend on the local build paths.
Keep compiled outputs private and follow [combined boot](combined-boot.md)
for the exact existing boot layout. The portable preparation wrapper has
host recovery tests, not a second fresh-install hardware qualification.

The ACPI dump alone cannot supply these Windows files: the repository's
collector copies hardware tables. Josie's
[N1X write-up](https://josie.lol/blog/linux-rtx-spark) describes dumping ACPI
and obtaining ASUS speaker firmware as separate operations.

## Licensing

This page records original observations, file identities and mappings. It
does not publish HP's driver or firmware, and finding them in recovery media
does not establish permission to redistribute them or repurpose them under
Linux. HP's general EULA and any applicable supplier terms still need to be
considered. The linux-firmware Cirrus license is not automatically a grant for
this Windows package. See [Licensing and redistribution](legal.md#hp-speaker-firmware).
