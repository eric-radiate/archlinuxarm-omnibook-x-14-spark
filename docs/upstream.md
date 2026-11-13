# Upstream

The bootable N1X stack on the reference machine is Josephine Pfeiffer's Arch
Linux ARM port for the ASUS ProArt P16 H7607BA.

- Repository: <https://github.com/pfeifferj/archlinuxarm-proart-p16>
- Reviewed commit: `3484cc008a9ee00b34c086c729e28e935cbc3430`
- Write-up: <https://josie.lol/blog/linux-rtx-spark.html>
- Hardware package: `h7607a-hardware` 1.0.0-4, described upstream as ASUS
  H7607BA keyboard, audio, input, and boot support
- Install record on the reference machine:
  `/usr/local/share/h7607a/installed-hardware-packages.json`

That project supports the ProArt P16 H7607BA-SE033W on firmware H7607BA.300.
Its installer checks the board name and BIOS version. Its early ACPI archive
is built from that machine's tables. Any owner-installed speaker tuning comes
from the ASUS audio package for that model; those calibration blobs are not
supplied by this HP tree.

Use the kernel, NVIDIA modules, userspace fix, and power-profile daemon at the
versions in `pins/packages.json`. Build the HP ACPI override from the OmniBook's
own tables with `01-platform/acpi/fix-hp-battery.sh`. Match speaker routing to the HP
card described in [Audio](audio.md).

The reference machine keeps those packages on `IgnorePkg` so a later
`nvidia-utils` upgrade cannot break the pinned tuple. Ordinary Arch Linux ARM
packages stay free to update.

`nvidia-n1x-modules` 615.78.08-4 depends on `nvidia-utils` 615.78.08-1 and
`linux-n1x-nvidia-bin` 7.0.0.1022.23-3. `h7607a-hardware` and
`power-profiles-daemon-n1x` are local builds from the upstream project and
stay on the same hold.

Package filenames, SHA256 values, signer fingerprints and the scope of the
signature checks are in [pins/provenance.json](../pins/provenance.json).
The cached packages were checked with `pacman-key --verify` on 2026-11-12;
uncached firmware packages are explicitly not claimed verified. Source input
hash checks do not imply independent verification of upstream source signatures.
See [NOTICE](../NOTICE) for copyright and license scope.
