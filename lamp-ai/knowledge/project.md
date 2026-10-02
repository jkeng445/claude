# Project knowledge — TEMPLATE, fill this in

Everything in this file is injected into the assistant's system prompt on every
request, and the assistant treats it as the authoritative source for the
project. **Replace every `TODO` below with your own validated values.** Delete
any section that does not apply rather than leaving a guess in it.

While the TODOs are still here, the assistant will say it has no project
protocol and fall back to general LAMP guidance. That is the intended behaviour:
it must not invent your protocol.

---

## 1. What this project is

- **Target disease / organism:** TODO
- **Target gene or region:** TODO
- **Sample type:** TODO (e.g. whole blood, nasal swab, plant leaf tissue, water)
- **Setting:** TODO (e.g. district clinic, field use by extension officers)
- **Stage:** TODO (bench development / field validation / routine use)
- **Intended use statement:** TODO. State plainly whether results are for
  research, screening with lab confirmation, or something else.

## 2. Assay

- **Primer set name / version:** TODO
- **Primer set source:** TODO (published paper with citation, or designed
  in-house — say which, and whether it has been validated)
- **Reaction volume:** TODO
- **Incubation temperature and time:** TODO (e.g. 65 °C for 30 min)
- **Enzyme / master mix:** TODO
- **Read-out:** TODO (colorimetric pH dye, hydroxynaphthol blue, fluorescence,
  turbidity, lateral flow)
- **Sample preparation:** TODO (extraction kit, or direct/boil-prep method)

## 3. How to read a result

This is the section the result-reading mode depends on most. Be precise.

- **Positive looks like:** TODO (e.g. "pink to yellow colour change")
- **Negative looks like:** TODO
- **Time point to read at:** TODO
- **Fluorescence cut-off / time-to-positive threshold:** TODO
- **Borderline / inconclusive appearance:** TODO
- **Known false-positive causes:** TODO (e.g. carry-over contamination, reading
  past the end point, non-specific amplification)

### Controls, every run

- **Negative / no-template control:** TODO — expected appearance
- **Positive control:** TODO — expected appearance
- **Rule:** if the negative control reads positive or the positive control
  fails, the whole run is invalid and no sample result may be reported from it.
- **Internal / extraction control, if any:** TODO

## 4. Performance, as measured by this project

Only put numbers here that your own project measured or that come from a cited
study on this exact assay. Leave it blank rather than filling it with estimates.

- **Limit of detection:** TODO
- **Sensitivity vs. reference method:** TODO (and the reference method)
- **Specificity vs. reference method:** TODO
- **Cross-reactivity tested against:** TODO
- **Sample size and setting of that evaluation:** TODO

## 5. Workflow and rules

- **Who runs the test:** TODO
- **What happens on a positive:** TODO (referral, confirmatory test, reporting)
- **What happens on an invalid run:** TODO
- **Notifiable-disease reporting obligations:** TODO
- **Contamination control:** TODO (separate pre/post-amplification areas, etc.)

## 6. Glossary for the public-explainer mode

How the project wants the disease and the test described to non-specialists, in
each language it works in.

- **Disease, in plain words:** TODO
- **The test, in plain words:** TODO
- **What a positive means for the person:** TODO
- **What a negative means for the person:** TODO
- **Languages to answer in:** TODO
