# Backend Setup

Full setup guide for the laptop server in `backend/`. A condensed version is in the root [README](../README.md). Problems? See [troubleshooting.md](troubleshooting.md).

Commands are given for Windows (PowerShell) and Linux/macOS. Where a command is identical everywhere, it appears once.

## Prerequisites

- Windows 10/11, Linux, or macOS.
- Python 3.12, the version the project is developed with. On Windows, install it from <https://www.python.org/downloads/> and tick "Add python.exe to PATH" in the installer. Check with `python --version`, or `py -3.12 --version` on Windows.
- Git. On Windows: <https://git-scm.com/download/win>.
- A working microphone. On Windows, allow microphone access for desktop apps under Settings > Privacy & security > Microphone.
- A free Hugging Face account (see below).
- Linux only: PortAudio, which `sounddevice` needs for microphone capture. Windows and macOS packages bundle it.
  - Arch: `sudo pacman -S portaudio`
  - Debian/Ubuntu: `sudo apt install libportaudio2`

Always install Python packages inside a virtual environment, never system-wide. Some systems (recent Linux distributions in particular) block global `pip install` on purpose, and even where it is allowed it can cause version clashes.

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

If `py -3.12` or `python3.12` is not found, use plain `python` as long as `python --version` reports 3.12. When the environment is active your prompt shows `(aiml_venv)`.

The first install downloads PyTorch and related packages, so it is large and slow.

### Activating the environment later

| System | Command (run in `backend/`) |
|---|---|
| Windows PowerShell | `.\aiml_venv\Scripts\Activate.ps1` |
| Windows Command Prompt | `aiml_venv\Scripts\activate.bat` |
| Linux / macOS | `source aiml_venv/bin/activate` |

On Windows PowerShell the first activation may fail with "running scripts is disabled on this system". Fix it once for your user with:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Or use Command Prompt, which has no such restriction.

## 2. Create a Hugging Face access token

Speaker diarization uses pyannote.audio models hosted on Hugging Face. They are gated: you need an account, a token, and explicit approval for each model.

1. Create a free account at <https://huggingface.co/join>, or log in.
2. Open <https://huggingface.co/settings/tokens>.
3. Click **Create new token**.
4. Choose the **Read** token type. Read access is all this project needs, and it limits the damage if the token ever leaks.
5. Give it a recognizable name such as `ar-glasses-read` and create it.
6. Copy the token (it starts with `hf_`) immediately. Hugging Face shows it only once. If you lose it, create a new one.

## 3. Accept the model terms

A valid token is not enough. For each gated model, open its page while logged in, read the conditions, fill in the short form, and accept. Until you do, downloads fail with `403 Forbidden` or "Cannot access gated repo".

| Model | Link |
|---|---|
| Segmentation | <https://huggingface.co/pyannote/segmentation-3.0> |
| Speaker diarization 3.1 | <https://huggingface.co/pyannote/speaker-diarization-3.1> |
| Speaker diarization community-1 | <https://huggingface.co/pyannote/speaker-diarization-community-1> |

On each page:

1. Log in to Hugging Face.
2. Read the user conditions at the top of the model card.
3. Fill in the requested fields (typically name, organization or university, and intended use, for example "academic capstone project: assistive captioning glasses") and tick the agreement box.
4. Submit. Access is usually granted immediately. If the page still shows the form afterwards, wait a minute and refresh.

If a later run reports a 403 for a different pyannote repository, the error message includes its URL. Open it and accept the conditions the same way.

## 4. Create the `.env` file

The backend reads the token from an environment file so it never appears in source code.

Create `backend/.env` with a single line (no quotes, no spaces around the equals sign), using your own token:

```
HF_TOKEN=hf_your_token_here
```

Windows (PowerShell), from `backend/`:

```powershell
Set-Content -Path .env -Value "HF_TOKEN=hf_your_token_here" -Encoding ascii
```

Linux / macOS, from `backend/`:

```bash
echo "HF_TOKEN=hf_your_token_here" > .env
```

Windows pitfalls:

- Do not use `echo "..." > .env` in Windows PowerShell 5.1. It writes UTF-16 and the token will not be read correctly.
- If you create the file in Notepad, choose **Save as type: All files** and name it exactly `.env`. Otherwise Notepad saves `.env.txt`.
- File Explorer hides known extensions by default, so `.env.txt` looks like `.env`. Run `dir` in the terminal to see the real name.

Rules for the `.env` file:

- It must live in `backend/`, next to `test_local_ai.py`, and you should run the scripts from that directory.
- Never commit it. Make sure `.env` is in the root `.gitignore`, and confirm with `git status` that it does not appear as an untracked file before committing.
- If you commit the token by accident, revoke it at <https://huggingface.co/settings/tokens> and create a new one. Deleting it in a later commit does not remove it from Git history.
- Optionally commit a `backend/.env.example` containing `HF_TOKEN=` so others know which variable to set.

If `HF_TOKEN` is missing, the engine logs a warning and runs with diarization disabled. Speech-to-text still works.

## 5. Run the local AI test

This needs no ESP32. It records 5 seconds from your microphone and runs the AI engine.

```
cd backend
(activate the venv)
python test_local_ai.py
```

The first run downloads the Whisper `base.en` model and the pyannote models, which can take several minutes. A successful run prints the transcribed text and a speaker label. The speaker label is currently hardcoded to "Speaker 1".

## 6. Run the UDP server

```
cd backend
(activate the venv)
python server.py
```

The server listens on UDP port 5005 on all interfaces. For now it replies to every packet with a fixed test payload instead of running inference.

To test it, open a second terminal, activate the same venv, and run this one-liner (works on every OS, no `nc` needed):

```
python -c "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(3); s.sendto(b'ping', ('127.0.0.1', 5005)); print(s.recvfrom(4096)[0].decode())"
```

You should see the JSON reply. If it times out, the server is not running or the port is blocked.

### Firewall

The ESP32 can only reach the server if the laptop's firewall allows it.

- Windows: the first time `server.py` runs, Windows Defender Firewall prompts for Python. Allow access on **Private networks**. If you dismissed the prompt, open Windows Security > Firewall & network protection > Allow an app through firewall, and enable Python for Private networks, or add an inbound UDP rule for port 5005. Without this the localhost test passes but packets from the glasses are silently dropped.
- Linux: if you use ufw, run `sudo ufw allow 5005/udp`.

### Finding the laptop's IP address

The ESP32 firmware needs this address.

- Windows: run `ipconfig` and read the IPv4 address of your Wi-Fi adapter.
- Linux: run `ip addr`.
- macOS: run `ipconfig getifaddr en0`.

The glasses and laptop must be on the same network. A phone hotspot or the laptop's own hotspot is safer for demos than campus Wi-Fi, which often blocks device-to-device traffic.

## Dependency notes

- Versions are pinned exactly in `backend/requirements.txt`, including `av==16.1.0`. Do not upgrade `av` without testing, because newer releases break faster-whisper 1.2.1. See [troubleshooting.md](troubleshooting.md).
- pyannote.audio 4.x takes the Hugging Face token as `token=`, not `use_auth_token=`.
- When adding a new dependency, pin its version and add it to `requirements.txt`.
