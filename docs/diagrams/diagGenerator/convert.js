// Convert compact MCP-style Excalidraw elements (with `label`) into a valid
// .excalidraw file with bound text elements.
const fs = require("fs");

const [, , inFile, outFile, fontFamilyArg] = process.argv;
const FONT = Number(fontFamilyArg) || 6; // Excalidraw ids: 1 Virgil, 2 Helvetica, 3 Cascadia, 6 Nunito
const src = JSON.parse(fs.readFileSync(inFile, "utf8"));

let seedCounter = 1000;
const rand = () => seedCounter++ * 2654435761 % 2147483647;

function base(el) {
  return {
    angle: 0,
    strokeColor: "#1e1e1e",
    backgroundColor: "transparent",
    fillStyle: "solid",
    strokeWidth: 2,
    strokeStyle: "solid",
    roughness: 0,
    opacity: 100,
    groupIds: [],
    frameId: null,
    roundness: null,
    seed: rand(),
    version: 1,
    versionNonce: rand(),
    isDeleted: false,
    boundElements: null,
    updated: Date.now(),
    link: null,
    locked: false,
    ...el,
  };
}

function measure(text, fontSize) {
  const lines = text.split("\n");
  const maxLen = Math.max(...lines.map((l) => l.length));
  return {
    width: Math.ceil(maxLen * fontSize * 0.6),
    height: Math.ceil(lines.length * fontSize * 1.25),
  };
}

const out = [];
for (const el of src) {
  const { label, ...rest } = el;
  const e = base(rest);

  if (e.type === "text") {
    const m = measure(e.text, e.fontSize);
    e.width = e.width || m.width;
    e.height = e.height || m.height;
    Object.assign(e, {
      fontFamily: FONT,
      textAlign: "left",
      verticalAlign: "top",
      containerId: null,
      originalText: e.text,
      lineHeight: 1.25,
      baseline: e.fontSize,
    });
  }

  if (e.type === "arrow") {
    Object.assign(e, {
      lastCommittedPoint: null,
      startBinding: null,
      endBinding: null,
      startArrowhead: e.startArrowhead || null,
      endArrowhead: e.endArrowhead === undefined ? "arrow" : e.endArrowhead,
    });
  }

  out.push(e);

  if (label) {
    const fontSize = label.fontSize || 16;
    const m = measure(label.text, fontSize);
    const txtId = e.id + "_txt";
    let tx, ty;
    if (e.type === "arrow") {
      // midpoint of the arrow
      const [dx, dy] = e.points[e.points.length - 1];
      tx = e.x + dx / 2 - m.width / 2;
      ty = e.y + dy / 2 - m.height / 2;
    } else {
      tx = e.x + (e.width - m.width) / 2;
      ty = e.y + (e.height - m.height) / 2;
    }
    e.boundElements = [{ id: txtId, type: "text" }];
    out.push(
      base({
        type: "text",
        id: txtId,
        x: tx,
        y: ty,
        width: m.width,
        height: m.height,
        text: label.text,
        fontSize,
        fontFamily: FONT,
        textAlign: "center",
        verticalAlign: "middle",
        containerId: e.id,
        originalText: label.text,
        lineHeight: 1.25,
        baseline: fontSize,
      })
    );
  }
}

const doc = {
  type: "excalidraw",
  version: 2,
  source: "https://claude.ai/claude-code",
  elements: out,
  appState: { viewBackgroundColor: "#ffffff", gridSize: null },
  files: {},
};

fs.writeFileSync(outFile, JSON.stringify(doc, null, 1));
console.log(`wrote ${outFile} with ${out.length} elements`);
