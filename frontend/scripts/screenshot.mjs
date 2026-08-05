/**
 * Capture screenshots of the running app.
 *
 * Uses `playwright-core` against the Chrome/Edge already installed on the
 * machine — `channel` rather than a bundled browser, so nothing is downloaded
 * and CI can pick whichever is present.
 *
 * Both servers must already be up:
 *     make api     (127.0.0.1:8000)
 *     make web     (localhost:3000)
 *
 *     node scripts/screenshot.mjs [outDir]
 *
 * Every shot asserts there is no horizontal scrollbar before saving. A sideways
 * scrollbar means some child escaped its grid track, and a screenshot that
 * quietly contains one is how that ships.
 */

import { chromium } from "playwright-core";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const OUT = process.argv[2] ?? "screenshots";
const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const VIEWPORT = { width: 1440, height: 900 };

const SAMPLE =
  "সে তাহার বইটা পড়ছে । এর কারন কী কেউ জানে না। " +
  "তিনি একজন বিখ্যত লেখক এবং তার দৃস্টি অত্যন্ত প্রখর. " +
  "He also writes in English sometimes.";

async function launch() {
  const errors = [];
  for (const channel of ["chrome", "msedge"]) {
    try {
      return await chromium.launch({ channel, headless: true });
    } catch (e) {
      errors.push(`${channel}: ${e.message.split("\n")[0]}`);
    }
  }
  throw new Error(`no usable browser channel.\n  ${errors.join("\n  ")}`);
}

/** Fails loudly rather than saving a shot with a stray sideways scrollbar. */
async function assertNoHorizontalScroll(page, label) {
  const info = await page.evaluate(() => {
    const de = document.documentElement;
    const wide = [...document.querySelectorAll("*")]
      .filter((e) => e.getBoundingClientRect().right > window.innerWidth + 1)
      .slice(0, 3)
      .map((e) => `${e.tagName}.${String(e.className).slice(0, 40)}`);
    return { scrollWidth: de.scrollWidth, clientWidth: de.clientWidth, wide };
  });
  if (info.scrollWidth > info.clientWidth) {
    throw new Error(
      `${label}: horizontal scroll (${info.scrollWidth} > ${info.clientWidth}); ` +
        `offenders: ${info.wide.join(", ") || "none identified"}`,
    );
  }
  return info;
}

const shots = [
  {
    name: "01-landing",
    url: "/",
    async prepare() {},
  },
  {
    // Full-page too: the landing is a scrolling document, and a viewport-sized
    // crop hides most of what it says.
    name: "01-landing-full",
    url: "/",
    fullPage: true,
    async prepare() {},
  },
  {
    name: "02-editor",
    url: "/editor",
    async prepare(page) {
      // Typed, not loaded via the Sample button: that button now serves a
      // random sentence from lib/samples.ts, and a screenshot that changes
      // every run is no longer a record of anything. This SAMPLE is chosen to
      // exercise both decorations — wavy underlines and the yellow
      // out-of-scope highlight on the English run.
      await page.locator(".bs-editor .ProseMirror").click();
      await page.keyboard.type(SAMPLE);
      // The debounce is 600 ms and a cold Hunspell suggester run is slower;
      // wait for the flags to actually appear rather than guessing a delay.
      await page.waitForSelector(".bs-flag", { timeout: 20000 });
      await page.waitForSelector(".bs-unsupported", { timeout: 20000 });
      const row = page.locator("table.tbl tbody tr", { hasText: "NOTVA" }).first();
      if (await row.count()) await row.click();
      await page.waitForTimeout(400);
    },
  },
  {
    name: "03-analytics",
    url: "/analytics",
    async prepare(page) {
      await page.waitForTimeout(900);
    },
  },
];

const main = async () => {
  await mkdir(OUT, { recursive: true });
  const browser = await launch();
  const context = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: 2, // legible Bengali conjuncts in the saved PNG
    locale: "bn-BD",
  });
  const page = await context.newPage();

  const hydrationErrors = [];
  page.on("console", (m) => {
    const text = m.text();
    if (/hydrat/i.test(text)) hydrationErrors.push(text.slice(0, 200));
  });

  // Defaults, so the shots show what a first-time visitor sees.
  await page.goto(`${BASE}/`, { waitUntil: "domcontentloaded" });
  await page.evaluate(() => {
    localStorage.setItem("bs-theme", "light");
    localStorage.setItem("bs-lang", "bn");
    localStorage.removeItem("bs-layout");
  });

  for (const shot of shots) {
    await page.goto(`${BASE}${shot.url}`, { waitUntil: "networkidle" });
    await shot.prepare(page);
    const info = await assertNoHorizontalScroll(page, shot.name);
    const file = path.join(OUT, `${shot.name}.png`);
    await page.screenshot({ path: file, fullPage: Boolean(shot.fullPage) });
    console.log(
      `${file}  ${VIEWPORT.width}x${VIEWPORT.height}  ` +
        `no-h-scroll (${info.scrollWidth} = ${info.clientWidth})`,
    );
  }

  await browser.close();

  if (hydrationErrors.length) {
    console.error("\nHYDRATION WARNINGS:");
    hydrationErrors.forEach((e) => console.error("  " + e));
    process.exitCode = 1;
  } else {
    console.log("\nno hydration warnings on any page");
  }
};

main().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
