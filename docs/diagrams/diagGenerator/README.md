# Diagram Generator

The diagrams in `docs/diagrams/` are generated from the compact element JSONs in this folder. **The JSON files are the source of truth** — the `.excalidraw` and `.html` files are independent outputs; editing one never updates the other. To change a diagram: edit its `elements_*.json`, then regenerate both outputs.

## Files

| File | Diagram |
|---|---|
| `elements_d1.json` | NextOwner — Business Workflow (swim-lanes) |
| `elements_d2.json` | NextOwner — System Architecture |
| `elements_acquire.json` | Acquire.com — researched architecture |
| `convert.js` | JSON → `.excalidraw` (editable; converts labels to bound text) |
| `svg_gen.js` | JSON → `.html` (view-only, styled SVG) |

## Regenerate (run from this folder — outputs land one level up in `docs/diagrams/`)

```bash
cd docs/diagrams/diagGenerator

# Business workflow — Helvetica everywhere
node convert.js elements_d1.json ../nextowner_business_workflow.excalidraw 2
node svg_gen.js elements_d1.json ../nextowner_business_workflow.html "NextOwner — Business Workflow" "40 -8 1080 928" "Helvetica"

# System architecture — Excalifont (sketchy) / Shantell Sans (HTML)
node convert.js elements_d2.json ../nextowner_system_architecture.excalidraw 5
node svg_gen.js elements_d2.json ../nextowner_system_architecture.html "NextOwner — System Architecture" "80 -8 1100 900" "Shantell Sans"

# Acquire.com research diagram
node convert.js elements_acquire.json ../acquire_architecture.excalidraw 2
```

## Arguments

- **convert.js** `<in.json> <out.excalidraw> [fontId]` — font ids: `1` Virgil · `2` Helvetica · `3` Cascadia (code) · `5` Excalifont (sketchy, legible) · `6` Nunito
- **svg_gen.js** `<in.json> <out.html> "<title>" "<viewBox>" ["Font Name"]` — any Google Font name (weights 400–800 preconfigured for Nunito/Inter/Shantell Sans), or `Helvetica` for the no-download system stack

## Element JSON format

Compact Excalidraw-style elements: `rectangle` (with optional `label: {text, fontSize}`, `\n` for multi-line), `arrow` (`points: [[0,0],[dx,dy]]`, optional `label`, `strokeStyle: "dashed"`, `startArrowhead`/`endArrowhead`), `text` (standalone). Zones = rectangles with `opacity: 30`. Keep new elements consistent with the existing color palette in the files.
