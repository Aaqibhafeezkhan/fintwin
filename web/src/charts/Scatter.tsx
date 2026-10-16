import { scaleLinear } from "d3-scale";
import { useState } from "react";
import { useSize } from "../hooks";

export type Pt = { id: string; x: number; y: number; label: string; detail: string; group?: number };

/** Two-variable scatter, one series color, selective direct labels for the extremes. */
export function Scatter({ points, xLabel, yLabel, xFmt, yFmt, labelIds = [], onClick }: {
  points: Pt[]; xLabel: string; yLabel: string; xFmt: (x: number) => string; yFmt: (y: number) => string;
  labelIds?: string[]; onClick?: (id: string) => void;
}) {
  const [ref, width] = useSize<HTMLDivElement>();
  const [hover, setHover] = useState<string | null>(null);
  const H = 340, M = { l: 52, r: 16, t: 14, b: 40 };
  const xs = points.map((p) => p.x), ys = points.map((p) => p.y);
  const x = scaleLinear().domain([Math.min(0, ...xs), Math.max(...xs)]).nice().range([M.l, width - M.r]);
  const y = scaleLinear().domain([Math.min(...ys), Math.max(0, ...ys)]).nice().range([H - M.b, M.t]);
  const hp = points.find((p) => p.id === hover);
  return (
    <div className="chart" ref={ref}>
      {width > 0 && (
        <svg width={width} height={H} role="img" aria-label={`${yLabel} versus ${xLabel}`}>
          {y.ticks(5).map((t) => (
            <g key={t}>
              <line className="gridline" x1={M.l} x2={width - M.r} y1={y(t)} y2={y(t)} />
              <text className="tick" x={M.l - 8} y={y(t)} dy="0.32em" textAnchor="end">{yFmt(t)}</text>
            </g>
          ))}
          {x.ticks(5).map((t) => <text key={t} className="tick" x={x(t)} y={H - M.b + 16} textAnchor="middle">{xFmt(t)}</text>)}
          <line className="baseline" x1={M.l} x2={width - M.r} y1={y(0)} y2={y(0)} />
          <text className="tick" x={(M.l + width - M.r) / 2} y={H - 4} textAnchor="middle" style={{ fill: "var(--ink-2)" }}>{xLabel}</text>
          <text className="tick" transform={`translate(12 ${(M.t + H - M.b) / 2}) rotate(-90)`} textAnchor="middle" style={{ fill: "var(--ink-2)" }}>{yLabel}</text>
          {points.map((p) => (
            <g key={p.id} style={{ cursor: onClick ? "pointer" : undefined }}
              onPointerEnter={() => setHover(p.id)} onPointerLeave={() => setHover(null)} onClick={() => onClick?.(p.id)}>
              <circle cx={x(p.x)} cy={y(p.y)} r={12} fill="transparent" />
              <circle cx={x(p.x)} cy={y(p.y)} r={hover === p.id ? 6 : 5} fill="var(--s1)" stroke="var(--surface)" strokeWidth={2} />
              {(labelIds.includes(p.id) || hover === p.id) && (
                <text x={x(p.x) + 8} y={y(p.y) - 7} fontSize={11} fill="var(--ink-2)">{p.label}</text>
              )}
            </g>
          ))}
        </svg>
      )}
      {hp && (
        <div className="tooltip" style={{ left: Math.min(x(hp.x) + 14, width - 220), top: Math.max(y(hp.y) - 60, 0) }}>
          <div className="tt-title">{hp.label}</div>
          <div className="tt-row"><span>{xLabel}</span><span>{xFmt(hp.x)}</span></div>
          <div className="tt-row"><span>{yLabel}</span><span>{yFmt(hp.y)}</span></div>
          <div className="muted">{hp.detail}</div>
        </div>
      )}
    </div>
  );
}
