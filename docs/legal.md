# Licensing and redistribution

The source tree is mixed-license. [NOTICE](../NOTICE) maps the scope:
independent helpers and documentation are MIT; kernel patches and the sleep
companion retain GPL-2.0-only. The full upstream MIT and GPL notices are in
[LICENSES](../LICENSES). Keep them when copying or adapting this tree.

The initial commit contained scripts, configuration, documentation and a
synthetic ASL fixture. It did not distribute firmware dumps, AML overrides,
kernel/module binaries or proprietary tuning. This review found no obvious
redistribution blocker in that tree. It did not establish independent
authorship of every line or provide legal clearance for third-party inputs.
The added full upstream notices and provenance remove ambiguity; creating a
new repository would not undo an earlier distribution.

[MIT requires retaining its copyright and permission notice](https://opensource.org/license/mit).
[Linux documents its GPL-2.0-only licensing and per-file exceptions](https://docs.kernel.org/process/license-rules.html).
A top-level MIT license does not relicense copied kernel code. Source
patches retain authorship and existing sign-offs. This project does not add
a contributor's sign-off without their certification.

ACPI collectors and patchers use the owner's local firmware; neither the
full original nor modified table is committed. The small AML instruction
pattern, hashes and independently written transformation identify the
reviewed fix. They are not a license to republish HP firmware. The optional
binary SoundWire workaround changes a local GPL module; its output stays
local. Prefer the upstream source topology on kernels that provide it.

If publishing binary releases, first assemble the complete corresponding
source, modifications, configurations and build/install scripts for the
exact GPL binaries, retain all notices, and separately check licenses for
every firmware and userspace artifact. A repository of helper scripts alone
is not sufficient for distributing a modified kernel bundle. Private signing
keys must remain private.

Signatures establish who signed particular package bytes; they do not grant
redistribution rights or certify HP functionality. The record in
[pins/provenance.json](../pins/provenance.json) distinguishes verified package
signatures from source inputs checked only by hash.

## HP speaker firmware

The [speaker tuning record](speaker-tuning.md) publishes independently written
observations, filenames, mappings and archive metadata. It does not include
HP's recovery image, Windows driver package, INF text or firmware binaries.
The repository's MIT license does not grant rights to those separate inputs.

The [U.S. Copyright Office distinguishes facts and discoveries from protected expression](https://www.copyright.gov/what-is-copyright/).
The recovery source is reported as factual provenance in original prose.

[HP's general software EULA](https://support.hp.com/us-en/document/ish_4416646-4390016-16)
describes use on a single HP product, withholds general distribution rights,
and has a separate restriction on use of recovery solutions. Separate supplier
terms can apply. No package-specific grant permitting redistribution or use
of these extracted files under Linux has been established in this review.
The `LICENSE.cirrus` shipped by linux-firmware does not by itself establish
that the HP Windows package was supplied under that license. Keep the HP
files out of git; the technical inventory is not a licensing clearance.

These are compliance measures and a scoped source review, not a legal opinion
or a guarantee against patent, trademark or other claims. Obtain legal advice
before a commercial or binary redistribution that goes beyond this tree.
