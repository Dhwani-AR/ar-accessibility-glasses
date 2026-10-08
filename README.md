# AR Accessibility Glasses

Wearable augmented-reality closed-captioning glasses for Deaf and Hard-of-Hearing (DHH) users. The glasses capture audio from a microphone array and stream it to a companion server on a laptop. The server transcribes the speech and works out who is speaking and from which direction. The result is shown as subtitles in the wearer's field of view, with a haptic cue pointing toward speakers outside their direct line of sight.

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

The glasses are a thin client: they capture audio, show text, and vibrate. All heavy AI runs on a laptop reached over Wi-Fi.

```
[4x INMP441 mics] --(I2S)--> [ESP32-S3] --(UDP over Wi-Fi)--> [Laptop server]
                                  ^                                  |
                                  |      JSON: text, speaker,        |
                                  +------------ angle, haptic -------+
                                  |
                                  +--> OLED (subtitles) + haptic motor
```

The firmware and the backend share no code. They share only an agreed message format, described in [protocol/README.md](protocol/README.md). For the full pipeline and design reasoning, see [docs/architecture.md](docs/architecture.md).

## Repository layout

This is a monorepo, so a change to the message format can be made on both sides in a single commit.

```
ar-accessibility-glasses/
|-- backend/      Python AI server (faster-whisper, pyannote.audio), runs on the laptop
|-- firmware/     ESP32-S3 firmware (C++, PlatformIO, Arduino framework)
|-- hardware/     CAD, wiring diagrams, optics files
|-- protocol/     Message contract between firmware and backend
`-- docs/         Architecture, hardware, setup guides, troubleshooting, milestone logs
```

## Quick start

These steps get the speech-to-text part running on your laptop with no ESP32 needed. Commands are shown for Windows (PowerShell) and Linux/macOS. You need Python 3.12 and Git installed.

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

If PowerShell refuses to run the activation script, see [docs/troubleshooting.md](docs/troubleshooting.md). Linux users also need PortAudio installed; see [docs/setup-backend.md](docs/setup-backend.md).

### 2. Get a Hugging Face token and accept the model terms

Speaker diarization uses gated pyannote models, so this step is required even though the models are free.

1. Create an account at <https://huggingface.co/join>.
2. Create a **Read** token at <https://huggingface.co/settings/tokens> and copy it (it starts with `hf_` and is shown only once).
3. While logged in, open each page below, fill in the short form, and accept the conditions:
   - <https://huggingface.co/pyannote/segmentation-3.0>
   - <https://huggingface.co/pyannote/speaker-diarization-3.1>
   - <https://huggingface.co/pyannote/speaker-diarization-community-1>

Skipping step 3 causes a `403 Forbidden` error when the models download. Full walkthrough: [docs/setup-backend.md](docs/setup-backend.md).

### 3. Create your `.env` file

Create `backend/.env` containing one line, with your own token:

```
HF_TOKEN=hf_your_token_here
```

Never commit this file. Windows users: avoid Notepad's default `.txt` extension and PowerShell's `echo >` redirection; the safe commands are in [docs/setup-backend.md](docs/setup-backend.md).

### 4. Run the local AI test

```
cd backend
python test_local_ai.py
```

This records 5 seconds from your microphone and prints the transcription. The first run downloads the models and takes a few minutes.

### 5. Firmware (when you have the board)

Set up PlatformIO and flash the ESP32-S3 by following [docs/setup-firmware.md](docs/setup-firmware.md).

## Documentation

| Document | What it covers |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Problem statement, system pipeline, design decisions |
| [docs/hardware.md](docs/hardware.md) | Parts list, pin assignments, optical system, design risks |
| [docs/setup-backend.md](docs/setup-backend.md) | Full backend setup: Python, Hugging Face, `.env`, running the server, firewall |
| [docs/setup-firmware.md](docs/setup-firmware.md) | PlatformIO setup, building, flashing, serial port issues |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Known issues and fixes for every part of the project |
| [protocol/README.md](protocol/README.md) | UDP packet layout and JSON reply format |

## Project status

| Area | Status |
|---|---|
| Repository structure | Done |
| PlatformIO project and OLED test | Done (verify on hardware) |
| Speech-to-text on laptop (faster-whisper) | Working with laptop microphone |
| Speaker diarization (pyannote.audio) | Loads once gated access is accepted; label still hardcoded |
| UDP server | Stub only (fixed reply, no inference) |
| Protocol specification | Draft |
| Microphone array capture, angle of arrival | Not started |
| Audio streaming from ESP32 | Not started |
| Haptics, camera, optics build, power | Not started |

## Conventions

- Commit messages follow Conventional Commits with a subsystem scope, for example `feat(backend): ...` or `feat(firmware): ...`.
- Never commit secrets or large artifacts: `.env`, `config.h`, virtual environments, model files, and recordings must stay in `.gitignore`.
- Changes to the message format update `protocol/`, the Python code, and the C++ code in the same commit.
- The team uses Windows and Linux, so add a `.gitattributes` file at the repository root containing `* text=auto` to keep line endings consistent, and build file paths in Python with `pathlib` rather than hardcoded separators.

## Limitations

The glasses depend on the laptop being on and reachable, because the AI models cannot run on an ESP32. Subtitles will lag speech by roughly one to a few seconds. The optical combiner suits controlled indoor lighting, not bright sunlight. More detail is in [docs/architecture.md](docs/architecture.md) and [docs/hardware.md](docs/hardware.md).

## Author

Meehir Prabhakar

## License

Not yet specified.
