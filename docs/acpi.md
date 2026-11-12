# Battery ACPI override

Stock firmware on this board makes Linux drop the battery.

`BAT0._STA` calls `\_SB.FFA0.RBUF`. That method builds a 64-byte buffer and
then creates field `DATA` at bit 208 for 400 bits. Bits 208 through 607 need
76 bytes. The kernel reports:

```
Field [DATA] at bit offset/length 208/400 exceeds size of target Buffer (512 bits)
```

The abort also takes down AC status and thermal methods that share the call.
`/sys/class/power_supply` stays empty until the table is overridden.

`01-platform/acpi/collect-acpi.sh DEST_DIR` saves DSDT, SSDT, and FACP from
sysfs for inspection. It skips MSDM. `DEST_DIR` has to be outside this
repository.

`01-platform/acpi/fix-hp-battery.sh` dumps the tables the running kernel is
using, disassembles them with `iasl`, and runs `fix-hp-battery.py` beside it.
The
patcher changes that one buffer from 64 bytes to 80 (640 bits) and increments
the DefinitionBlock revision so the kernel accepts the override. It compiles
the result and installs `hp-omnibook-battery.aml` for the `acpi_override`
hook.

Nothing is written to firmware flash. The script refuses to run unless the
product is `HP OmniBook X Laptop 14-ks000`, the board is `8F22`, and the BIOS
is `F.05`. It also refuses to resize a buffer that is not 64 bytes, and it
refuses to add a second `*.aml` beside one already present in
`/etc/initcpio/acpi_override/`.

The disassembly and the compiled table stay in `/var/lib/hp-omnibook-acpi` on
the machine. Do not commit them. AML bytes depend on the `iasl` version.

After reboot, `BAT0` and `ADP1` should appear under `/sys/class/power_supply`,
and the kernel log should be free of `AE_AML_BUFFER_LIMIT` for `\_SB.FFA0.RBUF`.

Keep a boot entry that does not load the override until the new initramfs has
been checked.
