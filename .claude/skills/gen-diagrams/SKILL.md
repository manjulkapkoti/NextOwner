---
name: gen-diagrams
description: Regenerate the architecture/workflow diagrams (.excalidraw + .html) from their elements_*.json sources using the diagGenerator node scripts. Use after editing any docs/diagrams/diagGenerator/elements_*.json file. Optional argument names a single diagram (d1, d2, or acquire); default regenerates all.
---

# Regenerate diagrams

The diagrams in `docs/diagrams/` are **generated outputs** — the `elements_*.json` files in `docs/diagrams/diagGenerator/` are the source of truth, and the `.excalidraw` and `.html` outputs are independent (editing one never updates the other). After changing a JSON source, regenerate **both** outputs.

`docs/diagrams/diagGenerator/README.md` documents the format and per-diagram arguments; the per-file title / viewBox / font args below match it exactly — don't guess them.

## Steps

Run from the generator folder:

```bash
cd docs/diagrams/diagGenerator
```

Then run the command(s) for the requested diagram (`$ARGUMENTS` = `d1`, `d2`, or `acquire`; if empty, run all three):

**d1 — Business Workflow** (Helvetica):
```bash
node convert.js elements_d1.json ../nextowner_business_workflow.excalidraw 2
node svg_gen.js elements_d1.json ../nextowner_business_workflow.html "NextOwner — Business Workflow" "40 -8 1080 928" "Helvetica"
```

**d2 — System Architecture** (Excalifont / Shantell Sans):
```bash
node convert.js elements_d2.json ../nextowner_system_architecture.excalidraw 5
node svg_gen.js elements_d2.json ../nextowner_system_architecture.html "NextOwner — System Architecture" "80 -8 1100 900" "Shantell Sans"
```

**acquire — Acquire.com research diagram**:
```bash
node convert.js elements_acquire.json ../acquire_architecture.excalidraw 2
```

## Notes

- `convert.js <in.json> <out.excalidraw> [fontId]` — font ids: `1` Virgil · `2` Helvetica · `3` Cascadia · `5` Excalifont · `6` Nunito.
- `svg_gen.js <in.json> <out.html> "<title>" "<viewBox>" ["Font Name"]`.
- No `package.json` / dependencies — plain `node`. Confirm Node is on PATH first.
- If a diagram looks clipped, the `viewBox` arg (in `svg_gen.js`) is the thing to adjust — see the generator README.
