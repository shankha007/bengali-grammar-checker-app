/**
 * UI strings. Data only — no components, so editing it never triggers a
 * Fast Refresh full reload of the tree that imports it.
 *
 * Bengali first in each pair because Bengali is the product's first language,
 * not its translation; the ordering makes an untranslated string obvious.
 *
 * NOT here: the grammar explanations. The backend returns `explanation_bn` and
 * `explanation_en` for every edit and the toggle picks which leads. A Bengali
 * grammar rule explained in English is a different sentence, not a translated
 * one, and it belongs beside the rule in `error_classes.yaml`.
 */
export const STRINGS = {
  brand: { bn: "ভাষাসেতু", en: "BhashaSetu" },
  brandAlt: { bn: "BhashaSetu", en: "ভাষাসেতু" },

  // nav
  navHome: { bn: "হোম", en: "Home" },
  navEditor: { bn: "সম্পাদক", en: "Editor" },
  navAnalytics: { bn: "পরিসংখ্যান", en: "Analytics" },

  checking: { bn: "পরীক্ষা হচ্ছে…", en: "Checking…" },
  words: { bn: "শব্দ", en: "words" },
  sentences: { bn: "বাক্য", en: "sentences" },
  issues: { bn: "সমস্যা", en: "issues" },

  sample: { bn: "নমুনা", en: "Sample" },
  sampleTitle: {
    bn: "ভুলসহ একটি নমুনা লেখা বসান — প্রতিবার নতুন",
    en: "Load a sample containing mistakes — a different one each click",
  },
  bijoy: { bn: "বিজয়", en: "Bijoy" },
  lowConfidence: { bn: "কম-নিশ্চিত", en: "low-conf" },
  thresholdTitle: {
    bn: "এই মাত্রার নিচের পরামর্শ দেখানো হবে না",
    en: "Suggestions below this confidence are hidden",
  },
  themeLabel: { bn: "থিম", en: "Theme" },
  languageLabel: { bn: "ভাষা", en: "Language" },
  bijoyTitle: {
    bn: "বিজয়/ANSI লেখা শনাক্ত করে ইউনিকোডে রূপান্তর",
    en: "Detect Bijoy/ANSI legacy encoding and convert to Unicode",
  },
  dismiss: { bn: "বন্ধ করুন", en: "dismiss" },

  // suggestion table
  colText: { bn: "শব্দ", en: "Text" },
  colFix: { bn: "পরামর্শ", en: "Fix" },
  colType: { bn: "ধরন", en: "Type" },
  colCategory: { bn: "শ্রেণি", en: "Category" },
  notChecked: { bn: "পরীক্ষা করা হয়নি", en: "not checked" },
  nothingToReport: { bn: "কোনো ভুল পাওয়া যায়নি", en: "Nothing to report." },
  acceptAria: { bn: "এই পরামর্শ গ্রহণ করুন", en: "Accept this suggestion" },
  ignoreAria: { bn: "এই পরামর্শ উপেক্ষা করুন", en: "Ignore this suggestion" },

  // detail pane
  selectRow: {
    bn: "কেন চিহ্নিত হয়েছে দেখতে একটি সারি বেছে নিন।",
    en: "Select a row to see why it was flagged.",
  },
  noAutoFix: {
    bn: "স্বয়ংক্রিয় সংশোধন নেই — এটি নিজে ঠিক করতে হবে।",
    en: "No automatic fix — this one needs a human.",
  },
  rule: { bn: "বিধান", en: "Rule" },
  acceptAll: { bn: "সবগুলো গ্রহণ করুন", en: "Accept all" },

  // tabs
  tabRead: { bn: "পঠন", en: "Read" },
  tabTypes: { bn: "ধরন", en: "Types" },
  tabStages: { bn: "স্তর", en: "Stages" },
  tabInfo: { bn: "তথ্য", en: "Info" },

  // readability
  readabilityHint: {
    bn: "/ ১০০ — বেশি মানে পড়তে সহজ",
    en: "/ 100 — higher is easier to read",
  },
  writeSomething: {
    bn: "স্কোর দেখতে কিছু লিখুন।",
    en: "Write something to see a score.",
  },
  syllablesPerWord: { bn: "প্রতি শব্দে অক্ষর", en: "Syllables per word" },
  tatsamaDensity: { bn: "তৎসম ঘনত্ব", en: "তৎসম density" },
  meanSentenceLength: { bn: "গড় বাক্যদৈর্ঘ্য", en: "Mean sentence length" },
  sentenceVariance: { bn: "বাক্যদৈর্ঘ্যের বৈচিত্র্য", en: "Sentence length variance" },
  wordCount: { bn: "শব্দসংখ্যা", en: "Word count" },
  sentenceCount: { bn: "বাক্যসংখ্যা", en: "Sentence count" },
  notComputed: { bn: "গণনা করা হয়নি", en: "Not computed" },
  readabilityCaveat: {
    bn: "— এর জন্য ডিপেন্ডেন্সি পার্সার দরকার, যা Phase 4-এ আসবে। এর ওজন অন্য উপাদানে ভাগ করে দেওয়া হয়েছে, শূন্য ধরা হয়নি। ধ্রুবকগুলো এখনো ক্যালিব্রেট করা হয়নি, তাই এটি খসড়ার তুলনায় আপেক্ষিক পাঠ — পাঠ্যস্তর নয়।",
    en: "— needs the dependency parser landing in Phase 4. Its weight is redistributed, not zeroed. The constants are uncalibrated, so read this as relative between drafts, not as a reading level.",
  },

  // pipeline
  noRunYet: { bn: "এখনো চালানো হয়নি।", en: "No run yet." },
  colStage: { bn: "স্তর", en: "Stage" },
  colEdits: { bn: "সংশোধন", en: "Edits" },
  pipelineNote: {
    bn: "স্তর ২–৪ এখনো তৈরি হয়নি — শুধু নীরব নয়। এগুলো skipped হিসেবে জানায়, যাতে না-করা কাজের কৃতিত্ব কেউ না পায়। মোট",
    en: "Stages 2–4 are not implemented, not merely quiet — they report as skipped so nothing credits them with work they did not do. Total",
  },

  // taxonomy
  colClass: { bn: "ভুলের ধরন", en: "Error class" },
  colFound: { bn: "পাওয়া গেছে", en: "Found" },
  otherScript: { bn: "অন্য লিপি — পরীক্ষা করা হয়নি", en: "other script — not checked" },
  activeAtStage: { bn: "সক্রিয়, স্তর", en: "active at stage" },
  noDetectorYet: { bn: "Phase 2 পর্যন্ত কোনো ডিটেক্টর নেই", en: "no detector until Phase 2" },

  // about
  privacyBn: {
    bn: "আপনার লেখা কোথাও সংরক্ষণ করা হয় না। কোনো লগইন নেই, কোনো ইমেল নেই।",
    en: "Your text is never stored on our servers. No login, no email, no signup.",
  },
  privacyMore: {
    bn: "প্রতিটি সুবিধা বিনামূল্যে। উত্তর পাঠানোর পরেই লেখা মুছে ফেলা হয়।",
    en: "Every feature is free. Text is discarded when the response is sent.",
  },
  dictionary: { bn: "অভিধান", en: "Dictionary" },
  // Shown across the top of the editor when the pack fell back to the seed
  // list. Silence here is the worst thing this app can do: without the real
  // dictionary every spelling flag is damped to 0.003 against a 0.55 gate, so
  // the checker reports misspelt Bengali as clean and looks perfectly healthy
  // doing it. Say it in the editor, not just in the About tab, because nobody
  // opens the About tab to find out why they were told nothing was wrong.
  seedLexiconWarning: {
    bn: "বানান পরীক্ষা বন্ধ আছে: বাংলা অভিধান লোড হয়নি, তাই এখন কেবল ব্যাকরণ ও যতিচিহ্নের ভুল ধরা পড়ছে। বানান ভুল থাকলেও দেখানো হবে না।",
    en: "Spell-checking is off: the Bengali dictionary did not load, so only grammar and punctuation are being checked. Misspellings will not be reported.",
  },
  device: { bn: "ডিভাইস", en: "Device" },
  generateRecovery: { bn: "পুনরুদ্ধার-বাক্য তৈরি করুন", en: "Generate recovery phrase" },
  recoveryNote: {
    bn: "বারোটি শব্দ, কোনো ইমেল বা পাসওয়ার্ড নেই। একবারই দেখানো হবে। এখনো সংরক্ষিত হয় না — হ্যাশ রাখা Phase 3-এর কাজ, তাই এটি এখন কিছু ফিরিয়ে আনবে না।",
    en: "Twelve words, no email, no password. Shown once. Not yet persisted — storing the hash is Phase 3 work, so this will not restore anything today.",
  },

  // editor + layout chrome
  editorAria: { bn: "লেখার জায়গা", en: "Bengali text editor" },
  resizeColumns: { bn: "কলামের প্রস্থ বদলান", en: "Resize columns" },
  resizeRows: { bn: "সারির উচ্চতা বদলান", en: "Resize rows" },
  resetSize: { bn: "ডবল-ক্লিকে আগের মাপে ফিরুন", en: "Double-click to reset" },
  outOfScopeTitle: {
    bn: "— এই লেখা বাংলা নয়। ইঞ্জিন এখানে কোনো মত দেয় না; চিহ্নিত করা হয়েছে, সংশোধন নয়।",
    en: "— not Bengali. The engine has no opinion here; it is highlighted, not corrected.",
  },

  // ---- landing -----------------------------------------------------------
  heroTitle: {
    bn: "বাংলা লেখার সহায়ক, যা কারণ ব্যাখ্যা করে",
    en: "A Bengali writing assistant that explains itself",
  },
  heroSub: {
    bn: "প্রতিটি সংশোধনের সঙ্গে বাংলায় ব্যাখ্যা ও ব্যাকরণের সূত্র দেওয়া হয় — কারণ ব্যাখ্যা করতে না পারলে সেটি দেখানোই হয় না।",
    en: "Every correction arrives with an explanation in Bengali and the grammar rule behind it. If the system cannot say why, it does not show the edit at all.",
  },
  heroPill1: { bn: "লগইন নেই", en: "No login" },
  heroPill2: { bn: "সম্পূর্ণ বিনামূল্যে", en: "Free, all of it" },
  heroPill3: { bn: "লেখা সংরক্ষণ করা হয় না", en: "Text never stored" },
  ctaStart: { bn: "লেখা শুরু করুন", en: "Start writing" },
  ctaAnalytics: { bn: "পরিসংখ্যান দেখুন", en: "View analytics" },
  featuresTitle: { bn: "কী কী আছে", en: "What it does" },
  featuresLede: {
    bn: "নিচের প্রতিটি সুবিধা এখনই কাজ করছে, সঙ্গে একটি করে বাস্তব উদাহরণ।",
    en: "Everything below works today, each with a worked example.",
  },
  exBefore: { bn: "যা লেখা হয়েছে", en: "Written" },
  exAfter: { bn: "যা হওয়া উচিত", en: "Corrected" },
  exUntouched: { bn: "স্পর্শ করা হয় না", en: "Left alone" },

  f1Title: { bn: "ণত্ব ও ষত্ব বিধান", en: "ণত্ব and ষত্ব rules" },
  f1Body: {
    bn: "তৎসম শব্দে ন-এর বদলে ণ এবং স-এর বদলে ষ কখন বসবে, সেই বিধান যাচাই করা হয়। ধরা পড়লে কেবল সংশোধন নয়, কোন উপবিধান লঙ্ঘিত হয়েছে তাও দেখানো হয়।",
    en: "Checks where তৎসম words require ণ instead of ন, and ষ instead of স. When something is flagged you get the specific clause of the বিধান that was broken, not just a replacement.",
  },
  f1Detail: {
    bn: "গুরুত্বপূর্ণ সীমারেখা: এই দুই বিধান কেবল তৎসম শব্দে খাটে। ঠান্ডা বা ভাসা-র মতো দেশি ও তদ্ভব শব্দে ন ও স-ই শুদ্ধ, তাই সেগুলোতে নিয়ম প্রয়োগ করা হয় না — যে ভুলটি প্যাটার্ন-মেলানো বানান-পরীক্ষক করে বসে।",
    en: "The boundary matters: both বিধান apply to তৎসম vocabulary only. In দেশি and তদ্ভব words such as ঠান্ডা and ভাসা, ন and স are already correct — so the rule is not applied there, which is precisely the mistake a pattern-matching checker makes.",
  },

  f2Title: { bn: "গুরুচণ্ডালী দোষ", en: "গুরুচণ্ডালী detection" },
  f2Body: {
    bn: "একই বাক্যে সাধু ও চলিত রীতি মিশে গেলে ধরা পড়ে, এবং সংখ্যালঘু রূপটিকে চিহ্নিত করা হয় — যাতে গোটা বাক্য নতুন করে লিখতে না হয়।",
    en: "Catches সাধু and চলিত forms mixed inside a single sentence, and flags the minority form — so you change a word, not the whole sentence.",
  },
  f2Detail: {
    bn: "সম্পূর্ণ সাধু বা সম্পূর্ণ চলিত লেখা ভুল নয়, তাই সেগুলো অস্পৃশ্য থাকে। গোটা লেখায় রীতি বদলাতে থাকলে সেটি আলাদা শ্রেণিতে একবারই জানানো হয়, প্রতিটি বাক্যে নয়।",
    en: "Consistently সাধু or consistently চলিত prose is correct and is left untouched. Drift across a whole document is reported separately and once, rather than as an error on every sentence.",
  },

  f3Title: { bn: "বানান ও অভিধান", en: "Spelling" },
  f3Body: {
    bn: "প্রায় ৮৮ হাজার শব্দমূলের bn_BD অভিধান ব্যবহার করা হয়, সঙ্গে প্রত্যয়-বিশ্লেষণ। বানান-প্রস্তাব সাজানো হয় ধ্বনিগত সাদৃশ্য অনুযায়ী।",
    en: "Backed by the ~88k-stem bn_BD dictionary with full affix expansion. Suggestions are ranked by phonetic similarity, not just edit distance.",
  },
  f3Detail: {
    bn: "বাংলার প্রত্যয় দীর্ঘ হতে পারে — বইগুলোকেও-এর মতো রূপ অভিধানে থাকে না, তবু শুদ্ধ। প্রত্যয় খুলে মূল শব্দ মিলিয়ে দেখা হয় বলে এগুলো ভুল বলে চিহ্নিত হয় না। আর যেহেতু আধুনিক বাংলায় শ/ষ/স বা ন/ণ-এর উচ্চারণ এক, ধ্বনি-সাদৃশ্যে সাজানো প্রস্তাব বাস্তব ভুলের অনেক কাছাকাছি পড়ে।",
    en: "Bengali agglutinates: বইগুলোকেও is in no dictionary and is perfectly correct. Affixes are stripped and the stem re-checked, so long inflected forms are not flagged. And because শ/ষ/স and ন/ণ are homophonous in modern Bengali, ranking candidates by sound puts the word the writer actually meant near the top.",
  },

  f4Title: { bn: "অন্য ভাষা চিহ্নিতকরণ", en: "Other scripts, marked not judged" },
  f4Body: {
    bn: "বাংলা নয় এমন অংশ হলুদ রঙে দেখানো হয় — ভুল হিসেবে নয়, বরং এখানে ইঞ্জিনের কোনো মত নেই বোঝাতে।",
    en: "Non-Bengali runs are highlighted in yellow — not as errors, but to say plainly that the engine has no opinion there.",
  },
  f4Detail: {
    bn: "নীরবতা আর অনুমোদন এক নয়। ইংরেজি অংশে সব নিয়মই চুপ থাকে, ফলে লেখকের দিক থেকে বোঝার উপায় থাকে না সেটি পরীক্ষা করে ঠিক বলা হয়েছে, নাকি এড়িয়ে যাওয়া হয়েছে। তাই দুটি আলাদা চিহ্ন: ঢেউখেলানো দাগ মানে ভুল মনে হচ্ছে, সমতল হলুদ মানে পড়াই হয়নি।",
    en: "Silence is not approval. Every rule is quiet on an English word, which from the writer's side is indistinguishable from having been checked and passed. So the two states get two different marks: a wavy underline means this looks wrong, a flat highlight means this was not read.",
  },

  f5Title: { bn: "যতিচিহ্ন", en: "Punctuation" },
  f5Body: {
    bn: "দাঁড়ির আগে বাড়তি ফাঁকা, বাংলা বাক্যের শেষে ইংরেজি ফুলস্টপ, বা পরপর একাধিক প্রশ্নচিহ্ন — এগুলো ধরা পড়ে।",
    en: "Catches a space before the dari, a Latin full stop ending a Bengali sentence, and repeated punctuation.",
  },
  f5Detail: {
    bn: "দাঁড়ি (।) বাংলা বাক্যের শেষচিহ্ন; ফুলস্টপ নয়। তবু সংক্ষিপ্ত রূপ, দশমিক সংখ্যা ও ওয়েব-ঠিকানায় ফুলস্টপ শুদ্ধ — Ph.D. বা ১০.৩০ বা example.com কখনো চিহ্নিত হয় না।",
    en: "The dari (।) ends a Bengali sentence; a period does not. But a period is correct inside abbreviations, decimals and URLs — so Ph.D., ১০.৩০ and example.com are never flagged.",
  },

  f6Title: { bn: "পঠনযোগ্যতা", en: "Readability" },
  f6Body: {
    bn: "বাংলার জন্য তৈরি স্কোর, Flesch-Kincaid-এর অনুবাদ নয়। প্রতিটি উপাদান আলাদা করে দেখানো হয়, একটিমাত্র অস্বচ্ছ সংখ্যা নয়।",
    en: "A score built for Bengali rather than a ported Flesch-Kincaid, with every component shown instead of one opaque number.",
  },
  f6Detail: {
    bn: "ইংরেজিতে শব্দের দৈর্ঘ্য কঠিনতার সঙ্কেত; বাংলায় তা কেবল প্রত্যয়ের দৈর্ঘ্য মাপে। বাংলায় আসল সঙ্কেত তৎসম শব্দের ঘনত্ব। অক্ষর গোনার সময় অন্তর্নিহিত অ-ধ্বনিও ধরা হয়, যা কোথাও লেখা থাকে না — লাতিন লিপির জন্য তৈরি গণনা এই জায়গাতেই ভুল করে।",
    en: "In English, word length signals difficulty; in Bengali it mostly measures agglutination. The real signal is তৎসম density. Syllable counting also accounts for the inherent vowel, which is never written — the thing a Latin-trained counter has no way to know.",
  },

  f7Title: { bn: "আপনার লেখা আপনারই", en: "Your text stays yours" },
  f7Body: {
    bn: "কোনো লগইন নেই, ইমেল নেই, সাইনআপ নেই। উত্তর পাঠানোর পরেই আপনার লেখা মুছে ফেলা হয়।",
    en: "No login, no email, no signup. Your text is discarded the moment the response is sent.",
  },
  f7Detail: {
    bn: "পরিসংখ্যানও আপনার ব্রাউজারেই IndexedDB-তে থাকে, কোনো সার্ভারে নয় — এবং সেখানে কেবল সংখ্যা ও ভুলের শ্রেণির নাম রাখা হয়। লেখা রাখার মতো কোনো ঘরই সেখানে নেই।",
    en: "Your analytics live in your own browser via IndexedDB, never on a server — and that store holds only counts and error-class names. It has no field that could contain your text.",
  },

  f8Title: { bn: "আপনার মতো করে সাজানো", en: "Built to sit out of your way" },
  f8Body: {
    bn: "পাঁচটি থিম, টেনে আকার বদলানো যায় এমন প্যানেল, আর ইংরেজি ও বাংলার মধ্যে ইন্টারফেস বদলের সুবিধা।",
    en: "Five themes, panes you can drag to resize, and an interface that switches between Bengali and English.",
  },
  f8Detail: {
    bn: "উঁচু-বৈসাদৃশ্যের থিমটি দেখতে সুন্দর হওয়ার জন্য নয়, WCAG মেনে চলার জন্য। প্যানেলের মাপ কি-বোর্ড দিয়েও বদলানো যায়, এবং এত ছোট করা যায় না যাতে আর ফিরে পাওয়া না যায়।",
    en: "The high-contrast theme exists for WCAG rather than for looks. Panes resize by keyboard as well as by drag, and cannot be dragged small enough to become unrecoverable.",
  },

  // ---- analytics ---------------------------------------------------------
  analyticsTitle: { bn: "আপনার পরিসংখ্যান", en: "Your analytics" },
  analyticsIntro: {
    bn: "সব হিসাব আপনার ব্রাউজারে IndexedDB-তে রাখা — কোনো সার্ভারে যায় না, এবং আপনার লেখা কখনোই সংরক্ষিত হয় না, শুধু সংখ্যা।",
    en: "Everything here lives in your browser's IndexedDB. Nothing is sent to a server, and your text is never stored — only counts.",
  },
  today: { bn: "আজ", en: "Today" },
  thisWeek: { bn: "এই সপ্তাহ", en: "This week" },
  thisMonth: { bn: "এই মাস", en: "This month" },
  mChecks: { bn: "পরীক্ষা", en: "Checks" },
  mWords: { bn: "শব্দ লেখা", en: "Words written" },
  mIssues: { bn: "সমস্যা পাওয়া", en: "Issues found" },
  mAccepted: { bn: "গৃহীত", en: "Accepted" },
  mIgnored: { bn: "উপেক্ষিত", en: "Ignored" },
  mAcceptRate: { bn: "গ্রহণের হার", en: "Acceptance rate" },
  last14: { bn: "গত ১৪ দিন", en: "Last 14 days" },
  byClass: { bn: "ধরন অনুযায়ী", en: "By error class" },
  noData: {
    bn: "এখনো কোনো তথ্য নেই। সম্পাদকে কিছু লিখলে এখানে দেখা যাবে।",
    en: "No data yet. Write something in the editor and it will show up here.",
  },
  clearData: { bn: "সব তথ্য মুছুন", en: "Clear all data" },
  clearConfirm: {
    bn: "সব পরিসংখ্যান মুছে ফেলা হবে। এটি ফেরানো যাবে না।",
    en: "This deletes all analytics. It cannot be undone.",
  },
  storageNote: {
    bn: "ভবিষ্যতে ডেডিকেটেড ব্যাকএন্ড এলে এটি সরানো যাবে; এখন সব কিছু স্থানীয়।",
    en: "A dedicated backend can replace this later; for now everything is local.",
  },
} as const;

export type StringKey = keyof typeof STRINGS;
export type Lang = "bn" | "en";
