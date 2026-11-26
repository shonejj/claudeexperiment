// Odoo browser check (Playwright): login, visit pages, screenshots at several widths,
// collect console errors and failed requests, write a JSON report.
//
// node odoo_check.mjs --url http://localhost:8069 --credentials creds.json \
//      --paths "/odoo/inventory,/odoo/action-module.xml_id" --widths 1440,768,390 --out dir [--db name]
// Credentials file: {"login": "...", "password": "...", "database": "..."} — use only the throwaway
// credentials written by `odoo-master runtime serve`, or test accounts the user explicitly provided.
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
const require = createRequire(import.meta.url);
let pw;
try { pw = require("playwright"); } catch { try { pw = require("playwright-core"); } catch { console.error(JSON.stringify({ ok: false, error: "playwright not installed" })); process.exit(3); } }

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, v, i, a) => (v.startsWith("--") ? [...acc, [v.slice(2), a[i + 1] && !a[i + 1].startsWith("--") ? a[i + 1] : "true"]] : acc), []));
const base = (args.url || "http://localhost:8069").replace(/\/$/, "");
const out = args.out || ".odoo-master/screenshots";
const widths = (args.widths || "1440,768,390").split(",").map(Number);
const paths = (args.paths || "/odoo").split(",").map((s) => s.trim()).filter(Boolean);
if (!args.credentials) { console.error(JSON.stringify({ ok: false, error: "--credentials file required (never invent credentials)" })); process.exit(2); }
const creds = JSON.parse(fs.readFileSync(args.credentials, "utf8"));
fs.mkdirSync(out, { recursive: true });

const launchOpts = { args: ["--no-sandbox"] };
if (process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE) launchOpts.executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
const browser = await pw.chromium.launch(launchOpts);
const report = { url: base, started_at: new Date().toISOString(), login: null, pages: [], ok: true };
try {
  const context = await browser.newContext({ viewport: { width: widths[0], height: 900 } });
  const page = await context.newPage();
  const consoleErrors = [];
  const failed = [];
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 500)); });
  page.on("pageerror", (e) => consoleErrors.push(String(e).slice(0, 500)));
  page.on("requestfailed", (r) => failed.push({ url: r.url().slice(0, 300), error: r.failure()?.errorText }));
  page.on("response", (r) => { if (r.status() >= 500) failed.push({ url: r.url().slice(0, 300), status: r.status() }); });

  const dbq = creds.database ? `?db=${encodeURIComponent(creds.database)}` : "";
  await page.goto(`${base}/web/login${dbq}`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.fill('input[name="login"]', creds.login);
  await page.fill('input[name="password"]', creds.password);
  // Odoo keeps a websocket open, so "networkidle" never settles: wait for the web client instead.
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.startsWith("/web/login"), { timeout: 30000 }).catch(() => {});
  await page.waitForSelector(".o_web_client, .o_main_navbar, .alert-danger", { timeout: 30000 }).catch(() => {});
  const loggedIn = !(await page.locator(".alert-danger").count()) && !page.url().includes("/web/login");
  report.login = { ok: loggedIn, url: page.url() };
  if (!loggedIn) { report.ok = false; throw new Error("login failed"); }

  for (const p of paths) {
    for (const w of widths) {
      consoleErrors.length = 0; failed.length = 0;
      await page.setViewportSize({ width: w, height: 900 });
      const resp = await page.goto(base + p, { waitUntil: "domcontentloaded", timeout: 60000 }).catch((e) => ({ error: String(e) }));
      await page.waitForSelector(".o_view_controller, .o_action_manager .o_content, .o_error_dialog, main", { timeout: 30000 }).catch(() => {});
      await page.waitForTimeout(1500);
      const errorDialog = await page.locator(".o_error_dialog, .o_dialog .modal-title:has-text('Error')").count();
      const file = path.join(out, `${p.replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "") || "root"}_${w}.png`);
      await page.screenshot({ path: file, fullPage: true });
      const entry = { path: p, width: w, status: resp?.status ? resp.status() : null, error: resp?.error || null, title: await page.title(),
        error_dialog: errorDialog > 0, console_errors: [...consoleErrors], failed_requests: [...failed], screenshot: file };
      entry.ok = !entry.error && !entry.error_dialog && entry.console_errors.length === 0 && entry.failed_requests.length === 0 && (entry.status === null || entry.status < 400);
      if (!entry.ok) report.ok = false;
      report.pages.push(entry);
    }
  }
} catch (e) {
  report.ok = false; report.error = String(e).slice(0, 500);
} finally {
  await browser.close();
  report.finished_at = new Date().toISOString();
  fs.writeFileSync(path.join(out, "report.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ ok: report.ok, report: path.join(out, "report.json"), pages: report.pages.length, login: report.login }));
}
