import type { Knobs, Levers, Params } from "./engine/types";

export type PresetSummary = {
  health_score: number; health_p10: number; p_breach: number; p_icr_below_1_5: number;
  p_downgrade_below_ig: number; median_quarters_to_breach: number | null; rating_dist: number[];
  bands?: Record<string, number[][]>; p_breach_by_q?: number[];
};

export type ReverseItem = { label: string; unit: "pct" | "bp" | "pp"; p10: number | null; p50: number | null };

export type Company = {
  ticker: string; name: string; cik: number; sector: string; edgar_url: string;
  quality: {
    quarters: number; first: string; last: string; balance_sheet_identity_max_gap_pct: number;
    core_completeness_last20_pct: number; maturity_ladder_date: string | null; maturity_ladder_stale: boolean;
    notes: string[]; missing_by_field_last20: Record<string, number>;
  };
  params: Params;
  history: {
    dates: string[];
    series: Record<"revenue" | "ebitda" | "net_income" | "cfo" | "capex" | "fcf" | "cash" | "debt" | "equity" | "icr"
      | "nd_ebitda" | "rating", (number | null)[]>;
    provenance: Record<string, (string | null)[]>;
  };
  presets: Record<string, PresetSummary>;
  reverse_stress: Record<string, ReverseItem>;
  tornado: { knob: string; value: number; label: string; d_health: number; d_p_breach: number }[];
};

export type Meta = {
  generated: string; horizon: number;
  ratings: { labels: string[]; icr_lower: (number | null)[]; spreads: number[] };
  knobs: Record<string, { default: number; desc: string }>;
  presets: Record<string, { label: string; desc: string; knobs: Knobs }>;
  levers: Levers;
};

export type IndexEntry = {
  name: string; sector: string; showcase: boolean; last_quarter: string;
  matrix: Record<string, { health: number; p_breach: number }>;
};
export type Index = { companies: Record<string, IndexEntry>; meta: Meta };

type Bands = number[][];
export type ForecastBacktest = {
  ticker: string; cutoff: string; cutoff_label: string; stress: string; last_quarter_known: string; horizon: number;
  scores: Record<string, { n: number; coverage50: number; coverage90: number; stress_coverage90: number; crps: number;
    crps_baseline: number; crps_skill: number; pit: number[] }>;
  series: Record<string, { history: { dates: string[]; values: number[] }; realized: { dates: string[]; values: (number | null)[] };
    base_bands: Bands; stress_bands: Bands }>;
  structural: { dates: string[]; actual_cum_fcf: number[]; model_cum_fcf_bands: Bands; final_error_pct: number;
    corr: number | null } | Record<string, never>;
  pre_shock: Record<"base" | "stress", { health_score: number; p_breach: number; p_icr_below_1_5: number;
    p_downgrade_below_ig: number }>;
};
export type CrossRow = {
  ticker: string; name: string; health_base: number; health_stress: number; p_breach_stress: number;
  realized_burn_ratio: number | null; realized_debt_raise_pct_rev: number; realized_min_cum_fcf_pct_rev: number | null;
};
export type Backtest = {
  cutoffs: Record<string, { date: string; label: string; stress: string }>;
  forecast: Record<string, ForecastBacktest>;
  aggregate: Record<string, { coverage50: number; coverage90: number; median_crps_skill: number;
    share_beating_baseline: number; cases: number }>;
  cross_section: { cutoff: string; rows: CrossRow[]; stats: Record<string, { spearman: number; p_value: number; n: number }>;
    failed: Record<string, string> };
};

const base = import.meta.env.BASE_URL;
const cache = new Map<string, Promise<unknown>>();
function getJson<T>(path: string): Promise<T> {
  if (!cache.has(path)) {
    cache.set(path, fetch(`${base}${path}`).then((r) => {
      if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
      return r.json();
    }));
  }
  return cache.get(path) as Promise<T>;
}

export const loadIndex = () => getJson<Index>("data/index.json");
export const loadBacktest = () => getJson<Backtest>("data/backtest.json");

/** Snapshot first; fall back to the optional local live API (`python -m fintwin.api`) for unseen tickers. */
export async function loadCompany(ticker: string): Promise<Company> {
  try {
    return await getJson<Company>(`data/companies/${ticker}.json`);
  } catch {
    cache.delete(`data/companies/${ticker}.json`);
    const r = await fetch(`/api/company/${encodeURIComponent(ticker)}`);
    if (!r.ok) throw new Error(r.status === 404 ? `No snapshot for ${ticker}. Start the live API to fetch any ticker.` : `Live API error ${r.status}`);
    return r.json();
  }
}
