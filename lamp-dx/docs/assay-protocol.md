# Assay protocol and biosafety

> **Research use only.** Work under your institution's biosafety rules. Handle potentially infectious samples at the containment level required for that pathogen, usually BSL-2 with a biosafety cabinet for primary samples. Only trained staff should handle them.

## Reagents

- **Master mix:** use a commercial LAMP mix first, such as NEB WarmStart® LAMP Kit (DNA & RNA, fluorescent dye included) or NEB WarmStart® Colorimetric LAMP 2X Master Mix (phenol red). Commercial mixes are validated. Home-made mixes add a variable you can't afford early on.
- **Primers:** 4–6 LAMP primers per target (F3, B3, FIP, BIP, plus optional LF/LB). Use published, validated primer sets for your first targets rather than designing new ones.
- **Controls, every run:**
  - **NTC** (no-template control: water instead of sample) must stay negative. If it amplifies, the whole run is invalid.
  - **PC** (positive control: synthetic target at a known copy number) must amplify. If it doesn't, the reagents, heating or optics have failed.
  - **IC** (internal control: a human or host gene such as RNase P, run beside each sample) proves the sample was valid and not inhibited. A negative target with a failed IC is reported **INVALID**, never NOT DETECTED.

## Default 8-tube strip layout

`S1  IC1  S2  IC2  S3  IC3  NTC  PC`, which gives 3 samples per run with full controls. A 16-well block would allow 7 samples per run.

## Run steps

1. **Prepare the sample** (in the pre-amplification area): inactivate or lyse it, using heat (e.g. 95 °C for 5 min) or a lysis buffer suited to the sample type.
2. **Set up reactions:** add the master mix, the primers and the sample (typically 25 µL in total), then cap the tubes tightly.
3. Load the strip and close the heated lid.
4. Run `python -m lampdx.run --port <port> --layout layout.json --minutes 35`. The block heats to 65 °C, holds for 35 min, and is imaged every 30 s.
5. Read the HTML report. If the run is INVALID, find the cause before testing again.
6. **Dispose of the strip without opening it** (seal it in a bag, autoclave or incinerate it under local rules).

## Contamination control (LAMP's #1 failure mode)

LAMP makes huge amounts of product. A single opened positive tube can contaminate a room for months, and every later NTC will then turn positive.

- **Never open tubes after amplification.** The device reads through closed tubes for exactly this reason.
- Keep separate pre-amplification and post-amplification areas, pipettes and gloves, and work in one direction only.
- Clean benches with 10 % bleach and then 70 % ethanol. Use filter tips.
- Watch NTC results over time. A rising trend of late NTC signals is an early warning.

## Validation before any real-world claim

1. **Limit of detection:** run a dilution series of the PC (e.g. 10⁵ down to 10⁰ copies, ≥ 20 replicates near the limit). The LoD is the lowest level detected in ≥ 95 % of replicates.
2. **Cutoff time:** choose `cutoff_min` from where NTCs and true negatives start showing late signal in your data. Don't keep the default 30 min without checking.
3. **Sensitivity and specificity:** compare against a reference method (lab qPCR) on real samples, at least 100 positives and 100 negatives for a credible first claim. Collect them through a partner lab with ethics approval.
4. Feed the labelled runs into `python -m lampdx.train` and validate on held-out runs.
