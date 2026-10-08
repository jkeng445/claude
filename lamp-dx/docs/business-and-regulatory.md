# Business and regulatory plan: KJG-2026-002 LAMP-Dx

Figures marked *est.* are planning assumptions, not quotes. Replace them with real supplier, customer and regulator numbers as you get them.

## The honest picture first

- **Molecular point-of-care diagnostics is a hard business.** Lucira Health (home molecular COVID test) filed for bankruptcy in 2023 and its assets were sold to Pfizer. Cue Health wound down in 2024. Both had big funding. The usual failure points are the cost of making test kits, regulation, and demand collapsing after the pandemic.
- **The device is the easy part.** The value and the moat are in the **test kits**: validated primers, controls, and ideally **dried (lyophilised) reagents that need no cold chain**. That last point matters a lot in African, South Asian and rural markets.
- **Clinical diagnosis (human patients) needs regulatory approval.** Expect years and substantial money: ISO 13485 quality system, clinical performance studies, then FDA (510(k)/De Novo), EU IVDR, WHO prequalification for donor-funded buyers, and national regulators (e.g. Kenya PPB, Nigeria NAFDAC, SAHPRA). Do not market for clinical use before approval.

## Recommended path: get revenue where regulation is lighter, build toward clinical

| Phase | Market | Why | Regulatory load |
|---|---|---|---|
| **1 (now–12 mo)** | **Agriculture and plant health**: e.g. cassava brown streak, maize lethal necrosis, banana bunchy top, seed certification | Paying buyers (seed companies, exporters, research institutes, extension services), real field demand, published LAMP assays exist | Low: research and agricultural use |
| 1 | **Veterinary and food/water**: e.g. African swine fever, poultry disease, Salmonella/E. coli screening | Farms and processors pay to avoid losses; fast on-site results beat sending samples to a lab | Low to moderate, varies by country |
| 1 | **Education and research kits** (universities, labs, iGEM teams) | Quick sales, builds reputation and data | Research use only |
| **2 (12–36 mo)** | **Clinical, through a partner**: malaria, TB, HPV, STIs | Huge need, but entry requires approval | High: partner with an established assay company or research hospital that holds a quality system |

## Revenue model

- **Device:** sell to institutions *(est.)* 400–900 USD, against parts costing ≈ 90–200 USD for prototypes and ≈ 40–80 USD at volume. Commercial portable LAMP readers typically sell for several thousand USD, so price is your wedge.
- **Test kits (the recurring revenue):** *(est.)* 3–8 USD per test in agricultural and veterinary B2B. Reagent cost depends heavily on volume and on making or licensing your own mix: research-catalogue prices are high, bulk and in-house mixes are far lower. **Get NEB, local distributor and bulk-enzyme quotes before you set prices.**
- **Software/service:** cloud dashboard for multi-site customers (surveillance maps, QC trends). Add this later. It isn't needed for the MVP.

### Unit economics worked example (assumptions, replace with real numbers)

| Item | Value |
|---|---|
| Device price / parts cost | 600 / 70 USD → ≈ 88 % gross margin on hardware (before assembly, support, warranty) |
| Kit price / cost per test | 5 / 2 USD → 3 USD gross per test |
| Customer runs 200 tests/month | 600 USD/month gross per device from kits |
| **Takeaway** | One active customer's kit usage is worth more than the device sale within a month or two. Keep the device cheap and put the margin in validated kits. |

## 90-day execution plan

| Weeks | Goal | Done when |
|---|---|---|
| 1–3 | Build 2 prototypes (docs/hardware.md) | Firmware tests pass on hardware; block holds 65 ±0.5 °C, checked with a reference thermometer |
| 3–5 | Optics and chemistry with a commercial kit and a synthetic positive control | Clear Tt standard curve over 10¹–10⁵ copies; NTCs clean over 10+ runs |
| 5–8 | Pick **one** agricultural or veterinary target with a published LAMP assay; partner with a university or national research lab | Signed collaboration; access to reference-tested samples |
| 8–12 | Field comparison: ≥ 100 samples vs lab qPCR | Sensitivity/specificity report; 3 customer letters of intent |
| Parallel | Funding: grant programmes such as Grand Challenges (Gates/Grand Challenges Africa), Wellcome, FIND, and national innovation funds | 2–3 applications submitted using the validation data |

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Amplicon contamination produces false positives | Read through closed tubes, NTC on every run, protocol discipline (assay-protocol.md) |
| Reagent cold chain | Prioritise lyophilised kits; partner with a lyophilisation supplier |
| Sample preparation is the real bottleneck | Start with sample types that need minimal prep (leaf discs, swabs), then develop a simple lysis kit |
| Someone copies the hardware | Expected. The moat is validated assays, data, distribution and support, not the box |
| Software calls are wrong | Rule-based, explainable calls; advisory-only model until validated; every raw curve kept in the run JSON for audit |
