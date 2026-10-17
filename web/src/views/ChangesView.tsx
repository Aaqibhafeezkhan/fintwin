import { useEffect, useState } from "react";
import { loadChanges, type ChangeWeek, type Changes, type Mover } from "../data";
import { prettyName } from "../format";
import { Delta, IconExternal, Metric, Section, Skeleton, Status } from "../ui";

const FEED = `${import.meta.env.BASE_URL}data/feed.xml`;

function MoverRow({ m, onOpen }: { m: Mover; onOpen: (t: string) => void }) {
  return (
    <tr>
      <td>
        <button className="btn-link" onClick={() => onOpen(m.ticker)} style={{ fontFamily: "var(--font-mono)" }}>{m.ticker}</button>
        <div className="sub">{prettyName(m.name)}</div>
      </td>
      <td className="num"><Status health={m.health_before} label={m.health_before.toFixed(0)} /></td>
      <td className="num"><Status health={m.health_after} label={m.health_after.toFixed(0)} /></td>
      <td className="num"><Delta value={m.delta} fmt={(x) => x.toFixed(0)} suffix="pts" /></td>
      <td>
        {m.drivers.length ? m.drivers.slice(0, 2).map((d) => (
          <div key={d.component}>{d.label} <span className="sub">{d.points > 0 ? "+" : "−"}{Math.abs(d.points).toFixed(1)} pts</span></div>
        )) : <span className="sub">components not recorded last week</span>}
      </td>
      <td>{m.new_filing ? <>new quarter <span className="sub">{m.quarter}</span></> : <span className="sub">no new filing: rates, macro regime or model update</span>}</td>
    </tr>
  );
}

function Week({ w, onOpen, threshold }: { w: ChangeWeek; onOpen: (t: string) => void; threshold: number }) {
  return (
    <>
      <div className="metrics" style={{ ["--n" as string]: 4, marginBottom: 20 }}>
        <Metric label="Weaker" value={w.n_weaker} format={(v) => v.toFixed(0)} foot={`health down ${threshold}+ points`} />
        <Metric label="Stronger" value={w.n_stronger} format={(v) => v.toFixed(0)} foot={`health up ${threshold}+ points`} />
        <Metric label="New quarterly filings" value={w.n_new_filings} format={(v) => v.toFixed(0)} foot="10-Q / 10-K since last week" />
        <Metric label="Companies compared" value={w.n_companies} format={(v) => v.toFixed(0)} foot={w.previous ? `against the ${w.previous} build` : "against last week"} />
      </div>
      {w.movers.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Company</th><th className="num">Health before</th><th className="num">Now</th><th className="num">Change</th><th>What moved it</th><th>Why now</th></tr>
            </thead>
            <tbody>{w.movers.map((m) => <MoverRow key={m.ticker} m={m} onOpen={onOpen} />)}</tbody>
          </table>
        </div>
      ) : (
        <p className="callout">No company's baseline health moved by {threshold} points or more this week.
          {w.new_filings.length > 0 && <> {w.new_filings.length} companies filed new quarters: {w.new_filings.slice(0, 12).map((f) => f.ticker).join(", ")}{w.new_filings.length > 12 ? "…" : ""}.</>}
        </p>
      )}
    </>
  );
}

/** What changed since last Monday's rebuild, and which part of the health score moved. */
export function ChangesView({ onOpen }: { onOpen: (t: string) => void }) {
  const [data, setData] = useState<Changes | null | undefined>(undefined);
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => { loadChanges().then(setData); }, []);
  if (data === undefined) return <Skeleton h={420} />;
  const [latest, ...earlier] = data?.weeks ?? [];
  return (
    <>
      <Section eyebrow="This week" title="What changed since last Monday"
        right={<a className="btn-link" href={FEED} target="_blank" rel="noreferrer">RSS feed <IconExternal /></a>}>
        <p className="lede">Every Monday all twins are rebuilt from the newest SEC filings and FRED data. This page compares the new
          build with the previous one, lists the companies whose baseline health moved materially, and shows which part of the score
          moved it: liquidity runway, interest coverage, leverage or solvency.</p>
      </Section>
      {!latest ? (
        <p className="callout">The first comparison appears after the next weekly rebuild.</p>
      ) : (
        <Section eyebrow={`Week of ${latest.date}`}><Week w={latest} onOpen={onOpen} threshold={data!.threshold} /></Section>
      )}
      {earlier.length > 0 && (
        <Section eyebrow="Earlier weeks">
          {earlier.map((w) => (
            <div key={w.date} style={{ borderTop: "1px solid var(--rule)", padding: "10px 0" }}>
              <button className="btn-link" aria-expanded={open === w.date} onClick={() => setOpen(open === w.date ? null : w.date)}>
                {w.date}: {w.n_weaker} weaker, {w.n_stronger} stronger, {w.n_new_filings} new filings
              </button>
              {open === w.date && <div style={{ marginTop: 14 }}><Week w={w} onOpen={onOpen} threshold={data!.threshold} /></div>}
            </div>
          ))}
        </Section>
      )}
      <p className="muted" style={{ marginTop: 18, maxWidth: 760 }}>Health is the twin's baseline score (0 to 100) with no stress scenario.
        A component's contribution is its change times its weight in the score. Moves without a new filing come from interest rates, the
        recession regime or an update of the model.</p>
    </>
  );
}
