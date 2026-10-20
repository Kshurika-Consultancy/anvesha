# Python runtime acquisition provenance

ANV-027; reviewed 2026-10-20. `python-downloads.json` is independently assembled
uv download metadata, using public facts from the PBS
[20261013 release assets](https://github.com/astral-sh/python-build-standalone/releases/tag/20261013).
Each URL and SHA-256 binds an install-only stripped, GIL-enabled archive for
CPython 3.12.15 or 3.14.8. No executable, build script or model weight is vendored.
Use the explicit [installation command](../../docs/SQLITE_RUNTIME.md#install-the-reviewed-runtime);
uv verifies archive hashes. The manifest has no client queries or credentials.

The build's [dependency declaration](https://github.com/astral-sh/python-build-standalone/blob/20261013/pythonbuild/downloads.json)
pins SQLite 3.53.1. Actual loaded source identity is compared to the
[SQLite release identity](https://www.sqlite.org/releaselog/3_53_1.html) in
verification evidence. Fixed upstream releases establish the narrow WAL-reset
fix status; no claim of overall runtime security or vendor-backport certification.
The checked-in hashes are acquisition pins, not platform acceptance. Windows and
Linux x86-64 are tested in CI; macOS and ARM64 entries still need actual tests.

CPython retains its PSF/CNRI and bundled dependency notices; SQLite is public
domain according to its [license](https://www.sqlite.org/copyright.html).
PBS build scripts have their own MPL-2.0 license and are not copied into core.
Python is installed unmodified from the reviewed upstream distribution. Its
dependencies keep their own terms; Apache-2.0 applies only to Anvesha's independent
code. No terms for input documents, models or hosted gateways change.

Install-only archives omit full build metadata and can omit separate notices.
The complete upstream notice aggregate is retained unmodified in
[third_party/python-build-standalone-20261013](../../third_party/python-build-standalone-20261013/)
with URL/hash provenance, and copied into the container alongside Python's own
runtime files. It covers upstream variants and does not assert every component
is present. Complete runtime sources/build recipes and dependency source URLs
are available in the pinned PBS repository/dependency declaration above; Anvesha
source is this public repository. Debian OS/package notices remain in the base
image. Keep these materials and applicable source obligations when redistributing
a built image. This repository does not publish runtime binaries or a container.

Maintainers must review future runtime/digest updates with primary evidence,
actual loaded identities, application tests and applicable third-party notices.
No floating download, automatic self-update or unsafe DLL replacement is added.
Broader release/security/update policy remains ANV-014; actual backup/restore
retention and hosted controls remain ANV-008.
