# Omarchy AArch64 Image

This project builds a generic AArch64 UEFI disk image for QEMU-compatible
virtual machines. The only supported profile is `aarch64-virt`, targeting
QEMU's `virt` machine and UTM's QEMU backend. It does not target Apple hardware,
Asahi Linux, SBSA machines, physical AArch64 boards, GRUB, or x86 multilib.

The project is one part of a three-repository release pipeline:

- [`riverscn/omarchy-aarch64`](https://github.com/riverscn/omarchy-aarch64)
  maintains the AArch64 runtime adaptation of Omarchy.
- [`riverscn/omarchy-pkgs-aarch64`](https://github.com/riverscn/omarchy-pkgs-aarch64)
  builds and publishes the signed stable AArch64 pacman repository.
- This repository assembles the VM image from Arch Linux ARM and that signed
  repository. It does not build or carry local package artifacts.

`main` is this repository's only long-lived development branch. Image releases
are immutable `v*-virt.*` tags built from reviewed commits on `main`; package
channels and runtime release lines do not create matching image branches.
Temporary integration branches are deleted after their commits reach `main`.

Keeping the repositories as siblings is convenient for development:

```text
workspace/
├── omarchy-aarch64/
├── omarchy-pkgs-aarch64/
└── omarchy-aarch64-image/
```

## Package source and updates

Image builds consume the complete signed repository published by the explicit
stable `omarchy-pkgs-aarch64` GitHub Release:

```ini
[omarchy]
SigLevel = Required
Server = https://github.com/riverscn/omarchy-pkgs-aarch64/releases/download/aarch64-stable
```

The builder downloads the Release manifest and public key on every build. It
rejects the snapshot unless all of these conditions hold:

- the manifest is the stable AArch64 schema expected by this project;
- its signing fingerprint matches the fingerprint pinned in `sources.env`;
- every package selected by `config/omarchy-packages.aarch64` is present;
- the manifest was assembled by the exact pinned package-repository commit;
- that reviewed package commit pins the selected `omarchy-aarch64` source and
  exact `omarchy`/`omarchy-settings` package version; and
- pacman verifies the signed database and packages with the trusted key.

The image installs `omarchy-aarch64-keyring`, so subsequent keyring updates are
managed by pacman. The repository remains enabled in the installed guest;
normal system updates therefore update Arch Linux ARM and Omarchy together:

```bash
sudo pacman -Syu
```

Omarchy's `refresh pacman` command intentionally regenerates `pacman.conf`.
The image installs the runtime-owned stable/RC/edge mapping, a repository
fragment, and the matching `pre-refresh-pacman` hook. Stable is the factory
default; `omarchy-channel-set` can then select stable, RC, edge, or dev without
depending on GitHub's repository-wide `latest` alias. Dev follows the edge
package repository and links the adapted canonical `quattro` source, matching
upstream's three-repository/four-choice model.

The source commit and signing fingerprint remain deliberate image release
boundaries. If the stable package snapshot moves to a newer Omarchy commit,
update `OMARCHY_AARCH64_REF` after reviewing that source update; until then the
image build fails instead of combining mismatched source and packages.

## Image contents

- Arch Linux ARM's generic AArch64 root filesystem and `linux-aarch64` kernel.
- GPT with a 1 GiB EFI System Partition and a Btrfs root using `@`, `@home`,
  `@log`, and `@pkg` subvolumes.
- An AArch64 Omarchy UKI at `EFI/Linux/omarchy_linux.efi`, rebuilt by the
  Limine mkinitcpio hook whenever the kernel changes. Limine is the normal boot
  path through `EFI/BOOT/BOOTAA64.EFI`, with its vendor copy retained at
  `EFI/limine/limine_aa64.efi`; it presents the branded Omarchy Bootloader menu
  and loads the UKI. It also provides snapshot and recovery entries, with
  Plymouth and a read-only `@factory` snapshot.
- Direct UKI boot remains an explicit user choice through Omarchy's
  `Setup > Direct Boot` command. The image does not register or prioritize a
  direct firmware entry automatically because doing so bypasses Limine and its
  snapshot menu. When reusing UEFI variable storage from an older test image,
  disable its existing `Omarchy` direct-boot entry before testing this path.
- During offline assembly, the builder exposes an isolated
  `/sys/firmware/efi` view only inside the disposable target chroot. Limine
  therefore follows its normal firmware-detection path; the package carries no
  environment-variable bypass and the host firmware state is not modified.
- VirtIO graphics, disk, network, RNG, QEMU guest-agent, SPICE clipboard and
  dynamic-display integration.
- QEMU 9p host-directory sharing preconfigured at `/mnt/hostshare` with the
  conventional `share` tag. After first-boot owner setup, the image detects the
  host and guest UID/GID values and exposes a writable mapped view at
  `~/Hostshare`. Its `nofail` mount does not block boot when no share is
  attached.
- PipeWire audio with PulseAudio, ALSA, JACK, and GStreamer compatibility. The
  printing stack is retained.
- The upstream Omarchy desktop and development defaults whenever a native
  package is available, including LibreOffice, Kdenlive, Moonlight, Night
  Light, Bluetooth userspace, and power profiles. GPU screen recording and OBS
  remain excluded until their generic AArch64 VM runtime is validated.
- The architecture-compatible Omarchy applications Obsidian, Pinta, Tensaku,
  and tzupdate. Pinta uses the maintained Microsoft binary .NET runtime; the
  .NET SDK remains a package-build dependency and is not installed in the VM.
- No `linux-firmware`, split `linux-firmware-*`, or `sof-firmware` payload is
  carried for the virtual hardware profile. Physical-machine setup is skipped,
  while portable upstream userspace packages remain installed. QEMU user-mode
  emulation is not installed or used.
- A tty1 first-boot wizard for keyboard, owner credentials, Git identity,
  hostname, and timezone before SDDM starts.
- An idempotent service that expands the root partition and Btrfs filesystem
  when the virtual disk is enlarged.

The distributed image is intentionally unencrypted. Per-machine encryption
requires an installer that creates a unique LUKS container rather than a shared
key embedded in a reusable disk image.

## GitHub and UTM releases

The `Publish AArch64 UTM image` workflow builds on GitHub's native
`ubuntu-24.04-arm` runner. It checks out the reviewed Omarchy source and native
builder revisions recorded in `sources.env`, restores only the signed rootfs
and Node.js download cache, builds the QCOW2, runs `qemu-img check`, and then
creates a draft Release. The draft is published only after GitHub reports the
same SHA-256 digest for every uploaded asset.

Create a version tag such as `v4.0.2-virt.1`, or run the workflow manually and
provide that tag. The Release does not duplicate the disk as a standalone
QCOW2. It contains:

- `install-Omarchy-virt.command`, used by the one-command macOS installer;
- `Install-Omarchy-virt.zip`, the GUI-oriented alternative;
- numbered `Omarchy-virt.utm.zip.part-*` payloads fetched by that installer;
- the executable installer by itself for command-line users;
- release/image manifests and SHA-256 checksums; and
- image provenance and an archive of the exact package inventories.

The primary user entry point always follows the latest verified Release:

```bash
/bin/bash -o pipefail -c 'curl -fsSL https://github.com/riverscn/omarchy-aarch64-image/releases/latest/download/install-Omarchy-virt.command | /bin/bash'
```

GitHub limits each Release asset to 2 GiB, while the compressed UTM bundle can
be larger. The packager therefore streams the uncompressed ZIP directly into
1,900 MiB numbered parts without first writing another full archive. The
macOS installer downloads and verifies every part, reconstructs and verifies
the UTM bundle, installs it in `~/Downloads` by default, and opens it in UTM.
An alternate destination directory can be passed as its first argument.

The clean template lives under `utm/Omarchy-virt.utm`; the small icon is stored
as base64 so the repository remains text-reviewable. No `efi_vars.fd`, saved
state, logs, or disk image is versioned or copied from the template. Before
opening the VM, the installer also generates new VM, drive, and locally
administered MAC identities. UTM creates fresh AArch64 EFI variable storage on
first launch, so firmware boot entries from the release builder cannot leak to
users.

For local release-layout testing after building an image:

```bash
./bin/package-utm-release --tag v4.0.2-virt.1
```

Set `OMARCHY_UTM_CONSUME_IMAGE=1` only in storage-constrained automation: after
the archive stream has been split successfully, it removes that exact source
QCOW2 and its checksum. Normal local packaging retains the image.

## Build

Image assembly runs AArch64 target commands in a chroot and therefore requires
a native AArch64 Arch Linux ARM host. Docker, Git, and the usual core tools are
required. The container wrapper performs privileged disk assembly without
installing the image tools on the host.

The wrapper currently reuses the AArch64 build environment owned by the package
repository. Build that container once from the sibling checkout:

```bash
docker build \
  --platform linux/arm64 \
  --target builder \
  --tag omarchy-pkg-builder:latest-aarch64-edge \
  ../omarchy-pkgs-aarch64/build
```

Then build the disk image directly; there is no package-build step:

```bash
./bin/build-image-container
```

The equivalent native command is:

```bash
sudo ./bin/build-image
```

Common options accepted by both entry points are:

```bash
./bin/build-image-container --size 80G --format both
./bin/build-image-container --refresh --force
sudo ./bin/build-image --rootfs /path/to/ArchLinuxARM-aarch64-latest.tar.gz
```

`--omarchy-source /path/to/omarchy-aarch64` is an explicit development
override. `--omarchy-repository /path/to/repository` likewise consumes a
complete, signed repository prepared locally by `omarchy-pkgs-aarch64`. Use
the two together to test unpublished source and package changes:

```bash
./bin/build-image-container \
  --omarchy-source ../omarchy-aarch64 \
  --omarchy-repository ../omarchy-pkgs-aarch64/pkgs.omarchy.org/stable/aarch64 \
  --force
```

The local repository is mounted read-only and is used only while assembling
the image. The installed guest still points at the explicit stable GitHub
Release, so a successful test image follows the normal stable update channel
without rebuilding.
The source commit, package-repository commit, and expected runtime package
version must match the immutable inputs in `sources.env` and the complete
package state recorded in the repository manifest.

The Arch Linux ARM rootfs is verified with its signing key and pinned signer
fingerprint. Node.js is checked against its published SHA-256 list. Cached
rootfs, keyring, Node.js, and pacman package downloads are reused by default;
`--refresh` refreshes rolling non-repository inputs. Stable Release metadata is
always downloaded again so a cached manifest cannot be mistaken for the
current channel snapshot.

The default artifact is `build/omarchy-aarch64-virt.qcow2`. Existing outputs
are not replaced unless `--force` is supplied. A successful build also emits:

- a SHA-256 checksum for each image;
- complete and explicit installed-package inventories;
- a package size/dependency table and orphan list; and
- `build/image-provenance.txt`, recording verified inputs, repository manifest
  digest, signing fingerprint, source commit, profile, format, and image size.

## Run

Install `qemu-system-aarch64`, `qemu-img`, and AArch64 EDK2 firmware, then run:

```bash
./bin/run-image build/omarchy-aarch64-virt.qcow2
```

The helper is a basic GTK and SSH-forwarding launcher. UTM can import the same
QCOW2 using an ARM64 `virt` machine, UEFI, VirtIO disk/network/GPU, and a SPICE
agent channel. The SPICE channel is required for guest clipboard sharing and
dynamic display resizing. QEMU frontends can expose a host directory at the
preconfigured `/mnt/hostshare` path by assigning its 9p device the `share`
mount tag. In UTM, select a shared directory and choose VirtFS rather than
SPICE WebDAV. The image follows the permission-mapping approach in
[UTM's VirtFS documentation](https://docs.getutm.app/guest-support/linux/#virtfs),
but uses frontend-neutral `hostshare` naming: `/mnt/hostshare` is the raw mount
and `~/Hostshare` is the automatically mapped, user-facing directory. Configure
the shared directory while the VM is stopped, then boot normally; no manual
UID/GID lookup or `chown` is needed.

## Profiles and tests

Everything specific to `aarch64-virt` lives under
`profiles/aarch64-virt/`: image defaults, package additions/exclusions,
replacement and removal rules, and the filesystem overlay.
Package removal is performed through pacman rather than by deleting owned files.

Run the static contract suite with the source repository as a sibling:

```bash
OMARCHY_TEST_SOURCE=../omarchy-aarch64 ./tests/run
```

The environment variable may be omitted for the sibling layout. A complete
image build and QEMU/UTM boot remain release checks.
