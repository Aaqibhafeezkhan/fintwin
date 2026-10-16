import { useCallback, useEffect, useRef, useState } from "react";
import type { Summary } from "./engine/summary";
import type { Knobs, Levers, Params } from "./engine/types";
import type { SimRequest } from "./engine/worker";

export function useSize<T extends HTMLElement>() {
  // a callback ref, so the observer attaches whenever the element mounts (also after a loading state)
  const ro = useRef<ResizeObserver | null>(null);
  const [width, setWidth] = useState(0);
  const ref = useCallback((el: T | null) => {
    ro.current?.disconnect();
    ro.current = null;
    if (!el) return;
    setWidth(Math.floor(el.getBoundingClientRect().width));
    ro.current = new ResizeObserver(([e]) => setWidth(Math.floor(e.contentRect.width)));
    ro.current.observe(el);
  }, []);
  useEffect(() => () => ro.current?.disconnect(), []);
  return [ref, width] as const;
}

let worker: Worker | null = null;
let nextId = 1;
const pending = new Map<number, (r: { summary: Summary; ms: number }) => void>();
function getWorker() {
  if (!worker) {
    worker = new Worker(new URL("./engine/worker.ts", import.meta.url), { type: "module" });
    worker.onmessage = (e) => {
      const cb = pending.get(e.data.id);
      pending.delete(e.data.id);
      cb?.(e.data);
    };
  }
  return worker;
}

export function runSimulation(params: Params, knobs: Knobs, levers: Levers, nPaths = 5000, seed = 7) {
  return new Promise<{ summary: Summary; ms: number }>((resolve) => {
    const id = nextId++;
    pending.set(id, resolve);
    getWorker().postMessage({ id, params, knobs, levers, nPaths, seed } satisfies SimRequest);
  });
}

/** Live Monte Carlo: re-runs (debounced, latest-wins) whenever inputs change. */
export function useSimulation(params: Params | null, knobs: Knobs, levers: Levers, nPaths = 5000) {
  const [state, setState] = useState<{ summary: Summary | null; ms: number; busy: boolean }>({ summary: null, ms: 0, busy: false });
  const latest = useRef(0);
  const key = JSON.stringify([params?.ticker, knobs, levers, nPaths]);
  useEffect(() => {
    if (!params) return;
    const ticket = ++latest.current;
    setState((s) => ({ ...s, busy: true }));
    const timer = setTimeout(() => {
      runSimulation(params, knobs, levers, nPaths).then((r) => {
        if (ticket === latest.current) setState({ summary: r.summary, ms: r.ms, busy: false });
      });
    }, 60);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, params]);
  return state;
}

export function useHashState(def: string): [string, (v: string) => void] {
  const [v, setV] = useState(() => decodeURIComponent(location.hash.slice(1)) || def);
  useEffect(() => {
    const on = () => setV(decodeURIComponent(location.hash.slice(1)) || def);
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, [def]);
  return [v, (nv: string) => { location.hash = encodeURIComponent(nv); }];
}
