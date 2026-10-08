# Architecture

This document explains what the system does, how its parts fit together, and why the main design choices were made. For parts, pins, and optics see [hardware.md](hardware.md). For the message format see [../protocol/README.md](../protocol/README.md).

## Problem statement

Deaf and Hard-of-Hearing (DHH) people struggle in multi-speaker social and professional settings, a challenge known as the "cocktail party problem". Smartphone speech-to-text apps exist, but they make the user look down at a handheld screen. That costs eye contact, situational awareness, and any sense of where a voice is coming from.

The goal is a lightweight AR assistive glasses prototype, built under a strict INR 7,000 budget, that:

- captures spatial audio with a microphone array,
- transcribes speech in near real time,
- determines the direction of the active speaker,
- projects subtitles into the wearer's peripheral view, and
- gives a haptic cue toward off-axis speakers outside the wearer's direct field of view.

## System overview

```
[Wearer scene]
   |
   +--> [4x INMP441 mic array] --(I2S DMA)--> [ESP32-S3] --(UDP / Wi-Fi)--+
   |                                                                      |
   +--> [OV2640 camera] --------(DVP bus)---> [ESP32-S3]                  |
                                                                          v
   +----------------------------------------------------------------------+
   |  LAPTOP SERVER (backend/)
   |  Phase 1: ingest PCM buffers over a UDP socket
   |  Phase 2: compute angle of arrival (TDoA / cross-correlation)
   |  Phase 3: transcribe audio with faster-whisper
   |  Phase 4: identify the active speaker with pyannote.audio
   |  Phase 5: pack {text, speaker, angle, haptic} as JSON
   +---------------------------------+------------------------------------+
                                     |
                              (UDP reply)
                                     v
   [ESP32-S3 firmware]
      - parse the JSON payload
      - trigger the haptic motor if the speaker is off-axis
      - render text on the SSD1306 OLED with U8g2 (horizontal flip enabled)
              |
              v
   [Optical stack] --> virtual subtitles in the wearer's field of view
```

## Components

**Glasses (firmware/, C++ on ESP32-S3).** A thin client. It reads the microphones over I2S with DMA, sends the audio over UDP, receives a small JSON reply, drives the haptic motor, and draws text on the OLED. It runs no AI models.

**Laptop server (backend/, Python).** Listens on a UDP port, accumulates audio into chunks, estimates the direction of the speaker, transcribes with faster-whisper, labels speakers, and sends a short JSON reply back to the glasses.

**Optics.** A Pepper's Ghost combiner reflects the downward-facing OLED into the wearer's eye. Details are in [hardware.md](hardware.md).

## Key design decisions

### Offload AI to a laptop

Models such as Whisper cannot run on an ESP32-S3. Splitting the system into a thin client and a laptop server keeps the wearable small, cheap, and low-power, and lets the AI side be developed and tested without any hardware. The cost is that the glasses are useless without the laptop on the same network. This is accepted as a design choice and listed under limitations. A possible future change is to run the server on a phone.

### Two programs, one contract

The firmware and the backend are separate programs that share no code. They agree only on the network message format. That agreement is the contract in [protocol/](../protocol/README.md). Either side can be developed against a fake counterpart: the backend can be tested with a script that sends recorded audio, and the firmware with a script that sends canned JSON.

### Monorepo

The project spans embedded firmware (C++), AI backend (Python), and physical design (CAD, optics). Both a monorepo and several independent repositories were considered.

The monorepo was chosen because:

- A change to the packet layout or JSON schema can be made in the Python server and the C++ firmware in a single commit, so versions never mismatch.
- Bugs that cross boundaries (for example end-to-end audio latency) live in one issue tracker.
- Architecture notes, schematics, and milestone logs are versioned together with the code.
- A small team avoids juggling several remotes and branches.

The drawbacks are mixed tooling in one root (Python virtual environments, PlatformIO builds, CAD files), larger clones if binary assets are committed, and a shared commit history. These are managed with a thorough `.gitignore`, Git LFS if STL or Fritzing files grow large, and Conventional Commit scopes such as `feat(backend):` and `feat(firmware):` to keep the log readable. Path-filtered CI jobs can recover most of the independence a multi-repo setup would give.

For comparison, a multi-repo layout (firmware, backend, hardware, docs as separate repositories) gives stricter separation of concerns, independent CI pipelines, and easier access control for outside collaborators. Its downsides are version synchronization every time the contract changes, repeated push and pull across remotes, and fragmented issue tracking. Those costs outweigh the benefits for a capstone team that owns every part.

### Direction of arrival

Direction is estimated from the time difference of arrival (TDoA) between microphones, using cross-correlation. At 16 kHz, one sample corresponds to about 2.1 cm of path difference, and the microphone spacing on a glasses frame is small, so only a handful of distinct delay values fit across the field. Sub-sample interpolation (for example GCC-PHAT with parabolic peak fitting) and a microphone layout that is not a single straight line will be needed. These points are tracked in [hardware.md](hardware.md).

### Speaker labeling

pyannote.audio is the planned diarization tool, but it is largely an offline model that works on audio chunks. Because the system already estimates the angle of each speaker, grouping speech by direction may give a lighter and lower-latency way to label speakers. The final choice depends on testing. Currently the engine returns a fixed label, "Speaker 1".

### Camera

The OV2640 camera is in the hardware design, but nothing downstream consumes its output yet. One possible use is face detection to match a detected face to a sound direction. If no use is confirmed, it can be dropped to save power and GPIO pins.

## Latency

Speech recognition works on chunks of audio, so subtitles lag speech by roughly one to a few seconds. Shorter chunks reduce lag but lower accuracy and increase compute load. Chunk size is a tuning parameter to test, not a fixed value.

## Limitations

- The glasses depend on the laptop server being on and reachable.
- Subtitle delay of one to a few seconds.
- Optical contrast suits controlled indoor environments, not bright outdoor use.
- Battery life with Wi-Fi, microphones, and camera active will be limited on a 1000 mAh cell.

## Development order

Each half can be built and tested alone:

1. Backend only: record from the laptop microphone, run Whisper, print text (working now).
2. Network: ESP32 sends test audio, laptop replies with canned JSON.
3. Display and haptics: render replies on the OLED and drive the motor.
4. Microphone array: capture multi-channel audio and compute angle of arrival.
5. Integration and tuning.
