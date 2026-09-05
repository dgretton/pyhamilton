# PyHamilton - install bootstrap (Windows PowerShell)
#
#   powershell -c "irm https://raw.githubusercontent.com/dgretton/pyhamilton/main/install.ps1 | iex"
#
# This script does one thing: get a Python. Everything else -- creating the
# method project, installing PyHamilton, provisioning the 32-bit Venus sidecar,
# configuring the Hamilton install, verifying it -- lives in Python, in
# pyhamilton/_bootstrap.py, which this hands off to. Keeping the shell layer
# this thin is deliberate: the logic exists once, in a language with a test
# suite, instead of twice in two shell dialects that drift apart.
#
# Arguments pass straight through:
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Root C:\methods -Dev

param(
  [string]$Root,
  [string]$Version,
  [switch]$Dev,
  [switch]$SkipConfigure
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Piped through `irm ... | iex`, this runs in the caller's session, so `exit`
# would close their window -- including the error still on screen. $PSScriptRoot
# is empty only in that case, which is how the two are told apart.
$InvokedViaIex = -not $PSScriptRoot
$Raw = 'https://raw.githubusercontent.com/dgretton/pyhamilton/main'

function Die ($m) {
  Write-Host "`nINSTALL FAILED: $m" -ForegroundColor Red
  if ($InvokedViaIex) { throw 'Install aborted -- see the message above.' }
  exit 1
}

if ($env:OS -ne 'Windows_NT') {
  Die 'PyHamilton drives Hamilton Venus, which is Windows-only. On macOS or Linux you can still run simulations: `uv add pyhamilton` and use HamiltonInterface(simulating=True).'
}

Write-Host '==> Checking for uv' -ForegroundColor Cyan

# uv is the package manager: one static executable, installed per-user with no
# administrator rights, which also supplies the Python that PyHamilton runs on.
function Find-Uv {
  $cmd = Get-Command uv -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  foreach ($p in @("$env:USERPROFILE\.local\bin\uv.exe", "$env:LOCALAPPDATA\uv\bin\uv.exe")) {
    if (Test-Path $p) { return $p }
  }
  return $null
}

# Find-Uv accepts a uv that is not on PATH, so the install can succeed while
# every future `uv run` in a new terminal reports "uv is not recognized" -- and
# re-running this, which is the advertised fix, would never help. Guarantee the
# PATH entry ourselves.
#
# The registry rather than [Environment]::SetEnvironmentVariable: reading the
# user PATH through that API expands any %USERPROFILE%-style entries, and
# writing the expanded result back would bake them in permanently.
function Add-ToUserPath ($dir) {
  $onPath = ($env:Path -split ';' | Where-Object { $_ } |
             ForEach-Object { $_.TrimEnd('\') }) -icontains $dir.TrimEnd('\')
  if ($onPath) { return }
  try {
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment', $true)
    $raw = $key.GetValue('Path', '', 'DoNotExpandEnvironmentNames')
    $already = ($raw -split ';' | Where-Object { $_ } |
                ForEach-Object { $_.TrimEnd('\') }) -icontains $dir.TrimEnd('\')
    if (-not $already) {
      $new = if ($raw) { "$dir;$raw" } else { $dir }
      $key.SetValue('Path', $new, [Microsoft.Win32.RegistryValueKind]::ExpandString)
      Write-Host "  added $dir to your PATH (new terminals will find uv)"
    }
    $key.Close()
  } catch {
    Write-Host "  could not update your PATH ($($_.Exception.Message))."
    Write-Host "  If a new terminal says 'uv is not recognized', add $dir to PATH by hand."
    return
  }
  $env:Path = "$dir;$env:Path"
}

# uv's installer refuses to run under a Restricted or AllSigned policy. Windows
# ships Restricted on some editions and IT images set it on others -- and an
# instrument PC is domain-joined more often than a laptop, so this is a
# first-day blocker rather than an edge case.
#
# -Scope Process lasts exactly as long as this window and leaves the saved
# policy untouched. A machine whose policy comes from Group Policy cannot be
# relaxed even that far, and Set-ExecutionPolicy does not fail there -- it
# simply does not take -- which is why the effective policy is re-read rather
# than the call trusted.
function Approve-ExecutionPolicyForUv {
  $allowed = @('Unrestricted', 'RemoteSigned', 'Bypass')
  if ($allowed -contains (Get-ExecutionPolicy).ToString()) { return $true }
  try {
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force -ErrorAction Stop
  } catch {
    return $false
  }
  if ($allowed -contains (Get-ExecutionPolicy).ToString()) {
    Write-Host '  relaxed the execution policy for THIS WINDOW ONLY (your saved setting is unchanged)'
    return $true
  }
  return $false
}

$uv = Find-Uv
if (-not $uv) {
  Write-Host '  not found - installing it (per-user, no administrator rights needed)'
  if (-not (Approve-ExecutionPolicyForUv)) {
    Die @"
PowerShell's execution policy is '$(Get-ExecutionPolicy)', and uv's installer will
not run under it. This window could not be relaxed on its own, which usually means
the policy comes from Group Policy on a managed machine.

Run this once, then run the install command again:

    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

If that is refused too, IT has to allow it -- or take the manual route: download
uv from https://github.com/astral-sh/uv/releases, put uv.exe on your PATH, and
run the install command again.
"@
  }
  try {
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
  } catch {
    Die @"
could not install uv: $($_.Exception.Message)
Behind a proxy or an institutional firewall? Download it from
https://github.com/astral-sh/uv/releases, put it on your PATH, and run this again.
"@
  }
  $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
  $uv = Find-Uv
  if (-not $uv) { Die 'uv installed but is not on PATH. Close this window, open a new PowerShell, and run the command again.' }
}
Write-Host "  OK  uv at $uv" -ForegroundColor Green
Add-ToUserPath (Split-Path -Parent $uv)
$env:UV_BIN = $uv

# The installer proper: the copy beside this script when there is one (a real
# checkout), otherwise fetch the single file it needs. It is standard-library
# only and imports nothing from pyhamilton, which is what lets it run here,
# before the package exists.
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot 'pyhamilton\_install.py'))) {
  $installer = Join-Path $PSScriptRoot 'pyhamilton\_install.py'
} else {
  $installer = Join-Path ([System.IO.Path]::GetTempPath()) "pyhamilton-install-$(Get-Random).py"
  try {
    Invoke-WebRequest -Uri "$Raw/pyhamilton/_install.py" -OutFile $installer -UseBasicParsing
  } catch {
    Die "could not download the installer: $($_.Exception.Message)"
  }
}

$passthrough = @()
if ($Root)           { $passthrough += @('--root', $Root) }
if ($Version)        { $passthrough += @('--version', $Version) }
if ($Dev)            { $passthrough += '--dev' }
if ($SkipConfigure)  { $passthrough += '--skip-configure' }

# --no-project: run against a bare interpreter, not a project environment,
# which does not exist yet. uv downloads that interpreter if the machine has
# none.
& $uv run --no-project --python 3.11 $installer @passthrough

if ($InvokedViaIex) {
  if ($LASTEXITCODE -ne 0) {
    Write-Host "`nINSTALL FAILED (exit code $LASTEXITCODE). See the message above, or re-run to start over." -ForegroundColor Red
  }
} else {
  exit $LASTEXITCODE
}
