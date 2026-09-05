"""PyHamilton's installer and configurator.

This file is **standard library only and imports nothing from pyhamilton**, on
purpose. Everything it does -- running the vendor installers, placing the HSL
library tree, writing ``defaults.json``, unblocking DLLs, provisioning the
32-bit sidecar interpreter, elevating -- is prerequisite work that has to run
when ``import pyhamilton`` is exactly what is failing. It used to live in
``__init__.py``, behind that import.

That constraint also lets it be delivered two ways from one file:

  * fetched on its own by ``install.ps1`` and run under an interpreter uv just
    downloaded, before PyHamilton exists on the machine at all;
  * shipped in the package, where ``pyhamilton configure`` runs this same file.

Same code, two routes, so the two cannot drift.

    python -m pyhamilton._bootstrap configure [--yes] [--dry-run]
    python -m pyhamilton._bootstrap doctor
    python -m pyhamilton._bootstrap sidecar [--python-version 3.11]
"""

from __future__ import annotations

import argparse
import ctypes
import filecmp
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

WINDOWS = os.name == "nt"
COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

CONFIG_DIR = Path.home() / ".pyhamilton"
DEFAULTS_PATH = CONFIG_DIR / "defaults.json"
SIDECAR_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "pyhamilton" / "py32"
SIDECAR_PYTHON = SIDECAR_DIR / "python.exe"
PYTHON_32BIT_KEY = "python_32bit_path"

# Line-buffered, utf-8: the transcript is the support artifact, and a piped
# stdout on Windows still defaults to a legacy codepage.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if COLOR else text


def say(message: str) -> None:
    print(f"  {message}")


def step(message: str) -> None:
    print("\n" + _c("36", f"==> {message}"))


def ok(message: str) -> None:
    print(f"  {_c('32', 'OK')}  {message}")


def warn(message: str) -> None:
    print(f"  {_c('33', 'WARN')}  {message}")


def fail(message: str) -> None:
    print(f"  {_c('31', 'FAIL')}  {message}")


class ConfigureError(Exception):
    """A failure worth showing the user, with the transcript above it."""


# --------------------------------------------------------------- locating things
def package_dir() -> Path:
    """The installed pyhamilton package directory.

    Found by location, never by import: this file must work when importing the
    package is what is broken. When run as part of the package it is the parent
    directory; when fetched standalone it has to be looked up.
    """
    here = Path(__file__).resolve().parent
    if (here / "interface.py").exists():
        return here
    for entry in sys.path:
        candidate = Path(entry) / "pyhamilton"
        if (candidate / "interface.py").exists():
            return candidate
    raise ConfigureError(
        "cannot find an installed pyhamilton package. Install it first "
        "(`uv add pyhamilton`, or `pip install -e .` in a checkout)."
    )


def venus_root() -> str | None:
    """Venus's install directory, from the registry, then the usual places."""
    if WINDOWS:
        try:
            import winreg
        except ImportError:  # pragma: no cover
            winreg = None
        if winreg is not None:
            keys = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Hamilton\HAMILTON"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Hamilton\HAMILTON"),
            ]
            for hive, path in keys:
                for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
                    try:
                        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ | view) as key:
                            for name in ("InstallDir", "Path", "InstallPath"):
                                try:
                                    value = winreg.QueryValueEx(key, name)[0]
                                except OSError:
                                    continue
                                if value and os.path.isdir(value):
                                    return value
                    except OSError:
                        continue
    for candidate in (r"C:\Program Files (x86)\HAMILTON", r"C:\Program Files\HAMILTON"):
        if os.path.isdir(candidate):
            return candidate
    return None


def is_admin() -> bool:
    if not WINDOWS:
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):  # pragma: no cover
        return False


def venus_is_running() -> list[str]:
    """Venus processes that would make configuring now a bad idea.

    Copying libraries out from under a running method, or replacing a DLL Venus
    has open, is the one thing an installer must not do on an instrument PC.
    """
    if not WINDOWS:
        return []
    watched = {"hxrun.exe", "hxgui.exe", "runhslexecutor.exe", "hamilton.exe"}
    try:
        output = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True, text=True, timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found = []
    for line in output.splitlines():
        name = line.split(",")[0].strip('"').lower()
        if name in watched:
            found.append(name)
    return sorted(set(found))


# ------------------------------------------------------------------- copying
@dataclass
class CopyResult:
    copied: int = 0
    unchanged: int = 0
    backed_up: list[str] = field(default_factory=list)


def copy_tree(source_dir, target_dir, backup_dir=None, dry_run=False,
              result: CopyResult | None = None) -> CopyResult:
    """Copy a tree, replacing files whose contents differ.

    The version this replaces skipped every file that already existed, which
    meant upgrading PyHamilton never updated a library file already present in
    the Hamilton install: an upgrade's failure mode was a stale library, and it
    was silent. Comparing contents makes a re-run idempotent *and* corrective,
    and anything about to be overwritten is backed up first.
    """
    result = result or CopyResult()
    source_dir, target_dir = Path(source_dir), Path(target_dir)
    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
    for item in sorted(source_dir.iterdir()):
        target = target_dir / item.name
        if item.is_dir():
            copy_tree(item, target, backup_dir, dry_run, result)
            continue
        if target.exists() and filecmp.cmp(item, target, shallow=False):
            result.unchanged += 1
            continue
        if target.exists() and backup_dir and not dry_run:
            backup = Path(backup_dir) / target.name
            Path(backup_dir).mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
            result.backed_up.append(str(target))
        if not dry_run:
            shutil.copy2(item, target)
        result.copied += 1
    return result


def unblock(directory: Path) -> int:
    """Strip the Zone.Identifier stream Windows adds to downloaded files.

    A blocked DLL fails to load with a CLR error that names an assembly and not
    the cause. The README's troubleshooting section sends people to a
    StackOverflow thread to fix this by hand; it is two lines of code.
    """
    if not WINDOWS:
        return 0
    removed = 0
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        stream = f"{path}:Zone.Identifier"
        try:
            if os.path.exists(stream):
                os.remove(stream)
                removed += 1
        except OSError:
            continue
    return removed


# ------------------------------------------------------------ vendor installers
# Silent-install switches, fingerprinted per installer. `os.startfile` on all
# nine at once gave nine UAC prompts in undefined order and no exit codes, so a
# vendor installer that failed, was cancelled, or was blocked by AV looked
# exactly like one that worked.
INNO_FLAGS = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"]


def installer_command(path: Path) -> list[str]:
    if path.suffix.lower() == ".msi":
        return ["msiexec", "/i", str(path), "/qn", "/norestart"]
    return [str(path), *INNO_FLAGS]


def run_installers(exe_dir: Path, dry_run=False) -> list[tuple[str, int]]:
    """Run the bundled vendor installers one at a time, collecting exit codes."""
    failures = []
    installers = sorted(p for p in exe_dir.iterdir()
                        if p.suffix.lower() in (".exe", ".msi"))
    if not installers:
        raise ConfigureError(
            f"no vendor installers found in {exe_dir}. If this is a git checkout, "
            "the LFS objects may not have been fetched (`git lfs pull`)."
        )
    for installer in installers:
        # An LFS pointer file is a few hundred bytes of text. Running one does
        # nothing and reports nothing.
        with open(installer, "rb") as f:
            magic = f.read(2)
        if installer.suffix.lower() == ".exe" and magic != b"MZ":
            failures.append((installer.name, -1))
            fail(f"{installer.name} is not an executable (git-lfs pointer?)")
            continue
        if dry_run:
            say(f"would run: {' '.join(installer_command(installer))}")
            continue
        say(f"installing {installer.name}")
        try:
            code = subprocess.run(installer_command(installer), timeout=900).returncode
        except subprocess.TimeoutExpired:
            failures.append((installer.name, -2))
            fail(f"{installer.name} did not finish within 15 minutes")
            continue
        except OSError as exc:
            failures.append((installer.name, -3))
            fail(f"{installer.name}: {exc}")
            continue
        # 3010 is "success, reboot required" and 1638 is "a newer version is
        # already installed" -- both are fine outcomes for a re-run.
        if code in (0, 1638, 3010):
            ok(f"{installer.name} (exit {code})")
        else:
            failures.append((installer.name, code))
            fail(f"{installer.name} exited {code}")
    return failures


# ------------------------------------------------------------------- defaults
def merge_defaults(source: Path | None, updates: dict | None = None, dry_run=False) -> None:
    """Merge shipped defaults into ~/.pyhamilton/defaults.json.

    Never overwrite: re-running configure is the advertised fix for everything
    else, and it must not be the thing that destroys a customised liquids
    database path. Shipped keys fill gaps; existing values win.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    current = {}
    if DEFAULTS_PATH.exists():
        try:
            current = json.loads(DEFAULTS_PATH.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            backup = DEFAULTS_PATH.with_suffix(".json.bad")
            warn(f"{DEFAULTS_PATH} is not readable JSON; keeping a copy at {backup.name}")
            if not dry_run:
                shutil.copy2(DEFAULTS_PATH, backup)
            current = {}

    shipped = {}
    if source is None:
        pass  # called only to record a key; nothing shipped to merge
    elif source.exists():
        try:
            shipped = json.loads(source.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            warn(f"shipped defaults at {source} are not readable JSON")
    else:
        warn(f"no shipped defaults at {source} (packaging problem, not fatal)")

    merged = {**shipped, **current, **(updates or {})}
    if merged == current and DEFAULTS_PATH.exists():
        ok(f"{DEFAULTS_PATH} already up to date")
        return
    if dry_run:
        say(f"would write {DEFAULTS_PATH}")
        return
    DEFAULTS_PATH.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    ok(f"{DEFAULTS_PATH} written ({len(merged)} keys, existing values kept)")


# --------------------------------------------------------- 32-bit sidecar Python
# uv cannot supply this one: python-build-standalone publishes no 32-bit Windows
# build, so every interpreter uv offers is x86_64. python.org still ships an x86
# installer, and it installs per-user and silently, which is all we need.
PYTHON_ORG_URL = "https://www.python.org/ftp/python/{version}/python-{version}.exe"


def install_sidecar_python(version="3.11.9", dry_run=False) -> Path:
    if not WINDOWS:
        raise ConfigureError("the 32-bit sidecar is Windows-only")
    if SIDECAR_PYTHON.exists():
        ok(f"32-bit Python already at {SIDECAR_PYTHON}")
        return SIDECAR_PYTHON
    url = PYTHON_ORG_URL.format(version=version)
    say(f"downloading 32-bit Python {version}")
    if dry_run:
        say(f"would install {url} into {SIDECAR_DIR}")
        return SIDECAR_PYTHON
    with tempfile.TemporaryDirectory() as tmp:
        installer = Path(tmp) / "python-x86.exe"
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                installer.write_bytes(response.read())
        except OSError as exc:
            raise ConfigureError(
                f"could not download 32-bit Python from {url} ({exc}).\n"
                "    Behind a proxy? Download it by hand, install it anywhere, and "
                "point PYTHON_32BIT_PATH at its python.exe."
            )
        # Per-user, no PATH changes, no launcher: this interpreter exists only to
        # host the CLR bridge and must not become the machine's default python.
        code = subprocess.run([
            str(installer), "/quiet", "InstallAllUsers=0", "PrependPath=0",
            "Include_launcher=0", "Include_test=0", "AssociateFiles=0",
            f"TargetDir={SIDECAR_DIR}",
        ], timeout=1800).returncode
    if code != 0 or not SIDECAR_PYTHON.exists():
        raise ConfigureError(f"the 32-bit Python installer exited {code}")

    # pythonnet and nothing else. This is only possible because
    # run_venus_client.py imports nothing from pyhamilton -- several of the
    # package's dependencies publish no 32-bit Windows wheels at all.
    # PIP_TARGET / PIP_USER / PIP_PREFIX would put pythonnet somewhere this
    # interpreter does not import from, and PYTHONPATH would let the 64-bit
    # environment leak into the 32-bit one. Strip them for this call.
    pip_env = {k: v for k, v in os.environ.items()
               if k not in ("PIP_TARGET", "PIP_USER", "PIP_PREFIX",
                            "PYTHONPATH", "PYTHONHOME")}
    if subprocess.run([str(SIDECAR_PYTHON), "-m", "pip", "install", "--upgrade",
                       "pip", "pythonnet"], env=pip_env, timeout=900).returncode != 0:
        raise ConfigureError("could not install pythonnet into the 32-bit interpreter")
    ok(f"32-bit sidecar at {SIDECAR_PYTHON}")
    return SIDECAR_PYTHON


def record_sidecar_path(path: Path, dry_run=False) -> None:
    """Write the sidecar path where the interface will actually look.

    Both the config file and the user environment: an install whose correctness
    depends on an environment variable surviving is one that breaks the first
    time someone opens a different terminal.
    """
    merge_defaults(None, updates={PYTHON_32BIT_KEY: str(path)}, dry_run=dry_run)
    if not WINDOWS or dry_run:
        return
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                            winreg.KEY_READ | winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, "PYTHON_32BIT_PATH", 0, winreg.REG_SZ, str(path))
        ok("PYTHON_32BIT_PATH set for future terminals")
    except OSError as exc:
        warn(f"could not set PYTHON_32BIT_PATH ({exc}); the config file covers it")


# ------------------------------------------------------------------ elevation
def elevate(args: list[str]) -> int:
    """Re-launch this command elevated, once, and relay its output.

    The elevated console is a new window that closes when it finishes, taking
    any error with it -- so the child writes to a log file and this process
    prints it afterwards.
    """
    if not WINDOWS:
        raise ConfigureError("elevation is Windows-only")
    log = Path(tempfile.gettempdir()) / "pyhamilton-configure.log"
    if log.exists():
        log.unlink()
    # cmd /c ... > log 2>&1, so the child needs no cooperation to be captured.
    command = " ".join(f'"{part}"' for part in [sys.executable, "-m",
                                               "pyhamilton._bootstrap", *args])
    params = f'/c {command} > "{log}" 2>&1'
    say("asking for administrator rights (one UAC prompt)")
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", params, None, 0)
    if result <= 32:
        raise ConfigureError(
            "the administrator prompt was declined or failed. Nothing has been "
            "changed; re-run and accept it, or run this from an Administrator "
            "PowerShell."
        )
    # ShellExecuteW does not wait, so poll for the log to stop growing.
    import time
    last_size, stable = -1, 0
    while stable < 6:
        time.sleep(1)
        size = log.stat().st_size if log.exists() else 0
        stable = stable + 1 if size == last_size else 0
        last_size = size
    if log.exists():
        print(log.read_text(encoding="utf-8", errors="replace"))
        return 0 if "CONFIGURE FAILED" not in log.read_text(
            encoding="utf-8", errors="replace") else 1
    return 0


# ------------------------------------------------------------------- configure
def summarise(pkg: Path, hamilton_lib: Path) -> str:
    exe_dir = pkg / "bin"
    installers = sorted(p.name for p in exe_dir.iterdir()
                        if p.suffix.lower() in (".exe", ".msi")) if exe_dir.is_dir() else []
    pending = copy_tree(pkg / "library", hamilton_lib, dry_run=True) \
        if (pkg / "library").is_dir() else CopyResult()
    lines = [
        "This will:",
        f"  - run {len(installers)} vendor installer(s) from {exe_dir}",
        f"  - write {pending.copied} file(s) into {hamilton_lib} "
        f"({pending.unchanged} already match)",
        f"  - back up anything it replaces under {CONFIG_DIR / 'backup'}",
        f"  - merge shipped defaults into {DEFAULTS_PATH} (your values are kept)",
    ]
    return "\n".join(lines)


def configure(assume_yes=False, dry_run=False, skip_installers=False,
              skip_sidecar=False) -> int:
    if not WINDOWS:
        raise ConfigureError(
            "configure only applies to Windows -- it places files in the Venus "
            "installation. On macOS or Linux the simulation path needs nothing "
            "configured; run `pyhamilton doctor` to confirm it works."
        )
    pkg = package_dir()
    root = venus_root()
    if root is None:
        raise ConfigureError(
            "Venus does not appear to be installed (nothing in the registry, and "
            "no HAMILTON directory in either Program Files).\n"
            "    Install and test the Hamilton software suite first."
        )
    hamilton_lib = Path(root) / "Library"
    ok(f"Venus at {root}")

    running = venus_is_running()
    if running:
        raise ConfigureError(
            f"Venus appears to be running ({', '.join(running)}).\n"
            "    Close Run Control and any running method before configuring -- "
            "this replaces files Venus has open."
        )

    print()
    print(summarise(pkg, hamilton_lib))
    if not assume_yes and not dry_run:
        if not sys.stdin.isatty():
            raise ConfigureError(
                "configure needs confirmation but is not attached to a terminal. "
                "Pass --yes to run unattended."
            )
        answer = input("\nContinue? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            say("nothing was changed")
            return 1

    # One elevated step, and only if the destination actually needs it.
    if not dry_run and not is_admin() and not os.access(hamilton_lib, os.W_OK):
        args = ["configure", "--yes"]
        if skip_installers:
            args.append("--skip-installers")
        if skip_sidecar:
            args.append("--skip-sidecar")
        return elevate(args)

    failures = []
    if not skip_installers:
        step("Running the bundled vendor installers")
        failures = run_installers(pkg / "bin", dry_run=dry_run)

    step("Placing the HSL library files")
    backup = CONFIG_DIR / "backup"
    result = copy_tree(pkg / "library", hamilton_lib, backup_dir=backup, dry_run=dry_run)
    ok(f"{result.copied} written, {result.unchanged} unchanged, "
       f"{len(result.backed_up)} backed up to {backup}")

    step("Unblocking the OEM assemblies")
    if dry_run:
        say("would clear any Zone.Identifier streams under star-oem")
    else:
        removed = unblock(pkg / "star-oem")
        ok(f"{removed} file(s) unblocked" if removed else "nothing was blocked")

    step("Writing user defaults")
    merge_defaults(pkg / "defaults" / "defaults.json", dry_run=dry_run)

    if not skip_sidecar and not dry_run:
        step("Provisioning the 32-bit Venus sidecar interpreter")
        try:
            record_sidecar_path(install_sidecar_python(), dry_run=dry_run)
        except ConfigureError as exc:
            # Not fatal: everything except server_mode works without it.
            warn(str(exc))
            warn("server mode will not work until this is resolved; "
                 "everything else is configured.")

    if failures:
        raise ConfigureError(
            "these vendor installers did not succeed: "
            + ", ".join(f"{name} (exit {code})" for name, code in failures)
        )
    print()
    ok("configuration complete")
    say("Verify it with:  pyhamilton doctor")
    return 0


# ---------------------------------------------------------------------- main
def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog="pyhamilton", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_configure = sub.add_parser("configure", help="configure this machine's Venus install")
    p_configure.add_argument("--yes", "-y", action="store_true", help="do not ask for confirmation")
    p_configure.add_argument("--dry-run", action="store_true", help="show what would change")
    p_configure.add_argument("--skip-installers", action="store_true")
    p_configure.add_argument("--skip-sidecar", action="store_true")

    sub.add_parser("doctor", help="check this installation and say what is wrong")

    p_sidecar = sub.add_parser("sidecar", help="install the 32-bit sidecar interpreter")
    p_sidecar.add_argument("--python-version", default="3.11.9")

    p_new = sub.add_parser("new-project", help="write a project template here")
    p_new.add_argument("--ai", action="store_true", help="the AI assistant template")

    args = parser.parse_args(argv)
    try:
        if args.command == "configure":
            return configure(assume_yes=args.yes, dry_run=args.dry_run,
                             skip_installers=args.skip_installers,
                             skip_sidecar=args.skip_sidecar)
        if args.command == "sidecar":
            record_sidecar_path(install_sidecar_python(args.python_version))
            return 0
        if args.command == "doctor":
            # The only command that needs the package: its most valuable check
            # is a dry run through the real code path.
            return subprocess.run([sys.executable, "-m", "pyhamilton.doctor"]).returncode
        if args.command == "new-project":
            from pyhamilton import create_ai_project, create_project
            (create_ai_project if args.ai else create_project)()
            return 0
    except ConfigureError as exc:
        print(_c("31", f"\nCONFIGURE FAILED: {exc}"))
        print(
            "\nCopy everything above this line into a post on labautomation.io, or "
            "email stefanmgolas@gmail.com, along with your Windows version and what "
            "was already installed. That transcript is enough to diagnose it; a "
            "screenshot of one line usually is not."
        )
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted. Re-running is safe -- it picks up where it stopped.")
        return 130
    return 2


def configure_entry_point() -> int:
    """The historical `pyhamilton-configure` command."""
    return main(["configure", *sys.argv[1:]])


if __name__ == "__main__":
    sys.exit(main())
