"""The 32-bit Venus sidecar.

Venus is 32-bit, so the CLR assembly that talks to it can only be hosted by a
32-bit Python. This file is what that interpreter runs; user code stays 64-bit
and reaches it over the local HTTP channel.

    python run_venus_client.py <star-oem dir> <hsl method>

It deliberately imports **nothing from pyhamilton**. It used to start with
``from pyhamilton.interface import run_hamilton_process``, which meant the
32-bit environment needed the entire dependency tree -- including packages that
publish no 32-bit Windows wheels at all. Taking the two paths it needs from
argv instead reduces that environment to ``pythonnet`` and the standard
library, which is what makes provisioning it a 30-second download.
"""

import os
import sys
import time


def run(oem_star_path, oem_hsl_path):
    import clr

    clr.AddReference(os.path.join(oem_star_path, 'RunHSLExecutor'))
    clr.AddReference(os.path.join(oem_star_path, 'HSLHttp'))
    try:
        from RunHSLExecutor import Class1
    except ModuleNotFoundError:
        raise RuntimeError(
            'RunHSLExecutor DLLs successfully located, but an internal error '
            'prevented import as a CLR module. You might be missing the standard '
            'Hamilton software suite HSL executables, their DLLs may not be '
            'registered with Windows, or they may not be located in the expected '
            'system directory.'
        )
    executor = Class1()
    executor.StartMethod(oem_hsl_path)
    # Hold the CLR host open until the parent stops us. A busy `while True: pass`
    # spun a core for the lifetime of every run.
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    oem_star_path, oem_hsl_path = argv
    for path in (oem_star_path, oem_hsl_path):
        if not os.path.exists(path):
            print(f'sidecar: no such path: {path}', file=sys.stderr)
            return 1
    if sys.maxsize > 2 ** 32:
        # Not fatal -- Venus in simulation may still load -- but it is the cause
        # of the CLR errors that otherwise name only an assembly.
        print('sidecar: warning: this interpreter is 64-bit; Venus is 32-bit.',
              file=sys.stderr)
    run(oem_star_path, oem_hsl_path)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
