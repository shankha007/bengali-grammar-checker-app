/**
 * End-to-end check: type Bengali into the real editor and assert on what comes
 * back.
 *
 * The unit tests in tests/test_rules.py call the detector directly and the eval
 * harness scores it against the gold set; neither of them proves the browser
 * gets the same answer. This does — it drives the ProseMirror editor, reads the
 * /api/check response the app actually received, and counts the decorations the
 * app actually painted. A detector fix that never reaches the screen fails here.
 *
 * Uses `channel` rather than a bundled browser, like screenshot.mjs, so nothing
 * is downloaded.
 *
 * Both servers must already be up:
 *     .\make.ps1 api     (127.0.0.1:8000)
 *     .\make.ps1 web     (localhost:3000)
 *
 *     node scripts/e2e.mjs
 *
 * Half the cases expect NOTHING to be flagged. That ratio matches the unit
 * tests and for the same reason: spec §8 makes the false-positive rate the
 * governing metric, so the clean cases are the ones that protect the product.
 */

import { chromium } from "playwright-core";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const VIEWPORT = { width: 1440, height: 900 };

/** `want: null` means the sentence is correct and nothing may be flagged. */
const CASES = [
  // গুরুচণ্ডালী — the three shapes that used to go undetected. See the
  // second-pass notes in data/register.yaml.
  { name: "guru-honorific", text: "তিনি বাড়ি গিয়াছেন এবং এখন খাচ্ছেন।", want: "GURUCHANDALI_DOSHA" },
  { name: "guru-future", text: "লোকটি কহিল সে কাল যাবে।", want: "GURUCHANDALI_DOSHA" },
  { name: "guru-vowel-root", text: "তিনি খাইতেছিলেন যখন আমি এলাম।", want: "GURUCHANDALI_DOSHA" },
  { name: "guru-pronoun", text: "সে তাহার বইটা পড়ছে।", want: "GURUCHANDALI_DOSHA" },
  // ণত্ব / ষত্ব — words that were being corrected as plain misspellings, with
  // no বিধান cited.
  { name: "notva-udaharan", text: "এটি একটি উদাহরন মাত্র।", want: "NOTVA_SHOTVA" },
  { name: "notva-bisheshon", text: "তিনি বাক্যে বিশেষন ব্যবহার করেন।", want: "NOTVA_SHOTVA" },
  { name: "shotva-prosongsa", text: "সবাই তার কাজের প্রসংসা করেছে।", want: "NOTVA_SHOTVA" },
  { name: "notva-karon", text: "এর কারন কী কেউ জানে না।", want: "NOTVA_SHOTVA" },
  { name: "punctuation", text: "আমি বাড়ি যাচ্ছি ।", want: "PUNCTUATION" },
  { name: "non-word", text: "একজন বিখ্যত লেখক এসেছেন।", want: "NON_WORD" },
  // পুরুষ / সম্ভ্রম agreement.
  { name: "verb-person-first", text: "আমি ভাত খাইবেন।", want: "VERB_INFLECTION" },
  { name: "verb-person-honorific", text: "আপনি কোথায় যাচ্ছ?", want: "VERB_INFLECTION" },
  { name: "verb-person-familiar", text: "তিনি গতকাল বাড়ি গেল।", want: "VERB_INFLECTION" },
  // classifier and number.
  { name: "double-plural", text: "সব ছাত্ররা মাঠে খেলছে।", want: "CLASSIFIER" },
  { name: "classifier-animacy", text: "সে একটি বিদুষী নারী।", want: "CLASSIFIER" },
  { name: "classifier-thing", text: "তিনজন বই টেবিলে রাখা আছে।", want: "CLASSIFIER" },
  { name: "inanimate-plural", text: "বইরা টেবিলে রাখা আছে।", want: "AGREEMENT" },
  { name: "possessive-plural", text: "আমরা আমার কাজ শেষ করেছি।", want: "AGREEMENT" },
  // standard written form, and পড়া vs পরা.
  { name: "colloquial-form", text: "আমি কালকে বাজারে যাবো না।", want: "NON_WORD" },
  { name: "wearing-not-reading", text: "সে শাড়ি পড়ে অনুষ্ঠানে গেল।", want: "HOMONYM" },
  // Correct prose. Each one is a specific way the detector has been wrong.
  { name: "clean-cholito", text: "সে তার বইটা পড়ছে।", want: null },
  { name: "clean-sadhu", text: "তিনি বাজারে গিয়া দুইটি আম কিনিলেন।", want: null },
  { name: "clean-sadhu-honorific", text: "তিনি আসিয়াছিলেন এবং বসিয়াছিলেন।", want: null },
  { name: "clean-locative", text: "বইটি টেবিলে রাখা আছে।", want: null },
  { name: "clean-past-continuous", text: "আমরা কাজটা করছিলাম সারাদিন।", want: null },
  { name: "clean-deshi", text: "শীতকালে ঠান্ডা বাতাস বয়।", want: null },
  { name: "clean-abbrev", text: "তিনি ২০২৪ সালে Ph.D. সম্পন্ন করেছেন।", want: null },
  // The corrected forms of every error case above, plus the near-misses each
  // rule is most likely to trip on.
  { name: "clean-verb-person", text: "আমি ভাত খাইব।", want: null },
  { name: "clean-participle", text: "আমি সন্ধ্যায় বাড়ি ফিরে এলাম।", want: null },
  { name: "clean-two-clauses", text: "আমি বললাম, তিনি আসবেন।", want: null },
  { name: "clean-classifier", text: "তিনি একজন বিদুষী নারী।", want: null },
  { name: "clean-quantifier", text: "সব ছাত্র মাঠে খেলছে।", want: null },
  { name: "clean-genitive-plural", text: "সব ছাত্রদের বই এসেছে।", want: null },
  { name: "clean-standard-form", text: "আমি কাল বাজারে যাব না।", want: null },
  { name: "clean-reading", text: "সে বই পড়ে ঘুমিয়ে পড়ল।", want: null },
  { name: "clean-future", text: "আমি বই পড়ব।", want: null },
  { name: "clean-saree", text: "আমি শাড়ি পরে বিদ্যালয়ে যাব।", want: null },
];

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

const main = async () => {
  const browser = await launch();
  const context = await browser.newContext({ viewport: VIEWPORT, locale: "bn-BD" });
  const page = await context.newPage();

  const consoleErrors = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text().slice(0, 200));
  });

  // The response the app received, not one this script fetched itself — the
  // point is to prove the round trip the user gets.
  let latest = null;
  page.on("response", async (r) => {
    if (!r.url().includes("/api/check")) return;
    try {
      latest = { status: r.status(), body: await r.json() };
    } catch {
      latest = { status: r.status(), body: null };
    }
  });

  await page.goto(`${BASE}/editor`, { waitUntil: "networkidle" });
  const editor = page.locator(".bs-editor .ProseMirror");
  // Wait for the editor to mount. Clicking before it does silently types into
  // nothing, and every case then "passes" its way to zero flags.
  await editor.waitFor({ state: "visible", timeout: 30000 });

  let failures = 0;
  for (const c of CASES) {
    latest = null;
    await editor.click();
    await page.keyboard.press("Control+A");
    await page.keyboard.press("Delete");
    await page.keyboard.type(c.text);

    // Debounce is 600 ms; a cold Hunspell suggester run is slower, and the very
    // first request after a dev-server recompile can take far longer than
    // either. Wait for the response rather than guessing at a delay.
    const budgetMs = 45000;
    const deadline = Date.now() + budgetMs;
    while (!latest && Date.now() < deadline) await page.waitForTimeout(200);
    await page.waitForTimeout(600); // let React paint the decorations
    if (!latest) throw new Error(`${c.name}: no /api/check response in ${budgetMs}ms`);

    const classes = (latest.body?.edits ?? []).map((e) => e.errorClass ?? e.error_class);
    const flags = await page.locator(".bs-flag").count();
    const outOfScope = await page.locator(".bs-unsupported").count();

    const ok = c.want
      ? latest.status === 200 && classes.includes(c.want) && flags > 0
      : latest.status === 200 && classes.length === 0 && flags === 0;
    if (!ok) failures += 1;

    console.log(
      `${ok ? "ok  " : "FAIL"} ${c.name.padEnd(22)} http=${latest.status} ` +
        `flags=${flags} oos=${outOfScope} classes=[${classes.join(",")}]  ${c.text}`,
    );
  }

  // --- mobile layout ------------------------------------------------------
  //
  // The desktop cases above pass on a phone too — the checker does not care
  // about viewport width — and the layout was broken there anyway: the middle
  // column kept its desktop three-row grid inside a 60vh box, so the pane
  // holding "why was this flagged" was given less height than one wrapped line
  // and cut the explanation off mid-sentence.
  //
  // Nothing above would have caught it. These assertions are about geometry:
  // no sideways scroll, and no element hiding content behind overflow:hidden.
  const phone = await browser.newContext({
    viewport: { width: 390, height: 844 },
    locale: "bn-BD",
    isMobile: true,
    hasTouch: true,
  });
  const small = await phone.newPage();
  small.setDefaultTimeout(60000);

  let mobileFailures = 0;
  for (const path of ["/", "/editor", "/analytics"]) {
    await small.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded" });

    if (path === "/editor") {
      const box = small.locator(".bs-editor .ProseMirror");
      await box.waitFor({ state: "visible" });
      await box.click();
      await small.keyboard.type("সব ছাত্ররা মাঠে খেলছে। এর কারন কী কেউ জানে না।");
      await small.waitForSelector(".bs-flag");
      // Select a row: the detail pane is empty until something is chosen, and
      // an empty pane cannot demonstrate that it no longer clips.
      const row = small.locator("table.tbl tbody tr").first();
      if (await row.count()) await row.click();
    }
    await small.waitForTimeout(1200);

    const geometry = await small.evaluate(() => {
      const de = document.documentElement;

      // Panes squeezed to a sliver. This is the shape the bug took: the pane
      // was still *scrollable*, so nothing overflowed by the usual test — it
      // was simply too short to show a line of text, and the explanation
      // appeared cut in half. Height is the honest measure, not overflow.
      const slivers = [];
      document.querySelectorAll(".panel").forEach((el) => {
        const box = el.getBoundingClientRect();
        if (box.height > 0 && box.height < 48 && el.textContent.trim()) {
          slivers.push(
            `${el.tagName}.${String(el.className).slice(0, 40)} h=${Math.round(box.height)}`,
          );
        }
      });

      // The pane that answers "why was this flagged" must show its answer,
      // not scroll it inside a box the size of one line.
      const detail = document.querySelector("[data-testid=detail-pane]");
      const detailCut =
        detail && detail.scrollHeight > detail.clientHeight + 2
          ? `detail-pane content=${detail.scrollHeight} box=${detail.clientHeight}`
          : null;

      const wide = [...document.querySelectorAll("*")]
        .filter((el) => el.getBoundingClientRect().right > window.innerWidth + 1)
        .slice(0, 5)
        .map((el) => `${el.tagName}.${String(el.className).slice(0, 40)}`);

      return {
        hScroll: de.scrollWidth > de.clientWidth + 1,
        wide,
        slivers: slivers.slice(0, 5),
        detailCut,
        detailFound: Boolean(detail),
      };
    });

    const ok =
      !geometry.hScroll && geometry.slivers.length === 0 && !geometry.detailCut;
    if (!ok) mobileFailures += 1;
    console.log(
      `${ok ? "ok  " : "FAIL"} mobile ${path.padEnd(16)} ` +
        `hScroll=${geometry.hScroll} slivers=${geometry.slivers.length}` +
        (path === "/editor" ? ` detail=${geometry.detailFound ? "shown" : "MISSING"}` : ""),
    );
    if (geometry.detailCut) console.log(`        ${geometry.detailCut}`);
    for (const entry of geometry.slivers) console.log(`        sliver: ${entry}`);
    for (const entry of geometry.wide) console.log(`        overflows: ${entry}`);
  }

  await browser.close();

  if (mobileFailures) {
    console.error(`${mobileFailures} mobile layout failure(s)`);
    process.exitCode = 1;
  }

  if (consoleErrors.length) {
    console.error("\nCONSOLE ERRORS:");
    consoleErrors.forEach((e) => console.error("  " + e));
    process.exitCode = 1;
  } else {
    console.log("\nno console errors");
  }

  console.log(`${failures} failure(s) of ${CASES.length}`);
  if (failures) process.exitCode = 1;
};

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
