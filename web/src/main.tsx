import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  MarkerType,
  useReactFlow,
  type Node,
  type Edge,
  type NodeProps,
} from "@xyflow/react";
import {
  Search,
  Plus,
  ArrowUpRight,
  Download,
  Upload,
  Layers,
  Network,
  Box,
  Database,
  HardDrive,
  Shield,
  Server,
  ChevronRight,
  X,
  RefreshCw,
  Focus,
  Cloud,
  GitBranch,
  CircleHelp,
  StopCircle,
  ListFilter,
  Check,
  AlertTriangle,
} from "lucide-react";
import "@xyflow/react/dist/style.css";
import "./style.css";

import type {
  Provider,
  Resource,
  Relationship,
  Coverage,
  Snapshot,
  Saved,
  Job,
} from "./types";
import { EstateCanvas } from "./estate-canvas";
import { toEstate } from "./estate";
import "./canvas.css";

const names = { aws: "AWS", azure: "Azure", gcp: "Google Cloud" };
const icons: Record<string, typeof Box> = {
  network: Network,
  compute: Server,
  data: Database,
  database: Database,
  storage: HardDrive,
  security: Shield,
  identity: Shield,
};
const domain = (r: Resource) =>
  r.category === "database" ? "data" : r.category || "unknown";

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    `/api/${path}`,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const value = await response.json();
  if (!response.ok)
    throw new Error(value.error || `Request failed (${response.status})`);
  return value;
}

function ResourceNode({ data, selected }: NodeProps) {
  const resource = data.resource as Resource;
  const Icon = icons[domain(resource)] || Box;
  return (
    <div
      className={`resource-node ${selected ? "selected" : ""} domain-${domain(resource)}`}
    >
      <Handle type="target" position={Position.Left} />
      <div className="node-icon">
        <Icon size={18} />
      </div>
      <div className="node-copy">
        <span className="node-type">
          {resource.semantic_type.replaceAll(".", " / ")}
        </span>
        <strong title={resource.name}>{resource.name}</strong>
        <span className="node-location">
          {resource.location.split("/").pop()}
        </span>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
const nodeTypes = { resource: ResourceNode };

function App() {
  const flow = useReactFlow();
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [provider, setProvider] = useState<Provider>("aws");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const [connect, setConnect] = useState(false);
  const [coverageOpen, setCoverageOpen] = useState(false);
  const [help, setHelp] = useState(false);
  const [saved, setSaved] = useState<Saved[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [aggregate, setAggregate] = useState(false);
  const [topology, setTopology] = useState(false);
  const importInput = useRef<HTMLInputElement>(null);
  const lastOptions = useRef<Record<string, unknown> | null>(null);
  const activeJob = useRef<string | null>(null);

  const loadDemo = useCallback(async (p: Provider) => {
    try {
      setBusy(true);
      setError("");
      const data = await api<Snapshot>(`demo?provider=${p}`);
      setSnapshot(data);
      setProvider(p);
      setSelected(null);
      setFocus(null);
      setCategory("all");
      setAggregate(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, []);
  const refreshSaved = () =>
    api<Saved[]>("snapshots")
      .then(setSaved)
      .catch(() => {});
  useEffect(() => {
    void loadDemo("aws");
    void refreshSaved();
  }, [loadDemo]);
  const running = job?.status === "running";
  useEffect(() => {
    if (!running || !job) return;
    let stopped = false,
      timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const next = await api<Job>(`scans/${job.id}`);
        if (stopped || activeJob.current !== job.id) return;
        setJob(next);
        if (next.snapshot) {
          setSnapshot({
            ...next.snapshot,
            provider: next.provider,
            demo: false,
            complete: next.status === "complete",
          });
          setProvider(next.provider);
        }
        if (next.error) setError(next.error);
        if (next.status === "running") timer = setTimeout(poll, 900);
        else void refreshSaved();
      } catch (e) {
        if (!stopped) {
          setError((e as Error).message);
          timer = setTimeout(poll, 2000);
        }
      }
    };
    void poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [running, job?.id]);

  const startScan = async (options: Record<string, unknown>) => {
    try {
      setError("");
      const result = await api<{ id: string }>("scans", options);
      activeJob.current = result.id;
      lastOptions.current = options;
      setJob({
        id: result.id,
        provider: options.provider as Provider,
        status: "running",
        snapshot: null,
      });
      setProvider(options.provider as Provider);
      setSnapshot(null);
      setSelected(null);
      setFocus(null);
      setCategory("all");
      setQuery("");
      setConnect(false);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const selectSnapshot = async (id: string) => {
    try {
      const data = await api<Snapshot>(`snapshots/${id}`);
      setSnapshot(data);
      setProvider(data.provider!);
      setSelected(null);
      setFocus(null);
      setQuery("");
      setCategory("all");
      setJob(null);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const resources = snapshot?.resources || [];
  const relationships = snapshot?.relationships || [];
  const categories = [...new Set(resources.map(domain))].sort();
  const byId = useMemo(
    () => new Map(resources.map((r) => [r.canonical_id, r])),
    [resources],
  );
  const focusedIds = useMemo(() => {
    if (!focus) return null;
    const ids = new Set([focus]);
    for (const edge of relationships)
      if (edge.source_id === focus || edge.target_id === focus) {
        ids.add(edge.source_id);
        ids.add(edge.target_id);
      }
    return ids;
  }, [focus, relationships]);
  const visible = useMemo(
    () =>
      resources.filter(
        (r) =>
          (category === "all" || domain(r) === category) &&
          (!focusedIds || focusedIds.has(r.canonical_id)) &&
          (!query ||
            [r.name, r.provider_id, r.provider_type, JSON.stringify(r.tags)]
              .join(" ")
              .toLowerCase()
              .includes(query.toLowerCase())),
      ),
    [resources, category, focusedIds, query],
  );
  const estate = useMemo(
    () => toEstate(snapshot, visible),
    [snapshot, visible],
  );
  const grouped = aggregate || visible.length > 300;
  const { nodes, edges } = useMemo(() => {
    const laneOrder = [
      "network",
      "compute",
      "data",
      "storage",
      "messaging",
      "integration",
      "security",
      "identity",
      "observability",
      "configuration",
      "management",
      "unknown",
    ];
    const mapping = new Map<string, string>();
    const buckets = new Map<string, { r: Resource; count: number }>();
    for (const r of visible) {
      const key = grouped ? `${r.location}|${r.semantic_type}` : r.canonical_id;
      mapping.set(r.canonical_id, key);
      const existing = buckets.get(key);
      if (existing) existing.count++;
      else buckets.set(key, { r, count: 1 });
    }
    const usedDomains = [
      ...new Set([...buckets.values()].map((b) => domain(b.r))),
    ].sort((a, b) => laneOrder.indexOf(a) - laneOrder.indexOf(b));
    const rows: Record<string, number> = {};
    const nodes: Node[] = [...buckets.entries()].map(([id, { r, count }]) => {
      const col = usedDomains.indexOf(domain(r));
      const row = rows[domain(r)] || 0;
      rows[domain(r)] = row + 1;
      return {
        id,
        type: "resource",
        position: { x: col * 350, y: row * 144 },
        selected: !grouped && selected === r.canonical_id,
        data: {
          resource:
            count > 1
              ? {
                  ...r,
                  name: `${count} ${r.semantic_type.split(".").pop()} resources`,
                }
              : r,
          members: visible
            .filter((item) => mapping.get(item.canonical_id) === id)
            .map((item) => item.canonical_id),
        },
      };
    });
    const seen = new Set<string>();
    const edges: Edge[] = relationships.flatMap((r, i) => {
      const source = mapping.get(r.source_id),
        target = mapping.get(r.target_id);
      if (!source || !target || source === target) return [];
      const key = `${source}|${target}|${r.kind}`;
      if (seen.has(key)) return [];
      seen.add(key);
      const highlighted =
        selected && (r.source_id === selected || r.target_id === selected);
      return [
        {
          id: String(i),
          source,
          target,
          type: "smoothstep",
          label: highlighted ? r.kind.replaceAll("_", " ") : undefined,
          markerEnd: { type: MarkerType.ArrowClosed },
          className: highlighted ? "highlighted-edge" : "",
          data: { relationship: r },
        },
      ];
    });
    return { nodes, edges };
  }, [visible, relationships, selected, grouped]);
  useEffect(() => {
    const timer = setTimeout(
      () => void flow.fitView({ padding: 0.22, duration: 0 }),
      70,
    );
    return () => clearTimeout(timer);
  }, [snapshot?.id, category, focus, query, grouped, resources.length]);
  const resource = selected ? byId.get(selected) : undefined;
  const selectedEdges = resource
    ? relationships.filter(
        (e) => e.source_id === selected || e.target_id === selected,
      )
    : [];
  const gaps =
    snapshot?.coverage.filter(
      (c) => !["complete", "empty"].includes(c.status),
    ) || [];

  const download = (data: Blob, name: string) => {
    const url = URL.createObjectURL(data);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const exportJSON = () =>
    snapshot &&
    download(
      new Blob([JSON.stringify(snapshot, null, 2)], {
        type: "application/json",
      }),
      `wontology-${provider}-${snapshot.demo ? "example" : "snapshot"}.json`,
    );
  const importJSON = async (file?: File) => {
    if (!file) return;
    try {
      if (file.size > 8 * 1024 * 1024)
        throw new Error("Choose a snapshot smaller than 8 MiB");
      const body = JSON.parse(await file.text());
      const data = await api<Snapshot>("import", body);
      setSnapshot(data);
      setProvider(data.provider!);
      setJob(null);
      setSelected(null);
      setFocus(null);
      void refreshSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      if (importInput.current) importInput.current.value = "";
    }
  };
  const exportSVG = () => {
    const escape = (s: string) =>
      s.replace(
        /[<>&"']/g,
        (c) =>
          ({
            "<": "&lt;",
            ">": "&gt;",
            "&": "&amp;",
            '"': "&quot;",
            "'": "&apos;",
          })[c]!,
      );
    const all = nodes;
    if (!all.length) return;
    const pos = new Map(all.map((n) => [n.id, n.position]));
    const w = Math.max(...all.map((n) => n.position.x)) + 330,
      h = Math.max(...all.map((n) => n.position.y)) + 150;
    const links = edges
      .map((e) => {
        const a = pos.get(e.source)!,
          b = pos.get(e.target)!;
        return `<path d="M${a.x + 272 + 24} ${a.y + 46 + 24} L${b.x + 24} ${b.y + 46 + 24}" stroke="#6b6e75" stroke-width="1.5" fill="none"/>`;
      })
      .join("");
    const boxes = all
      .map((n) => {
        const r = n.data.resource as Resource;
        return `<g transform="translate(${n.position.x + 24},${n.position.y + 24})"><rect width="272" height="92" rx="8" fill="#ffffff" stroke="#d9d7df"/><text x="16" y="25" fill="#6a35ff" font-family="monospace" font-size="11">${escape(r.semantic_type)}</text><text x="16" y="50" fill="#0a0a14" font-family="sans-serif" font-size="14">${escape(r.name.slice(0, 32))}</text><text x="16" y="72" fill="#6b6e75" font-family="monospace" font-size="11">${escape(r.location.split("/").pop()!)}</text></g>`;
      })
      .join("");
    download(
      new Blob(
        [
          `<svg xmlns="http://www.w3.org/2000/svg" width="${w + 48}" height="${h + 48}" viewBox="0 0 ${w + 48} ${h + 48}"><rect width="100%" height="100%" fill="#f7f6fa"/>${links}${boxes}</svg>`,
        ],
        { type: "image/svg+xml" },
      ),
      "wontology-diagram.svg",
    );
  };

  return (
    <div className="app-shell score-canvas">
      <header className="topbar">
        <a className="wordmark" href="/" aria-label="Wontology home">
          <img src="/favicon.svg" alt="" />
          wontology<span className="version">0.1</span>
        </a>
        <div className="topbar-center">
          <span className="local-dot" />
          Local workspace<span className="divider">/</span>
          <span>Your cloud, mapped</span>
        </div>
        <div className="top-actions">
          <button
            className="icon-button"
            aria-label="Help"
            onClick={() => setHelp(true)}
          >
            <CircleHelp size={18} />
          </button>
          <a
            className="source-link"
            href="https://github.com/wagneragent/wontology"
            target="_blank"
            rel="noreferrer"
          >
            Source
            <ArrowUpRight size={15} />
          </a>
          <button
            className="primary compact"
            onClick={() => setConnect(true)}
            disabled={running}
          >
            <Plus size={16} />
            Connect cloud
          </button>
        </div>
      </header>
      <aside className="sidebar">
        <div className="sidebar-heading">WORKSPACE</div>
        <button
          className="nav-row active"
          onClick={() => {
            setCategory("all");
            setFocus(null);
            setQuery("");
          }}
        >
          <Network size={17} />
          Infrastructure<span className="count">{resources.length}</span>
        </button>
        <div className="sidebar-section">
          <div className="sidebar-heading">RESOURCE TYPES</div>
          <button
            className={`filter-row ${category === "all" ? "chosen" : ""}`}
            onClick={() => setCategory("all")}
          >
            <Layers size={15} />
            All resources<span>{resources.length}</span>
          </button>
          {categories.map((c) => {
            const Icon = icons[c] || Box;
            return (
              <button
                key={c}
                className={`filter-row ${category === c ? "chosen" : ""}`}
                onClick={() => setCategory(c)}
              >
                <Icon size={15} />
                <span className="capitalize">{c}</span>
                <span>{resources.filter((r) => domain(r) === c).length}</span>
              </button>
            );
          })}
        </div>
        <div className="sidebar-section">
          <div className="sidebar-heading">SAVED SNAPSHOTS</div>
          {saved.length ? (
            saved.map((s) => (
              <button
                key={s.id}
                className="saved-row"
                disabled={running}
                onClick={() => void selectSnapshot(s.id)}
              >
                <Cloud size={14} />
                <span>
                  {names[s.provider]}
                  <small>
                    {new Date(s.created_at).toLocaleDateString()} ·{" "}
                    {s.complete ? "complete" : "partial"}
                  </small>
                </span>
              </button>
            ))
          ) : (
            <p className="sidebar-note">
              Your scans will appear here.
              <br />
              Stored on this computer.
            </p>
          )}
        </div>
        <div className="sidebar-bottom">
          <button
            className="filter-row"
            disabled={running}
            onClick={() => importInput.current?.click()}
          >
            <Upload size={15} />
            Open snapshot
          </button>
          <input
            ref={importInput}
            type="file"
            accept=".json,application/json"
            className="visually-hidden"
            aria-label="Import snapshot"
            onChange={(e) => void importJSON(e.target.files?.[0])}
          />
          <div className="privacy-note">
            <Shield size={14} />
            <span>
              Cloud credentials stay local.
              <br />
              No account. No telemetry.
            </span>
          </div>
        </div>
      </aside>
      <main className="workspace">
        <div className="workspace-header">
          <div>
            <h1>
              {snapshot?.demo
                ? "An example of the bigger picture."
                : running
                  ? "Mapping your infrastructure…"
                  : snapshot
                    ? "Your infrastructure. Connected."
                    : "See how it all connects."}
            </h1>
            <p>
              {snapshot?.demo
                ? "Explore this synthetic environment, or connect your own cloud."
                : running
                  ? "Resources appear as they are discovered. You can keep exploring."
                  : snapshot
                    ? `${names[provider]} · ${snapshot.scope || resources[0]?.cloud_scope_id || "Cloud scope"}`
                    : "Connect a cloud to build your infrastructure ontology."}
            </p>
          </div>
          <div className="environment-badge">
            <span className={`provider-mark ${provider}`}>
              <Cloud size={24} />
            </span>
            <div>
              {names[provider]}
              <small>
                {snapshot?.demo
                  ? "Synthetic example"
                  : running
                    ? "Scan in progress"
                    : "Local snapshot"}
              </small>
            </div>
          </div>
        </div>
        {error && (
          <div className="error-banner" role="alert">
            <AlertTriangle size={16} />
            <span>{error}</span>
            <button
              className="icon-button"
              aria-label="Dismiss error"
              onClick={() => setError("")}
            >
              <X size={15} />
            </button>
          </div>
        )}
        <div className="canvas-toolbar">
          <div className="view-title">
            <GitBranch size={16} />
            {topology ? "Topology" : "Infrastructure canvas"}
            <span className="canvas-count">
              {visible.length} resources · {edges.length} visible links
            </span>
          </div>
          <div className="canvas-actions">
            <button
              className="view-toggle"
              aria-pressed={topology}
              onClick={() => setTopology(!topology)}
            >
              {topology ? "Navigable canvas" : "Full topology"}
            </button>
            {topology && (
              <label className="search">
                <Search size={15} />
                <input
                  aria-label="Search resources"
                  placeholder="Find a resource…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                {query && (
                  <button
                    aria-label="Clear search"
                    onClick={() => setQuery("")}
                  >
                    <X size={13} />
                  </button>
                )}
              </label>
            )}
            {topology && (
              <button
                className={`icon-button ${grouped ? "on" : ""}`}
                title="Group resources by type and location"
                aria-label="Group resources"
                aria-pressed={grouped}
                onClick={() => setAggregate(!aggregate)}
              >
                <Layers size={17} />
              </button>
            )}
            <button
              className="icon-button"
              title="Download diagram as SVG"
              aria-label="Export SVG topology"
              disabled={!nodes.length}
              onClick={exportSVG}
            >
              <Download size={17} />
            </button>
            <button
              className="icon-button"
              title="Download ontology as JSON"
              aria-label="Export JSON snapshot"
              disabled={!snapshot}
              onClick={exportJSON}
            >
              <Box size={17} />
            </button>
            {running ? (
              <button
                className="icon-button"
                aria-label="Cancel scan"
                onClick={() =>
                  void api(`scans/${job.id}/cancel`, {}).catch((e) =>
                    setError(e.message),
                  )
                }
              >
                <StopCircle size={17} />
              </button>
            ) : (
              <button
                className="icon-button"
                aria-label="Refresh scan"
                disabled={!lastOptions.current}
                onClick={() =>
                  lastOptions.current && void startScan(lastOptions.current)
                }
              >
                <RefreshCw size={17} />
              </button>
            )}
          </div>
        </div>
        <div
          className={`canvas ${topology ? "topology-canvas" : "navigation-canvas"}`}
        >
          {!topology && (
            <EstateCanvas
              estate={estate}
              accountName={names[provider]}
              selectedId={selected}
              onSelect={(selection) => setSelected(selection.id)}
              indexing={running}
              onReindex={
                lastOptions.current
                  ? () => void startScan(lastOptions.current!)
                  : undefined
              }
              onStopIndex={
                running
                  ? () =>
                      void api(`scans/${job.id}/cancel`, {}).catch((e) =>
                        setError(e.message),
                      )
                  : undefined
              }
            />
          )}
          {topology && (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              fitView
              minZoom={0.12}
              maxZoom={2}
              onNodeClick={(_, node) => {
                const members = node.data.members as string[];
                setSelected(members[0]);
                if (members.length > 1) {
                  setAggregate(false);
                  setQuery("");
                  setCategory(domain(byId.get(members[0])!));
                }
              }}
              onPaneClick={() => setSelected(null)}
              nodesConnectable={false}
              deleteKeyCode={null}
              attributionPosition="bottom-left"
            >
              <Background gap={24} size={1} />
              <Controls showInteractive={false} />
              <MiniMap
                pannable
                zoomable
                nodeColor="#6a35ff"
                maskColor="rgba(247,246,250,.75)"
              />
            </ReactFlow>
          )}
          {!nodes.length && (
            <div className="canvas-empty">
              <Network size={38} />
              <h2>
                {running
                  ? "Discovering your cloud…"
                  : query || category !== "all"
                    ? "No matching resources"
                    : job?.status === "failed"
                      ? "Connection needs attention"
                      : "Your infrastructure starts here"}
              </h2>
              <p>
                {running
                  ? "The first resources will appear here."
                  : query
                    ? "Try a resource name, type, ID, or tag."
                    : "Connect read-only cloud access or open a saved snapshot."}
              </p>
              {!running && !query && (
                <button className="primary" onClick={() => setConnect(true)}>
                  Connect cloud
                  <ArrowUpRight size={16} />
                </button>
              )}
            </div>
          )}
          {snapshot?.demo && (
            <div className="example-switcher">
              <span>EXAMPLE</span>
              {(["aws", "azure", "gcp"] as Provider[]).map((p) => (
                <button
                  key={p}
                  disabled={running || busy}
                  className={provider === p ? "selected" : ""}
                  onClick={() => void loadDemo(p)}
                >
                  {names[p]}
                </button>
              ))}
            </div>
          )}
          {focus && (
            <button className="focus-pill" onClick={() => setFocus(null)}>
              <Focus size={14} />
              Showing immediate connections
              <X size={14} />
            </button>
          )}
        </div>
        <footer className="workspace-footer">
          <button
            className={`coverage-button ${gaps.length ? "warning" : ""}`}
            onClick={() => setCoverageOpen(true)}
          >
            {running ? (
              <RefreshCw size={13} />
            ) : gaps.length ? (
              <AlertTriangle size={13} />
            ) : (
              <Check size={13} />
            )}
            <span>
              {running
                ? `${job?.progress?.service || "Connecting"} · scanning`
                : snapshot?.demo
                  ? "Synthetic example · no cloud access"
                  : snapshot
                    ? `${gaps.length ? `${gaps.length} coverage gaps` : "Configured collectors complete"}`
                    : "Ready to connect"}
            </span>
            <ChevronRight size={13} />
          </button>
          <span>{relationships.length} evidence-backed relationships</span>
          <span className="footer-right">
            {snapshot?.unresolved_relationships?.length || 0} unresolved
            references
          </span>
        </footer>
      </main>
      {resource && (
        <aside className="inspector">
          <div className="inspector-top">
            <span>RESOURCE DETAILS</span>
            <button
              className="icon-button"
              aria-label="Close resource details"
              onClick={() => setSelected(null)}
            >
              <X size={17} />
            </button>
          </div>
          <div className={`inspector-symbol domain-${domain(resource)}`}>
            {(() => {
              const Icon = icons[domain(resource)] || Box;
              return <Icon size={26} />;
            })()}
          </div>
          <h2>{resource.name}</h2>
          <p className="resource-kind">{resource.provider_type}</p>
          <div className="detail-grid">
            <span>Cloud</span>
            <strong>{names[resource.provider]}</strong>
            <span>Location</span>
            <strong>{resource.location.split("/").pop()}</strong>
            <span>Classification</span>
            <strong>{resource.semantic_type}</strong>
            <span>Health</span>
            <strong>{resource.health?.state || "unknown"}</strong>
          </div>
          <div className="id-box">
            <span>NATIVE ID</span>
            <code>{resource.provider_id}</code>
          </div>
          <button
            className="secondary full"
            onClick={() => {
              setTopology(true);
              setFocus(resource.canonical_id);
              setQuery("");
              setCategory("all");
            }}
          >
            <Focus size={15} />
            Explore connections
          </button>
          <h3>
            Relationships <span>{selectedEdges.length}</span>
          </h3>
          {selectedEdges.length ? (
            selectedEdges.map((edge, i) => {
              const other = byId.get(
                edge.source_id === selected ? edge.target_id : edge.source_id,
              );
              return (
                <details className="relationship" key={i}>
                  <summary>
                    <GitBranch size={14} />
                    <span>
                      {edge.kind.replaceAll("_", " ")}
                      <strong>{other?.name || "Unresolved resource"}</strong>
                    </span>
                    <ChevronRight size={13} />
                  </summary>
                  <div className="evidence">
                    <span>CONFIGURATION EVIDENCE</span>
                    {edge.evidence.map((e, j) => (
                      <p key={j}>
                        <code>{e.source}</code>
                        <code>{e.path}</code>
                        <small>{JSON.stringify(e.value)}</small>
                      </p>
                    ))}
                    <button
                      className="text-button"
                      onClick={() => setSelected(other?.canonical_id || null)}
                    >
                      Inspect resource
                      <ArrowUpRight size={13} />
                    </button>
                  </div>
                </details>
              );
            })
          ) : (
            <p className="sidebar-note">
              No observed relationships in this snapshot.
            </p>
          )}
          <details className="properties">
            <summary>Resource properties</summary>
            <pre>{JSON.stringify(resource.properties, null, 2)}</pre>
          </details>
        </aside>
      )}
      {connect && (
        <ConnectDialog
          provider={provider}
          onClose={() => setConnect(false)}
          onConnect={startScan}
        />
      )}
      {coverageOpen && (
        <Modal
          title="Discovery coverage"
          onClose={() => setCoverageOpen(false)}
        >
          <p className="dialog-description">
            Coverage applies to the configured collectors, not every service
            offered by the cloud. Permission gaps and unresolved references stay
            visible.
          </p>
          <div className="coverage-list">
            {snapshot?.coverage.map((c, i) => (
              <div key={i}>
                <span>
                  {c.service}
                  <small>
                    {c.location} · {c.resources_found} resources
                  </small>
                </span>
                <strong
                  className={
                    ["complete", "empty"].includes(c.status)
                      ? "good"
                      : "warning"
                  }
                >
                  {c.status.replaceAll("_", " ")}
                </strong>
                {c.error_message && <p>{c.error_message}</p>}
              </div>
            )) || <p>No scan yet.</p>}
          </div>
        </Modal>
      )}
      {help && (
        <Modal
          title="Your cloud, mapped locally."
          onClose={() => setHelp(false)}
        >
          <p className="dialog-description">
            Wontology reads cloud configuration and turns it into a typed,
            navigable graph. Select a resource to see its relationships and the
            configuration evidence behind each connection.
          </p>
          <ol className="help-steps">
            <li>
              Connect an existing local cloud identity with read-only metadata
              access.
            </li>
            <li>
              Choose the account region, Azure subscription, or GCP project.
            </li>
            <li>Explore, search, and export the resulting ontology.</li>
          </ol>
          <p className="dialog-description">
            Shared networks and IAM permissions do not prove runtime traffic.
            Unavailable services stay in coverage reports; unknown health stays
            unknown. Snapshots and credentials remain on your computer.
          </p>
          <a
            className="secondary"
            href="https://github.com/wagneragent/wontology#readme"
            target="_blank"
            rel="noreferrer"
          >
            Read the documentation
            <ArrowUpRight size={16} />
          </a>
        </Modal>
      )}
    </div>
  );
}

function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current!;
    d.showModal();
    return () => d.close();
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="dialog-header">
        <h2>{title}</h2>
        <button
          className="icon-button"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <X size={19} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

function ConnectDialog({
  provider: initial,
  onClose,
  onConnect,
}: {
  provider: Provider;
  onClose: () => void;
  onConnect: (o: Record<string, unknown>) => Promise<void>;
}) {
  const [provider, setProvider] = useState(initial),
    [profile, setProfile] = useState(""),
    [regions, setRegions] = useState("us-east-1"),
    [subscription, setSubscription] = useState(""),
    [project, setProject] = useState(""),
    [profiles, setProfiles] = useState<string[]>([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    void api<{ aws: string[]; gcp_project: string }>("profiles")
      .then((v) => {
        setProfiles(v.aws);
        setProject(v.gcp_project);
      })
      .catch(() => {});
  }, []);
  const commands = {
    aws: "aws sso login --profile your-profile",
    azure: "az login",
    gcp: "gcloud auth application-default login",
  };
  return (
    <Modal title="Connect your cloud" onClose={onClose}>
      <p className="dialog-description">
        Use your existing local cloud session. Wontology reads metadata and
        keeps the resulting graph on this computer.
      </p>
      <div className="provider-tabs">
        {(["aws", "azure", "gcp"] as Provider[]).map((p) => (
          <button
            key={p}
            className={provider === p ? "selected" : ""}
            onClick={() => setProvider(p)}
          >
            {names[p]}
          </button>
        ))}
      </div>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            await onConnect({
              provider,
              ...(provider === "aws"
                ? {
                    profile,
                    regions: regions
                      .split(",")
                      .map((r) => r.trim())
                      .filter(Boolean),
                  }
                : provider === "azure"
                  ? { subscription }
                  : { project }),
            });
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        {provider === "aws" ? (
          <>
            <label className="field">
              AWS profile
              <select
                value={profile}
                onChange={(e) => setProfile(e.target.value)}
              >
                <option value="">Default credential chain</option>
                {profiles.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </label>
            <label className="field">
              Regions
              <input
                value={regions}
                required
                placeholder="us-east-1, eu-west-1"
                onChange={(e) => setRegions(e.target.value)}
              />
              <small>
                Comma-separated. Only selected regions will be scanned.
              </small>
            </label>
          </>
        ) : provider === "azure" ? (
          <label className="field">
            Subscription ID
            <input
              required
              value={subscription}
              placeholder="00000000-0000-0000-0000-000000000000"
              onChange={(e) => setSubscription(e.target.value)}
            />
            <small>
              Uses Azure CLI or your configured Azure Identity credential.
            </small>
          </label>
        ) : (
          <label className="field">
            Project ID
            <input
              required
              value={project}
              placeholder="my-cloud-project"
              onChange={(e) => setProject(e.target.value)}
            />
            <small>
              Requires the Cloud Asset Inventory API and metadata permissions.
            </small>
          </label>
        )}
        <details className="credential-help">
          <summary>Need to establish a cloud session?</summary>
          <p>
            Authenticate with your cloud provider in your terminal, then return
            here.
          </p>
          <code>{commands[provider]}</code>
          <p>
            See the repository's cloud setup guide for minimum permissions. No
            credentials are pasted into Wontology.
          </p>
        </details>
        {error && (
          <p role="alert" className="warning">
            {error}
          </p>
        )}
        <div className="dialog-bottom">
          <span>
            <Shield size={14} />
            Read-only collection
          </span>
          <button className="primary" disabled={busy} type="submit">
            {busy ? "Connecting…" : "Connect and map"}
            <ArrowUpRight size={16} />
          </button>
        </div>
      </form>
    </Modal>
  );
}

createRoot(document.getElementById("root")!).render(
  <ReactFlowProvider>
    <App />
  </ReactFlowProvider>,
);
