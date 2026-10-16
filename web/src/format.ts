export function money(x: number | null | undefined, digits = 1): string {
  if (x == null || !Number.isFinite(x)) return "–";
  const a = Math.abs(x), s = x < 0 ? "−" : "";
  if (a >= 1e12) return `${s}$${(a / 1e12).toFixed(digits)}T`;
  if (a >= 1e9) return `${s}$${(a / 1e9).toFixed(digits)}B`;
  if (a >= 1e6) return `${s}$${(a / 1e6).toFixed(0)}M`;
  return `${s}$${a.toFixed(0)}`;
}

/** Axis ticks: compact and clean. */
export function moneyTick(x: number): string {
  const a = Math.abs(x), s = x < 0 ? "−" : "";
  if (a >= 1e9) return `${s}${+(a / 1e9).toFixed(a >= 1e10 ? 0 : 1)}B`;
  if (a >= 1e6) return `${s}${+(a / 1e6).toFixed(0)}M`;
  return `${s}${a}`;
}

export const pct = (x: number | null | undefined, digits = 0) =>
  x == null || !Number.isFinite(x) ? "–" : `${(x * 100).toFixed(digits)}%`;

export const fixed = (x: number | null | undefined, digits = 1) =>
  x == null || !Number.isFinite(x) ? "–" : x.toFixed(digits);

export function quarterLabel(iso: string): string {
  const d = new Date(iso + "T00:00:00Z");
  const q = Math.floor(((d.getUTCMonth() + 12 - 0) % 12) / 3) + 1;
  return `Q${q} '${String(d.getUTCFullYear()).slice(2)}`;
}

/** Quarter-end labels for the simulated horizon, continuing from the last reported quarter. */
export function futureQuarters(lastIso: string, T: number): string[] {
  const d = new Date(lastIso + "T00:00:00Z");
  const out: string[] = [];
  for (let t = 1; t <= T; t++) {
    const m = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 3 * t, 15));
    out.push(`Q${Math.floor(m.getUTCMonth() / 3) + 1} '${String(m.getUTCFullYear()).slice(2)}`);
  }
  return out;
}

export type Status = { key: "good" | "warning" | "serious" | "critical"; label: string; icon: string };
export function healthStatus(h: number): Status {
  if (h >= 70) return { key: "good", label: "Healthy", icon: "●" };
  if (h >= 50) return { key: "warning", label: "Watch", icon: "▲" };
  if (h >= 30) return { key: "serious", label: "Strained", icon: "◆" };
  return { key: "critical", label: "Distressed", icon: "■" };
}

const SUFFIX: Record<string, string> = { INC: "Inc.", "INC.": "Inc.", CORP: "Corp.", "CORP.": "Corp.", CO: "Co.", "CO.": "Co.", LTD: "Ltd.", "LTD.": "Ltd.", PLC: "plc", LLC: "LLC" };
const SMALL = new Set(["OF", "AND", "THE", "&"]);
/** SEC registrant names arrive in capitals ("BOEING CO"); show them the way a newspaper would ("Boeing Co."). */
export function prettyName(name: string): string {
  if (/[a-z]/.test(name)) return name;
  return name.split(/\s+/).map((w, i) => {
    const u = w.toUpperCase().replace(/,$/, "");
    if (SUFFIX[u]) return SUFFIX[u] + (w.endsWith(",") ? "," : "");
    if (i > 0 && SMALL.has(u)) return u === "&" ? "&" : u.toLowerCase();
    if (/[&\d]/.test(w) || w.length <= 2) return w;
    return w.charAt(0) + w.slice(1).toLowerCase();
  }).join(" ");
}

/** Keyboard hint for the company switcher: ⌘K on Apple devices, Ctrl K elsewhere. */
export const shortcutLabel = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent) ? "⌘K" : "Ctrl K";
