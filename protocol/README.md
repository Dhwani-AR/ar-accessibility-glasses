# Protocol

The contract between the glasses firmware (`firmware/`) and the laptop server (`backend/`). The two programs share no code, so this document is the single source of truth. Any change to a packet layout or JSON field must update this file, the Python code, and the C++ code in the same commit.

**Status: implemented (v1).** Bidirectional UDP audio streaming, heartbeats, and JSON subtitle/alert replies are active on both sides.

## Transport

- UDP over the local network, glasses to laptop and back.
- Default server port: `5005` (`backend/server.py`, `firmware/src/main.cpp`).
- The glasses initiate (with Wi-Fi modem sleep disabled via `WiFi.setSleep(false)` to reduce packet jitter). The server binds `0.0.0.0:5005` with a 1 MiB receive buffer (`SO_RCVBUF`) and replies to the source address and port of each incoming packet.
- The glasses and laptop must be on the same network, and the laptop's firewall must allow inbound UDP on port `5005`. See [../docs/setup-backend.md](../docs/setup-backend.md).
- UDP is unreliable: packets can be lost, duplicated, or reordered. Every glasses-to-laptop packet carries a 32-bit sequence number (`seq`) so the server can track packet continuity.

## Glasses to laptop: binary packet

All glasses-to-laptop packets start with a 12-byte little-endian header.

### Header (12 bytes, little-endian)

| Offset | Size | Field | Meaning |
|---|---|---|---|
| 0 | 1 byte | `type` | Packet type: `0x01` = audio, `0x02` = heartbeat |
| 1 | 1 byte | `version` | Protocol version (`1`) |
| 2 | 1 byte | `channels` | Number of interleaved channels (`4` for audio packets) |
| 3 | 1 byte | `reserved` | Reserved, set to `0` |
| 4 | 4 bytes | `seq` | Packet sequence number, incrementing by 1 per packet, wraps at 2^32 |
| 8 | 4 bytes | `t_ms` | Sender uptime timestamp in milliseconds (`millis()` on ESP32) |

Python format string: `"<BBBBII"` (`HDR` in `backend/server.py`).
C++ struct: `struct __attribute__((packed)) AudioHeader` in `firmware/src/main.cpp`.

### Audio packet (`type = 0x01`)

Raw PCM audio, 16 kHz, 16-bit signed integers (`int16_t`, little-endian), with channels interleaved frame by frame. A frame is one sample from every channel. Each 32-bit INMP441 I2S word is right-shifted by 16 bits (`>> 16`) before packing.

The frame count is inferred from the payload length (`payload_bytes = len(pkt) - 12`, which must be non-zero and divisible by `2 * channels`). With `4` channels and `160` frames (10 ms of audio at 16 kHz):

- header: 12 bytes
- payload: `160 * 4 * 2 = 1280` bytes
- total packet: `1292` bytes

This stays under a typical 1500-byte network MTU, avoiding IP fragmentation. At 100 packets per second this uses roughly 1 Mbps over Wi-Fi.

### Heartbeat packet (`type = 0x02`)

Header-only packet (no audio payload required). When received, the server logs the sequence number and timestamp and replies immediately with a sync payload:

```json
{
  "text": "Sync OK #1",
  "speaker": "Speaker 1",
  "angle": 45,
  "haptic": true
}
```

### Channel order and array geometry

The 4-microphone array is configured in `backend/server.py` with `width = 0.14` m (140 mm left-to-right) and `depth = 0.07` m (70 mm front-to-rear):

| Channel | Position | ESP32-S3 I2S Bus | Data Pin |
|---|---|---|---|
| `0` | Front-left | `I2S_NUM_0` (master, slot 0) | GPIO 1 |
| `1` | Front-right | `I2S_NUM_0` (master, slot 1) | GPIO 1 |
| `2` | Rear-left | `I2S_NUM_1` (slave, slot 0) | GPIO 47 |
| `3` | Rear-right | `I2S_NUM_1` (slave, slot 1) | GPIO 47 |

Both buses share `SCK` (GPIO 41) and `WS` (GPIO 42). If `I2S_NUM_1` times out (15 ms), channels `2` and `3` are zero-filled for that packet.

### Server behavior

- Drop packets shorter than 12 bytes, with `version != 1`, unknown `type`, `channels != 4`, empty audio payload, or payload size not divisible by `2 * channels`.
- Track `seq` with wrap-safe 32-bit unsigned subtraction (`(seq - last_seq) & 0xFFFFFFFF`):
  - `delta == 0`: drop duplicate packet.
  - `delta >= 0x80000000`: sequence went backwards (device restart or reorder); log a warning and clear the ring buffer.
  - `delta > 1`: log lost packets and zero-fill up to `MAX_GAP_PACKETS = 50` packets of silence.
- Convert PCM samples to `float32` in `[-1.0, 1.0)` and transpose to shape `(channels, frames)` via `np.frombuffer(pkt, dtype="<i2", offset=12).reshape(-1, ch).T.astype(np.float32) / 32768.0`.
- Accumulate into a `2.4 s` (`38400`-frame) sliding window with a `1.6 s` (`25600`-frame) stride (0.8 s overlap), and queue chunks into a bounded worker queue (`maxsize = 4`), dropping chunks with a warning if inference falls behind.
- Before inference, `AudioPipeline` removes per-channel DC offset, skips chunks below `speech_rms = 0.012`, deduplicates up to 6 overlapping boundary words, and runs GCC-PHAT DoA, `faster-whisper` (`base.en`), VADER sentiment analysis, target-name detection, and `SpeechBrain` ECAPA-TDNN speaker identification (up to 6 speakers).

## Laptop to glasses: JSON reply

A single UTF-8 JSON object per UDP packet, with no extra framing.

### Speech reply

```json
{
  "text": "[Pos] Hey Meehir, ready for the demo?",
  "speaker": "Speaker 1",
  "angle": 15,
  "haptic": true,
  "sentiment": "Positive",
  "score": 0.3612
}
```

### Loud sound alert (no speech transcribed)

```json
{
  "text": "[Loud Sound Alert]",
  "speaker": "Alert",
  "angle": -120,
  "haptic": true,
  "sentiment": "Neutral",
  "score": 0.0
}
```

### Fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `text` | string | Yes | Subtitle text to display. Speech replies are prefixed with `[Pos]`, `[Neg]`, or `[Neu]` and truncated to 63 characters (`char text[64]` on firmware). |
| `speaker` | string | Yes | Speaker label (`"Speaker 1"`..`"Speaker 6"` or `"Alert"`), truncated to 15 characters (`char speaker[16]` on firmware). |
| `angle` | integer | Yes | Estimated direction of arrival in degrees (`-180` to `180`). |
| `haptic` | boolean | Yes | `true` if the glasses should trigger alert feedback. |
| `sentiment` | string | No | VADER sentiment label: `"Positive"` (`score >= 0.05`), `"Negative"` (`score <= -0.05`), or `"Neutral"`. Omitted on heartbeat replies; ignored by firmware. |
| `score` | number | No | VADER compound sentiment score in `[-1.0, 1.0]` (`0.0` for loud-sound alerts). Omitted on heartbeat replies; ignored by firmware. |

### Angle convention and alert rules

- `angle` spans `-180` to `180` degrees: `0` is straight ahead, positive is right, negative is left, and `±180` is behind the wearer.
- Firmware maps `angle` to directional HUD labels:
  - `-45` to `45`: `^ FRONT`
  - `46` to `135`: `RIGHT >>`
  - `-135` to `-46`: `<< LEFT`
  - `< -135` or `> 135`: `v REAR`
- The server owns the `haptic` decision and sets `haptic: true` when any of the following trigger:
  - Rear voice: `abs(angle) > 100`
  - Loud sound: `rms >= 0.18`
  - Name call: fuzzy word match against configured target names (`name_thresh = 0.78`)
- When `haptic` is `true`, firmware turns on the onboard RGB LED (GPIO 48, blue `(0, 0, 64)`) for `1500 ms` via a non-blocking queue timeout and pulses the haptic pin (GPIO 40) and status LED (GPIO 2) for `200 ms`.

### Size limit and ESP32 parsing

- Keep each reply well under 1400 bytes (and under 511 bytes for the firmware's `char packetBuffer[512]` UDP read buffer).
- Firmware parses replies with `ArduinoJson` (`JsonDocument`), silently dropping malformed packets and defaulting missing fields to `""`, `"Unknown"`, `0`, and `false`. Unknown fields (such as `sentiment` and `score`) are ignored.
- Firmware handles word-wrapping across 3 body lines (`y = 29, 44, 59`) on the 128x64 SSD1306 OLED (vertically mirrored for the 45-degree HUD combiner), with `speaker` and the direction tag on the top header row (`y = 12`).

## Versioning and changes

- The binary packet carries a `version` byte. Bump it when the header or payload layout changes incompatibly.
- Adding an optional JSON field is backward compatible: the firmware ignores fields it does not know.
- Removing or renaming a field, or changing its meaning, is a breaking change. Update both sides and this file in one commit and note the change in the commit message, for example `feat(protocol): add sequence number to audio header`.

## Test tools

- Backend alone: send recorded or synthetic 12-byte-header packets (or a `type = 0x02` heartbeat) to UDP port `5005` and inspect the JSON reply.
- Firmware alone: send canned JSON replies to the glasses' UDP socket on port `5005`.
- A quick reply check from any OS is in [../docs/setup-backend.md](../docs/setup-backend.md#6-run-the-udp-server).
