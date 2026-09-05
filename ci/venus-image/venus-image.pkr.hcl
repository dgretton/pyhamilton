# Builds a Windows image with VENUS, .NET and the PyHamilton prerequisites
# already installed, for use as the source image of an Azure VM Scale Set that
# backs ephemeral GitHub Actions runners.
#
# Why an image at all: VENUS takes ~20 minutes to install and wants a reboot.
# Baking it once turns that into a VM boot, so a CI job that needs real VENUS
# costs seconds instead of a third of an hour. Everything that does NOT need
# VENUS should keep running on stock `windows-latest` for free -- see
# .github/workflows/ci.yml. This image is only for the `venus` job.
#
#   packer init  .
#   packer build -var-file=venus.pkrvars.hcl .
#
# Requires: an Azure subscription, `az login`, and the VENUS installer staged
# somewhere the build can reach it (see the `venus_installer_uri` variable).

packer {
  required_plugins {
    azure = {
      source  = "github.com/hashicorp/azure"
      version = "~> 2.0"
    }
  }
}

# ----------------------------------------------------------------- variables

variable "subscription_id" {
  type        = string
  description = "Azure subscription to build in."
}

variable "resource_group" {
  type        = string
  description = "Existing resource group that holds the Shared Image Gallery."
}

variable "gallery_name" {
  type        = string
  description = "Shared Image Gallery name. The VM Scale Set sources its image from here."
}

variable "image_version" {
  type        = string
  description = "Semver for this image build, e.g. 1.0.0. Bump every rebuild -- the whole point is that a runner's environment is identifiable after the fact."
}

variable "venus_installer_uri" {
  type        = string
  description = <<-EOT
    Where the build can fetch the VENUS installer. A SAS-signed blob URL is the
    normal answer. NOT committed to the repo: it is several gigabytes, and the
    repo already carries too many vendor binaries (see audit INST-6).
  EOT
  sensitive   = true
}

variable "venus_silent_args" {
  type        = string
  description = <<-EOT
    How to run the VENUS installer without a human.

    DETERMINE THIS FIRST -- stage 1 of the runbook. Fingerprint the installer:
      grep -aqi "InstallShield" VenusSetup.exe && echo InstallShield

    InstallShield: record a response file once, interactively --
      VenusSetup.exe /r /f1"C:\venus.iss"
    -- commit venus.iss beside this template, and set this to:
      /s /f1"C:\venus.iss" /f2"C:\venus-install.log"

    MSI-based or a Burn bundle:
      /quiet /norestart      (or  /s /v"/qn"  for an InstallShield-wrapped MSI)

    Leave this wrong and the build hangs on an invisible dialog until it times
    out, which looks exactly like a network problem. It is not.
  EOT
  default     = ""
}

variable "location" {
  type    = string
  default = "eastus"
}

variable "vm_size" {
  type        = string
  description = "Build-time VM size. Only affects how fast the image bakes."
  default     = "Standard_D4s_v5"
}

locals {
  image_name = "pyhamilton-venus"
}

# --------------------------------------------------------------------- build

source "azure-arm" "venus" {
  subscription_id = var.subscription_id
  location        = var.location
  vm_size         = var.vm_size

  # Server rather than a client SKU: no Desktop Experience quirks, and it is
  # the SKU Azure supports for scale sets without extra licensing steps.
  os_type         = "Windows"
  image_publisher = "MicrosoftWindowsServer"
  image_offer     = "WindowsServer"
  image_sku       = "2022-datacenter-azure-edition"

  communicator   = "winrm"
  winrm_use_ssl  = true
  winrm_insecure = true
  winrm_timeout  = "15m"
  winrm_username = "packer"

  # Publish into a Shared Image Gallery. A plain managed image works too, but
  # the gallery is what gives you versioning and multi-region replication, and
  # it is what the scale set should point at.
  shared_image_gallery_destination {
    subscription        = var.subscription_id
    resource_group      = var.resource_group
    gallery_name        = var.gallery_name
    image_name          = local.image_name
    image_version       = var.image_version
    replication_regions = [var.location]
  }

  # Azure requires a generalized image. Packer runs sysprep via the shutdown
  # command below; this tells it to expect that.
  build_resource_group_name         = var.resource_group
  managed_image_storage_account_type = "Premium_LRS"

  azure_tags = {
    purpose = "pyhamilton-ci"
    builder = "packer"
  }
}

build {
  name    = "venus-runner-image"
  sources = ["source.azure-arm.venus"]

  # ---- prerequisites, in the order the PyHamilton README asks for them ----
  provisioner "powershell" {
    inline = [
      "Set-ExecutionPolicy Bypass -Scope Process -Force",
      "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12",
      "Write-Host '==> chocolatey'",
      "iex ((New-Object Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))",
      "Write-Host '==> .NET Framework 4.8 + Python + git (with LFS)'",
      # git-lfs matters: the repo's vendor installers are LFS objects, and a
      # checkout without it yields pointer files (audit INST-1).
      "choco install -y --no-progress dotnetfx python311 git git-lfs",
      "git lfs install --system"
    ]
    elevated_user     = "SYSTEM"
    elevated_password = ""
  }

  provisioner "windows-restart" {
    restart_timeout = "30m"
  }

  # ---- VENUS itself ----
  provisioner "powershell" {
    environment_vars = [
      "VENUS_URI=${var.venus_installer_uri}",
      "VENUS_ARGS=${var.venus_silent_args}"
    ]
    inline = [
      "if (-not $env:VENUS_ARGS) { throw 'venus_silent_args is empty -- run stage 1 of the runbook first, or this build will hang on a dialog nobody can see.' }",
      "$dst = 'C:\\Windows\\Temp\\VenusSetup.exe'",
      "Write-Host '==> downloading VENUS installer'",
      "Invoke-WebRequest -Uri $env:VENUS_URI -OutFile $dst -UseBasicParsing",
      "Write-Host '==> installing VENUS (unattended)'",
      # Explicit exit-code check: a silent installer that fails is silent about
      # that too, and the failure would otherwise surface as a missing HxRun.exe
      # three stages later.
      "$p = Start-Process -FilePath $dst -ArgumentList $env:VENUS_ARGS -Wait -PassThru -NoNewWindow",
      "Write-Host \"    installer exit code: $($p.ExitCode)\"",
      # 3010 == success, reboot required. Not a failure.
      "if ($p.ExitCode -notin @(0, 3010)) { throw \"VENUS installer failed with exit code $($p.ExitCode)\" }"
    ]
    elevated_user     = "SYSTEM"
    elevated_password = ""
  }

  provisioner "windows-restart" {
    restart_timeout = "30m"
  }

  # ---- prove the image is actually usable before publishing it ----
  # An image that builds but cannot run a method is worse than no image: it
  # fails later, on someone else's pull request, with no obvious cause.
  provisioner "powershell" {
    inline = [
      "Write-Host '==> verifying VENUS install'",
      "$hx = 'C:\\Program Files (x86)\\HAMILTON\\Bin\\HxRun.exe'",
      "if (-not (Test-Path $hx)) { throw \"HxRun.exe not found at $hx -- VENUS did not install correctly\" }",
      "Write-Host \"    OK  $hx\"",
      "foreach ($d in 'Library','Methods','Config') {",
      "  $p = Join-Path 'C:\\Program Files (x86)\\HAMILTON' $d",
      "  if (-not (Test-Path $p)) { throw \"missing HAMILTON\\$d\" }",
      "  Write-Host \"    OK  HAMILTON\\$d\"",
      "}",
      "$ndp = Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\NET Framework Setup\\NDP\\v4\\Full'",
      "if ($ndp.Release -lt 528040) { throw \"need .NET 4.8+, found release $($ndp.Release)\" }",
      "Write-Host \"    OK  .NET release $($ndp.Release)\""
    ]
  }

  # ---- generalize ----
  # Deliberately NOT installing the GitHub Actions runner agent here: GitHub
  # provisions and registers it per instance for scale-set runners. An agent
  # baked into the image registers under the image's identity and every VM in
  # the set collides on the same runner name.
  provisioner "powershell" {
    inline = [
      "Write-Host '==> sysprep'",
      "while ((Get-Service RdAgent -ErrorAction SilentlyContinue) -and ((Get-Service RdAgent).Status -ne 'Running')) { Start-Sleep 5 }",
      "& $env:SystemRoot\\System32\\Sysprep\\Sysprep.exe /generalize /oobe /quiet /quit /mode:vm",
      "while ($true) {",
      "  $s = Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Setup\\State' | Select-Object -Expand ImageState",
      "  if ($s -eq 'IMAGE_STATE_GENERALIZE_RESEAL_TO_OOBE') { break }",
      "  Write-Host \"    sysprep: $s\"; Start-Sleep 10",
      "}"
    ]
  }
}
