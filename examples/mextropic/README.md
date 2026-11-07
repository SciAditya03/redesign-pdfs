# Mextropic Assay Capabilities - prototype build (Phase 4)

Five sample pages: cover (p1), contents (p3), introduction (p4), Proteomics opener (p12), Clinical Imaging dense page (p8).

## Regenerate
1. Install the fonts in `fonts/` (Manrope, DM Serif Display, IBM Plex Mono; Inter from rsms.me/inter). PowerPoint does not embed fonts.
2. `pip install numpy pillow`, then `python3 gen_images.py` (procedural imagery -> `assets/`)
3. `node build_prototype.js` (needs `pptxgenjs`; writes `out/Mextropic_Prototype.pptx`)
4. PDF: open the .pptx and export, or `soffice --headless --convert-to pdf`.

## Edit content
- `content.json`: all 102 capabilities, descriptions and the clinical-imaging note, parsed from the source PDF (`parse.py`).
- Design tokens: `THEME` and the `defineSlideMaster` layouts at the top of `build_prototype.js`.
- In the prototype, page numbers are static text; the full build uses real slide numbers.

## Known placeholders / flags
- No edition, date or contact details in the source: not yet added.
- Imagery is procedurally generated, not photography.
