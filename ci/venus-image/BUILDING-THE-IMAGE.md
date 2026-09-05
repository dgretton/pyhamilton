# Building the Venus test image

A golden VM with Windows, .NET and VENUS installed, that you revert to a clean
state before every test run. Built by hand, once. Budget half a day, most of it
waiting on installers.

The output is not really "an image" — it is **one VM plus a set of snapshots**.
Reverting to a snapshot is seconds and costs almost no disk, which is what makes
this worth doing at all. Only make full copies if you need two test runs at once.

---

## 0. Pick a host machine

Not a laptop you work on. It needs:

| | |
|---|---|
| Disk | **150 GB free** (Windows ~40, VENUS ~10, snapshots eat the rest) |
| RAM | 16 GB, so the guest can have 8 |
| CPU | virtualization enabled in firmware (VT-x / AMD-V) |

Hypervisor, in order of preference:

- **Hyper-V** if the host is Windows Pro/Enterprise — best performance, already there.
- **VirtualBox** otherwise. Works on Windows Home, free, good headless story.
- **VMware Workstation** — now free for personal use, also fine.

This runbook uses VirtualBox commands because it works everywhere; the Hyper-V
equivalents are one-to-one.

---

## 1. Create the VM

```powershell
$VM = "venus-test"
VBoxManage createvm --name $VM --ostype Windows2022_64 --register
VBoxManage modifyvm $VM --cpus 4 --memory 8192 --vram 128 --nested-hw-virt off
VBoxManage modifyvm $VM --nic1 nat --audio-driver none --usb off
VBoxManage createhd --filename "$env:USERPROFILE\VirtualBox VMs\$VM\$VM.vdi" --size 102400 --variant Standard
VBoxManage storagectl $VM --name SATA --add sata --controller IntelAhci
VBoxManage storageattach $VM --storagectl SATA --port 0 --device 0 --type hdd --medium "$env:USERPROFILE\VirtualBox VMs\$VM\$VM.vdi"
VBoxManage storagectl $VM --name IDE --add ide
VBoxManage storageattach $VM --storagectl IDE --port 0 --device 0 --type dvddrive --medium C:\path\to\windows.iso
```

100 GB is dynamically allocated — it only consumes what is written.

---

## 2. Install Windows

**Which Windows:** match what the lab's robot PCs actually run. The point of this
image is to be representative, and an image on a different OS than the
instruments quietly stops being evidence.

If you have no license to spare, the **Windows Server 2022 evaluation** ISO runs
180 days with no key, and Windows 11 Enterprise eval runs 90. Note the expiry —
put it in the notes file from step 8, because an expired guest fails in confusing
ways months later.

During setup:
- Choose **Desktop Experience**, not Server Core — the VENUS installer is a GUI.
- Decline the Microsoft account; use a local account.
- Let Windows Update finish completely *before* the next step, then disable it.
  Updates arriving mid-test are a source of irreproducibility.

---

## 3. Snapshot: `clean-windows`

```powershell
VBoxManage snapshot $VM take "clean-windows" --description "Windows + updates, nothing else"
```

**Do not skip this.** It is the single most useful snapshot you will make. It is
what you revert to in order to test the PyHamilton *installer* on a genuinely
untouched machine — which is half of what this whole exercise was for, and which
no developer's PC can ever provide again after the first run.

---

## 4. Prerequisites

Inside the guest:

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
iex ((New-Object Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
choco install -y dotnetfx python311 git git-lfs
git lfs install --system
```

`git-lfs` matters: the vendor installers in `pyhamilton/bin` are LFS objects, and
a checkout without it yields pointer files rather than executables.

Verify .NET is 4.8 or newer:

```powershell
(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full').Release  # >= 528040
```

Snapshot: `prereqs`.

---

## 5. Install VENUS

By hand, through the GUI, accepting defaults unless the lab's real machines
differ. Reboot when it asks. This is the twenty minutes you are amortising.

---

## 6. Verify before you trust it

An image that installs but cannot run a method is worse than no image — it fails
later, on someone else's work, with no obvious cause. Check now:

```powershell
Test-Path 'C:\Program Files (x86)\HAMILTON\Bin\HxRun.exe'          # must be True
'Library','Methods','Config' | % { Test-Path "C:\Program Files (x86)\HAMILTON\$_" }
```

Then the check that actually matters: **open VENUS and run a method in simulation
mode, with no robot attached.** If that does not work, nothing downstream will,
and you want to know before you build anything on top of this.

---

## 7. Enable headless access

So you can drive the VM from the host without a console. OpenSSH is far less
painful than WinRM:

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
New-NetFirewallRule -Name sshd -DisplayName 'OpenSSH Server' -Enabled True `
  -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
```

Forward it on the host so you can reach the guest:

```powershell
VBoxManage modifyvm $VM --natpf1 "ssh,tcp,,2222,,22"
```

---

## 8. Write down what is in it

A plain text file beside the VM. The failure mode of a hand-built image is never
that it breaks — it is that in six months nobody can say what is on it.

```
built:        2026-09-05
windows:      Server 2022 Datacenter (eval, EXPIRES 2027-03-04)
venus:        <version, from Help > About>
.NET:         4.8 (release 528040)
python:       3.11.9
installed by: <name>
notes:        pyhamilton NOT installed - that is what we test
```

---

## 9. Snapshot: `venus-clean` — and stop here

```powershell
VBoxManage snapshot $VM take "venus-clean" --description "VENUS installed, PyHamilton NOT"
```

**Deliberately do not install PyHamilton into the image.** Installing PyHamilton
and running `pyhamilton-configure` is one of the things you want to *test*; bake
it in and you have baked in the thing under test. Each run reverts to
`venus-clean` and installs PyHamilton fresh, which is what makes the install
genuinely covered.

---

## 10. Sysprep — only if you are making copies

If you are reverting one VM to a snapshot, **skip this entirely**; there is only
ever one identity and nothing to collide.

If you do need parallel copies, then immediately before capture:

```powershell
& $env:SystemRoot\System32\Sysprep\Sysprep.exe /generalize /oobe /shutdown
```

Then never boot the original again — boot a copy to make changes, and re-capture.
Cloning without generalizing gives every copy the same machine SID and computer
name, which is survivable on an isolated bench and painful anywhere else.

---

## Using it

The whole point, in four lines. This is your "fresh VM" primitive:

```powershell
$VM = "venus-test"
VBoxManage controlvm $VM poweroff 2>$null          # ignore "not running"
VBoxManage snapshot  $VM restore "venus-clean"     # seconds
VBoxManage startvm   $VM --type headless
# wait for ssh on 2222, then:
ssh -p 2222 lab@127.0.0.1 "git clone https://github.com/dgretton/pyhamilton C:\ph; cd C:\ph; pip install -e .; pytest -q"
```

Wrap that in a script and you have a repeatable clean-room test on demand.

To test the *installer* rather than the library, restore `clean-windows`
instead — no Python, no .NET, no git. That is the environment where the install
findings in the audit actually reproduce.

---

## Later: making this CI-triggered

Everything above is manual-trigger. To have a push to GitHub start it, register
the guest as a **self-hosted runner** with labels `[self-hosted, windows, venus]`
— the `venus` job in `.github/workflows/ci.yml` is already written against those
labels and just needs `if: false` removed.

Gate it to `workflow_dispatch` and trusted branches. A self-hosted runner
executes whatever the triggering workflow says, and this one has a robot's
software stack on it.
