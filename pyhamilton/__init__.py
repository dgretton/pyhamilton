"""
Pyhamilton
"""
import os
import shutil
from os.path import dirname, join, abspath

__version__ = '1.6'

PACKAGE_PATH = abspath(dirname(__file__))
PACKAGE_DIR = PACKAGE_PATH  # historical alias

# Where per-user state lives. Nothing is written inside the installed package:
# site-packages is read-only on a managed machine, and an import that mkdirs
# there fails before any diagnostic can run.
CONFIG_DIR = join(os.path.expanduser('~'), '.pyhamilton')
LAY_BACKUP_DIR = join(CONFIG_DIR, 'LAY-BACKUP')


def lay_backup_dir():
    """The layout backup directory, created on first use.

    Created on demand rather than at import, so importing pyhamilton never
    writes to the filesystem.
    """
    os.makedirs(LAY_BACKUP_DIR, exist_ok=True)
    return LAY_BACKUP_DIR


OEM_STAR_PATH = join(PACKAGE_PATH, 'star-oem')
OEM_LAY_PATH = join(OEM_STAR_PATH, 'VENUS_Method', 'STAR_OEM_Test.lay')
OEM_HSL_PATH = join(OEM_STAR_PATH, 'VENUS_Method', 'STAR_OEM_noFan.hsl')

LIBRARY_DIR = join(PACKAGE_PATH, 'library')
TEMPLATE_DIR = join(PACKAGE_PATH, 'templates', 'basic_template')
AI_TEMPLATE_DIR = join(PACKAGE_PATH, 'templates', 'ai_template')
EXE_DIR = join(PACKAGE_PATH, 'bin')
DEFAULTS_SOURCE = join(PACKAGE_PATH, 'defaults', 'defaults.json')

_OEM_REQUIRED_FILES = ('RunHSLExecutor.dll', 'HSLHttp.dll')


def oem_files_present():
    """True when the star-oem assemblies needed to talk to Venus are present."""
    return all(os.path.exists(join(OEM_STAR_PATH, name)) for name in _OEM_REQUIRED_FILES)


def require_oem_files():
    """Raise if the star-oem assemblies are missing.

    Checked here, at the point of use, rather than at import. The check used to
    run at import time, which meant a broken install could not be imported --
    and so `pyhamilton doctor`, whose whole job is to explain what is wrong,
    could never start. Anything that actually needs the assemblies calls this.
    """
    if oem_files_present():
        return
    missing = [name for name in _OEM_REQUIRED_FILES
               if not os.path.exists(join(OEM_STAR_PATH, name))]
    raise FileNotFoundError(
        f'PyHamilton cannot find {", ".join(missing)} in {OEM_STAR_PATH}.\n'
        'These ship with the package; a checkout without git-lfs, or an '
        'interrupted install, is the usual cause.\n'
        'Run `pyhamilton doctor` for the full picture, or reinstall the package.'
    )


def _venus_root_from_registry():
    """Venus's install directory, from the registry, or None."""
    try:
        import winreg
    except ImportError:
        return None
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Hamilton\HAMILTON'),
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Hamilton\HAMILTON'),
    ]
    for hive, path in keys:
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            try:
                with winreg.OpenKey(hive, path, 0, winreg.KEY_READ | view) as key:
                    for name in ('InstallDir', 'Path', 'InstallPath'):
                        try:
                            value = winreg.QueryValueEx(key, name)[0]
                        except OSError:
                            continue
                        if value and os.path.isdir(value):
                            return value
            except OSError:
                continue
    return None


def venus_root():
    """Venus's install directory.

    The registry first, then the two conventional locations. Hardcoding
    `C:\\Program Files (x86)\\HAMILTON` produced an unhandled FileNotFoundError
    on any machine that installed Venus elsewhere.
    """
    from_registry = _venus_root_from_registry()
    if from_registry:
        return from_registry
    for candidate in (r'C:\Program Files (x86)\HAMILTON', r'C:\Program Files\HAMILTON'):
        if os.path.isdir(candidate):
            return candidate
    return r'C:\Program Files (x86)\HAMILTON'


OEM_RUN_EXE_PATH = join(venus_root(), 'Bin', 'HxRun.exe')

from .interface import *
from .oemerr import *
from .liquid_handling_wrappers import *
from .devices import *
from .resources import *
from .liquid_class_db import *
from .consumables import *
from .liquid_classes import *

# ngs/ is the only part of the package that needs OpenCV, Pillow, NumPy and
# Matplotlib. Importing it unconditionally loaded all four on every `import
# pyhamilton`, which is most of the install weight for everyone who never
# touches an NGS protocol. Optional now: `pip install pyhamilton[ngs]`.
_NGS_ERROR = None
try:
    from .ngs import *
except ImportError as _exc:  # pragma: no cover - depends on what is installed
    _NGS_ERROR = _exc


def __getattr__(name):
    # Only reached for names this module does not define, which -- when the ngs
    # extra is absent -- is exactly how a missing ngs symbol shows up. Say what
    # to install instead of the bare AttributeError.
    if _NGS_ERROR is not None and not name.startswith('_'):
        raise AttributeError(
            f'{name!r} is not available. The NGS tools are an optional extra and '
            f'could not be imported ({_NGS_ERROR}).\n'
            'Install them with:  pip install "pyhamilton[ngs]"'
        )
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def full_paths_list(directory_abs_path):
    return [os.path.join(directory_abs_path, name)
            for name in os.listdir(directory_abs_path)]


def recursive_copy(source_dir, target_dir):
    """Copy a tree, overwriting files whose contents differ.

    The old version skipped any file that already existed, so upgrading
    PyHamilton never updated a library file already in the Hamilton install --
    an upgrade's failure mode was a stale library rather than an error.
    """
    from ._bootstrap import copy_tree
    return copy_tree(source_dir, target_dir)


def autoconfig():
    """Entry point kept for compatibility: see `pyhamilton configure`."""
    from ._bootstrap import main
    return main(['configure'])


def _create_from_template(template_dir, what):
    from ._bootstrap import copy_tree
    if not os.path.isdir(template_dir):
        raise FileNotFoundError(
            f'the {what} template is missing from this installation '
            f'({template_dir}).\nRun `pyhamilton doctor` -- this usually means the '
            'package was built without its data files.'
        )
    target = os.path.abspath(os.getcwd())
    print(f'Creating {what} in {target}')
    result = copy_tree(template_dir, target)
    print(f'  {result.copied} file(s) written, {result.unchanged} already up to date')
    if not result.copied and not result.unchanged:
        raise FileNotFoundError(f'the {what} template at {template_dir} is empty')


def create_project():
    # Returns None: setuptools console scripts do sys.exit(func()), so anything
    # else would be printed as a stray repr, or worse, treated as a failure.
    _create_from_template(TEMPLATE_DIR, 'project template')


def create_ai_project():
    _create_from_template(AI_TEMPLATE_DIR, 'AI assistant project template')
