import React, { useCallback, useEffect, useMemo, useRef, useState } from "https://esm.sh/react@18.3.1?dev";
import { createRoot } from "https://esm.sh/react-dom@18.3.1/client?dev";
import ReactFlow, { Background, Controls, Handle, MiniMap, Position } from "https://esm.sh/reactflow@11.11.4?dev";

class FlowErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error) {
    return {
      hasError: true,
      message: (error && error.message) ? error.message : "Unknown ReactFlow render error",
    };
  }

  componentDidCatch(error, errorInfo) {
    console.error("[FlowErrorBoundary] ReactFlow crashed", error, errorInfo);
  }

  handleReset() {
    this.setState({ hasError: false, message: "" });
    if (this.props.onReset) {
      this.props.onReset();
    }
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return React.createElement(
      "div",
      { className: "h-full w-full p-4 bg-red-50 border-t border-red-200" },
      React.createElement("div", { className: "text-sm font-semibold text-red-700" }, "Canvas render failed"),
      React.createElement("div", { className: "mt-2 text-xs text-red-700 break-words" }, this.state.message),
      React.createElement(
        "button",
        {
          className: "mt-3 px-3 py-1 rounded bg-white border border-red-300 text-red-700",
          onClick: () => this.handleReset(),
        },
        "Retry Canvas"
      )
    );
  }
}

function randomServiceName() {
  return `service-${Math.random().toString(36).slice(2, 7)}`;
}

function ServiceRootNode({ data, selected }) {
  return React.createElement(
    "div",
    {
      className: `rounded-xl border-2 bg-slate-900 text-white shadow-lg ${selected ? "border-sky-400" : "border-slate-700"}`,
      style: { minWidth: "240px", padding: "14px 16px" },
      title: data.description || "",
    },
    React.createElement(Handle, { type: "source", position: Position.Bottom, style: { background: "#38bdf8" } }),
    React.createElement("div", { className: "text-xs uppercase tracking-widest text-sky-300" }, "Service"),
    React.createElement("div", { className: "mt-1 text-lg font-semibold" }, data.title || "Untitled service"),
    React.createElement("div", { className: "mt-2 text-sm text-slate-300" }, data.description || "Empty service")
  );
}

function ElementNode({ data, selected }) {
  return React.createElement(
    "div",
    {
      title: data.description || "",
      className: `rounded-lg p-3 border ${selected ? "border-sky-400" : "border-gray-200"} bg-white`,
      style: { minWidth: "200px" },
    },
    React.createElement(Handle, { type: "target", position: Position.Top }),
    React.createElement("div", { className: "font-semibold" }, data.title || "Untitled element"),
    React.createElement("div", { className: "text-xs text-gray-500 mt-1" }, data.description || "No description"),
    React.createElement(Handle, { type: "source", position: Position.Bottom })
  );
}

function ServicesApp() {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [currentService, setCurrentService] = useState(null);
  const [modeMove, setModeMove] = useState(false);
  const [modeConnect, setModeConnect] = useState(false);

  const [serviceName, setServiceName] = useState("");
  const [serviceDesc, setServiceDesc] = useState("");
  const [elementTitle, setElementTitle] = useState("");
  const [elementDesc, setElementDesc] = useState("");

  const reactFlowWrapper = useRef(null);
  const [rfInstance, setRfInstance] = useState(null);
  const [flowMountKey, setFlowMountKey] = useState(0);

  const nodeTypes = useMemo(() => ({
    serviceRoot: ServiceRootNode,
    element: ElementNode,
  }), []);

  const syncInspectorFromSelection = useCallback((node, service) => {
    if (service) {
      setServiceName(service.name || "");
      setServiceDesc(service.description || "");
    }
    if (node && node.type === "element") {
      setElementTitle(node.data.title || "");
      setElementDesc(node.data.description || "");
    } else {
      setElementTitle("");
      setElementDesc("");
    }
  }, []);

  const loadServiceGraph = useCallback(async (serviceId) => {
    if (!serviceId) return;
    setLoading(true);
    setError("");
    try {
      const [svcRes, elemsRes, relsRes] = await Promise.all([
        fetch(`/api/services/${serviceId}`),
        fetch(`/api/services/${serviceId}/elements`),
        fetch(`/api/services/${serviceId}/relations`),
      ]);

      if (!svcRes.ok) throw new Error("Failed to load service");
      const svc = await svcRes.json();
      const elems = elemsRes.ok ? await elemsRes.json() : [];
      const rels = relsRes.ok ? await relsRes.json() : [];

      const serviceNode = {
        id: `service-${svc.id}`,
        type: "serviceRoot",
        position: { x: 40, y: 40 },
        data: {
          title: svc.name || "Untitled service",
          description: svc.description || "",
          serviceId: svc.id,
        },
      };

      const elementNodes = elems.map((el) => ({
        id: `element-${el.id}`,
        type: "element",
        position: { x: Number(el.x || 200), y: Number(el.y || 180) },
        data: {
          title: el.title || `Element ${el.id}`,
          description: el.description || el.key || "",
          elementId: el.id,
        },
      }));

      const validIds = new Set([serviceNode.id, ...elementNodes.map((n) => n.id)]);
      const relationEdges = rels
        .map((r) => {
          const source = r.source_type === "element" ? `element-${r.source_id}` : `service-${r.source_id}`;
          const target = r.target_type === "element" ? `element-${r.target_id}` : `service-${r.target_id}`;
          return {
            id: `rel-${r.id}`,
            source,
            target,
            label: r.label || "",
          };
        })
        .filter((e) => validIds.has(e.source) && validIds.has(e.target));

      const graphNodes = [serviceNode, ...elementNodes];
      setCurrentService(svc);
      setNodes(graphNodes);
      setEdges(relationEdges);
      setSelectedNode(serviceNode);
      syncInspectorFromSelection(serviceNode, svc);
    } catch (err) {
      console.error(err);
      setError(err.message || "Failed to load service");
    } finally {
      setLoading(false);
    }
  }, [syncInspectorFromSelection]);

  const ensureCurrentService = useCallback(async () => {
    if (currentService && currentService.id) return currentService;
    const newName = randomServiceName();
    const res = await fetch("/api/services", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName, description: "" }),
    });
    if (!res.ok) throw new Error("Failed to create service");
    const created = await res.json();
    window.dispatchEvent(new Event("services-updated"));
    await loadServiceGraph(created.id);
    return created;
  }, [currentService, loadServiceGraph]);

  useEffect(() => {
    const handler = (ev) => {
      const id = ev && ev.detail ? ev.detail.id : null;
      if (id) loadServiceGraph(id);
    };
    window.addEventListener("service-selected", handler);
    return () => window.removeEventListener("service-selected", handler);
  }, [loadServiceGraph]);

  const selectedSummary = useMemo(() => {
    if (!selectedNode) return null;
    if (selectedNode.type === "serviceRoot") {
      return {
        title: selectedNode.data.title,
        type: "Service",
        description: selectedNode.data.description || "",
      };
    }
    if (selectedNode.type === "element") {
      return {
        title: selectedNode.data.title,
        type: "Element",
        description: selectedNode.data.description || "",
      };
    }
    return null;
  }, [selectedNode]);

  const fitViewOptions = useMemo(() => ({ padding: 0.2 }), []);

  return React.createElement(
    "div",
    { className: "grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_340px]" },
    React.createElement(
      "div",
      { className: "rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden min-h-[70vh]" },
      loading ? React.createElement("div", { className: "p-3 text-sm text-gray-500" }, "Loading service...") : null,
      error ? React.createElement("div", { className: "p-3 text-sm text-red-600" }, error) : null,
      React.createElement(
        "div",
        { className: "h-[70vh] w-full", ref: reactFlowWrapper },
        React.createElement(
          "div",
          { className: "p-2 bg-gray-50 border-b flex gap-2 items-center" },
          React.createElement("button", { className: `px-3 py-1 rounded ${modeMove ? "bg-sky-600 text-white" : "bg-white"}`, onClick: () => setModeMove((v) => !v) }, modeMove ? "Move: On" : "Move"),
          React.createElement("button", { className: `px-3 py-1 rounded ${modeConnect ? "bg-sky-600 text-white" : "bg-white"}`, onClick: () => setModeConnect((v) => !v) }, modeConnect ? "Arrow: On" : "Arrow"),
          React.createElement("button", {
            className: "px-3 py-1 rounded bg-white",
            onClick: async () => {
              try {
                const svc = await ensureCurrentService();
                const center = { x: 220, y: 220 };
                const res = await fetch("/api/elements", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    service_id: svc.id,
                    title: "New Element",
                    description: "",
                    x: center.x,
                    y: center.y,
                  }),
                });
                if (!res.ok) throw new Error("Failed to create element");
                const el = await res.json();
                const newNode = {
                  id: `element-${el.id}`,
                  type: "element",
                  position: { x: Number(el.x || center.x), y: Number(el.y || center.y) },
                  data: { title: el.title, description: el.description || el.key || "", elementId: el.id },
                };
                setNodes((prev) => prev.concat(newNode));
                setSelectedNode(newNode);
                syncInspectorFromSelection(newNode, svc);
              } catch (e) {
                alert(e.message || "Failed to add element");
              }
            },
          }, "Add"),
          React.createElement("button", {
            className: "px-3 py-1 rounded bg-white",
            onClick: async () => {
              if (!selectedNode || selectedNode.type !== "element") return;
              const id = Number(selectedNode.id.replace("element-", ""));
              const ok = confirm("Delete this element?");
              if (!ok) return;
              const res = await fetch(`/api/elements/${id}`, { method: "DELETE" });
              if (!res.ok) return alert("Failed to delete");
              setNodes((prev) => prev.filter((n) => n.id !== selectedNode.id));
              setEdges((prev) => prev.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id));
              setSelectedNode(null);
              syncInspectorFromSelection(null, currentService);
            },
          }, "Delete")
        ),
        React.createElement(
          FlowErrorBoundary,
          { onReset: () => setFlowMountKey((v) => v + 1) },
          React.createElement(
            ReactFlow,
            {
              key: `flow-${flowMountKey}`,
              nodes,
              edges,
              nodeTypes,
              onInit: (instance) => setRfInstance(instance),
              onNodeClick: (_, node) => {
                setSelectedNode(node);
                syncInspectorFromSelection(node, currentService);
              },
              onConnect: async (connection) => {
                if (!modeConnect || !currentService) return;
                const sourceId = connection.source || "";
                const targetId = connection.target || "";
                if (!sourceId || !targetId) return;

                const sourceIsElement = sourceId.startsWith("element-");
                const targetIsElement = targetId.startsWith("element-");
                if (!sourceIsElement && !targetIsElement) return;

                const payload = {
                  source_type: sourceIsElement ? "element" : "service",
                  source_id: Number(sourceId.replace("element-", "").replace("service-", "")),
                  target_type: targetIsElement ? "element" : "service",
                  target_id: Number(targetId.replace("element-", "").replace("service-", "")),
                };

                const res = await fetch("/api/relations", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(payload),
                });
                if (!res.ok) return;
                const rel = await res.json();
                setEdges((prev) => prev.concat({ id: `rel-${rel.id}`, source: sourceId, target: targetId }));
              },
              fitView: true,
              fitViewOptions,
              nodesDraggable: modeMove,
              nodesConnectable: modeConnect,
              onNodeDragStop: async (_, node) => {
                if (!node.id.startsWith("element-")) return;
                const id = Number(node.id.replace("element-", ""));
                await fetch(`/api/elements/${id}`, {
                  method: "PUT",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ x: Math.round(node.position.x), y: Math.round(node.position.y) }),
                });
              },
              onDrop: async (event) => {
                event.preventDefault();
                const raw = event.dataTransfer.getData("text/plain");
                if (!raw || !rfInstance) return;
                const parsed = JSON.parse(raw);
                if (parsed.type !== "service") return;

                const svc = await ensureCurrentService();
                const bounds = reactFlowWrapper.current.getBoundingClientRect();
                const position = rfInstance.project({
                  x: event.clientX - bounds.left,
                  y: event.clientY - bounds.top,
                });

                const res = await fetch("/api/elements", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    service_id: svc.id,
                    title: `Element ${Math.floor(Math.random() * 1000)}`,
                    description: "",
                    x: Math.round(position.x),
                    y: Math.round(position.y),
                  }),
                });
                if (!res.ok) return;
                const el = await res.json();
                const node = {
                  id: `element-${el.id}`,
                  type: "element",
                  position: { x: Number(el.x || position.x), y: Number(el.y || position.y) },
                  data: { title: el.title, description: el.description || el.key || "", elementId: el.id },
                };
                setNodes((prev) => prev.concat(node));
              },
              onDragOver: (ev) => ev.preventDefault(),
              elementsSelectable: true,
            },
            React.createElement(MiniMap, { zoomable: true, pannable: true }),
            React.createElement(Controls, null),
            React.createElement(Background, { gap: 20, size: 1 })
          )
        )
      )
    ),
    React.createElement(
      "aside",
      { className: "rounded-2xl border border-gray-200 bg-white p-5 shadow-sm overflow-y-auto" },
      React.createElement("div", { className: "text-sm font-semibold uppercase tracking-widest text-gray-500" }, "Inspector"),
      currentService
        ? React.createElement(
            "div",
            { className: "mt-4 pb-4 border-b" },
            React.createElement("div", { className: "text-sm font-medium text-gray-600" }, "Active Service"),
            React.createElement("div", { className: "mt-2 space-y-2" },
              React.createElement("label", { className: "block text-xs font-medium text-gray-600" }, "Name"),
              React.createElement("input", {
                type: "text",
                value: serviceName,
                onChange: (e) => setServiceName(e.target.value),
                className: "w-full border rounded p-2 text-sm",
              }),
              React.createElement("label", { className: "block text-xs font-medium text-gray-600 mt-2" }, "Description"),
              React.createElement("textarea", {
                value: serviceDesc,
                onChange: (e) => setServiceDesc(e.target.value),
                rows: 3,
                className: "w-full border rounded p-2 text-sm",
              }),
              React.createElement("button", {
                className: "px-2 py-1 rounded bg-sky-600 text-white text-sm",
                onClick: async () => {
                  const name = serviceName && serviceName.trim() ? serviceName.trim() : randomServiceName();
                  const res = await fetch(`/api/services/${currentService.id}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name, description: serviceDesc }),
                  });
                  if (!res.ok) return alert("Failed to save service");
                  const updated = await res.json();
                  setCurrentService(updated);
                  setServiceName(updated.name || "");
                  setServiceDesc(updated.description || "");
                  setNodes((prev) => prev.map((n) => (n.id === `service-${updated.id}` ? { ...n, data: { ...n.data, title: updated.name || "", description: updated.description || "" } } : n)));
                  window.dispatchEvent(new Event("services-updated"));
                },
              }, "Save Service")
            )
          )
        : React.createElement("div", { className: "mt-4 text-sm text-gray-500" }, "Select a service from the left list, or press Add/Drop to auto-create one."),
      selectedSummary
        ? React.createElement(
            "div",
            { className: "mt-4 space-y-3" },
            React.createElement("div", { className: "text-sm font-medium text-gray-700" }, `${selectedSummary.type}: ${selectedSummary.title}`),
            selectedNode && selectedNode.type === "element"
              ? React.createElement(
                  "div",
                  { className: "space-y-2" },
                  React.createElement("label", { className: "block text-xs font-medium text-gray-600" }, "Element Title"),
                  React.createElement("input", {
                    type: "text",
                    value: elementTitle,
                    onChange: (e) => setElementTitle(e.target.value),
                    className: "w-full border rounded p-2 text-sm",
                  }),
                  React.createElement("label", { className: "block text-xs font-medium text-gray-600" }, "Element Description"),
                  React.createElement("textarea", {
                    value: elementDesc,
                    onChange: (e) => setElementDesc(e.target.value),
                    rows: 4,
                    className: "w-full border rounded p-2 text-sm",
                  }),
                  React.createElement("button", {
                    className: "px-3 py-1 rounded bg-sky-600 text-white text-sm",
                    onClick: async () => {
                      const id = Number(selectedNode.id.replace("element-", ""));
                      const title = elementTitle && elementTitle.trim() ? elementTitle.trim() : "Untitled element";
                      const description = elementDesc || "";
                      const res = await fetch(`/api/elements/${id}`, {
                        method: "PUT",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ title, description, key: description }),
                      });
                      if (!res.ok) return alert("Failed to save element");
                      const updated = await res.json();
                      setNodes((prev) => prev.map((n) => (
                        n.id === selectedNode.id
                          ? {
                              ...n,
                              data: {
                                ...n.data,
                                title: updated.title || title,
                                description: updated.description || updated.key || description,
                              },
                            }
                          : n
                      )));
                    },
                  }, "Save Element")
                )
              : React.createElement("div", { className: "text-sm text-gray-500" }, selectedSummary.description || "")
          )
        : null
    )
  );
}

const root = createRoot(document.getElementById("services-root"));
root.render(React.createElement(ServicesApp));