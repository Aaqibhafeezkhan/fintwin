import { useEffect, useState } from "react";
import { loadMemo, type Memo } from "../data";
import { Card } from "../ui";

const VERDICT_STATUS: Record<Memo["verdict"], { key: string; icon: string }> = {
  Strong: { key: "good", icon: "●" }, Adequate: { key: "good", icon: "●" }, Watch: { key: "warning", icon: "▲" },
  Weak: { key: "serious", icon: "◆" }, Distressed: { key: "critical", icon: "■" },
};

export function MemoCard({ ticker }: { ticker: string }) {
  const [memo, setMemo] = useState<Memo | null | undefined>(undefined);
  const [showSheet, setShowSheet] = useState(false);
  useEffect(() => { setMemo(undefined); loadMemo(ticker).then(setMemo); }, [ticker]);
  if (memo === undefined) return null;
  if (memo === null) return null; // memos are generated at build time; companies without one simply omit the card
  const v = VERDICT_STATUS[memo.verdict];
  return (
    <Card title={<>AI analyst memo <span className="pill" style={{ marginLeft: 8 }}><span aria-hidden style={{ color: `var(--${v.key})`, fontSize: 10 }}>{v.icon}</span>{memo.verdict}</span></>}
      sub={`Written by ${memo.generated_by} from the twin's fact sheet · every figure machine-checked against it`}>
      <p style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>{memo.headline}</p>
      <p className="sub">{memo.summary}</p>
      <div className="grid g2" style={{ marginTop: 14 }}>
        <div>
          <h3 style={{ marginBottom: 6 }}>Key risks</h3>
          <ul style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 8 }}>
            {memo.key_risks.map((r, i) => <li key={i}><b>{r.risk}</b><div className="muted">{r.evidence}</div></li>)}
          </ul>
        </div>
        <div>
          <h3 style={{ marginBottom: 6 }}>Resilience</h3>
          <ul style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 6 }} className="sub">
            {memo.resilience.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
          <h3 style={{ margin: "14px 0 6px" }}>Watch list</h3>
          <ul style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 6 }} className="sub">
            {memo.watch_list.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      </div>
      <h3 style={{ margin: "14px 0 6px" }}>Scenario notes</h3>
      <div className="table-wrap">
        <table><tbody>
          {memo.scenario_notes.map((s, i) => <tr key={i}><td style={{ width: 170, fontWeight: 600 }}>{s.scenario}</td><td className="sub">{s.note}</td></tr>)}
        </tbody></table>
      </div>
      <div className="muted" style={{ marginTop: 10, display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <span>{memo.unverified_numbers.length === 0 ? "✓ All figures verified against the fact sheet" : `⚠ ${memo.unverified_numbers.length} figure(s) could not be verified: ${memo.unverified_numbers.join(", ")}`}</span>
        <span>· data as of {memo.as_of}</span>
        <button className="btn" onClick={() => setShowSheet(!showSheet)}>{showSheet ? "Hide" : "Show"} fact sheet</button>
      </div>
      {showSheet && <pre className="eq" style={{ marginTop: 10, maxHeight: 360, overflow: "auto" }}>{JSON.stringify(memo.fact_sheet, null, 1)}</pre>}
    </Card>
  );
}
