# Firmware Setup

Setup guide for the ESP32-S3 firmware in `firmware/`. Problems? See [troubleshooting.md](troubleshooting.md). Pin assignments are in [hardware.md](hardware.md).

Commands are given for Windows (PowerShell) and Linux/macOS. Where a command is identical everywhere, it appears once.

## Prerequisites

- Python 3.12 and Git (see [setup-backend.md](setup-backend.md) for install notes).
- A Freenove ESP32-S3-WROOM-1 (N16R8) board and a USB-C data cable. Some cables are charge-only and will not work.

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

**Alternative for Windows users:** install Visual Studio Code and the PlatformIO IDE extension, then open the `firmware/` folder. The extension manages its own PlatformIO installation and adds Build, Upload, and Monitor buttons.

**Linux note:** if `pio` fails with `No module named pip` (seen on Arch), install pip through your package manager (`sudo pacman -S python-pip` on Arch, `sudo apt install python3-pip` on Debian/Ubuntu).

## 2. Enable the board's flash and PSRAM

The Freenove N16R8 has 16 MB flash and 8 MB Octal PSRAM, which must be enabled in `firmware/platformio.ini`:

```ini
board_upload.flash_size = 16MB
board_build.arduino.memory_type = qio_opi
board_build.partitions = default_16MB.csv
build_flags =
    -DBOARD_HAS_PSRAM
```

The `qio_opi` setting is mandatory for Octal PSRAM initialization. Remember that `GPIO 35`, `36`, and `37` are reserved internally by Octal PSRAM and must never be wired.

## 3. Wi-Fi and Server IP credentials

The Wi-Fi credentials and backend server IP live in `firmware/include/credentials.h`, which is gitignored and never committed. A fresh clone will fail with `fatal error: credentials.h: No such file or directory` until you create it.

Copy the template and fill in your own details:

```bash
cp firmware/include/credentials.example.h firmware/include/credentials.h
```

Then edit `firmware/include/credentials.h`:

```cpp
#pragma once

#define WIFI_SSID "your-2.4ghz-network-name"
#define WIFI_PASS "your-network-password"
#define SERVER_IP "192.168.x.x"
```

Use a **2.4 GHz** network (the ESP32-S3 does not support 5 GHz) and set `SERVER_IP` to the IPv4 address of the laptop running `backend/server.py` (see [setup-backend.md](setup-backend.md)). Never commit `credentials.h`.

## 4. Pre-power continuity check and flashing

Before plugging in USB after soldering your wiring harness, use a multimeter in continuity mode to verify that `3V3` (Left side, 1st pin from Top) and `GND` (Right side, 1st pin from Bottom) are not shorted.

Then build, upload, and monitor:

```bash
cd firmware
# (activate pio_venv)
pio run                  # build firmware
pio run -t upload        # flash the board over USB
pio device monitor       # open serial monitor at 115200 baud
```

On boot:
1. `DispTask` (Core 1) initializes the SSD1306 OLED on `SDA = GPIO 14` and `SCL = GPIO 21` and displays **"AR Glasses Ready / Waiting for UDP..."**.
2. `NetTask` (Core 0) connects to Wi-Fi, prints `Wi-Fi connected. ESP32 IP: ...` over serial, initializes synchronized dual-bus I2S DMA (`I2S0` master RX/TX on `GPIO 41/42/1/38`, `I2S1` slave RX on `GPIO 47`), and begins streaming 4-channel audio packets to `SERVER_IP:5005`.

### Serial port troubleshooting

- **Windows:** the board should appear as a COM port in Device Manager under "Ports (COM & LPT)". If missing, try a different USB data cable or install the CP210x/CH340 driver.
- **Linux:** if flashing fails with a permission error, add your user to the serial group (`sudo usermod -aG uucp $USER` on Arch, `sudo usermod -aG dialout $USER` on Debian/Ubuntu), then log out and back in.
- **All systems:** if upload cannot connect, hold `BOOT`, tap `RESET`, then release `BOOT` to enter download mode and retry.

## Libraries

Libraries are declared in `platformio.ini` under `lib_deps` and downloaded automatically on build:
- `olikraus/U8g2` for driving the SSD1306 128x64 I2C OLED
- `bblanchon/ArduinoJson` for deserializing incoming subtitle and haptic JSON payloads

## Code formatting

The repository root has a `.clang-format` (LLVM style, 4-space indent, 120 columns). Format your C++ files before every commit:

```bash
clang-format -i firmware/src/main.cpp
clang-format --dry-run --Werror firmware/src/main.cpp
```
