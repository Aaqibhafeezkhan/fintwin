/**
 * TypeScript port of engine/fintwin/model/sd_model.py — the same stock-and-flow model, stepped quarterly.
 * Kept line-for-line comparable with the Python reference; parity is enforced by model.test.ts against
 * golden runs exported from Python with identical shocks.
 */
import { ratingRank, SPREADS } from "./ratings";
import { OUTPUT_KEYS, type Levers, type Outputs, type Params, type Scenario } from "./types";

const DAYS_Q = 91.25;
const clip = (x: number, lo: number, hi: number) => Math.min(Math.max(x, lo), hi);
const sum4 = (a: number[]) => a[0] + a[1] + a[2] + a[3];

export const SHOCK_COLS = 5;

/** eps is a flat [N * T * 5] array (path-major, then quarter, then shock column). */
export function simulate(p: Params, scn: Scenario, eps: Float64Array, N: number, levers: Levers): Outputs {
  const T = p.horizon;
  const out = Object.fromEntries(OUTPUT_KEYS.map((k) => [k, new Float64Array(N * T)])) as unknown as Outputs;
  out.N = N;
  out.T = T;
  const ladder = p.maturities_q;
  const floor = p.cash_floor;

  for (let n = 0; n < N; n++) {
    let cash = p.cash0, ar = p.ar0, inv = p.inv0, ap = p.ap0, deferred = p.def0, ppe = p.ppe0, debt = p.debt0;
    let revolver = 0, equity = p.equity0, otherNet = p.other_net0, retEarn = p.retained0;
    let base = p.base_rev0, gPrev = p.g0, mDev = 0, rate = p.r0, coupon = p.coupon, cutMult = 1, lowCount = 0;
    const ebitHist = [...p.ebit_ttm0], ebitdaHist = [...p.ebitda_ttm0], intHist = [...p.interest_ttm0];
    let breached = false;
    let regime = p.rec_state0 ?? 0;

    for (let t = 0; t < T; t++) {
      const o = (n * T + t) * SHOCK_COLS;
      const eG = eps[o], eM = eps[o + 1], eR = eps[o + 2], eD = eps[o + 3], u = eps[o + 4];

      // macro regime: Markov switching between expansion and recession (NBER base rates)
      if (levers.recessions) regime = regime > 0 ? (u < p.rec_exit ? 0 : 1) : (u < p.rec_hazard ? 1 : 0);
      else regime = 0;

      // revenue: AR(1) growth in deseasonalized level, then season and scenario shock
      const vol = p.sigma_g * (1 + (p.rec_vol_mult - 1) * regime);
      const g = p.mu + p.phi * (gPrev - p.mu) + vol * eG + p.rec_drift * regime;
      base = base * Math.exp(g);
      gPrev = g;
      const rev = base * p.seasonal[(p.season0 + t) % 4] * (1 + scn.sales_shock[t]);

      // costs: fixed (inflating, cuttable) + variable ratio with mean-reverting shocks
      mDev = p.rho_m * mDev + p.sigma_m * eM;
      const v = Math.max(p.v + mDev + scn.cost_shift[t], 0);
      const fixed = p.F * Math.pow(1 + p.infl, t + 1) * cutMult;
      const costs = fixed + v * rev;
      const ebitda = rev - costs;
      const da = p.dep_rate * ppe;
      const ebit = ebitda - da;

      // rates and credit spread (R1: spread follows last TTM coverage)
      rate = rate + p.kappa * (p.theta - rate) + p.sigma_r * eR;
      const rEff = Math.max(rate + scn.rate_shift[t], 0);
      const icrPrev = sum4(ebitHist) / Math.max(sum4(intHist), 1e-9);
      const spread = SPREADS[ratingRank(icrPrev)] + scn.spread_shift[t];
      const mktRate = rEff + p.term_premium + spread;

      const effRate = (1 - p.floating) * coupon + p.floating * (rEff + spread);
      const interest = (debt * effRate) / 4 + (revolver * (rEff + spread + 0.015)) / 4;
      const intIncome = (Math.max(cash, 0) * rEff * 0.9) / 4;
      const ebt = ebit - interest + intIncome;
      const tax = p.tax_rate * Math.max(ebt, 0);
      const ni = ebt - tax;

      // working capital with first-order delays on receivables and inventory
      const arNew = ar + ((p.dso / DAYS_Q) * rev - ar) / p.tau_ar;
      const invTarget = (Math.max(p.dio + scn.dio_shift[t], 0) / DAYS_Q) * costs;
      const invNew = inv + (invTarget - inv) / p.tau_inv;
      const apNew = (p.dpo / DAYS_Q) * costs;
      const defNew = (p.ddays / DAYS_Q) * rev;
      const dNwc = arNew - ar + (invNew - inv) - (apNew - ap) - (defNew - deferred);
      ar = arNew; inv = invNew; ap = apNew; deferred = defNew;

      const sbc = p.sbc_ratio * rev;
      const otherCfo = p.ocf_ratio * rev;
      const cfo = ni + da + sbc - dNwc + otherCfo;
      otherNet = otherNet - otherCfo;

      // B1: stress triggers management responses
      const stressed = cash < 1.5 * p.cash_floor || icrPrev < 2.5;
      let capex = p.capex_ratio * rev;
      if (levers.cut_capex && stressed) capex = Math.min(capex, p.maint_capex * da);
      ppe = ppe + capex - da;

      let div = p.div_q;
      let bb = p.bb_ratio * Math.max(cfo - capex, 0);
      if (levers.cut_payouts && stressed) { div = 0; bb = 0; }

      // debt: maturities, rollover, new issuance (R2: access shrinks with coverage)
      const maturing = Math.min(ladder[t], debt);
      const access = (icrPrev >= 1.5 ? 1 : icrPrev >= 0.8 ? 0.6 : 0.3) * scn.refi_access[t];
      const refi = maturing * p.refi_ratio * access;
      cash = cash + cfo - capex - div - bb - maturing + refi;
      let issuedDebt = 0;
      if (levers.issue_debt) {
        issuedDebt = Math.max(p.cash_target - cash, 0) * access;
        cash = cash + issuedDebt;
      }
      let disc = p.sigma_fin * debt * eD;
      disc = disc > 0 ? disc * access : -Math.min(-disc, Math.max(cash - p.cash_target, 0));
      cash = cash + disc;
      issuedDebt = issuedDebt + Math.max(disc, 0);
      const remaining = debt - maturing + Math.min(disc, 0);
      const newDebt = remaining + refi + issuedDebt;
      if (newDebt > 0) coupon = (coupon * remaining + mktRate * (refi + issuedDebt)) / Math.max(newDebt, 1e-9);
      debt = newDebt;

      // liquidity backstops: revolver, then equity
      const draw = levers.draw_revolver ? clip(floor - cash, 0, Math.max(p.revolver_cap - revolver, 0)) : 0;
      const repay = cash > p.cash_target ? Math.min(revolver, cash - p.cash_target) : 0;
      revolver = revolver + draw - repay;
      cash = cash + draw - repay;
      // cash sweep: idle cash far above the treasury target pays down debt
      const sweep = Math.min(Math.max(cash - p.cash_cap, 0), debt);
      debt = debt - sweep;
      cash = cash - sweep;
      let issued = 0;
      if (levers.issue_equity) {
        issued = access > 0 ? Math.max(floor - cash, 0) : 0;
        cash = cash + issued;
      }
      equity = equity + ni + sbc - div - bb + issued;
      retEarn = retEarn + ni - div;

      // B2: sustained margin squeeze -> fixed-cost cuts after a delay
      const margin = ebitda / Math.max(rev, 1e-9);
      lowCount = margin < p.target_margin ? lowCount + 1 : 0;
      if (levers.cut_costs) {
        cutMult = lowCount >= p.cut_delay ? Math.max(cutMult - p.cut_speed, p.cut_floor)
          : Math.min(cutMult + 0.5 * p.cut_speed, 1);
      }

      // rolling TTM metrics
      ebitHist.shift(); ebitHist.push(ebit);
      ebitdaHist.shift(); ebitdaHist.push(ebitda);
      intHist.shift(); intHist.push(interest);
      const ebitTtm = sum4(ebitHist);
      const icr = ebitTtm / Math.max(sum4(intHist), 1e-9);
      const ebitdaTtm = sum4(ebitdaHist);
      const netDebt = debt + revolver - cash;
      const ndEbitda = ebitdaTtm > 0 ? netDebt / Math.max(ebitdaTtm, 1e-9) : 99;
      const rank = ratingRank(icr);
      const undrawn = Math.max(p.revolver_cap - revolver, 0);
      const liquidity = cash + undrawn;
      breached = breached || cash < 0;

      // Altman Z'' (book-value version)
      const assets = cash + ar + inv + ppe + otherNet + p.other_liab0;
      const liabilities = Math.max(assets - equity, 1e-9);
      const workingCap = cash + ar + inv - ap - deferred + p.wc_other0;
      const z = (6.56 * workingCap + 3.26 * retEarn + 6.72 * ebitTtm) / Math.max(assets, 1e-9)
        + (1.05 * equity) / liabilities;

      // health score 0-100
      const burn = Math.max(fixed + interest + ladder[Math.min(t + 1, T - 1)] * (1 - access), 1e-9);
      const sLiq = clip(liquidity / burn / 8, 0, 1) * 100;
      // sector tolerance: score leverage-heavy sectors against their own norms (dynamics use raw coverage)
      const tol = p.sector_tol ?? 1;
      const sCov = (ratingRank(icr * tol) / 14) * 100;
      const levCap = 6 * tol;
      const sLev = (ebitdaTtm > 0 ? clip((levCap - ndEbitda) / levCap, 0, 1) : 0) * 100;
      const sSolv = clip((z - 1.1) / 1.5, 0, 1) * 100;
      let health = 0.3 * sLiq + 0.3 * sCov + 0.2 * sLev + 0.2 * sSolv;
      if (breached) health = Math.min(health, 25);

      const i = n * T + t;
      out.revenue[i] = rev; out.ebitda[i] = ebitda; out.ebit[i] = ebit; out.net_income[i] = ni;
      out.cfo[i] = cfo; out.fcf[i] = cfo - capex; out.capex[i] = capex; out.cash[i] = cash; out.debt[i] = debt;
      out.revolver[i] = revolver; out.liquidity[i] = liquidity; out.interest[i] = interest; out.icr[i] = icr;
      out.nd_ebitda[i] = ndEbitda; out.rating[i] = rank; out.zscore[i] = z; out.health[i] = health;
      out.breach[i] = breached ? 1 : 0; out.equity[i] = equity; out.issued[i] = issued;
      out.fixed_cost_mult[i] = cutMult; out.debt_issued[i] = issuedDebt; out.recession[i] = regime;
      out.h_liq[i] = sLiq; out.h_cov[i] = sCov; out.h_lev[i] = sLev; out.h_solv[i] = sSolv;
    }
  }
  return out;
}
