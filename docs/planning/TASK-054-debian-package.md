# Task 054 - Debian Package and Linux Compatibility Matrix

## Objective

Add a policy-conscious `.deb` distribution for Debian, Ubuntu and Linux Mint
without replacing or mutating the existing per-user wheel installation. Bind
the package to the same product version and release commit as the wheel and
source archive, and prove installation in disposable environments.

## Package Contract

- Build `ai-presence-monitor_<version>_all.deb` from the exact project wheel.
- Install pure Python modules under `/usr/lib/python3/dist-packages` and fixed
  command wrappers under `/usr/bin`.
- Install the tray launcher, configuration example and bounded documentation
  under `/usr/lib` and `/usr/share`.
- Depend on CPython 3.10 through 3.12 and perform no network access during
  package installation.
- Never create or overwrite a user's `.env`, database, controls, services,
  hooks, autostart entry or home-directory files from maintainer scripts.
- Preserve the existing wheel installer as the supported unprivileged path.

## Implementation Phases

1. Add a deterministic Debian builder, SHA-256 sidecar and offline verifier.
2. Add regression tests for metadata, paths, wrappers and unsafe build input.
3. Include the `.deb` in the canonical Linux release bundle and checksums.
4. Document installation, coexistence, upgrade, removal and tray limitations.
5. Run `lintian`, a non-mutating Linux Mint smoke test and real disposable
   installs on Debian 12, Ubuntu 22.04 and Ubuntu 24.04 containers.
6. Assess local KVM/QEMU readiness for later full-desktop E2E testing.
7. Run the full quality and Python matrix gates before promotion.

## Platform Boundaries

Containers validate package management, dependencies, CLI, SQLite and file
layout. They do not prove a graphical tray, a desktop session, user systemd,
X11/Wayland, Codex GUI or suspend/resume behavior. Those require full virtual
machines or physical hosts.

Windows remains experimental and requires a real Windows VM for Task Scheduler,
Win32 and desktop E2E evidence. Wine is not equivalent evidence. macOS support
is not implemented; professional validation requires Apple hardware or a
legitimate hosted macOS runner rather than an unsupported Linux-hosted image.

## Promotion Boundary

This task may build local artifacts and promote validated source changes. It
does not publish a GitHub release, install the `.deb` into the current host,
enable Windows, install virtualization packages with elevated privileges or
claim GUI E2E evidence without a full guest operating system.

## Validation Evidence

On 2026-11-04, the development candidate passed package verification and
`lintian` with only the documented private-package override. Disposable real
APT installs passed on Debian 12, Ubuntu 22.04 and Ubuntu 24.04, covering
Python 3.11, 3.10 and 3.12 respectively. Each guest proved version reporting,
schema-3 initialization and health, bounded doctor output, package removal and
absence of residual files under the package Python namespace.

The Linux Mint 21.3 host exposes `/dev/kvm`, but QEMU, libvirt, virt-install,
VirtualBox and Multipass are not installed. Therefore hardware virtualization
is available in principle, while full desktop-guest E2E remains a separate,
operator-approved setup. The recommended future stack is QEMU/KVM with
libvirt/virt-manager and dedicated Debian/Ubuntu desktop guests. No elevated
package installation was performed in this task.
