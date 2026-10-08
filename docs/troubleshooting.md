# Troubleshooting

Known issues and fixes, grouped by part of the project. If you hit a new problem and solve it, add it here so the next person does not lose time on it.

## Backend (Python)

### `TypeError: open() got an unexpected keyword argument 'metadata_errors'`

This comes from faster-whisper's audio decoding. A newer release of `av` (PyAV) than faster-whisper 1.2.1 supports got installed. faster-whisper declares only a minimum `av` version with no upper limit (to the best of our knowledge), so pip installs the newest one, and `pip check` stays clean because the installed version technically satisfies the constraint.

The repository pins `av==16.1.0` in `backend/requirements.txt` to avoid it. If you see the error, run:

```
pip install "av<17"
```

A more robust approach for the real pipeline is to pass float32 NumPy arrays to `transcribe()` instead of file paths. Then faster-whisper skips file decoding and never calls `av.open`.

### `Pipeline.from_pretrained() got an unexpected keyword argument 'use_auth_token'`

pyannote.audio 4.x renamed this argument to `token`. The code already uses `token=`. If you see this error, the code was changed back or an old example was pasted in.

### `403 Client Error` or "Cannot access gated repo" when loading pyannote

A pyannote model's terms have not been accepted on your Hugging Face account. A valid token is not enough. Follow [setup-backend.md](setup-backend.md#3-accept-the-model-terms) and accept the conditions for every model listed there. If the error names a different repository, open its URL and accept it as well. Also confirm the token in `.env` has read access.

### "No Hugging Face token provided. Diarization disabled."

The backend did not find `HF_TOKEN`. Check that:

- the file is named exactly `.env` (not `.env.txt`; run `dir` or `ls -a` to see the real name),
- it is in `backend/`, and you run the scripts from that folder,
- it contains `HF_TOKEN=hf_...` with no quotes and no spaces around `=`, and
- on Windows it was not written as UTF-16 (see [setup-backend.md](setup-backend.md#4-create-the-env-file)).

### Diarization always says "Speaker 1"

`AIEngine.process_audio` returns a hardcoded speaker label for now. A 5-second single-microphone clip is also a poor test for diarization, which needs several speakers and more audio. Because the system will also estimate angle of arrival, labeling speakers by direction may turn out simpler and faster than pyannote.

### `sounddevice` cannot find an input device, or `PortAudio library not found`

- Linux: install PortAudio (`sudo pacman -S portaudio` on Arch, `sudo apt install libportaudio2` on Debian/Ubuntu).
- Windows: allow microphone access for desktop apps under Settings > Privacy & security > Microphone, and check that the correct input device is the default in Sound settings.
- All systems: run `python -c "import sounddevice as sd; print(sd.query_devices())"` to list devices.

### PowerShell: "running scripts is disabled on this system"

Windows blocks the venv activation script by default. Run this once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Or use Command Prompt and `activate.bat` instead.

### `python`, `py`, or `pip` not recognized (Windows)

Python was installed without "Add python.exe to PATH". Re-run the installer, choose Modify, and enable it, or use the `py` launcher (`py -3.12 ...`). After activating the venv, `pip` and `python` refer to the venv's copies.

### The first run is very slow or looks stuck

The first run downloads the Whisper and pyannote models (hundreds of megabytes). Later runs use the cache. A slow connection makes this take several minutes.

## Network

### The localhost test works but the ESP32 gets no reply

Almost always a firewall or network issue:

- Windows: allow Python through Windows Defender Firewall on **Private networks**, or add an inbound UDP rule for port 5005. See [setup-backend.md](setup-backend.md#firewall).
- Linux: `sudo ufw allow 5005/udp` if ufw is active.
- Confirm the ESP32 and the laptop are on the same network and that the firmware has the laptop's current IP. The laptop's IP can change between sessions, so a hotspot with a fixed address helps.
- Campus and public Wi-Fi often isolate devices from each other. Use a phone hotspot or the laptop's own hotspot.
- If Windows classifies your network as Public, it may block incoming traffic regardless. Set the network profile to Private in Settings > Network & internet.

### Server shows packets but the buffer looks wrong

`server.py` currently reads 4096 bytes per packet, which is about 128 ms of mono 16 kHz audio. Transcription needs audio accumulated into chunks of a few seconds, plus a packet header with sequence numbers. See [../protocol/README.md](../protocol/README.md).

## Firmware (ESP32-S3)

### `No module named pip` when PlatformIO installs its toolchain (Linux)

PlatformIO's installer calls the system Python and needs pip available there. Install pip through your package manager (`sudo pacman -S python-pip` on Arch, `sudo apt install python3-pip` on Debian/Ubuntu). On systems that protect the system Python, this does not permit global installs. If a half-finished install is left behind, delete the broken package folder (for example `~/.platformio/packages/tool-esptoolpy`) and run `pio pkg install` again.

### Upload fails: cannot connect or permission denied

- Windows: check Device Manager for a COM port. If missing, try another data cable and install the CP210x or CH340 driver that matches your board's USB chip.
- Linux: add your user to the `uucp` (Arch) or `dialout` (Debian/Ubuntu) group, then log out and back in.
- All systems: hold BOOT, tap RESET, release BOOT to enter download mode, then retry the upload. Close any serial monitor that is holding the port.

### PSRAM size prints as 0, or the board resets in a loop

The `platformio.ini` memory settings are missing or wrong. Add `board_build.arduino.memory_type = qio_opi`, the 16 MB flash and partition settings, and `-DBOARD_HAS_PSRAM`, as described in [setup-firmware.md](setup-firmware.md#3-enable-the-boards-flash-and-psram). Also confirm no code uses GPIO 35, 36, or 37.

### OLED stays blank

- Check wiring: SDA to GPIO 8, SCL to GPIO 9 (see [hardware.md](hardware.md)), plus power and ground.
- Confirm the pins in `main.cpp` match the wiring, and that the display's I2C address is the one U8g2 expects.
- Check whether GPIO 8 and 9 conflict with the camera pins on your board revision.

## Git and repository

### A secret was committed (`.env` or `config.h`)

Revoke the token immediately (<https://huggingface.co/settings/tokens>) and create a new one. Removing the file in a later commit does not remove it from history. Then add the file to `.gitignore`.

### `.env` shows up in `git status`

It is not covered by `.gitignore`. Add `.env` to the root `.gitignore`. If it was already committed, run `git rm --cached backend/.env` and commit, then rotate the token.

### Line-ending warnings or whole-file diffs between Windows and Linux machines

Add a `.gitattributes` file at the repository root containing `* text=auto`, so Git normalizes line endings between systems.

### Virtual environment folders appear in `git status`

Add `aiml_venv/`, `pio_venv/`, `.pio/`, and `__pycache__/` to the root `.gitignore`.
