export type Params = {
  ticker: string; name: string; last_quarter: string; horizon: number; history_quarters: number;
  seasonal: number[]; season0: number; base_rev0: number;
  mu: number; phi: number; sigma_g: number; g0: number; t_df: number; rho_gm: number;
  F: number; v: number; rho_m: number; sigma_m: number; infl: number;
  target_margin: number; cut_delay: number; cut_speed: number; cut_floor: number;
  dso: number; dio: number; dpo: number; ddays: number; tau_ar: number; tau_inv: number;
  dep_rate: number; capex_ratio: number; maint_capex: number; sbc_ratio: number; ocf_ratio: number;
  tax_rate: number; coupon: number; floating: number; refi_ratio: number; sigma_fin: number; cash_target: number;
  div_q: number; bb_ratio: number; revolver_cap: number; cash_floor: number; maturities_q: number[];
  r0: number; term_premium: number; kappa: number; theta: number; sigma_r: number;
  cash0: number; ar0: number; inv0: number; ap0: number; def0: number; ppe0: number; debt0: number;
  equity0: number; other_net0: number; other_liab0: number; wc_other0: number; retained0: number;
  ebit_ttm0: number[]; ebitda_ttm0: number[]; interest_ttm0: number[];
  _sources: Record<string, string>;
};

export type Knobs = Partial<{
  sales_depth: number; sales_duration: number; sales_recovery: number; rate_bp: number; spread_bp: number;
  spread_duration: number; cost_pp: number; cost_duration: number; dio_days: number; refi_freeze: number;
}>;

export type Levers = {
  cut_capex: boolean; cut_payouts: boolean; issue_debt: boolean; draw_revolver: boolean;
  issue_equity: boolean; cut_costs: boolean;
};

export type Scenario = {
  sales_shock: Float64Array; rate_shift: Float64Array; spread_shift: Float64Array;
  cost_shift: Float64Array; dio_shift: Float64Array; refi_access: Float64Array;
};

export const OUTPUT_KEYS = [
  "revenue", "ebitda", "ebit", "net_income", "cfo", "fcf", "capex", "cash", "debt", "revolver", "liquidity",
  "interest", "icr", "nd_ebitda", "rating", "zscore", "health", "breach", "equity", "issued", "fixed_cost_mult",
  "debt_issued",
] as const;
export type OutputKey = (typeof OUTPUT_KEYS)[number];
/** Each output is a row-major [N * T] matrix (path-major). */
export type Outputs = Record<OutputKey, Float64Array> & { N: number; T: number };
