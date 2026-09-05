"""Check a PyHamilton installation and say precisely what is wrong.

    pyhamilton doctor
    python -m pyhamilton.doctor

Run by the installer as its last step, and by anyone afterwards. The checks are
ordered so the *first* failure is the root cause rather than a symptom -- a
missing Access driver reported before the liquid-class read that it breaks.

Checks that need a working package live here; checks that must survive a broken
one live in ``_bootstrap.py``, which imports nothing from pyhamilton. This file
is the half that can afford to import.

Exit code is 0 when nothing failed. Warnings do not fail the run: an install
with no Venus on the machine is a perfectly good simulation install.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import platform
import socket
import struct
import subprocess
import sys
from pathlib import Path

from ._bootstrap import (
    CONFIG_DIR,
    DEFAULTS_PATH,
    PYTHON_32BIT_KEY,
    WINDOWS,
    _c,
    package_dir,
    venus_root,
)

for _stream in (sys.stdout, sys.stderr):
    with contextlib.suppress(AttributeError, ValueError):
        _stream.reconfigure(encoding="utf-8", errors="replace")

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"

# Every data directory the code actually reads at runtime. Each was missing
# from package_data at some point, and each failure was silent on a non-editable
# install -- `pyhamilton-new-project` creating nothing at all being the worst.
REQUIRED_DATA = [
    ("star-oem/RunHSLExecutor.dll", "the CLR bridge"),
    ("star-oem/HSLHttp.dll", "the HTTP transport"),
    ("templates/basic_template", "pyhamilton new-project"),
    ("templates/ai_template", "pyhamilton new-project --ai"),
    ("defaults/defaults.json", "the shipped user defaults"),
    ("library", "the HSL library tree copied into Venus"),
]

LIBRARY_SUBDIRS = [
    "ASWStandard", "Alpha Numeric Conversion", "DaisyChainedTiltModule",
    "ErrorSimulator", "HSLAppsLib", "HSLInhecoTEC", "HSLLabwrAccess",
    "Labware Properties", "SMT", "SMTs", "STAR Tools", "SchedulingDev",
]


class Report:
    def __init__(self):
        self.results = []

    def record(self, status, name, detail=""):
        self.results.append((status, name, detail))
        colour = {PASS: "32", WARN: "33", FAIL: "31"}[status]
        line = f"  {_c(colour, status)}  {name}"
        print(f"{line}\n        {detail}" if detail else line)

    def ok(self, name, detail=""):
        self.record(PASS, name, detail)

    def warn(self, name, detail=""):
        self.record(WARN, name, detail)

    def fail(self, name, detail=""):
        self.record(FAIL, name, detail)

    @property
    def failures(self):
        return [r for r in self.results if r[0] == FAIL]


def section(title):
    print("\n" + _c("36", f"== {title}"))


# ----------------------------------------------------------------- the checks
# A Microsoft Store Python is the single worst starting point on Windows, and
# it is the default one: typing `python` on a clean machine opens the Store.
# What it breaks is not obvious from any error it produces --
#   * it runs inside an app container, so writes to site-packages are silently
#     redirected to %LOCALAPPDATA%\Packages\...\LocalCache. Files appear to
#     install and then are not where anything looks for them.
#   * loading a native DLL from the package directory is restricted, which is
#     exactly what pythonnet does to reach Venus.
# The installer avoids it entirely by never invoking `python` -- uv supplies
# the interpreter. This check exists for everyone who installed some other way.
STORE_MARKERS = ("windowsapps", os.path.join("packages", "pythonsoftwarefoundation"))


def is_store_python(executable) -> bool:
    lowered = str(executable).lower()
    return any(marker in lowered for marker in STORE_MARKERS)


def check_interpreter(report):
    section("Interpreter")
    if WINDOWS and (is_store_python(sys.executable) or is_store_python(sys.prefix)):
        report.fail(
            "not a Microsoft Store Python",
            f"{sys.executable} came from the Microsoft Store. It runs in an app "
            "container: writes to site-packages are silently redirected, and "
            "loading the Venus CLR bridge is blocked. Nothing here will work "
            "reliably." + os.linesep + "        Fix: uninstall it (Settings > Apps), turn off the "
            '"python" App Execution Alias, and re-run the installer -- uv will '
            "supply a real interpreter.")
    version = ".".join(str(p) for p in sys.version_info[:3])
    bits = 64 if sys.maxsize > 2 ** 32 else 32
    if sys.version_info < (3, 10):
        report.fail("python >= 3.10", f"this is {version}; defaults.py needs dataclass slots=")
    else:
        report.ok("python version", f"{version} ({bits}-bit) at {sys.executable}")
    if WINDOWS and bits != 64:
        report.warn("64-bit interpreter",
                    "user code is meant to run 64-bit; only the Venus sidecar is 32-bit")
    scripts = Path(sys.executable).parent / ("Scripts" if WINDOWS else "bin")
    on_path = str(scripts).lower() in os.environ.get("PATH", "").lower()
    if on_path:
        report.ok("console scripts on PATH", str(scripts))
    else:
        report.warn("console scripts on PATH",
                    f"{scripts} is not on PATH; `pyhamilton` may not resolve as a command")


def check_environment(report):
    """The variables that quietly redirect an otherwise-correct install."""
    section("Environment")
    for name, why in (
        ("PYTHONPATH", "puts other directories ahead of this environment on sys.path"),
        ("PYTHONHOME", "overrides the standard library location and usually breaks the interpreter"),
        ("PIP_TARGET", "sends installs to a directory this interpreter does not import from"),
        ("PIP_USER", "sends installs to the user site, not this environment"),
    ):
        value = os.environ.get(name)
        if value:
            report.warn(f"{name} is set", f"{value} -- {why}")

    # Which pyhamilton actually wins. A second copy earlier on sys.path -- a
    # stray checkout in the working directory, a leftover user-site install --
    # means edits and fixes land in a copy nothing imports.
    import pyhamilton
    imported = Path(pyhamilton.__file__).resolve().parent
    try:
        from importlib.metadata import distribution
        installed = Path(distribution("pyhamilton").locate_file("pyhamilton")).resolve()
    except Exception:  # noqa: BLE001 - not installed as a distribution at all
        installed = None
    if installed and installed != imported:
        report.fail("one pyhamilton on sys.path",
                    f"`import pyhamilton` gets {imported}, but the installed "
                    f"distribution is {installed}. A second copy -- usually a "
                    "checkout in the working directory -- is shadowing it, so fixes "
                    "and reinstalls land somewhere nothing imports.")
    else:
        report.ok("one pyhamilton on sys.path", str(imported))

    # And which console script wins, which is a different question: PATH order
    # decides that, and a Scripts\ directory from another Python can come first.
    import shutil as _shutil
    resolved = _shutil.which("pyhamilton")
    if resolved:
        expected_scripts = Path(sys.executable).parent / ("Scripts" if WINDOWS else "bin")
        if Path(resolved).parent.resolve() != expected_scripts.resolve():
            report.warn("`pyhamilton` resolves to this environment",
                        f"the command on PATH is {resolved}, from a different "
                        "environment. `uv run pyhamilton ...` always uses the right one.")
        else:
            report.ok("`pyhamilton` command", resolved)


def check_package_data(report):
    section("Package contents")
    try:
        pkg = package_dir()
    except Exception as exc:  # noqa: BLE001
        report.fail("package located", str(exc))
        return None
    report.ok("package located", str(pkg))

    for relative, why in REQUIRED_DATA:
        path = pkg / relative
        if path.exists():
            report.ok(f"{relative}")
        else:
            report.fail(f"{relative} missing", f"needed for: {why}")

    library = pkg / "library"
    if library.is_dir():
        missing = [d for d in LIBRARY_SUBDIRS if not (library / d).is_dir()]
        if missing:
            report.fail("library tree is complete",
                        f"{len(missing)} of {len(LIBRARY_SUBDIRS)} subdirectories missing: "
                        + ", ".join(missing))
        else:
            report.ok("library tree is complete", f"{len(LIBRARY_SUBDIRS)} subdirectories")

    exe_dir = pkg / "bin"
    if exe_dir.is_dir():
        installers = sorted(p for p in exe_dir.iterdir()
                            if p.suffix.lower() in (".exe", ".msi"))
        pointers = []
        for installer in installers:
            with open(installer, "rb") as f:
                if installer.suffix.lower() == ".exe" and f.read(2) != b"MZ":
                    pointers.append(installer.name)
        if pointers:
            report.fail("bundled installers are real binaries",
                        "git-lfs pointers, not executables: " + ", ".join(pointers))
        else:
            report.ok("bundled installers", f"{len(installers)} present")
    else:
        report.warn("bundled installers", "no bin/ directory (assets not installed)")
    return pkg


def check_import(report):
    section("Import")
    # In a subprocess: an import that dies takes the process with it, and this
    # check has to survive to report the rest.
    code = "import pyhamilton, sys; sys.stdout.write(getattr(pyhamilton,'__version__','?'))"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                            text=True, timeout=300)
    if result.returncode == 0:
        report.ok("import pyhamilton", (result.stdout or "").strip() or "imported")
    else:
        tail = (result.stderr or "").strip().splitlines()[-1:] or ["(no output)"]
        report.fail("import pyhamilton", tail[0])


def check_dotnet(report):
    if not WINDOWS:
        return
    section(".NET")
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full") as key:
            release = winreg.QueryValueEx(key, "Release")[0]
    except OSError:
        report.fail(".NET Framework 4.x", "not found; the CLR bridge cannot load")
        return
    # 528040 is 4.8; anything at or above it is fine.
    if release >= 528040:
        report.ok(".NET Framework", f"release {release} (4.8 or newer)")
    elif release >= 378389:
        report.warn(".NET Framework", f"release {release}; 4.8 recommended")
    else:
        report.fail(".NET Framework", f"release {release} is older than 4.0")


def check_access_driver(report):
    if not WINDOWS:
        return
    section("Microsoft Access driver")
    bits = 64 if sys.maxsize > 2 ** 32 else 32
    try:
        import pyodbc
    except ImportError:
        report.warn("pyodbc", "not installed; liquid-class lookups will fail. "
                              'Install with: pip install "pyhamilton[venus]"')
        return
    drivers = [d for d in pyodbc.drivers() if "Access" in d]
    modern = [d for d in drivers if "accdb" in d]
    if modern:
        report.ok(f"Access driver at {bits}-bit", "; ".join(modern))
    elif drivers:
        report.fail(f"Access driver at {bits}-bit",
                    f"only the legacy Jet driver is present ({'; '.join(drivers)}). "
                    "Install the Access Database Engine matching this interpreter's bitness.")
    else:
        report.fail(f"Access driver at {bits}-bit",
                    "none installed. This is the cause of 'IM002: no default driver'. "
                    "Install the Microsoft Access Database Engine redistributable "
                    f"({bits}-bit, to match this interpreter).")


def check_venus(report):
    if not WINDOWS:
        report.warn("Venus", f"{platform.system()} cannot run Venus; simulation only")
        return None
    section("Venus")
    root = venus_root()
    if not root:
        report.warn("Venus installed", "not found; simulation still works")
        return None
    report.ok("Venus root", root)
    run_exe = Path(root) / "Bin" / "HxRun.exe"
    if run_exe.exists():
        report.ok("run control executable", str(run_exe))
    else:
        report.fail("run control executable", f"missing at {run_exe}")
    library = Path(root) / "Library"
    if library.is_dir():
        report.ok("Venus library directory", str(library))
    else:
        report.fail("Venus library directory", f"missing at {library}")
    return root


def check_config(report):
    section("User configuration")
    if not DEFAULTS_PATH.exists():
        report.warn("defaults.json", f"none at {DEFAULTS_PATH}; run `pyhamilton configure`")
        return {}
    try:
        config = json.loads(DEFAULTS_PATH.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError) as exc:
        # defaults.py silently falls back to built-ins here, so a corrupt file
        # produces wrong behaviour rather than an error. Name it.
        report.fail("defaults.json is readable JSON",
                    f"{exc}; PyHamilton will silently ignore it and use built-in defaults")
        return {}
    report.ok("defaults.json", f"{len(config)} key(s) at {DEFAULTS_PATH}")
    return config


def check_sidecar(report, config):
    if not WINDOWS:
        return
    section("32-bit Venus sidecar")
    path = os.environ.get("PYTHON_32BIT_PATH") or config.get(PYTHON_32BIT_KEY)
    if not path:
        report.warn("32-bit interpreter", "not configured; server mode is unavailable. "
                                          "`pyhamilton configure` installs one.")
        return
    if not Path(path).exists():
        report.fail("32-bit interpreter", f"configured as {path}, which does not exist")
        return
    probe = ("import struct, sys; "
             "sys.exit(0 if struct.calcsize('P') == 4 else 3)")
    try:
        code = subprocess.run([path, "-c", probe], timeout=120).returncode
    except (OSError, subprocess.SubprocessError) as exc:
        report.fail("32-bit interpreter runs", f"{path}: {exc}")
        return
    if code == 3:
        report.fail("32-bit interpreter", f"{path} is 64-bit; Venus needs a 32-bit host")
        return
    if code != 0:
        report.fail("32-bit interpreter runs", f"{path} exited {code}")
        return
    has_clr = subprocess.run([path, "-c", "import clr"], capture_output=True, timeout=180)
    if has_clr.returncode == 0:
        report.ok("32-bit sidecar", f"{path} with pythonnet")
    else:
        report.fail("pythonnet in the sidecar",
                    f"{path} cannot `import clr`; run `pyhamilton configure`")


def check_port(report):
    section("Network")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        try:
            sock.bind(("localhost", 3221))
            report.ok("TCP 3221 free", "the interface's HTTP channel can bind")
        except OSError as exc:
            report.fail("TCP 3221 free",
                        f"{exc}. Another PyHamilton process is probably still running.")


def check_dry_run(report):
    """The end-to-end check: does the real code path work, with no Venus?

    A Python-level dry run needs no Venus, no robot and no instrument PC, so it
    is the only verification that runs identically in CI, on a laptop, and on
    the machine attached to the robot.
    """
    section("Dry run")
    code = (
        "from pyhamilton import HamiltonInterface\n"
        "with HamiltonInterface(simulating=True) as ham:\n"
        "    pass\n"
        "print('dry run completed')\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                            text=True, timeout=300)
    if result.returncode == 0:
        report.ok("simulating=True interface opens and closes")
    else:
        tail = (result.stderr or "").strip().splitlines()[-1:] or ["(no output)"]
        report.fail("simulating=True interface", tail[0])


def main(argv=None) -> int:
    print("=" * 60)
    print(" PyHamilton doctor")
    print(f" {platform.platform()}")
    print("=" * 60)
    report = Report()
    check_interpreter(report)
    check_environment(report)
    check_package_data(report)
    check_import(report)
    check_dotnet(report)
    check_access_driver(report)
    check_venus(report)
    config = check_config(report)
    check_sidecar(report, config)
    check_port(report)
    check_dry_run(report)

    print("\n" + "=" * 60)
    counts = {status: sum(1 for r in report.results if r[0] == status)
              for status in (PASS, WARN, FAIL)}
    print(f" {counts[PASS]} passed, {counts[WARN]} warnings, {counts[FAIL]} failed")
    if report.failures:
        print(_c("31", "\n Fix these, in this order -- the first is usually the cause:"))
        for _, name, detail in report.failures:
            print(f"   - {name}: {detail}" if detail else f"   - {name}")
        print("\n Still stuck? Post this whole transcript on labautomation.io or "
              "email stefanmgolas@gmail.com.")
        return 1
    print(_c("32", " Everything checks out."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
