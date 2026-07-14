// Render compact Excalidraw-style element JSON (with `label`) as a polished
// standalone HTML file with inline SVG. Usage:
//   node svg_gen.js <elements.json> <out.html> "<page title>" "<viewBox>"
const fs = require("fs");
const [, , inFile, outFile, pageTitle, viewBox, fontName = "Nunito"] = process.argv;
const els = JSON.parse(fs.readFileSync(inFile, "utf8"));

// system fonts need no webfont link; some Google fonts ship a single weight
const SYSTEM_FONTS = { Helvetica: "'Helvetica Neue',Helvetica,Arial,sans-serif" };
const GF_AXES = { Nunito: ":wght@400;500;600;700;800", Inter: ":wght@400;500;600;700;800", "Shantell Sans": ":wght@400;500;600;700;800" };
const isSystem = fontName in SYSTEM_FONTS;
// If fonts/<FontName>.css exists next to this script (base64-embedded @font-face),
// inline it — the HTML then renders the font offline, with no external requests.
const path = require("path");
const embeddedPath = path.join(__dirname, "fonts", fontName.replace(/ /g, "") + ".css");
const embeddedCss =
  !isSystem && fs.existsSync(embeddedPath) ? fs.readFileSync(embeddedPath, "utf8") : "";
const fontUrl = isSystem || embeddedCss
  ? ""
  : `https://fonts.googleapis.com/css2?family=${fontName.replace(/ /g, "+")}${GF_AXES[fontName] ?? ""}&display=swap`;
const fontStack = isSystem
  ? SYSTEM_FONTS[fontName]
  : `'${fontName}','Segoe UI',system-ui,sans-serif`;

const esc = (s) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

// one arrowhead marker per stroke color
const markerColors = new Set();
for (const el of els)
  if (el.type === "arrow") markerColors.add(el.strokeColor || "#1e1e1e");
const markerId = (c) => "arr" + c.replace("#", "");
let defs = "";
for (const c of markerColors)
  defs += `<marker id="${markerId(c)}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse"><path d="M0,1 L9,5 L0,9 z" fill="${c}"/></marker>`;

function labelText(el, label) {
  const fs_ = label.fontSize || 16;
  const lines = label.text.split("\n");
  const lh = fs_ * 1.32;
  const cx = el.x + el.width / 2;
  const cy = el.y + el.height / 2;
  const startY = cy - ((lines.length - 1) * lh) / 2 + fs_ * 0.34;
  let t = `<text x="${cx}" y="${startY}" text-anchor="middle" font-size="${fs_}" fill="#1f2937">`;
  lines.forEach((ln, i) => {
    const w = i === 0 ? 700 : 500;
    const fill = i === 0 ? "#111827" : "#374151";
    t += `<tspan x="${cx}" ${i ? `dy="${lh}"` : ""} font-weight="${w}" fill="${fill}">${esc(ln)}</tspan>`;
  });
  return t + `</text>`;
}

let body = "";
for (const el of els) {
  if (el.type === "rectangle") {
    const zone = (el.opacity || 100) < 100; // translucent = background zone
    const rx = el.roundness ? 14 : 0;
    const dash = el.strokeStyle === "dashed" ? ` stroke-dasharray="8 6"` : "";
    body += `<rect x="${el.x}" y="${el.y}" width="${el.width}" height="${el.height}" rx="${rx}" fill="${el.backgroundColor || "none"}" fill-opacity="${zone ? (el.opacity / 100) * 0.9 : 1}" stroke="${el.strokeColor || "#1e1e1e"}" stroke-opacity="${zone ? 0.45 : 1}" stroke-width="${el.strokeWidth || 2}"${dash}${zone ? "" : ` class="box"`}/>`;
    if (el.label) body += labelText(el, el.label);
  } else if (el.type === "arrow") {
    const c = el.strokeColor || "#1e1e1e";
    const [dx, dy] = el.points[el.points.length - 1];
    const x2 = el.x + dx, y2 = el.y + dy;
    const dash = el.strokeStyle === "dashed" ? ` stroke-dasharray="7 5"` : "";
    const mEnd = el.endArrowhead ? ` marker-end="url(#${markerId(c)})"` : "";
    const mStart = el.startArrowhead ? ` marker-start="url(#${markerId(c)})"` : "";
    body += `<line x1="${el.x}" y1="${el.y}" x2="${x2}" y2="${y2}" stroke="${c}" stroke-width="${el.strokeWidth || 2}"${dash}${mEnd}${mStart}/>`;
    if (el.label) {
      const fs_ = el.label.fontSize || 14;
      const mx = el.x + dx / 2, my = el.y + dy / 2 - 6;
      body += `<text x="${mx}" y="${my}" text-anchor="middle" font-size="${fs_}" font-weight="600" fill="#4b5563" class="halo">${esc(el.label.text)}</text>`;
    }
  } else if (el.type === "text") {
    const fs_ = el.fontSize || 16;
    const caps = el.text === el.text.toUpperCase() && /[A-Z]/.test(el.text);
    const big = fs_ >= 24;
    const w = big ? 800 : caps ? 700 : 500;
    const ls = caps ? ` letter-spacing="1.2"` : "";
    body += `<text x="${el.x}" y="${el.y + fs_ * 0.9}" font-size="${fs_}" font-weight="${w}" fill="${el.strokeColor || "#111827"}"${ls}>${esc(el.text)}</text>`;
  }
}

const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>${esc(pageTitle)}</title>
${embeddedCss ? `<style>${embeddedCss}</style>` : ""}${fontUrl ? `<link rel="preconnect" href="https://fonts.googleapis.com"/>\n<link href="${fontUrl}" rel="stylesheet"/>` : ""}
<style>
  body { margin: 0; padding: 28px 16px; background: #f1f5f9;
         display: flex; flex-direction: column; align-items: center;
         font-family: ${fontStack}; }
  .frame { background: #ffffff; border-radius: 16px; padding: 18px;
           box-shadow: 0 8px 30px rgba(15,23,42,.08); max-width: 1240px; width: 100%; }
  svg { width: 100%; height: auto; display: block; }
  svg text { font-family: ${fontStack}; }
  .box { filter: drop-shadow(0 1.5px 2.5px rgba(15,23,42,.10)); }
  .halo { paint-order: stroke; stroke: #ffffff; stroke-width: 4px; }
  footer { color: #94a3b8; font-size: 12.5px; margin-top: 14px; }
</style>
</head>
<body>
<div class="frame">
<svg viewBox="${viewBox}" xmlns="http://www.w3.org/2000/svg">
<defs>${defs}</defs>
${body}
</svg>
</div>
<footer>NextOwner · generated ${new Date().toISOString().slice(0, 10)} · editable source: matching .excalidraw file</footer>
</body>
</html>`;

fs.writeFileSync(outFile, html);
console.log(`wrote ${outFile} (${(html.length / 1024).toFixed(1)} KB)`);
