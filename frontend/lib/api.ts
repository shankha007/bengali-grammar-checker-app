import type {
  BijoyResponse,
  CheckResponse,
  ErrorClassInfo,
  LanguageInfo,
} from "./types";

/**
 * `credentials: "include"` everywhere: the anonymous device cookie is httpOnly
 * (spec §5) and would otherwise never be sent.
 */
async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* response had no JSON body; the status line is all we get */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export interface CheckOptions {
  minConfidence?: number;
  includeSuppressed?: boolean;
  signal?: AbortSignal;
}

export function check(text: string, opts: CheckOptions = {}) {
  return json<CheckResponse>("/api/check", {
    method: "POST",
    signal: opts.signal,
    body: JSON.stringify({
      text,
      language: "bn",
      minConfidence: opts.minConfidence ?? 0.55,
      includeSuppressed: opts.includeSuppressed ?? false,
      includeReadability: true,
    }),
  });
}

export const getClasses = () => json<ErrorClassInfo[]>("/api/classes");
export const getLanguages = () => json<LanguageInfo[]>("/api/languages");
export const getIdentity = () =>
  json<{ deviceId: string; tier: string }>("/api/identity");
export const mintRecovery = () =>
  json<{ phrase: string; words: number }>("/api/identity/recovery", {
    method: "POST",
  });
export const convertBijoy = (text: string) =>
  json<BijoyResponse>("/api/convert/bijoy", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
