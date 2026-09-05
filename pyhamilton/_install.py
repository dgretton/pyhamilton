"""The PyHamilton installer.

Not normally run directly -- ``install.ps1`` fetches a Python and hands off to
it. Run it by hand while developing:

    uv run --no-project pyhamilton/_install.py [--root DIR] [--dev]

It creates a method project, installs PyHamilton into it, and then hands the
machine-level work (vendor installers, the Venus library tree, the 32-bit
sidecar) to ``pyhamilton._bootstrap``, which by that point is installed.

Standard library only, and it imports nothing from pyhamilton: it runs under
the interpreter uv just fetched, before the package exists anywhere.
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO_URL = "https://github.com/dgretton/pyhamilton"
BRANCH = "main"
DEFAULT_PROJECT = "pyhamilton-methods"
PYTHON_VERSION = "3.11"

WINDOWS = os.name == "nt"
COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass


def _c(code, text):
    return f"\033[{code}m{text}\033[0m" if COLOR else text


def say(message):
    print(f"  {message}")


def step(message):
    print("\n" + _c("36", f"==> {message}"))


def ok(message):
    print(f"  {_c('32', 'OK')}  {message}")


class InstallError(Exception):
    """A failure worth showing the user, with the transcript above it."""


def run(cmd, **kwargs):
    """Run a command, letting its output through. The transcript is the artifact."""
    return subprocess.run([str(part) for part in cmd], **kwargs)


def which_uv() -> str:
    candidates = [os.environ.get("UV_BIN"), shutil.which("uv")]
    home = Path.home()
    candidates += [home / ".local" / "bin" / ("uv.exe" if WINDOWS else "uv")]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise InstallError(
        "uv is not installed. Close this window, open a new terminal, and run the "
        "install command again."
    )


UV_MINIMUM = (0, 8)


def check_uv_version(uv: str) -> None:
    """An old uv gives an unsupported-lockfile error that names a schema, not a fix."""
    try:
        result = run([uv, "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", result.stdout or "")
    if not match:
        return
    if (int(match.group(1)), int(match.group(2))) < UV_MINIMUM:
        raise InstallError(
            f"the uv on this machine is {'.'.join(match.groups())}; PyHamilton needs "
            f"{UV_MINIMUM[0]}.{UV_MINIMUM[1]} or newer.\n"
            "    Update it with:  uv self update"
        )


# ------------------------------------------------------------------ preflight
def preflight(root: Path | None) -> list[str]:
    warnings: list[str] = []
    if not WINDOWS:
        warnings.append(
            f"{platform.system()} cannot run Venus. Simulation works; a robot does not."
        )
    if sys.maxsize <= 2 ** 32:
        raise InstallError(
            "this interpreter is 32-bit. PyHamilton's user-facing code runs 64-bit "
            "(only the Venus sidecar is 32-bit, and the installer provisions that "
            "separately)."
        )
    # A .venv inside a folder OneDrive syncs is tens of thousands of small
    # files, some locked while Python is running. The default project location
    # is not synced; a --root someone chooses can easily be.
    if root and any(part.lower().startswith("onedrive") for part in Path(root).parts):
        warnings.append(
            f"{root} looks like it is inside OneDrive. Syncing a .venv is slow and "
            "can corrupt it -- somewhere outside OneDrive is safer."
        )
    for hostile in ("PYTHONPATH", "PYTHONHOME"):
        if os.environ.get(hostile):
            warnings.append(
                f"{hostile} is set ({os.environ[hostile]}). It is cleared for the "
                "install, but it will still affect methods you run later."
            )

    try:
        free_gb = shutil.disk_usage(root or Path.home()).free / 1e9
        if free_gb < 2:
            raise InstallError(
                f"only {free_gb:.1f} GB free on this disk. The environment plus the "
                "32-bit sidecar needs about 1 GB, plus room to unpack it."
            )
    except OSError:
        pass
    return warnings


def venus_is_running() -> list[str]:
    """Refuse to touch a machine that is mid-run. Nothing else here is reversible."""
    if not WINDOWS:
        return []
    watched = {"hxrun.exe", "hxgui.exe", "runhslexecutor.exe"}
    try:
        output = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                                capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return sorted({line.split(",")[0].strip('"').lower() for line in output.splitlines()
                   if line.split(",")[0].strip('"').lower() in watched})


# -------------------------------------------------------------------- project
PYPROJECT = """[project]
name = "{name}"
version = "0.1.0"
description = "Hamilton methods"
requires-python = ">={python}"
dependencies = [{dependency}]
"""


def create_project(root: Path, dependency: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        say(f"using the existing project at {root}")
        return
    pyproject.write_text(
        PYPROJECT.format(name=root.name.replace(" ", "-").lower(),
                         python=PYTHON_VERSION, dependency=f'"{dependency}"'),
        encoding="utf-8")
    (root / ".python-version").write_text(PYTHON_VERSION + "\n", encoding="utf-8")
    ok(f"project created at {root}")


def fetch_source(root: Path) -> Path:
    """Fetch a checkout for --dev, without requiring Git.

    A zip of the branch is a complete working tree. Git is never a prerequisite:
    on a locked-down instrument PC it is often simply absent, and the LFS
    objects the vendor installers live in are inlined by GitHub's zip anyway.
    """
    target = root / "pyhamilton-src"
    if (target / "pyproject.toml").exists():
        say(f"using the existing source checkout at {target}")
        return target
    say("downloading the PyHamilton source")
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "repo.zip"
        try:
            with urllib.request.urlopen(f"{REPO_URL}/archive/refs/heads/{BRANCH}.zip") as response:
                archive.write_bytes(response.read())
        except OSError as exc:
            raise InstallError(f"could not download the source ({exc})")
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(tmp)
        inner = next((p for p in Path(tmp).iterdir()
                      if p.is_dir() and p.name.startswith("pyhamilton")), None)
        if inner is None:
            raise InstallError("the download looks incomplete -- try again")
        shutil.copytree(inner, target, dirs_exist_ok=True)
    ok(f"source at {target}")
    return target


def sync(uv: str, root: Path) -> None:
    """Install the dependencies, with the three retries that cover what fails.

    Each attempt changes one network variable rather than repeating the same
    request: a plain retry (which resumes from uv's cache), then fewer parallel
    downloads for a congested or throttled link, then the OS certificate store
    -- because institutional networks intercept TLS, which uv's bundled
    certificates reject and the OS trusts, IT having installed the interception
    root there.
    """
    env = dict(os.environ)
    env.setdefault("UV_HTTP_TIMEOUT", "120")
    # Only interpreters uv manages itself. The interpreter a Windows machine
    # already has is very often the Microsoft Store one, which runs in an app
    # container: writes to site-packages get redirected and loading the CLR
    # bridge is blocked, so an install "succeeds" and then behaves as if it
    # never happened. A managed interpreter also makes the environment the same
    # on every machine in the lab, which is the point of pinning at all.
    env["UV_PYTHON_PREFERENCE"] = "only-managed"
    # Assigned, not setdefault: these are exactly the variables a previous
    # setup, a lab image, or an IT logon script leaves behind, and inheriting a
    # hostile value is the failure this is meant to prevent.
    env.pop("UV_SYSTEM_PYTHON", None)
    for hostile in ("PYTHONPATH", "PYTHONHOME", "PIP_TARGET", "PIP_USER", "PIP_PREFIX"):
        env.pop(hostile, None)
    attempts = [
        ([], None, env),
        ([], "retrying with fewer parallel downloads (slow or congested network)",
         {**env, "UV_CONCURRENT_DOWNLOADS": "4"}),
        (["--native-tls"], "retrying with the system certificate store (--native-tls)", env),
    ]
    for flags, message, attempt_env in attempts:
        if message:
            say(message)
        if run([uv, "sync", *flags], cwd=root, env=attempt_env).returncode == 0:
            return
    raise InstallError(
        "could not install the packages after three attempts -- the transcript above "
        "says which one failed and how."
    )


def venv_python(root: Path) -> Path:
    return root / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")


def next_steps(root: Path, configured: bool) -> str:
    location = f'"{root}"' if " " in str(root) else str(root)
    configure_line = "" if configured else (
        "\n  *  Venus configuration was skipped. When you are ready:\n"
        "       uv run pyhamilton configure\n")
    return f"""
=================================================
 Done. Next steps:
=================================================
  1. CLOSE this PowerShell window and open a NEW one.
     Only a NEW window knows where `uv` is.
  2. Go to your methods folder:
       cd {location}
  3. Start a method from the template:
       uv run pyhamilton new-project
  4. Run it:
       uv run python robot_method.py
{configure_line}
If anything ever looks wrong:  uv run pyhamilton doctor
"""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Install PyHamilton.")
    parser.add_argument("--root", type=Path, help="install into this folder")
    parser.add_argument("--version", help="pin a PyHamilton version, e.g. 1.6")
    parser.add_argument("--dev", action="store_true",
                        help="install from a source checkout, editable")
    parser.add_argument("--skip-configure", action="store_true",
                        help="do not touch the Venus installation")
    args = parser.parse_args(argv)

    print("=================================================\n"
          " PyHamilton - environment setup\n"
          "=================================================")
    configured = False
    try:
        uv = which_uv()
        check_uv_version(uv)
        for warning in preflight(args.root):
            say(f"note: {warning}")
        running = venus_is_running()
        if running and not args.skip_configure:
            raise InstallError(
                f"Venus is running ({', '.join(running)}). Close Run Control and any "
                "running method first -- configuring replaces files Venus has open."
            )

        root = (args.root or Path.home() / DEFAULT_PROJECT).resolve()

        step("Creating the method project")
        if args.dev:
            source = fetch_source(root)
            # Editable, which is what the README has always described and what
            # anyone editing .lay files or HSL libraries actually wants. It is a
            # deliberate choice now rather than the only path that works: an
            # editable path dependency pins a directory, so the lock stops
            # reproducing on another machine.
            create_project(root, "pyhamilton")
            if run([uv, "add", "--editable", str(source)], cwd=root).returncode != 0:
                raise InstallError("could not add the source checkout as a dependency")
        else:
            spec = f"pyhamilton=={args.version}" if args.version else "pyhamilton"
            create_project(root, spec)

        step("Installing PyHamilton (this is the slow part)")
        sync(uv, root)
        if not venv_python(root).exists():
            raise InstallError("no interpreter in .venv after installing -- see above")
        ok(f"environment at {root / '.venv'}")

        if not args.skip_configure and WINDOWS:
            step("Configuring the Venus installation")
            # Everything machine-level lives in the package's _bootstrap module,
            # which is now installed. One implementation, not a second copy here.
            code = run([venv_python(root), "-m", "pyhamilton._bootstrap",
                        "configure", "--yes"], cwd=root).returncode
            if code != 0:
                raise InstallError(
                    "configuration did not complete -- see the transcript above. "
                    "The Python environment is fine; re-run `uv run pyhamilton "
                    "configure` once the problem above is fixed."
                )
            configured = True

        step("Verifying the install")
        if run([venv_python(root), "-m", "pyhamilton.doctor"], cwd=root).returncode != 0:
            raise InstallError("verification found a problem -- see above")
    except InstallError as exc:
        print(_c("31", f"\nINSTALL FAILED: {exc}"))
        print("\nCopy everything above this line into a post on labautomation.io, or "
              f"email stefanmgolas@gmail.com, with your OS ({platform.platform()}) and "
              "what was already installed.")
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted. Re-run when ready -- it picks up where it stopped.")
        return 130

    print(_c("32", next_steps(root, configured)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
