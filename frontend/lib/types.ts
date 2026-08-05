/**
 * Wire types. Mirrors `src/bhashasetu/api/models.py`.
 *
 * `Edit` matches the interface in the master spec §1 exactly, so the shape the
 * editor consumes is the shape the pipeline was designed to emit.
 */

export type ErrorCategory =
  | "orthography"
  | "morphology"
  | "syntax"
  | "register"
  | "punctuation";

export interface Edit {
  id: string;
  /** Character offset into the NORMALIZED text, not the text you sent. */
  start: number;
  end: number;
  original: string;
  /** Ranked, best first. May be empty — some errors have no single fix. */
  suggestions: string[];
  errorClass: string;
  category: ErrorCategory;
  confidence: number;
  stage: 0 | 1 | 2 | 3 | 4;
  explanation_bn: string;
  explanation_en: string;
  ruleReference: string | null;
}

export interface StageReport {
  stage: number;
  name: string;
  edits: number;
  ms: number;
  /** Non-null means the stage does not exist yet. Not "found nothing". */
  skipped: string | null;
}

export interface OutOfScopeSpan {
  start: number;
  end: number;
  text: string;
  /** Lowercased Unicode script name, e.g. "latin". A label, not a guarantee. */
  script: string;
}

export interface CheckResponse {
  language: string;
  normalized: string;
  normalizedDiffers: boolean;
  appliedRules: string[];
  edits: Edit[];
  suppressed: Edit[];
  sentences: { index: number; start: number; end: number }[];
  /** Runs the engine did not judge. Never errors — see backend scope.py. */
  outOfScope: OutOfScopeSpan[];
  stages: StageReport[];
  stageDistribution: Record<string, number>;
  totalMs: number;
  readability: Record<string, number> | null;
  readabilityMissing: string[];
}

export interface ErrorClassInfo {
  code: string;
  category: ErrorCategory;
  label_native: string;
  label_en: string;
  ruleReference: string | null;
  /** null = declared and evaluated, but no detector yet. */
  implementedAtStage: number | null;
}

export interface LanguageInfo {
  code: string;
  nameEn: string;
  nameNative: string;
  lexiconSize: number;
  dictionary: "hunspell" | "seed";
}

export interface BijoyResponse {
  text: string;
  detected: boolean;
  coverage: number;
  converted: boolean;
  note: string | null;
}

export const CATEGORY_LABEL: Record<ErrorCategory, { bn: string; en: string }> = {
  orthography: { bn: "বানান", en: "Spelling" },
  morphology: { bn: "রূপ", en: "Morphology" },
  syntax: { bn: "বাক্যগঠন", en: "Syntax" },
  register: { bn: "রীতি", en: "Register" },
  punctuation: { bn: "যতিচিহ্ন", en: "Punctuation" },
};

/**
 * Resolved from CSS variables, not hard-coded, so the five themes can each pick
 * category hues that stay legible against their own background.
 */
export const CATEGORY_VAR: Record<ErrorCategory, string> = {
  orthography: "var(--cat-orthography)",
  morphology: "var(--cat-morphology)",
  syntax: "var(--cat-syntax)",
  register: "var(--cat-register)",
  punctuation: "var(--cat-punctuation)",
};
