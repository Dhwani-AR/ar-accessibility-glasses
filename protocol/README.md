# Protocol

The contract between the glasses firmware (`firmware/`) and the laptop server (`backend/`). The two programs share no code, so this document is the single source of truth. Any change to a packet layout or JSON field must update this file, the Python code, and the C++ code in the same commit.

**Status: draft.** Only the JSON reply is implemented today (as a fixed test payload in `backend/server.py`). The audio packet layout below is a proposal and has not been implemented on either side. Items marked PROPOSED or TBD are open for decision.

## Transport

- UDP over the local network, glasses to laptop and back.
- Default server port: 5005 (`backend/server.py`).
- The glasses initiate. The server replies to the source address and port of each incoming packet.
- The glasses and laptop must be on the same network, and the laptop's firewall must allow inbound UDP on the server port. See [../docs/setup-backend.md](../docs/setup-backend.md).
- UDP is unreliable: packets can be lost, duplicated, or reordered. The audio packet carries a sequence number so the server can detect this.

## Glasses to laptop: audio packet (PROPOSED)

Raw PCM audio, 16 kHz, 16-bit signed integers, little-endian (both the ESP32-S3 and typical laptops are little-endian), with channels interleaved frame by frame. A frame is one sample from every channel.

### Header (8 bytes, little-endian)

| Offset | Size | Field | Meaning |
|---|---|---|---|
| 0 | 1 byte | `version` | Protocol version, starting at 1 |
| 1 | 1 byte | `channels` | Number of interleaved channels (4 for the full array) |
| 2 | 2 bytes | `frames` | Number of frames in this packet |
| 4 | 4 bytes | `seq` | Packet sequence number, incrementing by 1 per packet, wraps at 2^32 |

Python format string: `"<BBHI"`.

### Payload

`frames * channels * 2` bytes of interleaved int16 samples. For example, with 4 channels and 160 frames (10 ms of audio at 16 kHz):

- payload: 160 * 4 * 2 = 1280 bytes
- total packet: 1288 bytes

This stays under a typical 1500-byte network MTU, which avoids IP fragmentation. About 100 packets per second give roughly 1 Mbps for four channels, which Wi-Fi handles easily.

### Channel order (TBD)

The mapping of channel index to physical microphone must be fixed once the microphone array is wired, and recorded here with the array geometry (microphone positions in millimeters relative to the frame center).

### Server behavior (PROPOSED)

- Parse the header, check `version`, and drop packets with unexpected values.
- Use `seq` to detect gaps. Fill short gaps with silence or discard the affected chunk, and log the loss.
- Accumulate packets into chunks of a few seconds before running transcription. Packet size and chunk size are separate settings.
- Convert samples to float32 in the range -1.0 to 1.0 with `np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0`, then reshape to `(frames, channels)`.

## Laptop to glasses: JSON reply

A single UTF-8 JSON object per UDP packet, no framing beyond the packet itself. The current test payload:

```json
{
  "text": "Network Sync OK",
  "speaker": "Speaker 1",
  "angle": 45,
  "haptic": true
}
```

| Field | Type | Meaning |
|---|---|---|
| `text` | string | Subtitle text to display |
| `speaker` | string | Speaker label |
| `angle` | number | Estimated direction of the speaker, in degrees |
| `haptic` | boolean | `true` if the haptic motor should fire (off-axis speaker) |

### Angle convention (TBD)

Decide and record one convention before the firmware uses `angle`. Suggested: 0 degrees is straight ahead of the wearer, positive values are to the wearer's right, range -180 to 180. The haptic decision (what counts as off-axis, and which side vibrates) must be defined here as well. If the server decides `haptic`, the firmware only has to obey it.

### Size limit

Keep each reply well under 1400 bytes so it fits in one UDP packet. Long transcriptions must be split into several replies, and the OLED is only 128x64 pixels, so the firmware will show only a few short lines at a time. Whether the server or the firmware handles line wrapping is TBD.

### Parsing on the ESP32

The ArduinoJson library is the usual choice for parsing this on the ESP32. Add it to `lib_deps` in `firmware/platformio.ini` when parsing is implemented. Use a bounded document size and handle malformed or missing fields without crashing.

## Versioning and changes

- The audio packet carries a `version` byte. Bump it when the layout changes incompatibly.
- Adding an optional JSON field is backward compatible: the firmware should ignore fields it does not know.
- Removing or renaming a field, or changing its meaning, is a breaking change. Update both sides in one commit and note the change in the commit message, for example `feat(protocol): add sequence number to audio header`.

## Test tools

- Backend alone: a script that sends recorded or synthetic packets to the server and prints the reply.
- Firmware alone: a script that sends canned JSON replies to the glasses.
- A quick reply check from any OS is in [../docs/setup-backend.md](../docs/setup-backend.md#6-run-the-udp-server).
