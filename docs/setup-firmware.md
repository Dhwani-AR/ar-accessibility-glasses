# Firmware Setup

Setup guide for the ESP32-S3 firmware in `firmware/`. Problems? See [troubleshooting.md](troubleshooting.md). Pin assignments are in [hardware.md](hardware.md).

Commands are given for Windows (PowerShell) and Linux/macOS. Where a command is identical everywhere, it appears once.

## Prerequisites

- Python 3.12 and Git (see [setup-backend.md](setup-backend.md) for install notes).
- An ESP32-S3 board and a USB data cable. Some cables are charge-only and will not work.

## 1. Create the virtual environment and install PlatformIO

Windows (PowerShell):

```powershell
cd firmware
py -3.12 -m venv pio_venv
.\pio_venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux / macOS:

```bash
cd firmware
python3.12 -m venv pio_venv
source pio_venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` pins the PlatformIO version so every machine builds the same way.

Activating the environment later:

| System | Command (run in `firmware/`) |
|---|---|
| Windows PowerShell | `.\pio_venv\Scripts\Activate.ps1` |
| Windows Command Prompt | `pio_venv\Scripts\activate.bat` |
| Linux / macOS | `source pio_venv/bin/activate` |

If PowerShell blocks the script, see the execution policy fix in [setup-backend.md](setup-backend.md).

**Alternative for Windows users:** install Visual Studio Code and the PlatformIO IDE extension, then open the `firmware/` folder. The extension manages its own PlatformIO installation and adds Build, Upload, and Monitor buttons. Its PlatformIO version may differ from the pinned one, so if builds behave differently from a teammate's command-line build, compare versions with `pio --version`.

**Linux note:** if `pio` fails with `No module named pip` (seen on Arch), install pip through your package manager (`sudo pacman -S python-pip` on Arch, `sudo apt install python3-pip` on Debian/Ubuntu). On systems that protect the system Python, this does not permit global package installs.

## 2. Build, flash, and monitor

```
cd firmware
(activate pio_venv)
pio run                  # build (the first build downloads the ESP32 toolchain)
pio run -t upload        # flash the board over USB
pio device monitor       # open the serial monitor at 115200 baud
```

These commands are the same on every operating system once the environment is active. PlatformIO detects the serial port automatically.

Right now the firmware only initializes the OLED and draws "Optics Test OK". If you see that text on the display, the I2C wiring and the U8g2 setup work.

### Serial port troubleshooting

- **Windows:** the board should appear as a COM port in Device Manager under "Ports (COM & LPT)". If it does not appear, or shows up as an unknown device, try a different USB data cable and install the USB-serial driver for your board's USB chip (commonly CP210x or CH340, depending on which USB port on the board you use). No administrator rights or group membership are needed for flashing.
- **Linux:** if flashing fails with a permission error on the serial port, add your user to the serial group, then log out and back in.
  - Arch: `sudo usermod -aG uucp $USER`
  - Debian/Ubuntu: `sudo usermod -aG dialout $USER`
- **All systems:** if the upload cannot connect, hold the BOOT button, tap RESET, then release BOOT to enter download mode and retry.

## 3. Enable the board's flash and PSRAM

The Freenove N16R8 has 16 MB flash and 8 MB Octal PSRAM, but the generic `esp32-s3-devkitc-1` board definition does not enable them. Before streaming audio (which needs large buffers), add these to the environment section of `firmware/platformio.ini`:

```ini
board_upload.flash_size = 16MB
board_build.arduino.memory_type = qio_opi
board_build.partitions = default_16MB.csv
build_flags =
    -DBOARD_HAS_PSRAM
```

If `platformio.ini` already has a `build_flags` entry, add `-DBOARD_HAS_PSRAM` to that list instead of declaring it twice.

Check it worked by printing `ESP.getPsramSize()` and `ESP.getFlashChipSize()` over serial at boot. You should see roughly 8,388,608 and 16,777,216 bytes. The `qio_opi` setting matters: with the default memory type the PSRAM will not initialize properly. Remember that GPIO 35, 36, and 37 are reserved by Octal PSRAM and must not be used.

## 4. Wi-Fi credentials

The Wi-Fi name and password live in `firmware/include/credentials.h`, which is gitignored and never committed. A fresh clone does not have it, so the build fails with `fatal error: credentials.h: No such file or directory` until you create it.

Copy the template and fill in your own details:

```bash
cp firmware/include/credentials.example.h firmware/include/credentials.h
```

Then edit `credentials.h`:

```cpp
#pragma once

#define WIFI_SSID "your-network-name"
#define WIFI_PASS "your-network-password"
```

Use a 2.4 GHz network, because the ESP32-S3 does not support 5 GHz. Never commit `credentials.h`.

How to find the laptop's IP address is in [setup-backend.md](setup-backend.md). The message format the firmware must speak is in [../protocol/README.md](../protocol/README.md).

## Libraries

Libraries are declared in `platformio.ini` under `lib_deps` and downloaded automatically on build. The firmware currently uses `olikraus/U8g2` for the OLED.

## Code formatting

The repository root has a `.clang-format` (LLVM style, 4-space indent, 120 columns). Format your own C++ files before every commit.

Install (inside `pio_venv`; the same command works on Windows, Linux and macOS):

    pip install clang-format==<version>

Format one file:

    clang-format -i firmware/src/main.cpp

Check without changing anything:

    clang-format --dry-run --Werror firmware/src/main.cpp

Only format files in `firmware/src` and `firmware/include`, not `lib/` or generated code. In VS Code, enable "Format on Save" with the C/C++ extension or the clang-format extension.
