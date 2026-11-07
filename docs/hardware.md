# Hardware

Parts list, pin assignments, microphone array geometry, optical design, and known design risks for the glasses. See [architecture.md](architecture.md) for how the hardware fits into the whole system.

## Bill of materials (summary)

| Subsystem | Part | Notes |
|---|---|---|
| Controller | Freenove ESP32-S3-WROOM-1, N16R8 | 16 MB flash, 8 MB Octal PSRAM, dual-core Xtensa LX7 at 240 MHz. Handles peripheral timing, dual-bus I2S DMA, Wi-Fi UDP streaming, and display rendering |
| Microphones | 4x INMP441 I2S MEMS | Omnidirectional rectangular array (2 front brow, 2 rear temple). Share BCLK (`GPIO 41`) and WS (`GPIO 42`), with paired data lines (`GPIO 1` and `GPIO 47`) and `L/R` channel selection |
| Camera | OmniVision OV3660 | 24-pin DVP FPC interface connected to the onboard camera slot; left-side camera GPIOs are kept completely unpopulated |
| Display | 0.96 inch monochrome OLED, 128x64 | SSD1306 controller, 4-pin I2C (`VCC`, `GND`, `SCL` on `GPIO 21`, `SDA` on `GPIO 14`). Remapped off `GPIO 8/9` to avoid camera bus collisions |
| Haptics | Coin vibration motor + Adafruit MAX98357A I2S 3W Class D Amp | MAX98357A shares the `I2S0` clock bus (`GPIO 41/42`) and receives 150 ms square-wave bursts on `DIN` (`GPIO 38`), driving the motor directly via `VO+`/`VO-` |
| Power | 3.7 V 1000 mAh LiPo, TP4056 charger, SPDT slide switch, 5 V boost converter | Battery feeds TP4056 (`B+`/`B-`); output routes through the SPDT switch and 5 V boost converter to the ESP32-S3 `5V` pin |

The full budget cap is INR 7,000. Commercial micro-OLED display assemblies exceed INR 22,000, which is why the optics use a Pepper's Ghost design.

## Pin assignments

| Component / Subsystem | Module Pin | ESP32-S3 Pin | Physical Header Position (Front View) & Wiring Notes |
|---|---|---|---|
| Power Rail (+3.3V Trunk) | Shared `+3.3V` | `3V3` | Left side, 1st pin from Top (8-branch shared `+3.3V` trunk wire) |
| Ground Rail (GND Trunk) | Shared `GND` | `GND` | Right side, 1st pin from Bottom (10-branch shared `GND` trunk wire) |
| OLED Display | `SDA` | `GPIO 14` | Left side, 2nd pin from Bottom (right above `5V`, no camera conflict) |
| OLED Display | `SCL` | `GPIO 21` | Right side, 4th pin from Bottom (above `20`, `19`, `GND`, no camera conflict) |
| All 4x INMP441 & MAX98357A | `SCK` / `BCLK` | `GPIO 41` | Right side, 6th pin from Top (5-branch shared bit clock bus) |
| All 4x INMP441 & MAX98357A | `WS` / `LRC` | `GPIO 42` | Right side, 5th pin from Top (5-branch shared word select bus) |
| Mic 1 (Front-Left, `Ch 0`) | `SD` (`I2S0`) & `L/R` | `GPIO 1` (`L/R` to `GND`) | Right side, 3rd pin from Top (`SD` spliced with Mic 2; `L/R` tied to `GND`) |
| Mic 2 (Front-Right, `Ch 1`) | `SD` (`I2S0`) & `L/R` | `GPIO 1` (`L/R` to `3V3`) | Right side, 3rd pin from Top (`SD` spliced with Mic 1; `L/R` tied to `+3.3V`) |
| Mic 3 (Rear-Left, `Ch 2`) | `SD` (`I2S1`) & `L/R` | `GPIO 47` (`L/R` to `GND`) | Right side, 5th pin from Bottom (`SD` spliced with Mic 4; `L/R` tied to `GND`) |
| Mic 4 (Rear-Right, `Ch 3`) | `SD` (`I2S1`) & `L/R` | `GPIO 47` (`L/R` to `3V3`) | Right side, 5th pin from Bottom (`SD` spliced with Mic 3; `L/R` tied to `+3.3V`) |
| MAX98357A Haptic Amp | `DIN` (`I2S0 TX`) | `GPIO 38` | Right side, 9th pin from Top (`SD` & `GAIN` left unconnected; motor on `VO+`/`VO-`) |
| Onboard Status LEDs | Internal | `GPIO 2` & `48` | Internal to board (`IO2` status LED pulsed with haptics; leave header pins empty) |
| OV3660 Camera | 24-pin Ribbon | FPC Slot | Keep plugged in; leave Left Header pins `4–13` and `15–18` completely empty |
| Octal PSRAM (Reserved) | Internal | `GPIO 35, 36, 37` | Do not touch (Right side, 9th–11th pins from Bottom) |

## Microphone array geometry

To resolve full 360-degree azimuth without front-to-back ambiguity, the four INMP441 modules are mounted in a rectangular layout (`width = 0.14 m`, `depth = 0.07 m`):

- **Mic 1 (`Ch 0`, Front-Left):** Front-left brow corner (`GPIO 1`, `L/R = GND`), port facing forward (`0°`).
- **Mic 2 (`Ch 1`, Front-Right):** Front-right brow corner (`GPIO 1`, `L/R = +3.3V`), spaced ~14 cm from Mic 1, port facing forward (`0°`).
- **Mic 3 (`Ch 2`, Rear-Left):** Left temple arm (`GPIO 47`, `L/R = GND`), ~7 cm behind Mic 1, port facing outward/upward.
- **Mic 4 (`Ch 3`, Rear-Right):** Right temple arm (`GPIO 47`, `L/R = +3.3V`), ~7 cm behind Mic 2, port facing outward/upward.

## Optical system: Pepper's Ghost combiner

The visual subsystem folds the light path so that a small OLED appears as a floating virtual image in front of the wearer.

**Combiner.** A 2 mm clear cast acrylic plate sits at an exact 45 degree angle relative to the horizontal plane of the downward-facing OLED.

**Collimation and focal depth.** A plano-convex PMMA lens (25 to 30 mm diameter, focal length 40 to 50 mm) sits between the display and the combiner. The flat side faces the OLED and the curved side faces the optical path. It collimates the light so the virtual image appears about 1.5 to 2.0 m away, which prevents the eye strain of focusing at very close range.

**Reflection enhancement.** Untreated acrylic reflects only about 8 to 10 percent of light. A 50:50 architectural semi-reflective beam-splitter film on the rear surface raises reflectance to about 50 percent, delivering roughly 60 to 75 nits to the eye from a 150-nit panel.

**Ambient glare suppression.**

- A 3D-printed matte black brow cowl with a 10 to 15 mm overhang blocks overhead lighting from entering the combiner chamber.
- Polycarbonate safety glasses with a 20 to 30 percent neutral-density tint form the chassis and darken the real-world background to improve subtitle contrast.

Contrast is modeled as:

```text
C = (L_virtual + L_ambient) / L_ambient
```

where `L_virtual` is the luminance of the virtual image and `L_ambient` is the background luminance seen through the combiner.

**Aperture masking.** A matte black vinyl mask covers non-active OLED borders and solder pads to eliminate stray reflections.

Once mounted in the combiner, change the U8g2 constructor rotation in `firmware/src/main.cpp` from `U8G2_R0` to `U8G2_MIRROR` so reflected text reads left-to-right.

## Design risks and mitigations

**Four microphones on one ESP32-S3 (Resolved).** `I2S_NUM_0` is configured in master RX/TX mode driving `GPIO 41` (`BCLK`) and `GPIO 42` (`WS`), while `I2S_NUM_1` runs in slave RX mode. The ESP32-S3 GPIO matrix (`esp_rom_gpio_connect_in_signal`) routes the master clocks internally to `I2S_NUM_1` so all 4 channels sample in lockstep.

**Angle resolution.** At 16 kHz, one sample is about 2.1 cm of path difference. The backend uses 2D GCC-PHAT cross-correlation across both lateral (`Left/Right`) and longitudinal (`Front/Rear`) microphone pairs to compute full 360-degree azimuth (`atan2`).

**Haptic driver integration (Resolved).** Instead of a discrete transistor switch, the vibration motor is driven by the MAX98357A Class D amplifier sharing `I2S_NUM_0`'s clock bus and outputting a 150 ms square-wave burst on `GPIO 38` (`tx_desc_auto_clear = true`).

**Power path.** The 3.7 V LiPo charges via the TP4056 module (`B+`/`B-`), and `OUT+` passes through an SPDT slide switch and a 5 V boost converter into the ESP32-S3 `5V` pin.

## Files that belong in hardware/

- `fritzing/` for wiring diagrams and netlists (`connection_diagram.fzz`, `connection_diagram_netlist.xml`)
- `esp32_s3_pin_connections_v3.xlsx` for the complete pin map and trunk-wire splice counts
- `cad/` for frame and cowl designs
- `stl/` for print-ready models (use Git LFS if files become large)
- `optics/` for combiner angle, lens, and film notes and measurements
