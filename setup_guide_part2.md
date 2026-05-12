# Setup Guide — Part 2: Native Ubuntu 22.04 on the old machine

**Companion to:** [setup_guide.md](setup_guide.md) (the Windows + VMware guide).
**Target host:** an old computer, bare-metal Ubuntu 22.04 install.
**Why:** native gives you full GPU and no VM overhead — Gazebo rendering will be smoother and the PX4 build will be faster, assuming the hardware cooperates.
**This guide stops at "Ubuntu is booted and clean."** The actual workshop install (PX4, MAVSDK, Gazebo, env vars, files) is identical to **Path B §3.3 onwards in [setup_guide.md](setup_guide.md)** — don't duplicate, just jump there when prompted.

---

## 0. Reality check the hardware first

Before you spend time burning USBs, make sure the machine can actually run the workshop stack.

### Minimum viable spec

| Component | Floor | Comfortable |
|---|---|---|
| CPU | x86_64, 2 cores, ~2 GHz | 4 cores, ~3 GHz |
| RAM | 8 GB | 16 GB |
| Disk | 80 GB free, HDD ok | 100 GB+ on SSD |
| GPU | any with OpenGL 3.3 (most Intel HD ≥4000 / NVIDIA ≥GeForce 400 / AMD HD ≥5000) | dedicated GPU with vendor driver support |
| BIOS | UEFI ideally; legacy BIOS works but is fiddlier | UEFI |
| Network | wired or any working WiFi | wired (PX4 first-clone is ~1–2 GB) |

### Quick check on the old machine (boot from anything you can — Windows, an existing Linux, or a live USB)

```
- CPU: 64-bit? Most ≥2010 desktops are. If 32-bit only, stop — the workshop won't run.
- RAM: <8 GB will work but PX4 build will swap; <4 GB will fail. Add a stick if you can.
- Disk: free space + age (SSD is night-and-day for build times)
- GPU: vendor + model. Look up its newest supported driver. Very old NVIDIA (<GeForce 400) is in the 'legacy' driver branch and may not get OpenGL 3.3.
```

If GPU is too weak: software rendering (Mesa llvmpipe) works for Gazebo but is **painfully slow** — usable for code testing, not for real-time flight tuning. Note this as a possibility, not a recommendation.

> **Verdict:** if RAM ≥ 8 GB, 64-bit CPU, and the GPU has a maintained Linux driver, proceed. Otherwise reconsider — your time is worth more than wrestling with ancient hardware.

---

## 1. Make a Ubuntu 22.04 install USB

You need an 8 GB+ USB stick. Anything on it gets wiped.

### 1.1 Get the ISO

Download `ubuntu-22.04.4-desktop-amd64.iso` (or whatever the current 22.04.x is) from:

https://releases.ubuntu.com/22.04/

Verify the SHA256 if you care:

```
sha256sum ubuntu-22.04.4-desktop-amd64.iso
# compare to the SHA256SUMS file on the same page
```

### 1.2 Flash the USB

Use whichever tool is on the machine you have:

- **From Windows:** [Rufus](https://rufus.ie). Choose the ISO, target USB, GPT partition scheme + UEFI for modern hardware (or MBR + BIOS for older), "DD mode" if asked. Click Start.
- **From an existing Linux:** `sudo dd if=ubuntu-22.04.4-desktop-amd64.iso of=/dev/sdX bs=4M status=progress conv=fsync` — replace `/dev/sdX` with your USB device (check with `lsblk` first, **double-check, this wipes the target**).
- **From macOS:** [balenaEtcher](https://etcher.balena.io) or `dd` similar to Linux.

---

## 2. Boot the old machine from the USB

### 2.1 Get into the boot menu / BIOS

Plug the USB in. Power on. As the machine POSTs, mash one of these keys (varies by vendor):

| Vendor | Boot menu | BIOS/UEFI setup |
|---|---|---|
| Dell | F12 | F2 |
| HP | F9 / Esc | F10 |
| Lenovo | F12 | F1 / F2 |
| ASUS | F8 / Esc | Del / F2 |
| Acer | F12 | F2 |
| MSI | F11 | Del |
| Generic / older | F12 / Esc | Del / F2 |

If you don't get a menu, go into BIOS setup and check **boot order** — make USB first, save and exit.

### 2.2 BIOS settings worth confirming

- **Secure Boot:** `Disabled` (Ubuntu 22.04 supports it but disabling avoids weird edge cases on older firmware)
- **Boot mode:** prefer `UEFI` over `Legacy/CSM` if both are available; modern Ubuntu installs cleanly under UEFI
- **Fast Boot:** off (so the boot menu key actually registers)
- **AHCI** for SATA mode (not RAID/IDE) — this matters for SSD detection
- **TPM:** doesn't matter for Linux

### 2.3 Boot

Pick the USB from the boot menu. You'll see GRUB → "Try or Install Ubuntu". Pick that.

If the screen goes black on the GRUB selection, **highlight "Try or Install Ubuntu", press `e`, find the line starting `linux ...`, append ` nomodeset` before `quiet splash`, then F10 to boot.** This forces a basic graphics mode for installation. You'll fix the driver after install.

---

## 3. Install Ubuntu 22.04

You're "reviving" the machine, so I assume **wiping the disk** is fine. Adjust if you actually want to dual-boot something else.

### 3.1 Walk through the installer

- Language: your pick.
- Keyboard: your pick.
- Connect to a network: yes if you have one. The installer can pull updates while installing.
- Updates and other software: **check "Install third-party software"** (gives you proprietary GPU drivers and codecs from the start). Skip "Download updates while installing" if you're on a slow network — easier to fail fast.
- Installation type: **"Erase disk and install Ubuntu"** for a revive. (Advanced: pick "Something else" if you want custom partitions.)
- Time zone: your pick.
- Username / password: pick something you'll remember. You'll be typing this a lot for `sudo`.

> **If "Erase disk" worries you,** confirm there's nothing on the disk worth keeping by booting the live session first ("Try Ubuntu") and `lsblk` / `mount` / browse around with the Files app.

### 3.2 Reboot, remove USB

Installer prompts to reboot. Pull the USB when it asks. You should land at a fresh Ubuntu desktop login.

---

## 4. First-boot housekeeping

Open a terminal (Ctrl+Alt+T):

```bash
# Confirm the version
lsb_release -a            # must say 22.04 LTS

# Update everything
sudo apt update && sudo apt upgrade -y

# Reboot if a kernel update came down
sudo reboot
```

---

## 5. GPU drivers (the most failure-prone bit)

Old machines fall into three buckets here. Pick your bucket.

### 5.1 NVIDIA (any GeForce)

```bash
ubuntu-drivers devices
```

This lists candidate drivers. You'll see something like `nvidia-driver-535 - distro non-free recommended`. Install the recommended one:

```bash
sudo ubuntu-drivers autoinstall
sudo reboot
```

After reboot:

```bash
nvidia-smi        # should list your GPU + driver version
glxinfo -B | grep -E "OpenGL renderer|OpenGL version"
# expect "NVIDIA Corporation" as the renderer, OpenGL ≥ 3.3
```

If `ubuntu-drivers devices` shows your GPU is "in the legacy 470 driver branch" or older, install whatever it recommends — the workshop only needs OpenGL 3.3, which the legacy branches still provide. Anything older than the 390 branch is unlikely to work for Gazebo Harmonic.

### 5.2 AMD (Radeon)

You're done — AMD's open-source `amdgpu` / `radeon` drivers are in the kernel and ship with Ubuntu. Verify:

```bash
sudo apt install -y mesa-utils
glxinfo -B | grep -E "OpenGL renderer|OpenGL version"
# expect "AMD" or "Radeon" as the renderer
```

Older AMD cards (HD 5000–7000 series) use `radeon`; HD 8000+ uses `amdgpu`. Both work for Gazebo.

### 5.3 Intel integrated

Same story as AMD — Intel's i915 driver ships in the kernel:

```bash
sudo apt install -y mesa-utils
glxinfo -B | grep -E "OpenGL renderer|OpenGL version"
# expect "Intel" as the renderer
```

Integrated graphics will run Gazebo but slowly (Intel HD 4000 era will struggle). You'll spend less time waiting if you can scavenge a discrete GPU.

### 5.4 If glxinfo says `llvmpipe`

You're on software rendering. The driver didn't bind. Check:

```bash
lspci -k | grep -A 2 -E "VGA|3D"
# Look at "Kernel driver in use:" — should be your GPU's driver, not vesa/fbdev
sudo dmesg | grep -iE "drm|nvidia|amdgpu|i915" | tail -30
```

Most common culprits:
- NVIDIA proprietary driver wasn't installed (do §5.1)
- Secure Boot blocked the driver kernel module (disable in BIOS, or enroll the MOK key)
- Dual-GPU laptop (Optimus) — you may need `nvidia-prime` and switch to NVIDIA mode

---

## 6. SSH in from another machine (optional but very useful)

If your old machine is across the room, install OpenSSH server so you can edit code from your main laptop:

```bash
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
ip a                    # find this machine's IP on the LAN
```

From the other machine: `ssh user@<ip>`. With VS Code's **Remote-SSH** extension, you can edit and debug as if the code were local.

You'll still need to physically be at the old machine (or use `x11vnc` / similar) to see the Gazebo and QGroundControl GUIs.

---

## 7. Take a snapshot before installing the workshop stack

Hardware doesn't have VMware-style snapshots, but you can fake it cheaply:

### Option A — Timeshift

```bash
sudo apt install -y timeshift
sudo timeshift --create --comments "clean install" --tags D
```

If you break something later, boot a live USB and `sudo timeshift --restore`.

### Option B — full disk image with Clonezilla

Boot Clonezilla live USB, image the entire disk to an external drive. Slowest but bulletproof restore.

For most cases, Timeshift is enough.

---

## 8. Now run the workshop install

This is where Part 2 stops being unique. **Continue at [setup_guide.md](setup_guide.md) §3.3** ("After install, in the Ubuntu VM") and run every command from there. The instructions are identical except:

- You're on bare metal, so **skip §4** (shared folders / VMware Tools).
- For getting `hackerverse/` onto this machine: use `git`, `scp`, an external USB, or `rsync` over SSH.
- Build times will be **faster than in a VM** (full cores, full RAM).

The full sequence:

1. [setup_guide.md §3.3.1](setup_guide.md) — apt install dev essentials
2. [setup_guide.md §3.3.2](setup_guide.md) — clone PX4-Autopilot + run `ubuntu.sh` (15–25 min on modern hw, 30–60 min on old hw)
3. [setup_guide.md §3.3.3](setup_guide.md) — MAVSDK Python + C++ deb
4. [setup_guide.md §3.3.4](setup_guide.md) — env vars in `.bashrc`
5. [setup_guide.md §3.4](setup_guide.md) — drop in `start_px4.sh`, `roboverse.sdf`, `base6.glb`, modified `x500_vision/model.sdf`
6. [setup_guide.md §3.5](setup_guide.md) — sanity checks
7. [setup_guide.md §5](setup_guide.md) — first sim launch with `~/start_px4.sh`
8. [setup_guide.md §6](setup_guide.md) — EKF origin trick
9. [setup_guide.md §7](setup_guide.md) — first Python script
10. [setup_guide.md §8](setup_guide.md) — maze generator integration

---

## 9. Bare-metal-specific gotchas

These won't appear in the VM guide because VMware abstracts them away.

### 9.1 Sleep / suspend mid-run

Ubuntu defaults to suspending the screen on idle, which can stall ROS-style loops or kill MAVLink heartbeats. Disable for dev:

```
Settings → Power → Power Saving → "Screen Blank" = Never
Settings → Power → "Automatic Suspend" = Off
```

### 9.2 Wi-Fi flakiness on old chipsets

If `nmcli device` shows your wifi as `unmanaged` or it drops a lot:

```bash
sudo apt install -y network-manager
# Identify chipset:
lspci | grep -i wireless
lsusb | grep -i wireless
# Then search for "ubuntu 22.04 <your chipset> driver" — fixes are vendor-specific
```

For the install + workshop work, **plug in ethernet if you can** — it sidesteps half the variance.

### 9.3 Disk fills up faster than you think

Building PX4 generates ~5–10 GB of object files. After install, run:

```bash
du -sh ~/PX4-Autopilot ~/.cache /tmp
df -h /
```

Keep the root partition above 15 GB free. If tight, `sudo apt clean` and `sudo journalctl --vacuum-time=7d` claw back a few GB.

### 9.4 Old CPU + slow build

`bash ./PX4-Autopilot/Tools/setup/ubuntu.sh` and `make px4_sitl gz_x500_vision` are CPU-bound. On a 2014-era dual-core that takes ~45 min, on a 2020+ quad-core ~15 min. **Don't kill it** thinking it's hung — `top` to confirm CPU is busy.

### 9.5 Fan / thermals

Old machines with dust and aged thermal paste will throttle hard during the build. If the machine is sluggish even after the build:

```bash
sudo apt install -y lm-sensors stress
sudo sensors-detect --auto
sensors        # check core temps; >85°C is too hot
```

Open the case, blow out dust, repaste if you're feeling brave. This is the #1 cheap fix for "this old laptop is slow."

### 9.6 Display scaling on tiny old screens

Gazebo + QGC + a terminal on a 1366×768 laptop is cramped. Either plug in an external monitor, or use **Settings → Displays → Scale = 100%** with smaller fonts. QGC has its own scale setting in **Application Settings → General**.

---

## 10. Comparison: this machine vs the Windows VM

You'll likely have both running at some point. Quick orientation:

| Concern | Native Ubuntu (this guide) | VMware on Windows ([setup_guide.md](setup_guide.md)) |
|---|---|---|
| Setup time | longer (incl. OS install) | shorter (use v3 VM) |
| Performance | best (full hw) | ~70–85% of native |
| GPU rendering | depends on driver | depends on VMware 3D accel |
| Snapshots | Timeshift / Clonezilla | VMware native, instant |
| File sharing with main machine | SSH/rsync | VMware shared folders |
| If the OS dies | reinstall, ~1 hr | revert snapshot, 30 sec |
| Power-off behavior | runs until you shut it down | suspends with VMware |

The natural workflow: **iterate fast on the Windows VM** (snapshots make experiments cheap), **run final perf-sensitive tests on this native machine** (real GPU, no VM overhead).

---

## Quick reference — first session on this machine

```bash
# After install + drivers + reboot:
sudo apt update && sudo apt upgrade -y
ubuntu-drivers autoinstall          # if NVIDIA
sudo reboot

# Then continue at setup_guide.md §3.3.
# Or all-in-one until first sim launch:
sudo apt install -y build-essential curl git wget software-properties-common \
  python3-pip python3-venv python3-opencv libgz-msgs10-dev \
  python3-gz-transport13 python3-gz-msgs10
cd ~ && git clone https://github.com/PX4/PX4-Autopilot.git --recursive
bash ./PX4-Autopilot/Tools/setup/ubuntu.sh
# (close + reopen terminal here)
pip install mavsdk
cd /tmp && wget https://github.com/mavlink/MAVSDK/releases/download/v3.17.1/libmavsdk-dev_3.17.1_ubuntu22.04_amd64.deb
sudo apt install -y ./libmavsdk-dev_3.17.1_ubuntu22.04_amd64.deb libopencv-dev
cat >> ~/.bashrc <<'EOF'
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
export OGRE_RTT_MODE=Copy
export PX4_GZ_SIM_RENDER_ENGINE=ogre
export GZ_SIM_RENDER_ENGINE=ogre
EOF
sudo ln -s /usr/include/opencv4/opencv2/ /usr/include/opencv2/
source ~/.bashrc
# then drop in start_px4.sh, roboverse.sdf, base6.glb, modified x500_vision/model.sdf
# then ~/start_px4.sh, EKF origin, takeoff_and_land.py
```
