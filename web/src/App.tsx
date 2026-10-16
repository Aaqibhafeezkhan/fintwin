import { useEffect, useState } from "react";
import { loadCompany, loadIndex, type Company, type Index } from "./data";
import { useHashState } from "./hooks";
import { BacktestView } from "./views/BacktestView";
import { CompareView } from "./views/CompareView";
import { MachineView } from "./views/MachineView";
import { MethodView } from "./views/MethodView";
import { StressLab } from "./views/StressLab";
import { TwinView } from "./views/TwinView";

const TABS = [
  ["twin", "Company twin"], ["stress", "Stress lab"], ["machine", "The machine"],
  ["compare", "Stress matrix"], ["backtest", "Backtest"], ["method", "Method"],
] as const;
const COMPANY_TABS = new Set(["twin", "stress", "machine"]);

function useTheme() {
  const [theme, setTheme] = useState<string | null>(() => {
    try { return localStorage.getItem("theme"); } catch { return null; }
  });
  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
    try { if (theme) localStorage.setItem("theme", theme); } catch { /* storage unavailable */ }
  }, [theme]);
  const dark = theme ? theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  return [dark, () => setTheme(dark ? "light" : "dark")] as const;
}

export default function App() {
  const [route, setRoute] = useHashState("twin/CCL");
  const [view, tickerRaw, presetRaw] = route.split("/");
  const ticker = (tickerRaw || "CCL").toUpperCase();
  const [index, setIndex] = useState<Index | null>(null);
  const [company, setCompany] = useState<Company | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dark, toggleTheme] = useTheme();

  useEffect(() => { loadIndex().then(setIndex).catch((e) => setError(String(e))); }, []);
  useEffect(() => {
    setError(null);
    loadCompany(ticker).then((c) => setCompany(c)).catch((e) => setError(String(e.message ?? e)));
  }, [ticker]);

  const go = (v: string, t = ticker, p?: string) => setRoute([v, t, p].filter(Boolean).join("/"));
  const groups = index ? Object.entries(index.companies).sort((a, b) => a[0].localeCompare(b[0])) : [];

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark" aria-hidden>
            <svg width="18" height="18" viewBox="0 0 32 32"><path d="M5 22l7-7 5 5 10-11" stroke="white" strokeWidth="3.5" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </div>
          <div>
            <h1>FinTwin</h1>
            <small>Corporate financial health digital twin</small>
          </div>
        </div>
        <label className="company-picker">
          <span className="muted">Company</span>
          <select value={ticker} onChange={(e) => go(COMPANY_TABS.has(view) ? view : "twin", e.target.value)} aria-label="Company">
            <optgroup label="Showcase">
              {groups.filter(([, e]) => e.showcase).map(([t, e]) => <option key={t} value={t}>{t} · {e.name}</option>)}
            </optgroup>
            <optgroup label="Universe">
              {groups.filter(([, e]) => !e.showcase).map(([t, e]) => <option key={t} value={t}>{t} · {e.name}</option>)}
            </optgroup>
            {index && !index.companies[ticker] && <option value={ticker}>{ticker} (live)</option>}
          </select>
        </label>
        <form onSubmit={(e) => {
          e.preventDefault();
          const t = new FormData(e.currentTarget).get("t")?.toString().trim().toUpperCase();
          if (t) go(COMPANY_TABS.has(view) ? view : "twin", t);
        }}>
          <input type="search" name="t" placeholder="Any ticker…" aria-label="Load any ticker" size={11}
            title="Tickers outside the snapshot are built live by the local API (python -m fintwin.api)" />
        </form>
        <button className="icon-btn" onClick={toggleTheme} aria-label="Toggle dark mode" title="Toggle dark mode">{dark ? "☀" : "☾"}</button>
      </header>

      <nav className="tabs" role="tablist">
        {TABS.map(([k, label]) => (
          <button key={k} role="tab" className="tab" aria-selected={view === k} onClick={() => go(k)}>{label}</button>
        ))}
      </nav>

      {error && <div className="card loading">{error}</div>}
      {!index ? <div className="loading">Loading…</div> : (
        <main>
          {COMPANY_TABS.has(view) && (!company || company.ticker !== ticker) && !error && <div className="loading">Loading {ticker}…</div>}
          {view === "twin" && company?.ticker === ticker && <TwinView c={company} meta={index.meta} onStress={(p) => go("stress", ticker, p)} />}
          {view === "stress" && company?.ticker === ticker && (
            <StressLab key={ticker + (presetRaw ?? "")} c={company} meta={index.meta} preset={presetRaw ?? "pandemic"}
              setPreset={(p) => history.replaceState(null, "", `#${["stress", ticker, p].join("/")}`)} />
          )}
          {view === "machine" && company?.ticker === ticker && <MachineView c={company} meta={index.meta} />}
          {view === "compare" && <CompareView index={index} onOpen={(t) => go("twin", t)} />}
          {view === "backtest" && <BacktestView onOpen={(t) => go("twin", t)} />}
          {view === "method" && <MethodView />}
        </main>
      )}

      <footer className="footer">
        <span>Data: SEC EDGAR XBRL filings & FRED. Snapshot {index?.meta.generated}. Not investment advice.</span>
        <span>Python reference engine · TypeScript in-browser engine · parity-tested</span>
      </footer>
    </div>
  );
}
