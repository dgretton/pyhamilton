# PyHamilton

**Python for Hamilton liquid handling robots**

Hamilton software only works on Windows, so the same goes for PyHamilton.

Developed for Hamilton STAR and STARlet on Windows XP, Windows 7, and Windows 10. VANTAGE series supported with plugin. Other robot models and operating systems not supported yet.

Please post on [labautomation.io](https://labautomation.io/) if you have any questions, comments, issues, or feedback! You can also email stefanmgolas@gmail.com for troubleshooting help.


**Disclaimer:** PyHamilton is not officially endorsed or supported by the Hamilton Company. Please direct any questions to the above email address, and not to Hamilton Company. 

## Example usage
```python
if __name__ == "__main__":

    from pyhamilton import HamiltonInterface, INITIALIZE
    with HamiltonInterface() as ham_int:
    
        ham_int.wait_on_response(ham_int.send_command(INITIALIZE))
```

## Guides

Here is a protocol repository with guides about how to do things like magnetic bead washes and thermal cycling. These are all NGS protocols, but you can use the same steps in many other experiments.

[NGS Protocol Library](https://github.com/stefangolas/ngs-protocols)

## Documentation

[Available online](https://dgretton.github.io/pyhamilton-docs/).

## Tutorial Video
https://www.youtube.com/watch?v=G92neaVfvyw

## Installation

**Windows, with Venus installed.** One command in PowerShell:

```powershell
powershell -c "irm https://raw.githubusercontent.com/dgretton/pyhamilton/main/install.ps1 | iex"
```

That installs [uv](https://docs.astral.sh/uv/) if it is missing, creates a
methods project in `%USERPROFILE%\pyhamilton-methods`, installs PyHamilton and
a 64-bit Python to run it, provisions the 32-bit interpreter the Venus sidecar
needs, runs the bundled Hamilton installers, copies the HSL libraries into your
Venus installation, and finishes by verifying all of it. It asks for
confirmation once, before it changes anything, and for administrator rights
once, for the step that writes into the Venus install.

Useful switches (`-File install.ps1 ...`, or after `iex` in a checkout):

| Switch | Effect |
|---|---|
| `-Root D:\methods` | put the methods project somewhere else |
| `-Version 1.6` | pin a PyHamilton version |
| `-Dev` | install PyHamilton **editable**, from a source checkout, so your changes to the repo take effect immediately |
| `-SkipConfigure` | install Python and PyHamilton, but do not touch the Venus installation |

**Simulation only, on any operating system.** Venus is Windows-only, but the
Python-level dry run is not, so methods can be written and checked on a laptop:

```bash
uv init my-methods && cd my-methods
uv add pyhamilton
uv run pyhamilton doctor
```

Then use `HamiltonInterface(simulating=True)`.

**Anything else** — an existing environment, an offline machine, conda, plain
pip — installs the normal way, and `pyhamilton configure` does the machine-level
half on its own:

```
pip install "pyhamilton[venus]"     # add [ngs] for the NGS tools
pyhamilton configure                # vendor installers, HSL libraries, sidecar
pyhamilton doctor                   # check all of it
```

### Prerequisites

Only two things are not handled for you:

1. **Venus itself.** Install and test the standard Hamilton software suite
   first; contact Hamilton for a copy.
2. **The Microsoft Access Database Engine**, which must match your Python's
   bitness (64-bit) *and* your installed Office. `pyhamilton doctor` reports
   which one you have and what is wrong with it.

.NET 4.8 ships with Windows 10 and 11, and `uv` supplies Python, so neither is a
manual step any more. Git is not required.

### If something goes wrong

```
pyhamilton doctor
```

It checks the interpreter, the package's data files, .NET, the Access driver at
your bitness, your Venus installation, the 32-bit sidecar, TCP 3221, and
finishes with a `simulating=True` dry run through the real code path. It prints
the failures in the order they should be fixed. Paste the whole transcript into
a post on [labautomation.io](https://labautomation.io/), or email
stefanmgolas@gmail.com.

Re-running the installer, or `pyhamilton configure`, is always safe: it compares
file contents, backs up anything it replaces to `~/.pyhamilton/backup`, and
merges rather than overwrites your `~/.pyhamilton/defaults.json`.

## Installation Troubleshooting

**Run `pyhamilton doctor` first.** Most of what used to be in this list is now a
named check with the fix attached.

1. If you encounter an error relating to HxFan (i.e., your robot does not have a fan), open pyhamilton/star-oem/VENUS_Method/STAR_OEM_Test.med, navigate to the "HxFan" grouping, and delete all commands under this grouping.

2. To test PyHamilton on a computer with no robot attached, use
   `HamiltonInterface(simulating=True)`. This works on macOS and Linux too, and
   is the same code path a real run takes.

3. If your initialization hangs (such as on initial_error_example.py), make sure
   no other program is communicating with the robot -- Venus Run Control in
   particular. (The blocked-DLL problem that used to live here is handled:
   `pyhamilton configure` clears the `Zone.Identifier` stream from the OEM
   assemblies, and `pyhamilton doctor` reports it if anything is still wrong.)

4. If `pyhamilton` is not recognised as a command, the interpreter's `Scripts\`
   directory is not on your `PATH`. `uv run pyhamilton ...` works regardless,
   and `pyhamilton doctor` reports it.

## Applications

- [A high-throughput platform for feedback-controlled directed evolution](https://www.biorxiv.org/content/10.1101/2020.04.01.021022v1), _preprint_

- [Flexible open-source automation for robotic bioengineering](https://www.biorxiv.org/content/10.1101/2020.04.14.041368v1), _preprint_


_Developed for the Sculpting Evolution Group at the MIT Media Lab_
