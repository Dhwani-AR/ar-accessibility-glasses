# Backend Setup

Full setup guide for the laptop AI server in `backend/`. Problems? See [troubleshooting.md](troubleshooting.md).

Commands are given for Windows (PowerShell) and Linux/macOS. Where a command is identical everywhere, it appears once.

## Prerequisites

- Windows 10/11, Linux, or macOS.
- Python 3.12 (`python --version` or `py -3.12 --version`).
- Git.
- Linux only (if using `sounddevice` for local audio tests): PortAudio (`sudo pacman -S portaudio` on Arch, `sudo apt install libportaudio2` on Debian/Ubuntu).

Always install Python packages inside a virtual environment, never system-wide.

## 1. Create the virtual environment and install dependencies

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

The first install downloads PyTorch, `faster-whisper`, `speechbrain`, and `vaderSentiment`. Both `faster-whisper` (`base.en`) and SpeechBrain (`speechbrain/spkrec-ecapa-voxceleb`) are open-access models and download automatically on first run without requiring a Hugging Face token.

### Activating the environment later

| System | Command (run in `backend/`) |
|---|---|
| Windows PowerShell | `.\aiml_venv\Scripts\Activate.ps1` |
| Windows Command Prompt | `.\aiml_venv\Scripts\activate.bat` |
| Linux / macOS | `source aiml_venv/bin/activate` |

On Windows PowerShell, if script execution is blocked, run once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

## 2. Step 1: Verify the 4-channel microphone array (`verify_mics.py`)

Before loading the full AI models, verify your ESP32-S3 soldering and microphone channel order using the lightweight RMS meter script:

```bash
cd backend
# (activate aiml_venv)
python verify_mics.py
```

Power on the ESP32-S3 glasses and lightly tap each microphone with your fingernail to confirm the channel mapping:
- **Front-Left (`Mic 1`):** `Ch0` bar spikes (`I2S0`, `GPIO 1`, `L/R = GND`)
- **Front-Right (`Mic 2`):** `Ch1` bar spikes (`I2S0`, `GPIO 1`, `L/R = +3.3V`)
- **Rear-Left (`Mic 3`):** `Ch2` bar spikes (`I2S1`, `GPIO 47`, `L/R = GND`)
- **Rear-Right (`Mic 4`):** `Ch3` bar spikes (`I2S1`, `GPIO 47`, `L/R = +3.3V`)

Stop `verify_mics.py` with `Ctrl+C` before starting `server.py` so UDP port `5005` is freed.

## 3. Step 2: Run the AI UDP server (`server.py`)

```bash
cd backend
# (activate aiml_venv)
python server.py
```

What `server.py` and `pipeline.py` do at runtime:
1. **Model initialization:** Loads `faster-whisper` (`base.en`, `float16` on CUDA or `int8` on CPU), SpeechBrain `EncoderClassifier` (`speechbrain/spkrec-ecapa-voxceleb`), and VADER `SentimentIntensityAnalyzer` inside a background worker thread.
2. **UDP ingestion:** Listens on `0.0.0.0:5005` with a 1 MiB socket receive buffer (`SO_RCVBUF`), validates the 12-byte `<BBBBII` packet header, handles sequence wrap-around/reordering, and zero-fills packet gaps up to 50 packets.
3. **Sliding-window chunking:** Accumulates a **2.4-second window** (`38,400` samples per channel) and slides forward by a **1.6-second stride** (`25,600` samples), providing an 800 ms overlap so boundary words are not truncated.
4. **Inference & reply:** Removes per-channel DC offset, computes 360-degree azimuth via 2D GCC-PHAT, transcribes speech with prefix overlap deduplication, scores sentiment with VADER (`[Pos]`/`[Neg]`/`[Neu]`), checks for target name calls, tracks speaker identity via cosine similarity, logs structured output (`speaker`, `angle`, `sentiment`, `haptic`, `text`), and sends `{text, speaker, angle, haptic, sentiment, score}` JSON replies back to the glasses.

To test the UDP server handshake without the ESP32, run a simulated heartbeat packet (`ptype = 0x02`) from a second terminal:

```bash
python -c "import socket, struct; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(3); s.sendto(struct.pack('<BBBBII', 2, 1, 4, 0, 1, 100), ('127.0.0.1', 5005)); print(s.recvfrom(4096)[0].decode())"
```

You should immediately receive:
`{"text": "Sync OK #1", "speaker": "Speaker 1", "angle": 45, "haptic": true}`

### Firewall

The ESP32 can only reach the server if the laptop's firewall allows inbound UDP on port `5005`:
- **Windows:** Allow Python on **Private networks** in Windows Defender Firewall, or add an inbound rule for UDP port `5005`.
- **Linux:** If `ufw` is active, run `sudo ufw allow 5005/udp`.

### Finding the laptop's IP address

Set this address as `SERVER_IP` in `firmware/include/credentials.h`:
- **Windows:** `ipconfig`
- **Linux:** `ip addr`
- **macOS:** `ipconfig getifaddr en0`

Use a 2.4 GHz mobile hotspot or laptop hotspot rather than campus Wi-Fi, which often isolates client devices from one another.

## Dependency notes

- Versions are pinned in `backend/requirements.txt`, including `av==16.1.0`, `faster-whisper==1.2.1`, `speechbrain==1.1.2`, `torch==2.14.1`, `torchaudio==2.11.0`, and `vaderSentiment==3.3.2`.
- Do not upgrade `av` to `>=17` without testing, as it breaks `faster-whisper` 1.2.1 file decoding.
