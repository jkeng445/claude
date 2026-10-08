# Hardware build: KJG-2026-002 LAMP-Dx prototype

## Bill of materials (prototype, 1–5 units)

Prices are **rough USD estimates** for small quantities from common electronics suppliers. Get real quotes from your suppliers.

| # | Part | Spec | Est. USD |
|---|---|---|---|
| 1 | Controller | ESP32 DevKitC (ESP32-WROOM-32) | 6–10 |
| 2 | Heat block | 6061 aluminium, drilled for 8 × 0.2 mL PCR tubes (8-strip, 9 mm pitch); or a salvaged dry-bath block | 10–40 |
| 3 | Block heater | 12 V 20 W polyimide (Kapton) film heater, about 40×60 mm, or 2 × 25 W aluminium-clad power resistors | 5–10 |
| 4 | Lid heater | 12 V 10 W polyimide heater on an aluminium plate | 4–8 |
| 5 | Temperature sensors | 2 × 100 kΩ NTC thermistor, B = 3950, glass bead | 1–3 |
| 6 | Divider resistors | 2 × 100 kΩ 0.1 %, plus 2 × 100 nF caps | 1–2 |
| 7 | Heater switches | 3 × logic-level N-MOSFET (IRLZ44N / IRLB8721), 100 Ω gate and 100 kΩ pull-down resistors each | 3–5 |
| 8 | **Thermal cutoff** | **85 °C normally-closed bimetal switch (KSD9700-type) in series with the block heater**: hardware backup if software fails | 1–2 |
| 9 | Fuse | 3 A blade or glass fuse on the 12 V input | 1 |
| 10 | Power | 12 V 3 A adapter, plus a 12 V→5 V buck converter for the ESP32/Pi | 10–15 |
| 11 | Excitation (fluorescence) | 4 × 470 nm blue LEDs + resistors, driven by MOSFET #3 | 2–4 |
| 12 | Emission filter | Amber/orange long-pass acrylic or lighting gel (cuts below ~500 nm) in front of the camera | 3–15 |
| 13 | Illumination (colorimetric) | White LED strip segment, diffused | 2–3 |
| 14 | Camera + host | Raspberry Pi Zero 2 W + Camera Module 3, **or** a laptop with a fixed-focus USB webcam | 15–60 |
| 15 | Insulation | Silicone foam around the block; PTFE or PEEK standoffs | 3–5 |
| 16 | Fan | 40 mm 12 V (cool-down between runs) | 2–4 |
| 17 | Enclosure | 3D-printed black PETG, light-tight, with a hinged heated lid | 5–15 |
| 18 | Misc | Wires, JST connectors, perfboard, screws, thermal paste | 8–12 |
| | **Total** | | **≈ 90–200** |

At 1,000+ units with a custom PCB and injection-moulded case, expect roughly 40–80 USD in parts. That's an estimate; validate it with a contract manufacturer quote.

## Wiring

```
                 3.3 V
                   │
                [100k 0.1%]
                   ├──────────► GPIO34 (block NTC)  ── 100 nF ── GND
                [NTC 100k] (epoxied into a hole in the block, next to the tubes)
                   │
                  GND             (identical divider for the lid NTC → GPIO35)

 12 V ─[3 A fuse]─┬─[85 °C thermal cutoff]─ Block heater ─┐
                  │                                        D  IRLZ44N   G ─[100Ω]─ GPIO25
                  │                                        S ── GND     G ─[100k]─ GND
                  ├─ Lid heater ─ MOSFET (same) ─ GND,  gate ← GPIO26
                  ├─ LEDs + resistors ─ MOSFET ─ GND,   gate ← GPIO27
                  ├─ Fan ─ MOSFET ─ GND,                gate ← GPIO14
                  └─ buck 12→5 V ─► ESP32 5V/VIN (and Pi)
 ESP32 GND and 12 V GND must be connected (common ground).
```

- GPIO34/35 are ADC1 input-only pins, so they still work with Wi-Fi on. The firmware reads them with the factory-calibrated `analogReadMilliVolts()`.
- **Never** rely on software alone for overheat protection. The thermal cutoff (#8) and fuse (#9) are mandatory.

## Block and thermal notes

- Drill the tube holes to match the tube taper (0.2 mL tubes have a ~6 mm top bore and a conical bottom). Good contact matters more than heater power.
- Put the NTC in a blind hole between wells 4 and 5, set with thermal epoxy. Calibrate it once against a reference thermometer placed in a water-filled tube. Correct the offset if the tube reads more than 0.5 °C away from the block sensor.
- The heated lid (75 °C) stops condensation on the caps, which would otherwise change the reaction volume and fog the optics.
- Expected performance (from `firmware/test`): 25 → 65 °C in about 90 s, overshoot under 0.2 °C, hold within ±0.5 °C. Re-tune `block_pid` in `control.h` if your block mass differs a lot.

## Optics

- **Fluorescence** (real-time, quantitative): the master mix includes an intercalating dye, or calcein for some kits. Blue 470 nm LEDs illuminate from below or the side at an angle. The camera looks through the amber long-pass filter, so it sees the green emission and not the blue light.
- **Colorimetric** (simplest, cheapest): a phenol-red master mix turns from pink to yellow. Use diffuse white light with no filter. The software reads the G/R ratio.
- Lock camera exposure, gain and white balance. Auto modes destroy quantitation. Mount the camera rigidly so the well positions never move.
- Calibrate well positions once per build: capture a frame and note each well's centre and radius in `layout.json`.
