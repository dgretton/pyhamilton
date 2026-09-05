"""Path constants.

Historically this file duplicated the path logic in ``__init__.py`` verbatim,
including the import-time ``FileNotFoundError`` and the ``mkdir`` into
site-packages. Both now live in one place; this module re-exports them so
existing ``from pyhamilton.paths import ...`` imports keep working.
"""

from pyhamilton import (  # noqa: F401
    PACKAGE_PATH,
    CONFIG_DIR,
    LAY_BACKUP_DIR,
    lay_backup_dir,
    OEM_STAR_PATH,
    OEM_LAY_PATH,
    OEM_HSL_PATH,
    OEM_RUN_EXE_PATH,
    oem_files_present,
    require_oem_files,
    venus_root,
)
