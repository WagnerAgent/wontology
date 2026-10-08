// Navigable infrastructure canvas extracted from Wagner.
// Drills region → VPC → service → resource, drawing the dependency edges first
// (SVG) and the nodes on top, at every level. Fed by a real `Estate`
// (lib/estate-model + cachedResourcesToEstate). Owns its own toolbar
// (breadcrumbs + resource search + atlas). Renders in-tree under .score-canvas.

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Search,
  Plus,
  Minus,
  Maximize,
  LayoutGrid,
  X,
  RotateCw,
} from "lucide-react";

import {
  type Estate,
  type EstateGroup,
  type EstateResource,
  type Status,
} from "./estate-model";

export interface EstateOverlayEntry {
  sev: "warn" | "bad";
  by?: string;
  count?: number;
}
export type EstateOverlay = Record<string, EstateOverlayEntry>;

export interface EstateSelection {
  kind: "resource" | "service";
  id: string;
  name: string;
}

interface EstateCanvasProps {
  estate: Estate;
  selectedId?: string | null;
  overlay?: EstateOverlay;
  accountName?: string | null;
  onSelect?: (sel: EstateSelection) => void;
  onCallSpecialist?: () => void;
  /** Whether a scan is currently running (drives the Re-index/Stop control). */
  indexing?: boolean;
  /** Re-index the environment (incremental — keeps the current diagram up
   *  until the new scan completes, then swaps). */
  onReindex?: () => void;
  /** Stop the in-flight scan. */
  onStopIndex?: () => void;
}

const NW = 162;
const NH = 60;
const SEVRANK: Record<string, number> = { warn: 1, bad: 2 };
const GENERIC_ICON = "/icons/generic.svg";
const ATLAS_CAP = 2000;
const RES_GRID_CAP = 240;

type Pt = { x: number; y: number };
const anchor = (p: Pt) => ({
  l: { x: p.x, y: p.y + NH / 2 },
  r: { x: p.x + NW, y: p.y + NH / 2 },
  c: { x: p.x + NW / 2, y: p.y + NH / 2 },
});
const curve = (a: Pt, b: Pt) => {
  const m = (a.x + b.x) / 2;
  return `M${a.x} ${a.y} C${m} ${a.y}, ${m} ${b.y}, ${b.x} ${b.y}`;
};

type Roll = {
  count: number;
  ok: number;
  warn: number;
  bad: number;
  unknown: number;
  na: number;
};
const rollupGroups = (gs: EstateGroup[]): Roll =>
  gs.reduce<Roll>(
    (a, g) => ({
      count: a.count + g.count,
      ok: a.ok + g.ok,
      warn: a.warn + g.warn,
      bad: a.bad + g.bad,
      unknown: a.unknown + g.unknown,
      na: a.na + g.na,
    }),
    { count: 0, ok: 0, warn: 0, bad: 0, unknown: 0, na: 0 },
  );

function Health({ ok, warn, bad, unknown, na, count }: Roll) {
  if (count === 0) return null;
  const pct = (x: number) => `${(x / count) * 100}%`;
  return (
    <div className="ec-health">
      {ok > 0 && <i className="ok" style={{ width: pct(ok) }} />}
      {warn > 0 && <i className="warn" style={{ width: pct(warn) }} />}
      {bad > 0 && <i className="bad" style={{ width: pct(bad) }} />}
      {unknown > 0 && <i className="unknown" style={{ width: pct(unknown) }} />}
      {na > 0 && <i className="na" style={{ width: pct(na) }} />}
    </div>
  );
}

type FindRoll = { count: number; worst: "warn" | "bad" | null };
function FindBadge({ f }: { f: FindRoll }) {
  if (!f.count) return null;
  return (
    <span className={`ecn-fbadge ${f.worst ?? "warn"}`}>
      !<span className="fb-n">{f.count}</span>
    </span>
  );
}

const Glyph = ({ icon, alt }: { icon: string; alt?: string }) => (
  <img
    src={icon}
    alt={alt ?? ""}
    onError={(e) => {
      const img = e.currentTarget as HTMLImageElement;
      if (img.src.endsWith(GENERIC_ICON)) return;
      img.src = GENERIC_ICON;
    }}
  />
);

export function EstateCanvas({
  estate,
  selectedId,
  overlay,
  accountName,
  onSelect,
  onCallSpecialist,
  indexing = false,
  onReindex,
  onStopIndex,
}: EstateCanvasProps) {
  const [level, setLevel] = useState<"estate" | "region" | "vpc" | "service">(
    "estate",
  );
  const [curVpc, setCurVpc] = useState<string | null>(null);
  const [curGroup, setCurGroup] = useState<string | null>(null);
  const [curRegion, setCurRegion] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [atlas, setAtlas] = useState(false);
  const [findingsOnly, setFindingsOnly] = useState(false);
  const [q, setQ] = useState("");
  const [zoom, setZoom] = useState(1);
  const stageRef = useRef<HTMLDivElement>(null);
  const [stageWidth, setStageWidth] = useState(900);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const observer = new ResizeObserver(() => setStageWidth(stage.clientWidth));
    observer.observe(stage);
    setStageWidth(stage.clientWidth);
    return () => observer.disconnect();
  }, []);

  const ovl = overlay ?? {};
  const ovlEntries = Object.entries(ovl);
  const ovlCount = ovlEntries.length;

  const groupById = useMemo(() => {
    const m = new Map<string, EstateGroup>();
    for (const g of estate.groups) m.set(g.id, g);
    return m;
  }, [estate.groups]);
  const regionOf = (vpcKey: string) =>
    estate.vpcs.find((v) => v.key === vpcKey)?.region ?? "";
  const vpcLabel = (key: string) =>
    estate.vpcs.find((v) => v.key === key)?.label ?? key;

  const regions = estate.regions.length
    ? estate.regions
    : [...new Set(estate.vpcs.map((v) => v.region))];
  const multiRegion = regions.length > 1;

  // Reset drill state if the estate identity changes underneath us.
  useEffect(() => {
    setLevel("estate");
    setCurVpc(null);
    setCurGroup(null);
    setCurRegion(null);
  }, [estate]);

  const goService = (gid: string) => {
    const g = groupById.get(gid);
    if (!g) return;
    setCurRegion(g.region);
    setCurVpc(g.vpc);
    setCurGroup(gid);
    setLevel("service");
    setQ("");
  };

  useEffect(() => {
    if (!selectedId) return;
    const resource = estate.resources.find((item) => item.id === selectedId);
    if (resource) goService(resource.groupId);
  }, [selectedId]);

  useEffect(() => {
    setHover(null);
    if (stageRef.current) {
      stageRef.current.scrollTop = 0;
      stageRef.current.scrollLeft = 0;
    }
  }, [level, curVpc, curGroup]);

  const findingsIn = (pred: (gid: string) => boolean): FindRoll => {
    let count = 0;
    let worst: "warn" | "bad" | null = null;
    ovlEntries.forEach(([gid, o]) => {
      if (pred(gid)) {
        count += o.count ?? 1;
        if (!worst || SEVRANK[o.sev] > (SEVRANK[worst] || 0)) worst = o.sev;
      }
    });
    return { count, worst };
  };

  const results = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return [];
    return estate.resources
      .filter((r) =>
        `${r.name} ${r.typeLabel} ${r.group} ${r.vpcLabel} ${r.searchText || ""}`
          .toLowerCase()
          .includes(s),
      )
      .slice(0, 30);
  }, [q, estate.resources]);
  const matchSet = q.trim() ? new Set(results.map((r) => r.id)) : null;

  // ─────────────── scene per level ───────────────
  let scene: React.ReactNode = null;
  let W = 900;
  let H = 460;

  if (level === "estate" && multiRegion) {
    const rpos: Record<string, Pt> = {};
    const columns = Math.max(
      1,
      Math.min(regions.length, Math.floor((stageWidth - 40) / (NW + 80))),
    );
    W = Math.max(stageWidth, 40 + columns * (NW + 80));
    const left = (W - (columns * NW + (columns - 1) * 80)) / 2;
    regions.forEach(
      (r, i) =>
        (rpos[r] = {
          x: left + (i % columns) * (NW + 80),
          y: 80 + Math.floor(i / columns) * 140,
        }),
    );
    H = Math.max(320, 80 + Math.ceil(regions.length / columns) * 140);
    const ragg: Record<string, number> = {};
    estate.deps.forEach(([a, b]) => {
      const ga = groupById.get(a);
      const gb = groupById.get(b);
      if (!ga || !gb) return;
      const ra = regionOf(ga.vpc);
      const rb = regionOf(gb.vpc);
      if (ra !== rb)
        ragg[JSON.stringify([ra, rb])] =
          (ragg[JSON.stringify([ra, rb])] || 0) + 1;
    });
    const redges = Object.entries(ragg).map(([k, n]) => {
      const [s, t] = JSON.parse(k) as [string, string];
      return { s, t, n };
    });
    scene = (
      <>
        <svg className="ec-svg" width={W} height={H}>
          <defs>
            <marker
              id="eca"
              markerWidth="7"
              markerHeight="7"
              refX="5.5"
              refY="3"
              orient="auto"
            >
              <path d="M0 0 L6 3 L0 6 z" fill="var(--score-violet)" />
            </marker>
          </defs>
          {redges.map((e, i) => {
            const a = anchor(rpos[e.s]).c;
            const b = anchor(rpos[e.t]).c;
            const on = hover && (e.s === hover || e.t === hover);
            return (
              <g key={i}>
                <path
                  d={curve(a, b)}
                  fill="none"
                  stroke="var(--score-violet)"
                  strokeWidth={on ? 2.4 : 1.6}
                  strokeDasharray="5 4"
                  markerEnd="url(#eca)"
                  opacity={hover && !on ? 0.25 : 0.9}
                />
                <text
                  x={(a.x + b.x) / 2}
                  y={Math.min(a.y, b.y) - 10}
                  fontSize="10"
                  fill="var(--score-violet)"
                  textAnchor="middle"
                >
                  {e.n} cross-scope
                </text>
              </g>
            );
          })}
        </svg>
        {regions.map((r) => {
          const vs = estate.vpcs.filter((v) => v.region === r);
          const ro = rollupGroups(
            estate.groups.filter((g) => regionOf(g.vpc) === r),
          );
          const p = rpos[r];
          const rf = findingsIn(
            (gid) => regionOf(groupById.get(gid)!.vpc) === r,
          );
          const hidden = findingsOnly && rf.count === 0;
          return (
            <button
              key={r}
              className={`ecn vpc ${hover === r ? "hl" : ""} ${hidden ? "dim" : ""}`}
              style={{ left: p.x, top: p.y, width: NW }}
              onMouseEnter={() => setHover(r)}
              onMouseLeave={() => setHover(null)}
              onClick={() => {
                setCurRegion(r);
                setLevel("region");
                setHover(null);
              }}
            >
              <FindBadge f={rf} />
              <div className="ecn-top">
                <span className="ecn-name">{r}</span>
                <span className="ecn-n">{ro.count}</span>
              </div>
              <div className="ecn-sub">{vs.length} network scopes · region</div>
              <Health {...ro} />
            </button>
          );
        })}
      </>
    );
  } else if (level === "estate" || level === "region") {
    const vpcList =
      level === "region"
        ? estate.vpcs.filter((v) => v.region === curRegion)
        : estate.vpcs;
    const keys = vpcList.map((v) => v.key);
    const pos: Record<string, Pt> = {};
    const columns = Math.max(
      1,
      Math.min(3, keys.length, Math.floor((stageWidth - 40) / (NW + 80))),
    );
    W = Math.max(stageWidth, 40 + columns * (NW + 80));
    const left = (W - (columns * NW + (columns - 1) * 80)) / 2;
    keys.forEach(
      (k, i) =>
        (pos[k] = {
          x: left + (i % columns) * (NW + 80),
          y: 60 + Math.floor(i / columns) * 140,
        }),
    );
    H = 60 + Math.ceil(keys.length / columns) * 140 + NH + 20;
    const inSet = new Set(keys);
    const agg: Record<string, number> = {};
    estate.deps.forEach(([a, b]) => {
      const ga = groupById.get(a);
      const gb = groupById.get(b);
      if (!ga || !gb) return;
      if (ga.vpc !== gb.vpc && inSet.has(ga.vpc) && inSet.has(gb.vpc))
        agg[JSON.stringify([ga.vpc, gb.vpc])] =
          (agg[JSON.stringify([ga.vpc, gb.vpc])] || 0) + 1;
    });
    const edges = Object.entries(agg).map(([k, n]) => {
      const [s, t] = JSON.parse(k) as [string, string];
      return { s, t, n, xr: regionOf(s) !== regionOf(t) };
    });
    const nb = hover
      ? new Set(
          edges
            .filter((e) => e.s === hover || e.t === hover)
            .flatMap((e) => [e.s, e.t]),
        )
      : null;
    scene = (
      <>
        <svg className="ec-svg" width={W} height={H}>
          <defs>
            <marker
              id="ecv"
              markerWidth="7"
              markerHeight="7"
              refX="5.5"
              refY="3"
              orient="auto"
            >
              <path d="M0 0 L6 3 L0 6 z" fill="rgba(10,10,20,.32)" />
            </marker>
          </defs>
          {edges.map((e, i) => {
            const a = anchor(pos[e.s]).c;
            const b = anchor(pos[e.t]).c;
            const on = hover && (e.s === hover || e.t === hover);
            return (
              <path
                key={i}
                d={curve(a, b)}
                fill="none"
                stroke={
                  e.xr
                    ? "var(--score-violet)"
                    : on
                      ? "var(--score-violet)"
                      : "rgba(10,10,20,.16)"
                }
                strokeWidth={on ? 2 : 1.2}
                strokeDasharray={e.xr ? "5 4" : ""}
                markerEnd="url(#ecv)"
                opacity={hover && !on ? 0.22 : 1}
              />
            );
          })}
        </svg>
        {vpcList.map((v) => {
          const ro = rollupGroups(estate.groups.filter((g) => g.vpc === v.key));
          const p = pos[v.key];
          const dim = hover && !(nb && nb.has(v.key)) && hover !== v.key;
          const vf = findingsIn((gid) => groupById.get(gid)!.vpc === v.key);
          const hidden = findingsOnly && vf.count === 0;
          return (
            <button
              key={v.key}
              className={`ecn vpc ${hover === v.key ? "hl" : ""} ${
                dim || hidden ? "dim" : ""
              }`}
              style={{ left: p.x, top: p.y, width: NW }}
              onMouseEnter={() => setHover(v.key)}
              onMouseLeave={() => setHover(null)}
              onClick={() => {
                setCurVpc(v.key);
                setLevel("vpc");
              }}
            >
              <FindBadge f={vf} />
              <div className="ecn-top">
                <span className="ecn-name">{v.label}</span>
                <span className="ecn-n">{ro.count}</span>
              </div>
              <div className="ecn-sub">{v.region}</div>
              <Health {...ro} />
            </button>
          );
        })}
      </>
    );
  } else if (level === "vpc" && curVpc) {
    const gs = estate.groups.filter((g) => g.vpc === curVpc);
    const tiers = estate.lanes
      .map((lane) => lane.id)
      .filter((lane) => gs.some((g) => g.tier === lane));
    const pos: Record<string, Pt> = {};
    const cc: Record<string, number> = {};
    gs.forEach((g) => {
      const ci = tiers.indexOf(g.tier);
      cc[g.tier] = cc[g.tier] || 0;
      pos[g.id] = { x: 40 + ci * 188, y: 50 + cc[g.tier] * 86 };
      cc[g.tier] += 1;
    });
    W = 40 + tiers.length * 188 + 20;
    H =
      Math.max(
        ...tiers.map((t) => 50 + gs.filter((g) => g.tier === t).length * 86),
        240,
      ) + 20;
    const cols = tiers.map((t) => ({ t, x: 40 + tiers.indexOf(t) * 188 }));
    const intra = estate.deps.filter(
      ([a, b]) =>
        groupById.get(a)?.vpc === curVpc && groupById.get(b)?.vpc === curVpc,
    );
    const nb = hover
      ? new Set(
          intra
            .filter((e) => e[0] === hover || e[1] === hover)
            .flatMap((e) => e),
        )
      : null;
    scene = (
      <>
        {cols.map((c) => (
          <div key={c.t} className="ec-collabel" style={{ left: c.x, top: 22 }}>
            {c.t}
          </div>
        ))}
        <svg className="ec-svg" width={W} height={H}>
          <defs>
            <marker
              id="ecg"
              markerWidth="7"
              markerHeight="7"
              refX="5.5"
              refY="3"
              orient="auto"
            >
              <path d="M0 0 L6 3 L0 6 z" fill="rgba(10,10,20,.32)" />
            </marker>
          </defs>
          {intra.map(([a, b], i) => {
            if (!pos[a] || !pos[b]) return null;
            const fwd = pos[b].x >= pos[a].x;
            const A = fwd ? anchor(pos[a]).r : anchor(pos[a]).l;
            const B = fwd ? anchor(pos[b]).l : anchor(pos[b]).r;
            const on = hover && (a === hover || b === hover);
            return (
              <path
                key={i}
                d={curve(A, B)}
                fill="none"
                stroke={on ? "var(--score-violet)" : "rgba(10,10,20,.18)"}
                strokeWidth={on ? 2 : 1.2}
                markerEnd="url(#ecg)"
                opacity={hover && !on ? 0.2 : 1}
              />
            );
          })}
        </svg>
        {gs.map((g) => {
          const fo = ovl[g.id];
          const sev: Status = fo
            ? fo.sev
            : g.bad > 0
              ? "bad"
              : g.warn > 0
                ? "warn"
                : g.status;
          const p = pos[g.id];
          const dim = hover && !(nb && nb.has(g.id)) && hover !== g.id;
          const hidden = findingsOnly && !fo;
          return (
            <button
              key={g.id}
              className={`ecn svc ${hover === g.id ? "hl" : ""} ${
                dim || hidden ? "dim" : ""
              }`}
              style={{ left: p.x, top: p.y, width: NW }}
              onMouseEnter={() => setHover(g.id)}
              onMouseLeave={() => setHover(null)}
              onClick={() => goService(g.id)}
            >
              {fo && (
                <span
                  className={`ecn-flag ${fo.sev} ${fo.sev === "bad" ? "pulse" : ""}`}
                  title={fo.by ? `flagged by ${fo.by}` : "flagged"}
                >
                  !
                </span>
              )}
              <div className="ecn-top">
                <span className="ecn-ico">
                  <Glyph icon={g.icon} alt={g.typeLabel} />
                </span>
                <span className="ecn-name">{g.name}</span>
              </div>
              <div className="ecn-foot">
                <span className="ecn-region">
                  {g.count} {g.unit}
                  {g.count === 1 ? "" : "s"}
                </span>
                <span
                  className={`ecn-dot ${sev}`}
                />
              </div>
            </button>
          );
        })}
      </>
    );
  } else if (level === "service" && curGroup) {
    const g = groupById.get(curGroup);
    if (g) {
      const up = estate.deps.filter((d) => d[1] === curGroup).map((d) => d[0]);
      const down = estate.deps
        .filter((d) => d[0] === curGroup)
        .map((d) => d[1]);
      const right = down.filter((id) => !up.includes(id));
      const colY = (n: number, i: number) =>
        40 + i * 92 + (n < 3 ? (3 - n) * 26 : 0);
      const pos: Record<string, Pt> = {};
      up.forEach((id, i) => (pos[id] = { x: 24, y: colY(up.length, i) }));
      right.forEach(
        (id, i) => (pos[id] = { x: 24 + 2 * 250, y: colY(right.length, i) }),
      );
      const focal = {
        x: 24 + 250,
        y: 40 + (Math.max(up.length, down.length, 1) - 1) * 46 + 20,
      };
      const allRes = estate.resources.filter((r) => r.groupId === curGroup);
      const res = allRes.slice(0, RES_GRID_CAP);
      const rcols = 3;
      const rTop = Math.max(
        focal.y + 110,
        40 + Math.max(up.length, down.length) * 92 + 30,
      );
      W = 24 + 2 * 250 + NW + 24;
      H = rTop + Math.ceil(res.length / rcols) * 64 + 50;
      scene = (
        <>
          <svg className="ec-svg" width={W} height={H}>
            <defs>
              <marker
                id="ecs"
                markerWidth="7"
                markerHeight="7"
                refX="5.5"
                refY="3"
                orient="auto"
              >
                <path d="M0 0 L6 3 L0 6 z" fill="rgba(10,10,20,.32)" />
              </marker>
            </defs>
            {up.map((id) => {
              const ng = groupById.get(id);
              if (!ng || !pos[id]) return null;
              const xr = regionOf(ng.vpc) !== regionOf(g.vpc);
              return (
                <path
                  key={id}
                  d={curve(anchor(pos[id]).r, {
                    x: focal.x,
                    y: focal.y + NH / 2,
                  })}
                  fill="none"
                  stroke={xr ? "var(--score-violet)" : "rgba(10,10,20,.2)"}
                  strokeWidth="1.2"
                  strokeDasharray={xr ? "5 4" : ""}
                  markerEnd="url(#ecs)"
                />
              );
            })}
            {down.map((id) => {
              const ng = groupById.get(id);
              if (!ng || !pos[id]) return null;
              const xr = regionOf(ng.vpc) !== regionOf(g.vpc);
              return (
                <path
                  key={id}
                  d={curve(
                    { x: focal.x + NW, y: focal.y + NH / 2 },
                    anchor(pos[id]).l,
                  )}
                  fill="none"
                  stroke={xr ? "var(--score-violet)" : "rgba(10,10,20,.2)"}
                  strokeWidth="1.2"
                  strokeDasharray={xr ? "5 4" : ""}
                  markerEnd="url(#ecs)"
                />
              );
            })}
          </svg>
          <div
            className="ecn svc hl"
            style={{ left: focal.x, top: focal.y, width: NW }}
          >
            <div className="ecn-top">
              <span className="ecn-ico">
                <Glyph icon={g.icon} alt={g.typeLabel} />
              </span>
              <span className="ecn-name">{g.name}</span>
            </div>
            <div className="ecn-foot">
              <span className="ecn-region">
                {g.count} {g.unit}
                {g.count === 1 ? "" : "s"}
              </span>
            </div>
          </div>
          {[...up, ...right].map((id) => {
            const ng = groupById.get(id);
            const p = pos[id];
            if (!ng || !p) return null;
            return (
              <button
                key={id}
                className="ecn neighbor"
                style={{ left: p.x, top: p.y, width: NW }}
                onClick={() => goService(id)}
              >
                <div className="ecn-top">
                  <span className="ecn-ico">
                    <Glyph icon={ng.icon} alt={ng.typeLabel} />
                  </span>
                  <span className="ecn-name">{ng.name}</span>
                </div>
                <div className="ecn-sub">{ng.vpcLabel}</div>
              </button>
            );
          })}
          {res.map((r: EstateResource, i) => {
            const x = 24 + (i % rcols) * ((2 * 250 + NW) / rcols);
            const y = rTop + Math.floor(i / rcols) * 64;
            return (
              <button
                key={r.id}
                className={`ecn res ${selectedId === r.id ? "hl" : ""}`}
                style={{ left: x, top: y }}
                onClick={() =>
                  onSelect?.({ kind: "resource", id: r.id, name: r.name })
                }
              >
                {["bad", "warn"].includes(r.status) && (
                  <span className={`ecn-flag ${r.status}`}>!</span>
                )}
                <div className="ecn-top">
                  <span className="ecn-ico">
                    <Glyph icon={r.icon} alt={r.typeLabel} />
                  </span>
                  <span className="ecn-name">{r.name}</span>
                </div>
                <div className="ecn-foot">
                  <span className="ecn-region">{r.typeLabel}</span>
                  <span
                    className={`ecn-dot ${
                      r.status === "warn"
                        ? "warn"
                        : r.status === "bad"
                          ? "bad"
                          : r.status
                    }`}
                  />
                </div>
              </button>
            );
          })}
          {allRes.length > res.length && (
            <div className="ec-collabel" style={{ left: 24, top: H - 34 }}>
              +{allRes.length - res.length} more {g.unit}s · refine with search
            </div>
          )}
        </>
      );
    }
  }

  return (
    <div className="estate-canvas">
      <div className="canvas-bar">
        <div className="ec-bar-left">
          <div className="ec-crumbs">
            <button
              className={`ec-crumb ${level === "estate" ? "here" : ""}`}
              onClick={() => {
                setLevel("estate");
                setCurRegion(null);
                setHover(null);
              }}
            >
              <span className="ec-fermata" aria-hidden>
                <svg width="15" height="12" viewBox="0 0 20 16" fill="none">
                  <path
                    d="M2 12 A 8 8 0 0 1 18 12"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                  <circle cx="10" cy="13.5" r="2.2" fill="currentColor" />
                </svg>
              </span>
              <span className="ct-name">{accountName || "estate"}</span>
            </button>
            {multiRegion && curRegion && level !== "estate" && (
              <>
                <span className="sep">/</span>
                <button
                  className={`ec-crumb ${level === "region" ? "here" : ""}`}
                  onClick={() => {
                    setLevel("region");
                    setHover(null);
                  }}
                >
                  {curRegion}
                </button>
              </>
            )}
            {(level === "vpc" || level === "service") && curVpc && (
              <>
                <span className="sep">/</span>
                <button
                  className={`ec-crumb ${level === "vpc" ? "here" : ""}`}
                  onClick={() => {
                    setLevel("vpc");
                    setHover(null);
                  }}
                >
                  {vpcLabel(curVpc)}
                </button>
              </>
            )}
            {level === "service" && curGroup && (
              <>
                <span className="sep">/</span>
                <span className="ec-crumb here">
                  {groupById.get(curGroup)?.name}
                </span>
              </>
            )}
          </div>
          {(onReindex || onStopIndex) &&
            (indexing ? (
              <button
                type="button"
                className="ec-reindex indexing"
                onClick={onStopIndex}
                title="Indexing… — click to stop"
                aria-label="Stop indexing"
              >
                <span className="ec-reindex-spin" aria-hidden>
                  <RotateCw />
                </span>
              </button>
            ) : (
              <button
                type="button"
                className="ec-reindex"
                onClick={onReindex}
                title="Re-index environment"
                aria-label="Re-index environment"
              >
                <RotateCw />
              </button>
            ))}
          {ovlCount > 0 && (
            <button
              className={`ec-overlay-pill ${findingsOnly ? "on" : ""}`}
              onClick={() => setFindingsOnly((v) => !v)}
              title="Toggle findings-only"
            >
              <span className="d" />
              {ovlCount} flagged{findingsOnly ? " · only" : ""}
            </button>
          )}
        </div>

        <div className="canvas-tools">
          {onCallSpecialist && (
            <button
              type="button"
              className="canvas-summon"
              onClick={onCallSpecialist}
              title="Call a specialist (⌘K)"
            >
              <Plus />
              <span className="cs-label">Call a specialist</span>
              <span className="kbd">⌘K</span>
            </button>
          )}
          <div className="ec-search">
            <Search />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") setQ("");
                if (e.key === "Enter" && results[0]) {
                  goService(results[0].groupId);
                  onSelect?.({
                    kind: "resource",
                    id: results[0].id,
                    name: results[0].name,
                  });
                  setQ("");
                }
              }}
              placeholder="Find a resource…"
              aria-label="Find a resource"
            />
          </div>
          <button
            type="button"
            className={`tool-btn ${atlas ? "on" : ""}`}
            title="Atlas"
            aria-label="Open resource atlas"
            aria-pressed={atlas}
            onClick={() => setAtlas((a) => !a)}
          >
            <LayoutGrid />
          </button>
        </div>
      </div>

      <div className="ec-stage" ref={stageRef}>
        <div className="ec-zoom" aria-label="Canvas zoom controls">
          <button
            className="tool-btn"
            aria-label="Zoom out canvas"
            onClick={() => setZoom((z) => Math.max(0.35, z - 0.15))}
          >
            <Minus size={14} />
          </button>
          <button
            className="tool-btn"
            aria-label="Fit canvas"
            onClick={() =>
              setZoom(
                Math.min(
                  1,
                  Math.max(
                    0.35,
                    ((stageRef.current?.clientWidth || W) - 32) / W,
                  ),
                ),
              )
            }
          >
            <Maximize size={14} />
          </button>
          <button
            className="tool-btn"
            aria-label="Zoom in canvas"
            onClick={() => setZoom((z) => Math.min(2, z + 0.15))}
          >
            <Plus size={14} />
          </button>
        </div>
        <div className="ec-paper" />
        <div
          className="ec-scene-frame"
          style={{ width: W * zoom, minHeight: H * zoom }}
        >
          <div
            className="ec-scene"
            style={{
              width: W,
              minHeight: H,
              transform: `scale(${zoom})`,
              transformOrigin: "top left",
            }}
          >
            {scene}
          </div>
        </div>

        {q.trim() && (
          <div className="ec-results">
            {results.length === 0 && (
              <div className="ec-results-empty">No match for “{q}”.</div>
            )}
            {results.map((r) => (
              <button
                key={r.id}
                className="ec-rrow"
                onClick={() => {
                  goService(r.groupId);
                  onSelect?.({ kind: "resource", id: r.id, name: r.name });
                  setQ("");
                }}
              >
                <Glyph icon={r.icon} alt={r.typeLabel} />
                <span style={{ minWidth: 0, flex: 1 }}>
                  <span className="n">{r.name}</span>
                  <span className="p">
                    {r.vpcLabel} ·{" "}
                    {estate.lanes.find((lane) => lane.id === r.tier)?.label ??
                      r.tier}
                  </span>
                </span>
                <span
                  className="d"
                  style={{
                    background:
                      r.status === "ok"
                        ? "#3FA66A"
                        : r.status === "warn"
                          ? "#C28A1E"
                          : r.status === "bad"
                            ? "#C44"
                            : "#94a3b8",
                  }}
                />
              </button>
            ))}
          </div>
        )}

        {atlas && (
          <div className="ec-atlas">
            <div className="ec-atlas-head">
              <span className="atlas-title">
                Atlas · {estate.total} resources
              </span>
              <button
                type="button"
                className="ec-atlas-close"
                onClick={() => setAtlas(false)}
                title="Close atlas"
                aria-label="Close resource atlas"
              >
                <X size={12} />
              </button>
            </div>
            <div className="ec-grid">
              {estate.resources.slice(0, ATLAS_CAP).map((r) => {
                const fo = ovl[r.groupId];
                const st: Status = fo ? fo.sev : r.status;
                const match = matchSet?.has(r.id) ?? false;
                return (
                  <button
                    type="button"
                    key={r.id}
                    aria-label={`Jump to ${r.name}`}
                    title={`${r.name} · ${r.vpcLabel}`}
                    className={`ec-cell ${st === "warn" ? "warn" : st === "bad" ? "bad" : st} ${
                      match ? "match" : ""
                    } ${matchSet && !match ? "dim" : ""}`}
                    onClick={() => {
                      goService(r.groupId);
                      onSelect?.({ kind: "resource", id: r.id, name: r.name });
                    }}
                  />
                );
              })}
            </div>
            <div className="ec-atlas-note">
              One cell per resource · select to jump · gray = health unassessed
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
