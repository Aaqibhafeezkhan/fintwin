/**
 * Cross-implementation parity: the TypeScript engine must reproduce the Python reference engine
 * on golden runs (same parameters, scenario, levers and pre-drawn shocks).
 */
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { simulate } from "./model";
import { buildScenario } from "./scenario";
import { drawShocks } from "./shocks";
import { summarize } from "./summary";
import type { Levers, Outputs, Params } from "./types";

const DIR = join(__dirname, "__golden__");
const files = readdirSync(DIR).filter((f) => f.endsWith(".json"));

describe("parity with Python engine", () => {
  it("has golden cases", () => expect(files.length).toBeGreaterThan(0));

  for (const f of files) {
    it(f, () => {
      const g = JSON.parse(readFileSync(join(DIR, f), "utf-8"));
      const p: Params = g.params;
      const eps3d: number[][][] = g.eps;
      const N = eps3d.length, T = p.horizon;
      const eps = new Float64Array(N * T * 4);
      eps3d.forEach((path, n) => path.forEach((q, t) => q.forEach((v, k) => (eps[(n * T + t) * 4 + k] = v))));
      const out = simulate(p, buildScenario(g.knobs, T), eps, N, g.levers as Levers);
      let worst = 0;
      for (const [key, rows] of Object.entries(g.expected as Record<string, number[][]>)) {
        const got = out[key as keyof Outputs] as Float64Array;
        rows.forEach((row, n) => row.forEach((want, t) => {
          const have = got[n * T + t];
          const rel = Math.abs(have - want) / Math.max(Math.abs(want), 1);
          worst = Math.max(worst, rel);
          if (rel > 1e-6) throw new Error(`${key}[${n},${t}] ts=${have} py=${want}`);
        }));
      }
      expect(worst).toBeLessThan(1e-6);
    });
  }
});

describe("browser shock generator", () => {
  const p = JSON.parse(readFileSync(join(DIR, files[0]), "utf-8")).params as Params;
  it("is reproducible per seed and has unit variance", () => {
    const a = drawShocks(p, 4000, 12, 1), b = drawShocks(p, 4000, 12, 1);
    expect(a).toEqual(b);
    for (let k = 0; k < 4; k++) {
      let s = 0, s2 = 0;
      const n = a.length / 4;
      for (let i = 0; i < n; i++) { s += a[i * 4 + k]; s2 += a[i * 4 + k] ** 2; }
      expect(Math.abs(s / n)).toBeLessThan(0.05);
      expect(Math.abs(s2 / n - 1)).toBeLessThan(0.12);
    }
  });
  it("runs 5,000 paths fast and summarizes", () => {
    const t0 = performance.now();
    const eps = drawShocks(p, 5000, p.horizon, 7);
    const out = simulate(p, buildScenario({ sales_depth: 0.3 }, p.horizon), eps, 5000, {
      cut_capex: true, cut_payouts: true, issue_debt: true, draw_revolver: true, issue_equity: false, cut_costs: true,
    });
    const s = summarize(out);
    const ms = performance.now() - t0;
    expect(s.healthScore).toBeGreaterThanOrEqual(0);
    expect(ms).toBeLessThan(2000);
  });
});
