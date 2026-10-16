import { INVESTMENT_GRADE_MIN_RANK, RATINGS } from "./ratings";
import type { OutputKey, Outputs } from "./types";

export const BANDS = [5, 25, 50, 75, 95] as const;
export const BAND_VARS = ["revenue", "ebitda", "fcf", "cash", "liquidity", "debt", "icr", "nd_ebitda", "health",
  "zscore", "interest"] as const satisfies readonly OutputKey[];

/** numpy-style percentile with linear interpolation on a sorted copy. */
export function percentile(sorted: Float64Array, q: number): number {
  const pos = ((sorted.length - 1) * q) / 100;
  const lo = Math.floor(pos), hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

function column(m: Float64Array, N: number, T: number, t: number): Float64Array {
  const c = new Float64Array(N);
  for (let n = 0; n < N; n++) c[n] = m[n * T + t];
  return c;
}

export type Summary = {
  bands: Record<(typeof BAND_VARS)[number], number[][]>; // [band][t]
  pBreachByQ: number[];
  pRecessionByQ: number[];
  components: { liq: number; cov: number; lev: number; solv: number };
  healthMean: number;
  pBreach: number;
  pIcrBelow15: number;
  pSubIG: number;
  ratingDist: number[];
  healthScore: number;
  healthP10: number;
  healthHist: number[]; // histogram of path-average health, 20 bins of 5 points
  medianQuartersToBreach: number | null;
  minLiquidityBands: number[];
  equityNeededMedian: number;
  debtIssuedMedian: number;
  samplePaths: { cash: number[][]; health: number[][] };
};

export function summarize(o: Outputs, nSample = 40): Summary {
  const { N, T } = o;
  const bands = {} as Summary["bands"];
  for (const k of BAND_VARS) {
    bands[k] = BANDS.map(() => new Array(T).fill(0));
    for (let t = 0; t < T; t++) {
      const col = column(o[k], N, T, t).sort();
      BANDS.forEach((b, j) => (bands[k][j][t] = percentile(col, b)));
    }
  }
  const pBreachByQ = Array.from({ length: T }, (_, t) => {
    let s = 0;
    for (let n = 0; n < N; n++) s += o.breach[n * T + t];
    return s / N;
  });
  const pRecessionByQ = Array.from({ length: T }, (_, t) => {
    let s = 0;
    for (let n = 0; n < N; n++) s += o.recession[n * T + t];
    return s / N;
  });
  const mean = (a: Float64Array) => { let s = 0; for (let i = 0; i < a.length; i++) s += a[i]; return s / a.length; };
  const components = { liq: mean(o.h_liq), cov: mean(o.h_cov), lev: mean(o.h_lev), solv: mean(o.h_solv) };
  const healthMean = mean(o.health);
  const ratingDist = new Array(RATINGS.length).fill(0);
  let icrLow = 0, subIG = 0, eqSum: number[] = [], debtSum: number[] = [];
  const healthMean = new Float64Array(N), minLiq = new Float64Array(N);
  const breachQ: number[] = [];
  for (let n = 0; n < N; n++) {
    const last = n * T + T - 1;
    ratingDist[Math.max(o.rating[last], 0)] += 1 / N;
    if (o.rating[last] < INVESTMENT_GRADE_MIN_RANK) subIG++;
    let h = 0, ml = Infinity, mi = Infinity, eq = 0, dbt = 0, fb = -1;
    for (let t = 0; t < T; t++) {
      const i = n * T + t;
      h += o.health[i];
      ml = Math.min(ml, o.liquidity[i]);
      mi = Math.min(mi, o.icr[i]);
      eq += o.issued[i];
      dbt += o.debt_issued[i];
      if (fb < 0 && o.breach[i]) fb = t;
    }
    healthMean[n] = h / T;
    minLiq[n] = ml;
    if (mi < 1.5) icrLow++;
    eqSum.push(eq);
    debtSum.push(dbt);
    if (fb >= 0) breachQ.push(fb);
  }
  const hs = Float64Array.from(healthMean).sort();
  const ml = Float64Array.from(minLiq).sort();
  const med = (a: number[]) => percentile(Float64Array.from(a).sort(), 50);
  const healthHist = new Array(20).fill(0);
  healthMean.forEach((h) => (healthHist[Math.min(Math.floor(h / 5), 19)] += 1 / N));
  const pick = Array.from({ length: Math.min(nSample, N) }, (_, j) => Math.floor((j * N) / Math.min(nSample, N)));
  return {
    bands, pBreachByQ, pRecessionByQ, components, healthMean, pBreach: pBreachByQ[T - 1], pIcrBelow15: icrLow / N, pSubIG: subIG / N, ratingDist,
    healthScore: percentile(hs, 50), healthP10: percentile(hs, 10), healthHist,
    medianQuartersToBreach: breachQ.length ? med(breachQ) : null,
    minLiquidityBands: BANDS.map((b) => percentile(ml, b)),
    equityNeededMedian: med(eqSum), debtIssuedMedian: med(debtSum),
    samplePaths: {
      cash: pick.map((n) => Array.from(o.cash.subarray(n * T, n * T + T))),
      health: pick.map((n) => Array.from(o.health.subarray(n * T, n * T + T))),
    },
  };
}
