# AR Accessibility Glasses

Wearable augmented-reality closed-captioning glasses for Deaf and Hard-of-Hearing (DHH) users. The glasses capture 4-channel spatial audio from a microphone array and stream it over Wi-Fi UDP to a companion server on a laptop. The server computes the 360-degree direction of arrival (DoA), transcribes the speech, and tracks who is speaking. The result is rendered as word-wrapped subtitles and directional indicators in the wearer's field of view, paired with a haptic cue alerting them to speakers behind them or loud environmental sounds.

This is a capstone project built under a budget cap of INR 7,000.

## Contents

- [How it works](#how-it-works)
- [Repository layout](#repository-layout)
- [Quick start](#quick-start)
- [Documentation](#documentation)
- [Project status](#project-status)
- [Conventions](#conventions)
- [Limitations](#limitations)

## How it works

The glasses are a dual-core FreeRTOS thin client: they capture synchronized 4-channel audio, render HUD text, and drive an I2S haptic amplifier. All signal processing and neural inference run on a laptop reached over Wi-Fi.

```text
[4x INMP441 mics] --(Dual I2S DMA)--> [ESP32-S3] --(UDP 5005 / Wi-Fi)--> [Laptop server]
                                          ^                                     |
                                          |        JSON: text, speaker,         |
                                          +-------------- angle, haptic --------+
                                          |
                                          +--> SSD1306 OLED (3-line HUD) + MAX98357A Haptics
```

The firmware and the backend share no code. They share only an agreed binary uplink header (`<BBBBII` + 4-channel PCM) and JSON downlink format, described in [protocol/README.md](protocol/README.md). For the full pipeline and design reasoning, see [docs/architecture.md](docs/architecture.md).

## Repository layout

This is a monorepo, so a change to the message format can be made on both sides in a single commit.

```text
ar-accessibility-glasses/
|-- backend/      Python AI server (2D GCC-PHAT, faster-whisper, SpeechBrain ECAPA-TDNN)
|-- firmware/     ESP32-S3 firmware (C++, PlatformIO, FreeRTOS, U8g2, ArduinoJson)
|-- hardware/     Fritzing diagrams, netlists, pin connection sheets, CAD, and optics files
|-- protocol/     Message contract between firmware and backend
`-- docs/         Architecture, hardware, setup guides, troubleshooting, milestone logs
```

## Quick start

These steps get the backend server and hardware verification tools running on your laptop. Commands are shown for Windows (PowerShell) and Linux/macOS. You need Python 3.12 and Git installed.

### 1. Install the backend

Windows (PowerShell):

```powershell
cd backend
py -3.12 -m venv aiml_venv
.\aiml_venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux / macOS:

```bash
cd backend
python3.12 -m venv aiml_venv
source aiml_venv/bin/activate
pip install -r requirements.txt
```

Both `faster-whisper` (`base.en`) and SpeechBrain (`speechbrain/spkrec-ecapa-voxceleb`) are open-access models and download automatically on first run without requiring a Hugging Face account or `.env` token. If PowerShell blocks the activation script, see [docs/troubleshooting.md](docs/troubleshooting.md).

### 2. Verify the 4-channel microphone array (`verify_mics.py`)

Once your ESP32-S3 is flashed and streaming over UDP port `5005`, test your physical microphone wiring and `L/R` channel order before loading the AI models:

```bash
cd backend
python verify_mics.py
```

Lightly tap each microphone on the glasses frame to confirm that **Front-Left = `Ch0`**, **Front-Right = `Ch1`**, **Rear-Left = `Ch2`**, and **Rear-Right = `Ch3`**. Stop the script with `Ctrl+C` when finished.

### 3. Run the AI UDP server (`server.py`)

```bash
cd backend
python server.py
```

The server listens on `0.0.0.0:5005`, accumulates a **2.4-second sliding window** every **1.6-second stride**, computes 360-degree speaker angles via 2D GCC-PHAT, transcribes speech with prefix overlap deduplication, identifies speakers via ECAPA-TDNN embeddings, and sends `{text, speaker, angle, haptic}` JSON replies back to the glasses.

To test the server handshake from another terminal without the ESP32:

```bash
python -c "import socket, struct; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(3); s.sendto(struct.pack('<BBBBII', 2, 1, 4, 0, 1, 100), ('127.0.0.1', 5005)); print(s.recvfrom(4096)[0].decode())"
```

### 4. Build and flash the firmware

Copy `firmware/include/credentials.example.h` to `firmware/include/credentials.h`, set your 2.4 GHz `WIFI_SSID`, `WIFI_PASS`, and laptop `SERVER_IP`, and flash the ESP32-S3 using PlatformIO. Full instructions: [docs/setup-firmware.md](docs/setup-firmware.md).

## Documentation

| Document | What it covers |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Problem statement, 7-stage system pipeline, sliding-window & DoA design decisions |
| [docs/hardware.md](docs/hardware.md) | BOM, complete ESP32-S3 pin assignments, 4-mic geometry, Pepper's Ghost optics |
| [docs/setup-backend.md](docs/setup-backend.md) | Backend virtual environment, `verify_mics.py`, running `server.py`, firewall setup |
| [docs/setup-firmware.md](docs/setup-firmware.md) | PlatformIO setup, Octal PSRAM flags, `credentials.h`, flashing and serial monitoring |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Known issues and fixes across backend, network, firmware, and hardware |
| [protocol/README.md](protocol/README.md) | Binary `<BBBBII` UDP audio packet layout and JSON reply schema |

## Project status

| Area | Status |
|---|---|
| Repository structure & documentation | Done |
| Dual-bus 4-channel I2S DMA capture & UDP streaming (`firmware/`) | Done |
| 3-line OLED word wrapping & directional HUD header (`GPIO 14/21`) | Done |
| MAX98357A I2S TX haptic waveform driver (`GPIO 38`) | Done |
| Threaded UDP server with 2.4 s / 1.6 s sliding window (`backend/server.py`) | Done |
| 360° 2D GCC-PHAT Direction of Arrival (`backend/pipeline.py`) | Done |
| Speech-to-text (`faster-whisper`) with boundary overlap deduplication | Done |
| Online speaker identification (`SpeechBrain ECAPA-TDNN` centroid cache) | Done |
| 4-channel hardware verification utility (`backend/verify_mics.py`) | Done |
| Physical frame assembly, mic spacing calibration & YAMNet sound alerts | In progress |

## Conventions

- Commit messages follow Conventional Commits with a subsystem scope, for example `feat(backend): ...` or `feat(firmware): ...`.
- Never commit secrets or large artifacts: `credentials.h`, `.env`, virtual environments (`aiml_venv/`, `pio_venv/`), `.pio/`, model weights, and recordings must stay in `.gitignore`.
- Changes to the message format update `protocol/`, the Python code, and the C++ code in the same commit.
- The team uses Windows and Linux, so keep `* text=auto` in `.gitattributes` to normalize line endings, and build file paths in Python with `pathlib` rather than hardcoded separators.
- Format C++ before every commit. Run `clang-format -i firmware/src/main.cpp` using the repo's `.clang-format`. Setup and commands: [docs/setup-firmware.md](docs/setup-firmware.md#code-formatting).

## Limitations

The glasses depend on the laptop server being on and reachable over a local 2.4 GHz Wi-Fi network or hotspot, because the AI models cannot run on an ESP32-S3. Subtitles lag speech by roughly 1.6 to 2.0 seconds due to sliding-window buffering and inference. The optical combiner suits controlled indoor lighting rather than direct outdoor sunlight. More detail is in [docs/architecture.md](docs/architecture.md) and [docs/hardware.md](docs/hardware.md).

## Author

Meehir Prabhakar

## License

Not yet specified.
