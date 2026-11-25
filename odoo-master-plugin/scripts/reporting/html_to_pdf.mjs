// html_to_pdf.mjs <in.html> <out.pdf> <waitForMermaid 0|1>
// Uses Playwright's Chromium. Resolves 'playwright' from the global/node path; set NODE_PATH if needed.
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
const require = createRequire(import.meta.url);
let pw;
try { pw = require("playwright"); } catch (e) {
  try { pw = require("playwright-core"); } catch (e2) { console.error("playwright not installed"); process.exit(3); }
}
const [, , input, output, mermaid] = process.argv;
const launchOpts = { args: ["--no-sandbox"] };
if (process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE) launchOpts.executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
const browser = await pw.chromium.launch(launchOpts);
try {
  const page = await browser.newPage();
  await page.goto(pathToFileURL(input).href, { waitUntil: "load", timeout: 60000 });
  if (mermaid === "1") {
    // Give mermaid (if it could be loaded) a moment to render; continue regardless.
    await page.waitForFunction(() => !document.querySelector("pre.mermaid:not([data-processed])"), null, { timeout: 8000 }).catch(() => {});
  }
  await page.pdf({ path: output, format: "A4", printBackground: true, margin: { top: "14mm", bottom: "14mm", left: "12mm", right: "12mm" } });
} finally {
  await browser.close();
}
