# CS35L56 speaker tuning from HP recovery media

Matching OEM speaker files have been located for the HP OmniBook X Laptop
14-ks000, board **8F22**. This is a record of the recovery media and its driver
metadata, checked on 2026-11-12 Pacific time (2026-11-13 UTC) on another
computer. The firmware has **not** been installed or tested on the HP under
Linux. No firmware binaries were extracted during the inspection, and none
are included in this repository.

The existing [speaker route](audio.md) produced audio on ROM firmware 3.4.4
with `FIRMWARE_MISSING` on 2026-11-02. Finding these files does not establish
the loudness, bass response or protection behavior after a Linux installation.
No tuned/ROM comparison has been measured.

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

This mapping is an installation reference, not a record of Linux load success.
Confirm the actual system ID, speaker ID, amp prefixes and requested names on
the HP's installed driver before using it. Vendor kernels can differ from
their nominal upstream version. The
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

## Remaining work on the HP

Before any installation, check the running system with
`python3 03-system/check/check-machine.py` and capture the current CS35L56
kernel messages. Confirm the filename requests and per-amp mapping against
that driver. Resolve the applicable license terms for local use before
copying files from recovery media.

After a local installation, confirm that the matching
`.wmfw` and each amp's `.bin` load, review calibration messages, check left
and right playback, and compare audio at controlled settings. The expected
sound improvement remains a prediction until that test is performed. No
firmware installer or automatic extraction step is supplied by this update.

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
