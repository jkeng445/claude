# Adire Lamp Designer

Turns the Adire patterns in this repo (`adire-*.svg`) into custom lampshades.

- **`lamp-designer.html`**: open it in any browser, no install needed. Pick a pattern, a drum or tapered shade, a size and a motif scale. You can preview the lamp lit and unlit, then download:
  - **Print wrap (SVG, real mm)**: the flat shape you cut and roll into the shade. It has a 3 mm bleed, a red cut line and a dashed 15 mm glue overlap. Tapered shades come out as the correct curved (annular-sector) template.
  - **Mockup (SVG)**: a product image for listings and for client approval.
- **`build.py`**: rebuilds `lamp-designer.html` from `template.html`. Any new `adire-*.svg` in the repo root that has a `<pattern id="tile">` shows up automatically:

  ```
  python3 lamp/build.py
  ```

The wrap geometry is verified: on a tapered 200/350/220 mm shade, the cut arcs measure exactly π × 350 mm and π × 200 mm, plus the overlap.

## Producing a shade

1. Export the wrap at the customer's size. Standard frames are drum Ø300 × H220, drum Ø400 × H250, and tapered 200/350 × H220.
2. Print at **100% scale**. For laminate or vinyl use a large-format printer (eco-solvent or UV). For a fabric shade, print on cotton with a print-on-demand fabric service.
3. Laminate the print onto **self-adhesive lampshade styrene (PVC)**, then cut on the red line.
4. Roll it onto top and bottom rings with double-sided tape, glue the overlap, and fold the bleed over the rings.
5. Use **LED bulbs only** (max ~9 W; they stay cool) and keep the bulb at least 50 mm from the shade.

## Business notes (estimates to check against your local suppliers)

- **Your edge**: authentic Yoruba Adire motifs, any size, files ready in seconds. Most custom-shade sellers offer stock fabrics, not culturally specific prints.
- **Unit cost drivers**: printed area (about 0.2 m² for a Ø300 drum), styrene, rings, base or fitting, and your time. Get real quotes on your first 5 units before setting prices.
- **Sell three ways**: (1) finished lamps; (2) shade-only "retrofit" for the customer's existing base; (3) digital wrap files for DIYers, which have zero production cost.
- **Next steps**: put mockups up on Etsy, Instagram and Shopify; take pre-orders before you hold stock; offer a premium tier with hand-dyed indigo fabric made with real Adire artisans and tell that story.
