# Troubleshooting

Known issues and fixes, grouped by part of the project. If you hit a new problem and solve it, add it here so the next person does not lose time on it.

## Backend (Python)

### `OSError: [Errno 98] Address already in use` (or `WinError 10048`) on port 5005

`verify_mics.py` or another instance of `server.py` is still running and holding UDP port `5005`. Stop the other process with `Ctrl+C` before launching `server.py`.

### `TypeError: open() got an unexpected keyword argument 'metadata_errors'`

This comes from `faster-whisper` if `av` (PyAV) `>=17` gets installed. The repository pins `av==16.1.0` in `backend/requirements.txt`. Note that `pipeline.py` passes in-memory `float32` NumPy arrays directly to `self.asr.transcribe(mono, ...)`, which bypasses PyAV file decoding entirely.

### `Worker is behind; dropping chunk` warning in `server.py`

The inference worker thread took longer than the `1.6 s` stride to process a `2.4 s` audio window (most common on CPU-only machines during initial model warm-up). If this happens continuously on CPU:
- Confirm `compute_type="int8"` is active in `pipeline.py`.
- Increase `STRIDE_SECONDS` from `1.6` to `2.0` in `backend/server.py`, or switch the Whisper model in `pipeline.py` from `"base.en"` to `"tiny.en"`.

### Direction of Arrival (DoA) angles are inverted or point the wrong way

1. Run `python backend/verify_mics.py` and tap each microphone one by one.
2. Confirm that **Front-Left = `Ch0`**, **Front-Right = `Ch1`**, **Rear-Left = `Ch2`**, and **Rear-Right = `Ch3`**.
3. If `Ch0` and `Ch1` are swapped, check the `L/R` pin wiring on your front INMP441 pair (`Mic 1 L/R` must go to `GND`; `Mic 2 L/R` must go to `+3.3V`).
4. Measure the physical spacing between your mounted microphones and update `width` (Left-to-Right distance in meters) and `depth` (Front-to-Rear distance in meters) in `server.py` when instantiating `AudioPipeline`.

### Subtitles never trigger, or trigger constantly on background noise

Adjust the RMS thresholds in `AudioPipeline.__init__()` inside `backend/pipeline.py`:
- `self.speech_rms = 0.012`: Lower this (e.g., `0.006`) if quiet speech is ignored; raise it (e.g., `0.025`) if room fan noise triggers transcription.
- `self.alert_rms = 0.18`: Adjust if `[Loud Sound Alert]` triggers too easily or requires too loud a sound.

### PowerShell: "running scripts is disabled on this system"

Windows blocks the venv activation script by default. Run this once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

## Network

### The localhost test works but the ESP32 gets no reply

- **Firewall:** Allow Python through Windows Defender Firewall on **Private networks**, or run `sudo ufw allow 5005/udp` on Linux.
- **Packet format:** Ensure you are sending binary packets with the 12-byte `<BBBBII` header (`version = 1`, `ptype = 0x01` for 4-channel audio or `0x02` for heartbeat). Raw text packets like `b"ping"` are intentionally rejected by `parse_packet()`.
- **Client isolation:** Campus and public Wi-Fi networks block peer-to-peer UDP traffic between devices. Use a 2.4 GHz phone hotspot or laptop hotspot and verify `SERVER_IP` in `firmware/include/credentials.h`.

## Firmware (ESP32-S3)

### OLED stays blank on boot

- **Check remapped I2C pins:** `SDA` must be wired to **`GPIO 14`** (Left side, 2nd pin from Bottom) and `SCL` to **`GPIO 21`** (Right side, 4th pin from Bottom), plus `+3.3V` and `GND`. Do **not** wire the OLED to `GPIO 8` or `GPIO 9` (those collide with the OV3660 camera bus).
- **Check continuity:** Ensure `Wire.begin(14, 21)` is called before `oled.begin()` in `firmware/src/main.cpp`.

### Vibration motor does not buzz when `haptic: true` is received

- The motor is driven by the **MAX98357A I2S Class D Amplifier**, not a simple GPIO high/low switch.
- Verify the MAX98357A is wired to `Vin` (`+3.3V`), `GND`, `BCLK` (`GPIO 41`), `LRC` (`GPIO 42`), and `DIN` (`GPIO 38`), with the motor connected directly to the `VO+` and `VO-` screw terminals (no series resistor).
- Confirm `I2S_NUM_0` is initialized with `I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_TX` and `data_out_num = 38`.

### PSRAM size prints as 0, or the board resets in a loop

Verify `firmware/platformio.ini` includes `board_build.arduino.memory_type = qio_opi`, `board_upload.flash_size = 16MB`, and `-DBOARD_HAS_PSRAM`. Ensure nothing is soldered to `GPIO 35`, `36`, or `37`.

### `No module named pip` when PlatformIO installs its toolchain (Linux)

Install pip through your system package manager (`sudo pacman -S python-pip` on Arch, `sudo apt install python3-pip` on Debian/Ubuntu).

### `fatal error: credentials.h: No such file or directory`

Copy `firmware/include/credentials.example.h` to `firmware/include/credentials.h` and fill in `WIFI_SSID`, `WIFI_PASS`, and `SERVER_IP`.

## Git and repository

### Virtual environment or build folders appear in `git status`

Ensure `aiml_venv/`, `pio_venv/`, `.pio/`, `__pycache__/`, `.env`, and `firmware/include/credentials.h` are listed in the root `.gitignore`.
