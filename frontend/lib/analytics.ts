/**
 * Local analytics, in IndexedDB.
 *
 * PRIVACY IS THE DESIGN CONSTRAINT, not a footnote. Spec §10: "no text
 * persisted server-side unless the user explicitly saves it." This store goes
 * further — it never records text at all, on the server or locally. Every field
 * below is a count or a class name. There is no `text`, no `original`, no
 * `suggestion`, and adding one would turn a private feature into a keystroke
 * log sitting in the user's browser.
 *
 * IndexedDB rather than localStorage because this is append-mostly time-series
 * data that gets range-queried by date; localStorage would mean parsing the
 * whole history on every write.
 *
 * A dedicated backend can replace this later. The shape here is deliberately
 * one that a server could ingest unchanged: flat rows, a date key, a device id.
 */

const DB_NAME = "bhashasetu";
const DB_VERSION = 1;
const STORE = "events";

export type EventType = "check" | "accept" | "ignore";

export interface AnalyticsEvent {
  id?: number;
  type: EventType;
  /** Local calendar day, YYYY-MM-DD. Local, not UTC — "today" means the user's
   *  today, and a UTC key puts an evening's work on tomorrow's row. */
  day: string;
  ts: number;
  /** Words in the document at the time of the check. Counts only. */
  words?: number;
  sentences?: number;
  issues?: number;
  outOfScope?: number;
  /** Error class, for accept/ignore events. A taxonomy label, not content. */
  errorClass?: string;
}

export function dayKey(d: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

let dbPromise: Promise<IDBDatabase> | null = null;

function open(): Promise<IDBDatabase> {
  if (typeof indexedDB === "undefined") {
    return Promise.reject(new Error("IndexedDB unavailable"));
  }
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, {
          keyPath: "id",
          autoIncrement: true,
        });
        store.createIndex("day", "day", { unique: false });
        store.createIndex("ts", "ts", { unique: false });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return dbPromise;
}

export async function record(event: Omit<AnalyticsEvent, "id" | "day" | "ts">) {
  try {
    const db = await open();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.objectStore(STORE).add({ ...event, day: dayKey(), ts: Date.now() });
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch {
    // Analytics must never break the app. Private mode, a quota error, or a
    // browser with IndexedDB disabled all end up here and are all survivable.
  }
}

export async function allEvents(): Promise<AnalyticsEvent[]> {
  try {
    const db = await open();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readonly");
      const req = tx.objectStore(STORE).getAll();
      req.onsuccess = () => resolve(req.result as AnalyticsEvent[]);
      req.onerror = () => reject(req.error);
    });
  } catch {
    return [];
  }
}

export async function clearAll(): Promise<void> {
  try {
    const db = await open();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.objectStore(STORE).clear();
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch {
    /* nothing to clear */
  }
}

// ---------------------------------------------------------------------------
// Aggregation

export interface Summary {
  checks: number;
  words: number;
  issues: number;
  accepted: number;
  ignored: number;
  outOfScope: number;
  /** accepted / (accepted + ignored). NaN-free: 0 when nothing was decided. */
  acceptRate: number;
}

const EMPTY: Summary = {
  checks: 0,
  words: 0,
  issues: 0,
  accepted: 0,
  ignored: 0,
  outOfScope: 0,
  acceptRate: 0,
};

/**
 * Words are summed as a **per-day maximum**, not a running total.
 *
 * A check fires every 600 ms while typing, so summing `words` across events
 * would report a 200-word document as tens of thousands of words. The high-water
 * mark for a day is a defensible proxy for "how much was written" and, crucially,
 * does not inflate with editing time. It undercounts someone who writes several
 * separate documents in a day — an honest limitation, and the safer direction.
 */
export function summarise(events: AnalyticsEvent[]): Summary {
  if (!events.length) return { ...EMPTY };

  const maxWordsPerDay = new Map<string, number>();
  const out: Summary = { ...EMPTY };

  for (const e of events) {
    if (e.type === "check") {
      out.checks += 1;
      out.issues += e.issues ?? 0;
      out.outOfScope += e.outOfScope ?? 0;
      const prev = maxWordsPerDay.get(e.day) ?? 0;
      if ((e.words ?? 0) > prev) maxWordsPerDay.set(e.day, e.words ?? 0);
    } else if (e.type === "accept") {
      out.accepted += 1;
    } else if (e.type === "ignore") {
      out.ignored += 1;
    }
  }

  out.words = [...maxWordsPerDay.values()].reduce((a, b) => a + b, 0);
  const decided = out.accepted + out.ignored;
  out.acceptRate = decided ? out.accepted / decided : 0;
  return out;
}

/** Inclusive lower bound, in local days. */
function since(daysBack: number): string {
  const d = new Date();
  d.setDate(d.getDate() - daysBack);
  return dayKey(d);
}

export interface Buckets {
  today: Summary;
  week: Summary;
  month: Summary;
  daily: { day: string; words: number; issues: number; accepted: number }[];
  byClass: { errorClass: string; accepted: number; ignored: number }[];
  total: number;
}

export function bucket(events: AnalyticsEvent[]): Buckets {
  const t = dayKey();
  const w = since(6); // rolling 7 days including today
  const m = since(29);

  const daysIndex = new Map<
    string,
    { day: string; words: number; issues: number; accepted: number }
  >();
  for (let i = 13; i >= 0; i--) {
    const key = since(i);
    daysIndex.set(key, { day: key, words: 0, issues: 0, accepted: 0 });
  }

  for (const e of events) {
    const row = daysIndex.get(e.day);
    if (!row) continue;
    if (e.type === "check") {
      row.issues += e.issues ?? 0;
      row.words = Math.max(row.words, e.words ?? 0); // same high-water rule
    } else if (e.type === "accept") {
      row.accepted += 1;
    }
  }

  const classMap = new Map<string, { accepted: number; ignored: number }>();
  for (const e of events) {
    if (!e.errorClass) continue;
    const entry = classMap.get(e.errorClass) ?? { accepted: 0, ignored: 0 };
    if (e.type === "accept") entry.accepted += 1;
    if (e.type === "ignore") entry.ignored += 1;
    classMap.set(e.errorClass, entry);
  }

  return {
    today: summarise(events.filter((e) => e.day === t)),
    week: summarise(events.filter((e) => e.day >= w)),
    month: summarise(events.filter((e) => e.day >= m)),
    daily: [...daysIndex.values()],
    byClass: [...classMap.entries()]
      .map(([errorClass, v]) => ({ errorClass, ...v }))
      .sort((a, b) => b.accepted + b.ignored - (a.accepted + a.ignored)),
    total: events.length,
  };
}
