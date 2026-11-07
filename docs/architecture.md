# Architecture

This document explains what the system does, how its parts fit together, and why the main design choices were made. For parts, pins, and optics see [hardware.md](hardware.md). For the message format see [../protocol/README.md](../protocol/README.md).

## Problem statement

Deaf and Hard-of-Hearing (DHH) people struggle in multi-speaker social and professional settings, a challenge known as the "cocktail party problem". Smartphone speech-to-text apps exist, but they make the user look down at a handheld screen. That costs eye contact, situational awareness, and any sense of where a voice is coming from.

The goal is a lightweight AR assistive glasses prototype, built under a strict INR 7,000 budget, that:

- captures 4-channel spatial audio with a rectangular microphone array,
- transcribes speech in near real time using a sliding overlapping window,
- determines the 360-degree direction of the active speaker,
- identifies and tracks speakers across utterances without cloud tokens,
- projects word-wrapped subtitles and directional indicators into the wearer's peripheral view, and
- gives a haptic cue for rear-approaching voices (`|angle| > 100°`) or loud environmental alerts.

## System overview

```text
[Wearer scene]
   |
   +--> [4x INMP441 mic array] --(Dual I2S DMA)--> [ESP32-S3] --(UDP 5005 / Wi-Fi)--+
   |                                                                                |
   +--> [OV3660 camera] ---------(24-pin DVP)----> [ESP32-S3]                       |
                                                                                    v
   +--------------------------------------------------------------------------------+
   |  LAPTOP SERVER (backend/server.py + backend/pipeline.py)
   |  Phase 1: ingest 1,292-byte UDP packets (12B header + 160x4 int16 PCM frames)
   |           into a ring buffer with sequence tracking and gap zero-filling
   |  Phase 2: slice 2.4 s sliding windows every 1.6 s stride (0.8 s overlap)
   |           and dispatch to a background inference worker thread
   |  Phase 3: RMS acoustic gating (skip silence, flag loud transients >= 0.18)
   |  Phase 4: compute 360-degree azimuth via 2D GCC-PHAT (Left/Right & Front/Rear)
   |  Phase 5: transcribe with faster-whisper (base.en) + strip overlapping prefix words
   |  Phase 6: identify speaker via SpeechBrain ECAPA-TDNN cosine centroid cache
   |  Phase 7: pack {text, speaker, angle, haptic} as JSON reply
   +---------------------------------------+----------------------------------------+
                                           |
                                    (UDP JSON reply)
                                           v
   [ESP32-S3 firmware (firmware/src/main.cpp)]
      - Core 0 (NetTask): read dual I2S DMA, send UDP audio, parse JSON to FreeRTOS queue
      - Core 1 (DispTask): draw split HUD header (speaker + << LEFT / ^ FRONT / RIGHT >> / v REAR)
                           and 3-line pixel-wrapped subtitles on SSD1306 OLED (GPIO 14/21)
      - Haptics: stream 150 ms I2S square-wave burst to MAX98357A (GPIO 38) + status LED (GPIO 2)
              |
              v
   [Optical stack] --> virtual subtitles in the wearer's field of view
```

## Components

**Glasses (`firmware/`, C++ on ESP32-S3).** A dual-core FreeRTOS thin client. Core 0 (`NetTask`) drives `I2S_NUM_0` (master RX/TX) and `I2S_NUM_1` (slave RX) with shared clocks routed via the internal GPIO matrix, packs 160-frame 4-channel 16-bit PCM packets with a 12-byte `AudioHeader`, streams them over UDP port 5005, and pushes incoming JSON replies to a non-blocking queue. Core 1 (`DispTask`) renders the directional header bar and 3-line word-wrapped text on the SSD1306 OLED and triggers the MAX98357A haptic amplifier.

**Laptop server (`backend/`, Python).** `server.py` runs a non-blocking UDP receive loop (1 MB `SO_RCVBUF`) that validates packet headers, zero-fills dropped packet gaps (capped at 50 packets), accumulates a 2.4-second sliding window with a 1.6-second stride, and dispatches chunks to a worker thread running `AudioPipeline` (`pipeline.py`).

**Optics.** A Pepper's Ghost combiner reflects the downward-facing OLED into the wearer's eye. Details are in [hardware.md](hardware.md).

## Key design decisions

### Offload AI to a laptop

Models such as Whisper and ECAPA-TDNN cannot run on an ESP32-S3. Splitting the system into a thin client and a laptop server keeps the wearable small, cheap, and low-power, and lets the AI side be developed and tested independently.

### Two programs, one contract

The firmware and the backend agree strictly on the binary uplink header (`<BBBBII`: `type`, `version`, `channels`, `reserved`, `seq`, `t_ms` followed by interleaved `<i2` PCM) and the downlink JSON schema (`text`, `speaker`, `angle`, `haptic`) documented in [protocol/](../protocol/README.md).

### Sliding window with prefix deduplication

Hard non-overlapping 2.0-second cuts split words spoken across chunk boundaries. The server instead extracts a 2.4-second window (`38,400` frames) every 1.6 seconds (`25,600` frames), maintaining an 800 ms context overlap. `AudioPipeline.dedup_overlap()` compares up to 6 trailing words from the previous chunk against the leading words of the new chunk to strip repeated boundary words before transmitting to the OLED.

### 360-degree Direction of Arrival (2D GCC-PHAT)

Using a 2D rectangular array (`width = 0.14 m`, `depth = 0.07 m`), `AudioPipeline.estimate_angle()` computes Generalized Cross-Correlation with Phase Transform (GCC-PHAT) across the front/rear lateral pairs (`Ch 0 vs 1`, `Ch 2 vs 3`) and left/right longitudinal pairs (`Ch 2 vs 0`, `Ch 3 vs 1`), combining the normalized delay vectors via `atan2(vy, vx)` to output a full `-180°` to `+180°` azimuth without front-to-back ambiguity.

### Online speaker identification (ECAPA-TDNN)

Instead of offline `pyannote.audio` diarization (which is too slow for sub-second turn-around and requires gated Hugging Face tokens), `AudioPipeline.identify_speaker()` extracts 192-dimensional speaker embeddings using SpeechBrain's `spkrec-ecapa-voxceleb` model and matches them against a rolling cosine-similarity centroid cache (`sim_thresh = 0.68`, up to 6 active speakers) updated via exponential moving average.

## Development status

1. **Firmware (`firmware/src/main.cpp`):** Complete — Dual-bus 4-channel I2S DMA capture, UDP packet streaming, OLED remapping (`GPIO 14/21`), 3-line word wrapping, directional HUD tags, and MAX98357A I2S TX haptic bursts (`GPIO 38`).
2. **Backend (`backend/server.py`, `backend/pipeline.py`):** Complete — Threaded UDP ingestion, sequence gap handling, 2.4 s / 1.6 s sliding window, 2D GCC-PHAT DoA, `faster-whisper` ASR with overlap deduplication, and `SpeechBrain` speaker tracking.
3. **Hardware verification (`backend/verify_mics.py`):** Complete — Real-time 4-channel RMS terminal meter for verifying physical microphone soldering and `L/R` channel order.
4. **Next steps:** Physical microphone tap calibration, array dimension tuning (`width`/`depth`), and optional environmental sound event classification (YAMNet) for non-speech loud alerts.
