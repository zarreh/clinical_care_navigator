// Renders every docs/diagrams/*.mmd to a static SVG in docs/assets/diagrams/.
//
// Why static images: a Mermaid code fence only becomes a picture where something
// runs Mermaid client-side. The docs site does (and fetches it from a CDN), but
// GitHub's raw view, editor previews such as VS Code's, and offline readers show
// the code instead. A committed SVG renders the same everywhere.
//
// Usage: npm install && npm run render   (or `make docs-diagrams` from the repo root)
import { chromium } from "playwright";
import { readdir, readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const srcDir = path.join(here, "..", "..", "docs", "diagrams");
const outDir = path.join(here, "..", "..", "docs", "assets", "diagrams");
const mermaidJs = path.join(here, "node_modules", "mermaid", "dist", "mermaid.min.js");

const THEME = {
  fontFamily: "Inter, ui-sans-serif, system-ui, Segoe UI, Arial, sans-serif",
  primaryColor: "#e0f2fe",
  primaryBorderColor: "#0284c7",
  primaryTextColor: "#0f172a",
  lineColor: "#475569",
  secondaryColor: "#eef2ff",
  tertiaryColor: "#f8fafc",
  edgeLabelBackground: "#ffffff",
};

await mkdir(outDir, { recursive: true });
const files = (await readdir(srcDir)).filter((f) => f.endsWith(".mmd")).sort();
const browser = await chromium.launch();
const page = await browser.newPage();
await page.setContent("<html><body></body></html>");
await page.addScriptTag({ path: mermaidJs });
await page.evaluate((theme) => {
  // htmlLabels:false keeps node text as native SVG <text>, which every SVG viewer
  // renders; HTML <foreignObject> labels disappear in many of them.
  window.mermaid.initialize({
    startOnLoad: false,
    theme: "base",
    themeVariables: theme,
    securityLevel: "strict",
    htmlLabels: false,
    flowchart: { htmlLabels: false, diagramPadding: 16, curve: "basis" },
  });
}, THEME);

for (const file of files) {
  const source = await readFile(path.join(srcDir, file), "utf8");
  const name = file.replace(/\.mmd$/, "");
  const svg = await page.evaluate(
    async ({ source, id }) => {
      const { svg } = await window.mermaid.render(id, source);
      const holder = document.createElement("div");
      holder.innerHTML = svg;
      const el = holder.querySelector("svg");
      // An opaque background so the picture reads on both light and dark pages,
      // and explicit pixel size so it has an intrinsic size as an <img>.
      const [, , w, h] = el.getAttribute("viewBox").split(/\s+/).map(Number);
      el.setAttribute("width", String(Math.ceil(w)));
      el.setAttribute("height", String(Math.ceil(h)));
      el.setAttribute("style", "background-color:#ffffff;");
      return new XMLSerializer().serializeToString(el);
    },
    { source, id: `d-${name}` }
  );
  await writeFile(path.join(outDir, `${name}.svg`), svg + "\n");
  console.log(`rendered ${name}.svg (${svg.length} bytes)`);
}
await browser.close();
