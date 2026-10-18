# ABI baselines

The existing Ubuntu x86-64 release build adds debug information without changing
its Release optimization or LTO settings. Packaging retains the existing strip
policy. The unstripped build-tree library is saved separately with its source
commit, version, ELF identity, SONAME, exported symbols, checksum and tool versions.

`save_abi_baseline.py LIBRARY VERSION` validates DWARF and a self-comparison before
writing the JSON manifest and archive. It does not need a previous baseline and
does not compile anything. The first normal release establishes the starting
point; no historical debug recovery or Boost dependency is introduced.

Only release jobs publish baselines. Enable the comparison change only after a
formal release has supplied a baseline. Draft and prerelease assets are not
selected. Releases declaring `.github/abi-baseline-schema` must supply the
manifest and library. Both modes check the release API inventory for exactly one
of each required asset before downloading; missing or duplicate assets fail
rather than reverting to bootstrap.
Older releases are explicitly reported as predating baseline recording.

PR checks read the small manifests from recorded releases to protect historical
symbol versions, and download the latest applicable unstripped library for type
comparison. Release checks compare every recorded type baseline. This is not a
claim of complete historical type coverage on each PR. Source commit, tag, ELF
identity and SONAME are verified before use. Archive contents and library checksums
are verified only for downloaded archives: the latest in PR mode, all in release
mode. Inventory presence alone does not establish an archive's integrity.

Before layout suppression, exported function parameter and return type identities
are compared using abidw declarations. Typedefs are resolved to their underlying
types so retargeting cannot be hidden by a stable alias name. Unresolved or
unsupported type nodes fail analysis. This additional identity comparison is not
a replacement for abidiff's layout and calling-convention checks.

Type analysis suppresses layout changes reached through pointers to the explicitly
opaque WasmEdge_VMContext and WasmEdge_ConfigureContext types. It does not suppress
by-value layouts, public value types, removed exports or pointer-to-value signature
changes. Other opaque types require review and a focused regression test before
adding an exception; there is no blanket Context-name suppression.

The gate controls the selected Ubuntu job, not every platform or manual GitHub
release publication. Repository required-check and publication settings remain
separate from this YAML. No extra library build is introduced.

This does not recover missing historical type information. Local historical
rebuilds are regression evidence, not automatically trusted release baselines.
The scope is Linux x86-64, not all release platforms or Debian package upgrades.
