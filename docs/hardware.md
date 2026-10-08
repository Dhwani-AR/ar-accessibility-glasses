# Hardware

Parts list, pin assignments, optical design, and known design risks for the glasses. See [architecture.md](architecture.md) for how the hardware fits into the whole system.

## Bill of materials (summary)

| Subsystem | Part | Notes |
|---|---|---|
| Controller | Freenove ESP32-S3-WROOM-1, N16R8 | 16 MB flash, 8 MB Octal PSRAM, dual-core Xtensa LX7 at 240 MHz. Handles peripheral timing, DMA, Wi-Fi, and display rendering |
| Microphones | 4x INMP441 I2S MEMS | Omnidirectional. Share the bit clock (BCLK) and word select (WS) lines, with paired data lines (SD) set for left/right channel separation |
| Camera | OmniVision OV2640, 2 MP | 24-pin DVP interface, extended 75 mm flexible flat cable from the temple compute unit to the nose bridge |
| Display | 0.96 inch monochrome OLED, 128x64 | SSD1306 or SSD1315 controller, 4-pin I2C (VCC, GND, SCL, SDA). I2C chosen over SPI to avoid pin conflicts with the camera and Octal PSRAM |
| Haptics | Miniature vibration motor with driver circuit | Cues the wearer toward off-axis speakers |
| Power | 3.7 V 1000 mAh LiPo, TP4056 charge/protection board | SPDT switch isolates the battery from the ESP32-S3 5 V rail during USB flashing and debugging |

The full budget cap is INR 7,000. Commercial micro-OLED display assemblies exceed INR 22,000, which is why the optics use a Pepper's Ghost design.

## Pin assignments

| Function | GPIO | Status |
|---|---|---|
| OLED SDA | 8 | In use (see `firmware/src/main.cpp`) |
| OLED SCL | 9 | In use (see `firmware/src/main.cpp`) |
| Microphones (I2S) | TBD | Not yet wired |
| Haptic motor | TBD | Not yet wired |
| Camera (DVP) | Board-defined | Not yet used |

Rules for choosing pins:

- With 8 MB Octal PSRAM, GPIO 35, 36, and 37 are reserved by the PSRAM interface. Do not use them.
- Confirm against the Freenove pinout that GPIO 8 and 9 do not collide with the camera data lines on your board revision before connecting the camera. If they do, move the OLED I2C pins and update `main.cpp`.
- Update this table whenever a pin is assigned, so wiring and firmware never disagree.

## Optical system: Pepper's Ghost combiner

The visual subsystem folds the light path so that a small OLED appears as a floating virtual image in front of the wearer.

**Combiner.** A 2 mm clear cast acrylic plate sits at an exact 45 degree angle relative to the horizontal plane of the downward-facing OLED.

**Collimation and focal depth.** A plano-convex PMMA lens (25 to 30 mm diameter, focal length 40 to 50 mm) sits between the display and the combiner. The flat side faces the OLED and the curved side faces the optical path. It collimates the light so the virtual image appears about 1.5 to 2.0 m away, which prevents the eye strain of focusing at very close range.

**Reflection enhancement.** Untreated acrylic reflects only about 8 to 10 percent of light. A 50:50 architectural semi-reflective beam-splitter film on the rear surface raises reflectance to about 50 percent, delivering roughly 60 to 75 nits to the eye from a 150-nit panel.

**Ambient glare suppression.**

- A 3D-printed matte black brow cowl with a 10 to 15 mm overhang blocks overhead lighting from entering the combiner chamber.
- Polycarbonate safety glasses with a 20 to 30 percent neutral-density tint form the chassis and darken the real-world background to improve subtitle contrast.

Contrast is modeled as:

```
C = (L_virtual + L_ambient) / L_ambient
```

where `L_virtual` is the luminance of the virtual image and `L_ambient` is the background luminance seen through the combiner.

**Aperture masking.** A matte black vinyl mask covers non-active OLED borders and solder pads to eliminate stray reflections.

The firmware renders text with U8g2 using horizontal flip mode, because the combiner mirrors the image.

## Design risks to verify early

These came out of an early design review. Each is worth a quick bench test before building further.

**Four microphones on one ESP32-S3.** Each I2S controller accepts one data-in line, and each INMP441 pair shares a line as left and right channels. Four microphones therefore need both I2S controllers, and keeping the two sample-synchronized is the hard part, because direction estimation depends on that alignment. Test capture and synchronization on the bench first. Microphones with TDM output are an alternative.

**Angle resolution.** At 16 kHz, one sample is about 2.1 cm of path difference. Across a frame of about 14 cm, only about 13 distinct delay values cover 180 degrees. Sub-sample interpolation and a microphone layout that is not a single line (to avoid front/back ambiguity) are needed.

**Optical contrast.** With 60 to 75 nits and a typical indoor background, the contrast formula gives a ratio of only about 1.3 to 1.7. That works in a controlled demo, but not outdoors. Plan the demo environment accordingly.

**Power path.** A 3.7 V LiPo cannot feed a 5 V pin directly, and many onboard regulators need about 5 V in to hold 3.3 V. A boost converter may be needed, or check the dropout of the board's regulator. With Wi-Fi, camera, and microphones active, expect only a few hours of runtime from 1000 mAh.

**PSRAM configuration.** The generic `esp32-s3-devkitc-1` board definition does not enable the N16R8's Octal PSRAM. See [setup-firmware.md](setup-firmware.md) for the required `platformio.ini` settings.

**Camera purpose.** Decide whether the OV2640 has a role (see [architecture.md](architecture.md)) before spending time and GPIO pins on it.

## Files that belong in hardware/

As the project grows, keep these in the `hardware/` folder:

- `fritzing/` for wiring diagrams
- `cad/` for frame and cowl designs
- `stl/` for print-ready models (use Git LFS if files become large)
- `optics/` for combiner angle, lens, and film notes and measurements
