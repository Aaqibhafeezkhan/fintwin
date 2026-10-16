import type { Knobs, Scenario } from "./types";

export const KNOB_DEFAULTS: Required<Knobs> = {
  sales_depth: 0, sales_duration: 2, sales_recovery: 6, rate_bp: 0, spread_bp: 0, spread_duration: 4,
  cost_pp: 0, cost_duration: 4, dio_days: 0, refi_freeze: 0,
};

/** Mirror of fintwin.scenarios.presets.build_scenario. */
export function buildScenario(knobs: Knobs, T: number): Scenario {
  const k = { ...KNOB_DEFAULTS, ...knobs };
  const depth = k.sales_depth;
  const hold = Math.trunc(k.sales_duration);
  const rec = Math.max(Math.trunc(k.sales_recovery), 1);
  const s: Scenario = {
    sales_shock: new Float64Array(T), rate_shift: new Float64Array(T), spread_shift: new Float64Array(T),
    cost_shift: new Float64Array(T), dio_shift: new Float64Array(T), refi_access: new Float64Array(T),
  };
  for (let i = 0; i < T; i++) {
    if (i < hold) s.sales_shock[i] = -depth;
    else if (i < hold + rec) s.sales_shock[i] = -depth * (1 - (i - hold + 1) / (rec + 1));
    const ramp = Math.min((i + 1) / 2, 1);
    s.rate_shift[i] = (k.rate_bp / 1e4) * ramp;
    s.spread_shift[i] = i < Math.trunc(k.spread_duration) ? k.spread_bp / 1e4 : 0;
    s.cost_shift[i] = i < Math.trunc(k.cost_duration) ? k.cost_pp / 100 : 0;
    s.dio_shift[i] = k.dio_days;
    s.refi_access[i] = i < Math.trunc(k.refi_freeze) ? 0 : 1;
  }
  // The demand shock hits revenue gradually: the first quarter takes half the blow.
  if (T && hold > 1) s.sales_shock[0] = -depth * 0.5;
  return s;
}
