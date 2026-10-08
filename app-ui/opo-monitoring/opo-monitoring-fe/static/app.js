const timeline = document.getElementById("timeline");
const evidencePane = document.getElementById("evidence");
const conversationInput = document.getElementById("conversation-input");
const messageInput = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const interactionPanel = document.getElementById("interaction-panel");
const findingsPanel = document.getElementById("findings-panel");
const findingsContent = document.getElementById("findings-content");
const mainLayout = document.querySelector("main");
const toggleRightPanel = document.getElementById("toggle-right-panel");
const panelResizer = document.getElementById("panel-resizer");
const agentSelect = document.getElementById("agent-select");
const tdbbPanel = document.getElementById("tdbb-panel");
const ncePanel = document.getElementById("nce-panel");
const nceLegend = document.getElementById("nce-legend");
const nceLegendMax = document.getElementById("nce-legend-max");
const V4_AGENT = "opo-analysis-agent-v4";
const V5_AGENT = "opo-analysis-agent-v5";
const selectedAgentId = () => registeredAgents[agentSelect.selectedIndex]?.agentId;
const isScopedAgent = (agentId) => agentId === V4_AGENT || agentId === V5_AGENT;

let conversationId = null;
let conversationVersion = null;
let busy = false;
let registeredAgents = [];

function setRightPanelCollapsed(collapsed) {
  mainLayout.classList.toggle("right-panel-collapsed", collapsed);
  toggleRightPanel.innerHTML = collapsed ? "&larr;" : "&rarr;";
  toggleRightPanel.title = collapsed ? "Show interaction and evidence" : "Minimize panel";
  toggleRightPanel.setAttribute(
    "aria-label",
    collapsed ? "Show interaction and evidence panel" : "Minimize interaction and evidence panel"
  );
}

const EVIDENCE_WIDTH_KEY = "opoEvidencePanelWidth";
const MIN_EVIDENCE_WIDTH = 320;
const MAX_EVIDENCE_WIDTH = 760;

function setEvidenceWidth(widthPx) {
  const clamped = Math.min(MAX_EVIDENCE_WIDTH, Math.max(MIN_EVIDENCE_WIDTH, widthPx));
  mainLayout.style.setProperty("--evidence-width", `${clamped}px`);
  return clamped;
}

function resizeChartsIfAny() {
  ["trend-plot", "wafer-plot"].forEach((id) => {
    const el = document.getElementById(id);
    if (el.data) Plotly.Plots.resize(el);
  });
}

(function restoreEvidenceWidth() {
  const saved = Number(localStorage.getItem(EVIDENCE_WIDTH_KEY));
  if (saved) setEvidenceWidth(saved);
})();

let resizingPanels = false;

panelResizer.addEventListener("mousedown", (event) => {
  if (mainLayout.classList.contains("right-panel-collapsed")) return;
  resizingPanels = true;
  document.body.classList.add("resizing-panels");
  event.preventDefault();
});

document.addEventListener("mousemove", (event) => {
  if (!resizingPanels) return;
  const rect = mainLayout.getBoundingClientRect();
  setEvidenceWidth(rect.right - event.clientX);
});

document.addEventListener("mouseup", () => {
  if (!resizingPanels) return;
  resizingPanels = false;
  document.body.classList.remove("resizing-panels");
  const width = parseInt(getComputedStyle(mainLayout).getPropertyValue("--evidence-width"), 10);
  if (width) localStorage.setItem(EVIDENCE_WIDTH_KEY, String(width));
  resizeChartsIfAny();
});

const OUTLIER_COLOUR = "#f85149";

const PLOT_LAYOUT = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { color: "#8b97a8", size: 11 },
  margin: { l: 48, r: 16, t: 10, b: 40 },
  height: 280,
  hovermode: "closest",
  xaxis: { gridcolor: "#2a3441", linecolor: "#2a3441", zeroline: false },
  yaxis: {
    gridcolor: "#2a3441",
    linecolor: "#2a3441",
    zeroline: false,
    title: "OPO KPI",
  },
  showlegend: false,
  hoverlabel: { bgcolor: "#1e2631", bordercolor: "#2a3441", font: { color: "#e4e8ee" } },
};

const PLOT_CONFIG = { displaylogo: false, responsive: true, displayModeBar: false };

let trendSeries = null;
let availableTrendSeries = null;
let lastWaferRows = [];
let lastAnomalousWafers = [];

function availableTrendScopes() {
  return (availableTrendSeries || []).map((series) => ({
    product: series.product,
    layer: series.layer_id,
    scanner: series.exposure_equipment_id || series.machine,
    months: [...new Set((series.points || []).map((point) => String(point.date).slice(0, 7)))].sort(),
  }));
}

// Every workflow step renders the same two overlay KPIs, never per-machine series.
// The outliers schema is a free-form object_list: the model emits either a
// grouped { points: [[date, x, y], ...] } shape or a single { timestamp, value } point.
function outlierPoints(item) {
  if (Array.isArray(item.points)) {
    return item.points.map(([date, kpiValue]) => ({ date, kpiValue }));
  }
  if (item.timestamp !== undefined) {
    return [{ date: item.timestamp, kpiValue: Array.isArray(item.value) ? item.value[0] : item.value }];
  }
  if (item.date !== undefined && item.kpi_value !== undefined) {
    return [{ date: item.date, kpiValue: item.kpi_value }];
  }
  return [];
}

// Every workflow step renders the same two overlay KPIs, never per-machine series.
function drawPlot(outliers, selectedMachine) {
  const plot = document.getElementById("trend-plot");
  if (!trendSeries) return;
  plot.style.height = "";
  if (!trendSeries.length) {
    Plotly.purge(plot);
    return;
  }

  const points = trendSeries.flatMap((s) =>
    (s.points || []).map((p) => ({ ...p, machine: s.machine, product: s.product })));

  const trace = (name, key, color) => {
    const filtered = points.filter((p) => Number.isFinite(Number(p[key])));
    return {
      type: "scatter",
      mode: "markers",
      name,
      x: filtered.map((p) => p.date),
      y: filtered.map((p) => Number(p[key])),
      marker: {
        size: 6,
        color,
        opacity: filtered.map((p) => (selectedMachine && p.machine !== selectedMachine ? 0.3 : 1)),
      },
      hovertemplate: `%{x}<br>${name} %{y:.2f} absolute OPO KPI<extra>${name}</extra>`,
    };
  };

  const traces = [
    trace("KPI X", "kpi_value", "#4c9aff"),
    trace("KPI Y", "kpi_value_y", "#f0883e"),
  ];

  // Ring the exact points the agent identified as outliers; no visual approximation.
  const rings = { x: [], y: [], text: [] };
  (outliers || []).forEach((item) => {
    outlierPoints(item).forEach(({ date, kpiValue }) => {
      if (!Number.isFinite(Number(kpiValue))) return;
      rings.x.push(date);
      rings.y.push(Number(kpiValue));
      rings.text.push(`${item.machine} / ${item.product}`);
    });
  });

  if (rings.x.length) {
    traces.push({
      type: "scatter",
      mode: "markers",
      name: "Outlier",
      x: rings.x,
      y: rings.y,
      text: rings.text,
      marker: {
        size: 9,
        color: "rgba(0,0,0,0)",
        line: { color: OUTLIER_COLOUR, width: 2 },
      },
      hovertemplate: "<b>Outlier</b><br>%{text}<br>%{x} — %{y:.2f} absolute OPO KPI<extra></extra>",
    });
  }

  Plotly.react(plot, traces, { ...PLOT_LAYOUT, showlegend: true }, PLOT_CONFIG);
}

// v3 plots overlay X and Y of the scoped wafers in stacked panels so neither hides the other.
function drawV3Trend(series, changeDate) {
  const plot = document.getElementById("trend-plot");
  const seriesList = Array.isArray(series) ? series : series?.series || [];
  const points = seriesList.flatMap((item) => item.points || [])
    .sort((left, right) => String(left.date).localeCompare(String(right.date)));
  if (!points.length) {
    Plotly.purge(plot);
    return 0;
  }
  const text = points.map((p) => [p.lot_id, p.wafer_id, p.chuck_id].filter(Boolean).join(" \u00b7 "));
  const trace = (name, key, color, yaxis) => ({
    type: "scatter",
    mode: "markers",
    name: `Overlay ${name}`,
    x: points.map((p) => p.date),
    y: points.map((p) => p[key]),
    yaxis,
    text,
    marker: { size: 5, color, opacity: 0.8 },
    hovertemplate: `%{x}<br>${name} %{y:.2f} nm<br>%{text}<extra></extra>`,
  });
  const axis = (title, domain) => ({ ...PLOT_LAYOUT.yaxis, title, domain });
  const layout = {
    ...PLOT_LAYOUT,
    height: 360,
    margin: { ...PLOT_LAYOUT.margin, t: 28 },
    showlegend: true,
    legend: { orientation: "h", x: 0, y: 1.1 },
    // Force a full x-axis autorange on every redraw: Plotly.react otherwise keeps
    // any zoom/pan the analyst left on the previous (possibly narrower) dataset.
    xaxis: { ...PLOT_LAYOUT.xaxis, autorange: true },
    yaxis: axis("X |m|+3\u03c3 (nm)", [0.54, 1]),
    yaxis2: axis("Y |m|+3\u03c3 (nm)", [0, 0.46]),
    shapes: changeDate ? [{
      type: "line", xref: "x", yref: "paper", x0: changeDate, x1: changeDate, y0: 0, y1: 1,
      line: { color: OUTLIER_COLOUR, dash: "dot", width: 1.5 },
    }] : [],
  };
  plot.style.height = `${layout.height}px`;
  Plotly.react(plot, [
    trace("X", "kpi_value", "#4c9aff", "y"),
    trace("Y", "kpi_value_y", "#f0883e", "y2"),
  ], layout, PLOT_CONFIG);
  return points.length;
}

let tdbbRun = null;

function renderTdbb(evidence) {
  const note = document.getElementById("tdbb-note");
  const bars = document.getElementById("tdbb-bars");
  const maps = document.getElementById("tdbb-maps");
  const select = document.getElementById("tdbb-budget");
  const scope = evidence.comparison_scope;
  tdbbRun = evidence.tdbb_run || null;
  document.getElementById("tdbb-period").textContent = scope?.change_date
    ? `Before / after ${scope.change_date}`
    : "Change date unavailable";
  if (!tdbbRun) {
    note.textContent = scope?.change_date ? "TDBB has not run yet." : (scope?.interpretation || "");
    Plotly.purge(bars);
    Plotly.purge(maps);
    select.innerHTML = "";
    NCE_VIEWS.forEach((view) => Plotly.purge(document.getElementById(view.plotId)));
    return;
  }
  const [before, after] = ["before", "after"].map((name) => tdbbRun.periods.find((p) => p.period === name));
  const settings = tdbbRun.settings;
  note.textContent = `${settings.model_step} \u00b7 ${settings.context_levels.join(" + ")} \u00b7 before ${before.start_date} \u2013 ${before.end_date}: ${before.lot_count} lots / ${before.wafer_count} wafers \u00b7 after ${after.start_date} \u2013 ${after.end_date}: ${after.lot_count} lots / ${after.wafer_count} wafers`;

  drawTdbbOverview(bars, before, after);

  const mapped = before.budgets.filter((b) => tdbbRun.maps.some((m) => m.budget === b.budget));
  const current = select.value;
  select.innerHTML = mapped.map((b) => `<option value="${escapeHtml(b.budget)}">${escapeHtml(b.label)}</option>`).join("");
  const largest = evidence.tdbb_comparison?.largest_increase?.budget;
  const choose = [current, largest, "nce_wafer.average"].find((key) => mapped.some((b) => b.budget === key));
  select.value = choose || mapped[0]?.budget || "";
  select.onchange = () => drawTdbbMaps(select.value);
  drawTdbbMaps(select.value);
  renderNceViews();
}

// NCE root-cause panels: fixed budgets reused from the same before/after TDBB maps, not a
// separate dataset. Fingerprint = ce_wafer (correctable wafer-level translation/mag/rotation),
// EExy = ce_field spread across true per-point locations (correctable field-level exposure
// corrections), Fingerprint residual = nce_wafer (non-correctable leftover) - the budget that
// actually carries the Sep-1 jump, matching the TDBB overview story above.
const NCE_VIEWS = [
  { budget: "ce_wafer.average", plotId: "fingerprint-plot" },
  { budget: "ce_field.average", plotId: "eexy-plot" },
  { budget: "nce_wafer.average", plotId: "residual-plot" },
];

function renderNceViews() {
  const available = NCE_VIEWS.filter(({ budget }) => tdbbRun?.maps.some((m) => m.budget === budget));
  NCE_VIEWS.filter((view) => !available.includes(view)).forEach(({ plotId }) => Plotly.purge(document.getElementById(plotId)));
  nceLegend.hidden = !available.length;
  if (!available.length) return;
  // First pass measures each panel's own color scale; the second pass redraws all three with
  // one shared scale. The legend itself is a standalone HTML element (not a Plotly colorbar
  // embedded in one of the three cards), so it can be centered against the whole NCE analysis
  // section instead of being stuck inside whichever single card's own plot canvas drew it.
  const colorMax = Math.max(...available.map(({ budget, plotId }) => drawTdbbMaps(budget, plotId, { compact: true })));
  nceLegendMax.textContent = colorMax.toFixed(2);
  available.forEach(({ budget, plotId }) => {
    // eexy-plot's card spans the full row width (CSS .tdbb-overview) - a taller plot lets its
    // circles keep growing with that extra width instead of staying capped at the shared height.
    const height = plotId === "eexy-plot" ? 520 : 360;
    drawTdbbMaps(budget, plotId, { compact: true, colorMax, showColorbar: false, height });
  });
}

// Mirrors the TDBB Overview: metrics as columns, context levels as rows, X/Y bars before vs after.
function drawTdbbOverview(plot, before, after) {
  const metrics = [...new Map(before.budgets.map((b) => [b.metric, b.metric_label])).entries()];
  const contexts = [...new Map(before.budgets.map((b) => [b.context, b.context_label])).entries()];
  const cell = (period, metric, context) => period.budgets.find((b) => b.metric === metric && b.context === context) || {};
  const top = Math.max(0.1, ...[before, after].flatMap((p) => p.budgets.flatMap((b) => [b.x_m3s ?? 0, b.y_m3s ?? 0]))) * 1.18;
  const gap = 0.012;
  const width = (1 - 0.04) / metrics.length;
  const height = (1 - 0.06) / contexts.length;
  const traces = [];
  const layout = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: "#8b97a8", size: 10 },
    margin: { l: 34, r: 8, t: 46, b: 20 },
    height: 150 * contexts.length + 70,
    barmode: "group",
    bargap: 0.25,
    showlegend: true,
    legend: { orientation: "h", x: 1, xanchor: "right", y: 1.07 },
    hovermode: "closest",
    annotations: [],
  };
  contexts.forEach(([context, contextLabel], row) => {
    metrics.forEach(([metric, metricLabel], column) => {
      const index = row * metrics.length + column + 1;
      const suffix = index === 1 ? "" : index;
      const x0 = 0.04 + column * width;
      const y1 = 0.94 - row * height;
      layout[`xaxis${suffix}`] = { domain: [x0 + gap, x0 + width - gap], anchor: `y${suffix}`, type: "category", fixedrange: true, linecolor: "#2a3441", tickfont: { size: 10 } };
      layout[`yaxis${suffix}`] = { domain: [y1 - height + 0.035, y1 - 0.01], anchor: `x${suffix}`, range: [0, top], fixedrange: true, gridcolor: "#2a3441", zeroline: false, showticklabels: column === 0, tickfont: { size: 9 } };
      [["before", before, "#4c9aff"], ["after", after, "#f0883e"]].forEach(([name, period, color]) => {
        const values = cell(period, metric, context);
        traces.push({
          type: "bar",
          name: name === "before" ? `Before (${period.start_date} \u2013 ${period.end_date})` : `After (${period.start_date} \u2013 ${period.end_date})`,
          legendgroup: name,
          showlegend: index === 1,
          xaxis: `x${suffix}`,
          yaxis: `y${suffix}`,
          x: ["X", "Y"],
          y: [values.x_m3s, values.y_m3s],
          marker: { color },
          text: [values.x_m3s, values.y_m3s].map((v) => (v == null ? "" : v.toFixed(2))),
          textposition: "outside",
          textfont: { size: 9, color: "#c9d1d9" },
          cliponaxis: false,
          hovertemplate: `${metricLabel} \u00b7 ${contextLabel}<br>%{x}: %{y:.3f} nm<extra>${name}</extra>`,
        });
      });
      if (row === 0) {
        layout.annotations.push({ xref: "paper", yref: "paper", x: x0 + width / 2, xanchor: "center", y: 0.985, showarrow: false, text: `<b>${metricLabel}</b>`, font: { color: "#e4e8ee", size: 11 } });
      }
    });
    layout.annotations.push({ xref: "paper", yref: "paper", x: 0, y: 0.94 - row * height - height / 2, xanchor: "right", showarrow: false, textangle: -90, text: `<b>${contextLabel}</b>`, font: { color: "#e4e8ee", size: 11 } });
  });
  plot.style.height = `${layout.height}px`;
  Plotly.react(plot, traces, layout, PLOT_CONFIG);
}

// Faint reference grid behind the vectors, matching the pitch overlay tools draw
// across a wafer/field map (so points read as sitting "on" a grid, not floating).
// Lines are drawn at the actual reticle field boundaries (derived from the field-center
// pitch in the data), not an arbitrary fixed division, so each point sits within its
// own field cell like a real overlay map tool.
// A square grid's corners (range*sqrt(2)) fall outside a circular boundary of the
// same radius, so clipRadius shortens each line to its chord within that circle.
function fieldBoundaries(values) {
  const unique = [...new Set(values.map((v) => Math.round(v * 100) / 100))].sort((a, b) => a - b);
  if (unique.length < 2) return [];
  const gaps = [];
  for (let i = 1; i < unique.length; i++) {
    const gap = unique[i] - unique[i - 1];
    if (gap > 1e-6) gaps.push(gap);
  }
  const pitch = gaps.length ? Math.min(...gaps) : 0;
  if (!pitch) return [];
  return unique.map((v) => v - pitch / 2).concat([unique[unique.length - 1] + pitch / 2]);
}

function gridLineShapes(suffix, boundariesX, boundariesY, clipRadius) {
  const shapes = [];
  const fallbackExtent = Math.max(...boundariesX.map(Math.abs), ...boundariesY.map(Math.abs), 1);
  const extentAt = (coordinate) => {
    if (clipRadius == null) return fallbackExtent;
    if (Math.abs(coordinate) >= clipRadius) return null;
    return Math.sqrt(clipRadius * clipRadius - coordinate * coordinate);
  };
  boundariesX.forEach((x) => {
    const extent = extentAt(x);
    if (extent == null) return;
    shapes.push({ type: "line", xref: `x${suffix}`, yref: `y${suffix}`, x0: x, x1: x, y0: -extent, y1: extent, line: { color: "#232b36", width: 1 }, layer: "below" });
  });
  boundariesY.forEach((y) => {
    const extent = extentAt(y);
    if (extent == null) return;
    shapes.push({ type: "line", xref: `x${suffix}`, yref: `y${suffix}`, x0: -extent, x1: extent, y0: y, y1: y, line: { color: "#232b36", width: 1 }, layer: "below" });
  });
  return shapes;
}

// Field metrics now carry both a "field" map (intrafield pattern averaged across all fields)
// and a "wafer" map (each field's own average, positioned at its real field center) - prefer
// the wafer-positioned view so field budgets render on the same wafer-shaped map as wafer budgets.
// CE-Field's intrafield formula is linear and symmetric about the field center, so averaging it
// per field (not per intrafield position) always cancels to exactly zero - that map carries no
// signal, so fall back to the intrafield "field" view for any budget where that happens.
function drawTdbbMaps(budget, plotId = "tdbb-maps", { compact = false, colorMax: colorMaxOverride, showColorbar = true, height = 360 } = {}) {
  const plot = document.getElementById(plotId);
  if (!tdbbRun || !budget) return 0;
  const magnitude = (p) => Math.max(p.m3s_x ?? 0, p.m3s_y ?? 0);
  const mapFor = (l, period) => tdbbRun.maps.find((m) => m.budget === budget && m.level === l && m.period === period)?.points || [];
  const levels = tdbbRun.maps.filter((m) => m.budget === budget).map((m) => m.level);
  const waferPoints = ["before", "after"].flatMap((period) => mapFor("wafer", period));
  const waferHasSignal = waferPoints.some((p) => magnitude(p) > 1e-9 || Math.abs(p.dx) > 1e-9 || Math.abs(p.dy) > 1e-9);
  const level = levels.includes("wafer") && waferHasSignal ? "wafer" : levels.includes("field") ? "field" : levels[0] || "wafer";
  const panels = [[level, "before"], [level, "after"]];
  const all = panels.flatMap(([l, period]) => mapFor(l, period));
  const colorMax = colorMaxOverride ?? Math.max(...all.map(magnitude), 0.001);
  const longest = () => Math.max(...all.map((p) => Math.hypot(p.dx, p.dy)), 1e-6);
  const target = { wafer: 14, field: 4 };
  let scale = target[level] / longest();
  // The dense field-on-wafer maps plot every true (field center + intrafield offset) point, a
  // few of which land a little past the nominal 150mm wafer radius by construction - grow the
  // drawn circle to the real data extent instead of clipping those points' own base position.
  const waferRadius = level === "wafer" ? Math.max(150, ...all.map((p) => Math.hypot(p.x, p.y))) : 150;
  // Shrink the shared scale (never per-arrow, which would distort relative lengths) so every
  // arrow TIP stays within the wafer circle / field rectangle - a point near the wafer edge can
  // otherwise poke its arrow outside the physical boundary it's meant to be drawn on. The tip
  // moves from the point (fixed) towards point+vector as k goes 0->1, so the largest k that
  // still fits is found per point (ray/circle or ray/rect intersection), not by naively scaling
  // the tip's distance from the origin, which ignores the point's own fixed offset.
  const circleFit = (p) => {
    const vx = p.dx * scale, vy = p.dy * scale;
    const a = vx * vx + vy * vy;
    if (a < 1e-12) return 1;
    const b = 2 * (p.x * vx + p.y * vy);
    const c = p.x * p.x + p.y * p.y - waferRadius * waferRadius;
    if (a + b + c <= 0) return 1;
    const discriminant = b * b - 4 * a * c;
    if (discriminant < 0) return 1;
    return Math.max(0, Math.min(1, (-b + Math.sqrt(discriminant)) / (2 * a)));
  };
  const axisFit = (base, delta, bound) => {
    if (delta === 0) return 1;
    const tip = base + delta;
    if (tip <= bound && tip >= -bound) return 1;
    const edge = tip > bound ? bound : -bound;
    return Math.max(0, Math.min(1, (edge - base) / delta));
  };
  const rectFit = (p) => Math.min(axisFit(p.x, p.dx * scale, 13), axisFit(p.y, p.dy * scale, 16.5));
  // 0.99 safety margin absorbs floating-point slop right at the boundary check above, so tips
  // land a hair inside the circle/rect instead of possibly a hair outside it.
  scale *= 0.99 * Math.min(1, ...all.map(level === "wafer" ? circleFit : rectFit));
  const shapeExtent = level === "wafer" ? waferRadius : 16.5;
  const tipExtent = Math.max(shapeExtent, ...all.flatMap((p) => [Math.abs(p.x + p.dx * scale), Math.abs(p.y + p.dy * scale)]));
  const range = tipExtent * 1.08;
  const traces = [];
  const layout = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: "#8b97a8", size: 11 },
    // The 90px right margin is only needed when this plot draws its own Plotly colorbar -
    // reserving it unconditionally was stealing plotting width from the NCE panels, which
    // render a standalone HTML legend instead and show no colorbar here (equal-aspect circles
    // are width-capped by domain width, so that stolen width - not height - was the real cap).
    margin: { l: 8, r: showColorbar ? 90 : 12, t: 22, b: 8 },
    height,
    showlegend: false,
    hovermode: "closest",
    annotations: [],
    shapes: [],
  };
  panels.forEach(([l, period], index) => {
    const suffix = index ? index + 1 : "";
    const points = mapFor(l, period);
    layout[`xaxis${suffix}`] = { domain: [index * 0.5 + 0.015, index * 0.5 + 0.485], range: [-range, range], visible: false, fixedrange: true, constrain: "domain" };
    layout[`yaxis${suffix}`] = { domain: [0, 0.92], range: [-range, range], visible: false, fixedrange: true, scaleanchor: `x${suffix}`, constrain: "domain" };
    const label = compact ? period[0].toUpperCase() + period.slice(1) : `${l === "wafer" ? "Wafer" : "Field"} \u00b7 ${period}`;
    layout.annotations.push({
      xref: "paper", yref: "paper", x: index * 0.5 + 0.25, y: 1, showarrow: false,
      text: `<b>${label}</b>`, font: { color: "#e4e8ee", size: 11 },
    });
    if (l === "wafer") {
      layout.shapes.push(...gridLineShapes(suffix, fieldBoundaries(points.map((p) => p.x)), fieldBoundaries(points.map((p) => p.y)), waferRadius));
      layout.shapes.push({ type: "circle", xref: `x${suffix}`, yref: `y${suffix}`, x0: -waferRadius, y0: -waferRadius, x1: waferRadius, y1: waferRadius, line: { color: "#667085", width: 1 } });
    } else {
      layout.shapes.push(...gridLineShapes(suffix, fieldBoundaries(points.map((p) => p.x)), fieldBoundaries(points.map((p) => p.y))));
      layout.shapes.push({ type: "rect", xref: `x${suffix}`, yref: `y${suffix}`, x0: -13, y0: -16.5, x1: 13, y1: 16.5, line: { color: "#667085", width: 1 } });
    }
    traces.push({
      type: "scatter",
      mode: "lines",
      xaxis: `x${suffix}`,
      yaxis: `y${suffix}`,
      x: points.flatMap((p) => [p.x, p.x + p.dx * scale, null]),
      y: points.flatMap((p) => [p.y, p.y + p.dy * scale, null]),
      // Same fixed width on every panel - varying it by point count would make panels with
      // genuinely denser data (e.g. EExy's per-point intrafield view) look artificially
      // different in scale from sparser ones, which breaks a fair visual comparison between them.
      line: { color: "#e4e8ee", width: 1.2 },
      hoverinfo: "skip",
    });
    traces.push({
      type: "scatter",
      mode: "markers",
      xaxis: `x${suffix}`,
      yaxis: `y${suffix}`,
      x: points.map((p) => p.x),
      y: points.map((p) => p.y),
      customdata: points.map((p) => [p.dx, p.dy, p.m3s_x, p.m3s_y]),
      marker: {
        size: 4,
        color: points.map(magnitude),
        cmin: 0,
        cmax: colorMax,
        colorscale: "Viridis",
        showscale: index === 1 && showColorbar,
        // x:1.02 previously landed past paper's valid [0,1] range and got clipped. Anchoring
        // the bar's RIGHT edge at the paper boundary makes it grow leftward into the reserved
        // right margin instead, keeping it outside both wafer maps and clear of the card edge.
        colorbar: {
          title: { text: "3\u03c3 nm", side: "right" },
          thickness: 10,
          len: 0.8,
          x: 1,
          xanchor: "right",
          y: 0.46,
          yanchor: "middle",
        },
      },
      hovertemplate: "(%{x:.1f}, %{y:.1f}) mm<br>mean %{customdata[0]:.3f} / %{customdata[1]:.3f} nm<br>|m|+3\u03c3 X %{customdata[2]:.2f} Y %{customdata[3]:.2f} nm<extra></extra>",
    });
    // Arrowhead at each vector's tip, rotated to its direction - only for vectors long
    // enough to have a visible direction, so near-zero points stay plain dots.
    const arrowPoints = points.filter((p) => Math.hypot(p.dx, p.dy) > 1e-6);
    traces.push({
      type: "scatter",
      mode: "markers",
      xaxis: `x${suffix}`,
      yaxis: `y${suffix}`,
      x: arrowPoints.map((p) => p.x + p.dx * scale),
      y: arrowPoints.map((p) => p.y + p.dy * scale),
      marker: {
        // Plotly's "arrow" symbol is a thin open chevron - at small sizes, next to the base
        // dot, it reads as a single bent flag/checkmark rather than a clear arrowhead. A solid
        // triangle (rotated the same way via marker.angle) gives an unambiguous point + direction.
        symbol: "triangle-up",
        size: 9,
        angle: arrowPoints.map((p) => (Math.atan2(p.dx, p.dy) * 180) / Math.PI),
        color: arrowPoints.map(magnitude),
        cmin: 0,
        cmax: colorMax,
        colorscale: "Viridis",
        showscale: false,
      },
      hoverinfo: "skip",
    });
  });
  plot.style.height = `${layout.height}px`;
  Plotly.react(plot, traces, layout, PLOT_CONFIG);
  // Re-measure the container: a prior draw while this div was display:none (e.g. the NCE
  // panel before step 3) leaves Plotly's internal size stale, which overflows into sibling
  // grid cells once the container becomes visible - resize forces it to match the real size.
  Plotly.Plots.resize(plot);
  return colorMax;
}

async function loadTrends() {
  try {
    trendSeries = await window.OpoBff.loadTrends();
    availableTrendSeries = trendSeries;
    drawPlot(null, null);
    if (isScopedAgent(selectedAgentId())) {
      Plotly.purge(document.getElementById("trend-plot"));
    }
    const points = trendSeries.reduce((total, series) => total + series.points.length, 0);
    document.getElementById("chart-note").textContent =
      `KPI X \u0026 KPI Y \u00b7 ${points} points`;
  } catch (err) {
    document.getElementById("chart-note").textContent = `Could not load trends: ${err.message}`;
  }
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// Model output is escaped first, then a small markdown subset is re-applied.
function renderMarkdown(text) {
  const lines = escapeHtml(text).split("\n");
  let html = "";
  let inList = false;

  for (let line of lines) {
    line = line
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`(.+?)`/g, "<code>$1</code>");

    const bullet = line.match(/^\s*[-*]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+\.\s+(.*)$/);

    if (bullet || numbered) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += `<li>${(bullet || numbered)[1]}</li>`;
      continue;
    }
    if (inList) { html += "</ul>"; inList = false; }

    if (/^\s*#{1,6}\s/.test(line)) {
      html += `<h3>${line.replace(/^\s*#{1,6}\s*/, "")}</h3>`;
    } else if (line.trim()) {
      html += `<p>${line}</p>`;
    }
  }
  if (inList) html += "</ul>";
  return html;
}

function renderStructuredFindings(summary) {
  const list = (items) => (items || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const references = (summary.evidence_references || [])
    .map((item) => `<code>${escapeHtml(item)}</code>`).join(" ");
  return `<div class="structured-findings">
    <section class="finding-primary">
      <div class="finding-label">Finding</div>
      <p>${escapeHtml(summary.finding)}</p>
    </section>
    <div class="finding-meta">
      <div><span class="finding-label">Confidence</span><strong>${escapeHtml(summary.confidence)}</strong></div>
      <div><span class="finding-label">Evidence</span><span>${references || "None listed"}</span></div>
    </div>
    <section><div class="finding-label">Limitations</div><ul>${list(summary.limitations)}</ul></section>
    <section><div class="finding-label">Recommended next actions</div><ul>${list(summary.recommended_next_actions)}</ul></section>
    <section><div class="finding-label">Alternative explanations</div><ul>${list(summary.alternative_explanations)}</ul></section>
  </div>`;
}

// Shown once as soon as tdbb_summary/nce_root_cause_analysis appear in evidence, not gated on
// final conversation status - the investigate_root_cause approval now follows summarize_tdbb,
// so a "completed"-only check would hide this message behind that later gate.
function renderTdbbSummaryMessage(evidence) {
  if (timeline.querySelector('[data-node="tdbb-summary"]')) return;
  const summary = evidence.tdbb_summary;
  const limits = (summary.limitations || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const node = addNode("msg agent", `<span class="badge ready">TDBB comparison</span>
    ${renderMarkdown(summary.message || "")}
    ${evidence.tdbb_comparison?.headline ? `<p><strong>${escapeHtml(evidence.tdbb_comparison.headline)}</strong></p>` : ""}
    ${limits ? `<ul>${limits}</ul>` : ""}`);
  node.dataset.node = "tdbb-summary";
}

function renderNceRootCauseMessage(evidence) {
  if (timeline.querySelector('[data-node="nce-root-cause"]')) return;
  const analysis = evidence.nce_root_cause_analysis;
  const list = (items) => (items || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const evidenceItems = list(analysis.correlated_evidence);
  const actions = list(analysis.recommended_next_actions);
  const limits = list(analysis.limitations);
  const node = addNode("msg agent", `<span class="badge ready">NCE root-cause correlation</span>
    ${renderMarkdown(analysis.message || "")}
    ${evidenceItems ? `<p><strong>Correlated evidence</strong></p><ul>${evidenceItems}</ul>` : ""}
    ${actions ? `<p><strong>Recommended next actions</strong></p><ul>${actions}</ul>` : ""}
    ${limits ? `<p><strong>Limitations</strong></p><ul>${limits}</ul>` : ""}`);
  node.dataset.node = "nce-root-cause";
}

function renderFindingsPanel(summary) {
  findingsContent.innerHTML = summary?.finding
    ? renderStructuredFindings(summary)
    : `<div class="findings">${renderMarkdown(summary || "")}</div>`;
  findingsPanel.hidden = false;
}

function clearEmptyState() {
  const empty = timeline.querySelector(".empty-state");
  if (empty) empty.remove();
}

function addNode(className, html) {
  clearEmptyState();
  const node = document.createElement("div");
  node.className = className;
  node.innerHTML = html;
  timeline.appendChild(node);
  timeline.scrollTop = timeline.scrollHeight;
  return node;
}

function setBusy(value, label) {
  busy = value;
  sendBtn.disabled = value;
  agentSelect.disabled = value || !registeredAgents.length;
  document.querySelectorAll(".gate-actions button").forEach((b) => (b.disabled = value));
  messageInput.disabled = value || !interactionPanel.hidden;

  const existing = document.getElementById("busy-node");
  if (existing) existing.remove();
  if (value) {
    addNode("msg status", `<span id="busy-inner"><span class="spinner"></span>${escapeHtml(label)}</span>`)
      .id = "busy-node";
  }
}

// Gate text comes from the agent package payload (question, details, labels);
// an outlier selector is shown when the payload offers candidates.
function previewWafersForCandidate(candidate) {
  if (!candidate) {
    renderWaferMap({ wafer_rows: lastWaferRows, anomalous_wafers: lastAnomalousWafers });
    return;
  }
  // Trend series are lot-level aggregates; lot_id is the correct key into the
  // wafer API, which only holds per-wafer detail for a subset of lots.
  const scoped = lastWaferRows.filter((row) =>
    row.exposure_equipment_id === candidate.machine
    && row.layer_id === candidate.layer_id
    && row.lot_id === candidate.lot_id);
  renderWaferMap({ wafer_rows: scoped, anomalous_wafers: lastAnomalousWafers });
}

// Shows a visible message instead of silently blocking the gate on an empty required field.
function showGateInputError(gateNode, inputEl, message) {
  inputEl.focus();
  inputEl.classList.add("invalid");
  gateNode.querySelector(".gate-error")?.remove();
  gateNode.querySelector(".gate-actions").insertAdjacentHTML(
    "beforebegin",
    `<p class="gate-error">${escapeHtml(message)}</p>`,
  );
}

function renderGate(request) {
  const payload = request.payload || {};
  const candidates = payload.detected_outliers || [];
  const selected = payload.selected_outlier;
  const details = Object.entries(payload.details || {})
    .filter(([, value]) => value !== null && value !== undefined && value !== "");

  const detail = details.length
    ? details.map(([label, value]) => `<div class="kv"><span>${escapeHtml(label)}</span><span>${
        escapeHtml(Array.isArray(value) ? value.join(", ") : value)}</span></div>`).join("")
    : selected
      ? `Most extreme: <code>${escapeHtml(selected.machine)}</code> /
       <code>${escapeHtml(selected.product)}</code> &mdash;
       <code>${escapeHtml(selected.kpi_value)}</code> absolute OPO KPI on
       <code>${escapeHtml(selected.date)}</code>`
      : candidates.length ? "Select the candidate to investigate." : "";

  const selector = candidates.length
    ? `<select id="outlier-select" aria-label="Candidate outlier to investigate">${candidates
        .map((candidate, index) => {
          const candidateId = candidate.id ?? String(index);
          return `<option value="${escapeHtml(candidateId)}"${
          selected?.id && candidate.id === selected.id ? " selected" : ""
        }>
          ${escapeHtml(candidate.machine)} / ${escapeHtml(candidate.product)} —
          ${escapeHtml(candidate.kpi_value)} absolute OPO KPI (${escapeHtml(candidate.date)})
        </option>`;
        }).join("")}</select>`
    : "";

  const actionOptions = Array.isArray(payload.options) ? payload.options : null;
  const actionSelector = actionOptions
    ? `<label class="gate-input-label" for="action-select">Recommended action</label>
       <select id="action-select" aria-label="Recommended action">
         <option value="">Choose an action</option>
         ${[...new Set([...actionOptions, "End investigation"])].map((option) =>
           `<option value="${escapeHtml(option)}">${escapeHtml(option)}</option>`).join("")}
       </select>`
    : "";

  const field = payload.input;
  const input = field?.name
    ? `<label class="gate-input-label" for="gate-input">${escapeHtml(field.label || field.name)}</label>
       <input id="gate-input" type="${field.type === "number" ? "number" : "text"}" step="any"
         placeholder="${escapeHtml(field.placeholder || "")}" autocomplete="off" />`
    : "";

  interactionPanel.hidden = false;
  interactionPanel.innerHTML = `
    <div class="gate">
      <div class="gate-label">Approval required</div>
      <h3>${escapeHtml(payload.question || gateQuestion(request))}</h3>
      <div class="gate-detail">${detail}</div>
      ${selector}
      ${actionSelector}
      ${input}
      <div class="gate-actions">
        <button type="button" data-action="approve"${actionOptions ? " disabled" : ""}>${escapeHtml(payload.approve_label || "Approve")}</button>
        <button type="button" data-action="reject" class="reject">${escapeHtml(payload.reject_label || "Reject")}</button>
      </div>
    </div>`;

  // Keep every candidate circled while the user is still choosing which one to investigate.
  if (candidates.length) {
    drawPlot(candidates, selected);
    const outlierSelect = interactionPanel.querySelector("#outlier-select");
    const candidateFor = (value) =>
      candidates.find((candidate, index) => (candidate.id ?? String(index)) === value);
    previewWafersForCandidate(candidateFor(outlierSelect?.value) || candidates[0]);
    outlierSelect?.addEventListener("change", () => {
      previewWafersForCandidate(candidateFor(outlierSelect.value));
    });
  }

  const gate = interactionPanel;
  const actionSelect = gate.querySelector("#action-select");
  actionSelect?.addEventListener("change", () => {
    gate.querySelector('[data-action="approve"]').disabled = !actionSelect.value;
  });
  gate.querySelector("#gate-input")?.addEventListener("input", (event) => {
    event.target.classList.remove("invalid");
    gate.querySelector(".gate-error")?.remove();
  });
  gate.querySelector('[data-action="approve"]').onclick = () => {
    const select = gate.querySelector("#outlier-select");
    const values = {};
    const inputEl = gate.querySelector("#gate-input");
    if (actionSelect) values.selected_action = actionSelect.value;
    if (inputEl) {
      const raw = inputEl.value.trim();
      const required = field.required !== false;
      if (required && !raw) {
        showGateInputError(gate, inputEl, `Enter "${field.label || field.name}" before continuing.`);
        return;
      }
      if (field.type === "number") {
        if (raw) {
          const number = Number(raw);
          if (!Number.isFinite(number)) {
            showGateInputError(gate, inputEl, `Enter a valid number for "${field.label || field.name}".`);
            return;
          }
          values[field.name] = number;
        }
      } else {
        values[field.name] = raw;
      }
    }
    gate.querySelector(".gate-error")?.remove();
    resolveGate(gate, "Approved", {
      approved: true,
      selectedOutlierId: select?.value ?? null,
      values,
    });
  };
  gate.querySelector('[data-action="reject"]').onclick = () =>
    resolveGate(gate, "Rejected", { approved: false });
}

function gateQuestion(request) {
  return request.approval_id === "investigate_outlier"
    ? "Investigate the selected outlier?"
    : request.approval_id === "select_recommended_action"
      ? "Select and approve a recommended action?"
    : `Approval required: ${request.approval_id}`;
}

function resolveGate(gateNode, label, decision) {
  const gateEl = gateNode.querySelector(".gate");
  const actionsEl = gateNode.querySelector(".gate-actions");
  const buttons = [...actionsEl.querySelectorAll("button")];
  const select = gateNode.querySelector("select");
  const input = gateNode.querySelector("input");
  buttons.forEach((button) => (button.disabled = true));
  if (select) select.disabled = true;
  if (input) input.disabled = true;
  gateEl.classList.remove("gate-failed");
  gateEl.querySelector(".gate-error")?.remove();
  send(
    () => window.OpoBff.resume(conversationId, decision, conversationVersion),
    "Continuing investigation\u2026",
    {
      onSuccess: () => {
        gateEl.classList.add("resolved");
        actionsEl.innerHTML = `<span class="gate-label">${escapeHtml(label)}</span>`;
      },
      onError: (err) => {
        gateEl.classList.add("gate-failed");
        actionsEl.insertAdjacentHTML(
          "beforebegin",
          `<p class="gate-error">Could not continue: ${escapeHtml(err.message)}. You can try again.</p>`,
        );
        buttons.forEach((button) => (button.disabled = false));
        if (select) select.disabled = false;
        if (input) input.disabled = false;
      },
    },
  );
}

function renderEvidence(evidence) {
  if (!evidence) return;
  let html = "";

  const filters = evidence.trend_filters || {};
  const list = (values) => (values || []).join(", ");
  const scope = [
    ["Range", filters.lookback_days ? `Last ${filters.lookback_days} days` : null],
    ["From", filters.start_date],
    ["To", filters.end_date],
    ["Lots", list(filters.lot_ids)],
    ["Products", list(filters.product_ids)],
    ["Layers", list(filters.layer_ids)],
    ["Exposure equipment", list(filters.exposure_equipment_ids)],
    ["Chucks", list(filters.chuck_ids)],
  ].filter(([, value]) => value);
  if (scope.length) {
    html += `<div class="card"><h3>Scope</h3>${scope
      .map(([label, value]) => `<div class="kv"><span>${escapeHtml(label)}</span><span>${escapeHtml(value)}</span></div>`)
      .join("")}</div>`;
  }

  if (evidence.tdbb_comparison?.budgets?.length) {
    const comparison = evidence.tdbb_comparison;
    const value = (v) => (v == null ? "" : Number(v).toFixed(2));
    const pct = (v) => (v == null ? "" : `${v > 0 ? "+" : ""}${v}%`);
    html += `<div class="card"><h3>TDBB budgets (nm)</h3>
      <div class="kv"><span>Runs before / after</span><span>${escapeHtml(comparison.before.run_count)} / ${escapeHtml(comparison.after.run_count)}</span></div>
      ${comparison.headline ? `<p>${escapeHtml(comparison.headline)}</p>` : ""}
      <table>
        <tr><th>Budget</th><th>X before</th><th>X after</th><th>\u0394X</th><th>Y before</th><th>Y after</th><th>\u0394Y</th></tr>
        ${comparison.budgets.map((b) => `<tr class="${comparison.largest_increase?.budget === b.budget ? "anomalous" : ""}">
          <td>${escapeHtml(b.label)}</td>
          <td>${escapeHtml(value(b.before_x))}</td><td>${escapeHtml(value(b.after_x))}</td><td>${escapeHtml(pct(b.delta_x_pct))}</td>
          <td>${escapeHtml(value(b.before_y))}</td><td>${escapeHtml(value(b.after_y))}</td><td>${escapeHtml(pct(b.delta_y_pct))}</td>
        </tr>`).join("")}
      </table></div>`;
  }

  if (evidence.selected_outlier) {
    const o = evidence.selected_outlier;
    html += `<div class="card"><h3>Outlier</h3>
      <div class="kv"><span>Machine</span><span>${escapeHtml(o.machine)}</span></div>
      <div class="kv"><span>Product</span><span>${escapeHtml(o.product)}</span></div>
      <div class="kv"><span>KPI deviation</span><span>${escapeHtml(o.deviation_pct)}%</span></div>
    </div>`;
  }

  if (evidence.workspace?.workspace_id) {
    html += `<div class="card"><h3>Workspace</h3>
      <div class="kv"><span>ID</span><span>${escapeHtml(evidence.workspace.workspace_id)}</span></div>
      ${Object.entries(evidence.applied_filters || {}).map(([k, v]) =>
        `<div class="kv"><span>${escapeHtml(k)}</span><span>${escapeHtml(v)}</span></div>`).join("")}
    </div>`;
  }

  if (evidence.registration) {
    const registration = evidence.registration;
    html += `<div class="card"><h3>Registration</h3>
      <div class="step">
        <span class="dot ${registration.status === "READY" ? "done" : ""}"></span>
        <span>${escapeHtml(registration.status)} — ${escapeHtml(registration.progress_pct)}%</span>
      </div>
      <div class="kv"><span>Table</span><span>${escapeHtml(registration.table)}</span></div>
    </div>`;
  }

  if (evidence.wafer_rows?.length) {
    const anomalous = new Set(evidence.anomalous_wafers || []);
    const wafers = new Map();
    evidence.wafer_rows.forEach((r) => {
      const key = `${r.lot_id ?? ""}\u0000${r.wafer_id}`;
      const magnitude = Number(r.overlay_magnitude_um);
      const wafer = wafers.get(key) || { lot: r.lot_id, wafer: r.wafer_id, points: 0, max: null };
      wafer.points += 1;
      if (Number.isFinite(magnitude)) wafer.max = wafer.max === null ? magnitude : Math.max(wafer.max, magnitude);
      wafers.set(key, wafer);
    });
    html += `<div class="card"><h3>Wafers</h3><table>
      <tr><th>Lot</th><th>Wafer</th><th>Points</th><th>Max magnitude</th></tr>
      ${[...wafers.values()].map((w) => `
        <tr class="${anomalous.has(w.wafer) ? "anomalous" : ""}">
          <td>${escapeHtml(w.lot)}</td>
          <td>${escapeHtml(w.wafer)}</td>
          <td>${escapeHtml(w.points)}</td>
          <td>${escapeHtml(w.max === null ? "" : w.max.toFixed(4))}</td>
        </tr>`).join("")}
    </table></div>`;
  }

  if (evidence.spatial_pattern && evidence.spatial_pattern.pattern !== "no_data") {
    const sp = evidence.spatial_pattern;
    html += `<div class="card"><h3>Spatial pattern</h3>
      <div class="kv"><span>Pattern</span><span>${escapeHtml(sp.pattern)}</span></div>
      <div class="kv"><span>Edge points</span><span>${escapeHtml(sp.edge_count)}</span></div>
      <div class="kv"><span>Center points</span><span>${escapeHtml(sp.center_count)}</span></div>
      <div class="kv"><span>Edge fraction</span><span>${escapeHtml(sp.edge_fraction)}</span></div>
    </div>`;
  }

  if (html) evidencePane.innerHTML = html;
}

function effectiveScope(evidence) {
  const scope = evidence.detection_scope || {};
  return evidence.confirmed_threshold == null ? scope : {
    ...scope,
    mode: "absolute",
    limit_value: evidence.confirmed_threshold,
    direction: "above",
    threshold_unit: "absolute",
  };
}

function ruleLabel(scope) {
  const {
    mode,
    limit_value: limit,
    direction,
    baseline_deviation_pct: deviation,
    threshold_unit: unit,
  } = scope;
  return mode === "absolute"
    ? `${direction} ${limit}${unit === "percent" ? "% from baseline" : " absolute OPO KPI"}`
    : `more than ${deviation}% above each machine's own baseline`;
}

function renderTrendChart(evidence) {
  if (!evidence) return;
  const note = document.getElementById("chart-note");
  const selectedOutlier = evidence.selected_outlier || null;
  const selected = selectedOutlier?.machine || null;
  const scope = effectiveScope(evidence);
  const outliers = evidence.outliers || [];
  const hasAppliedRule = evidence.confirmed_threshold != null || outliers.length > 0;
  // Once a specific candidate is selected, ring only that point - not the whole candidate set.
  drawPlot(hasAppliedRule ? (selectedOutlier ? [selectedOutlier] : outliers) : null, selected);
  if (!scope.mode) return;
  const rule = ruleLabel(scope);

  if (!outliers.length) {
    note.textContent = `No points ${rule}`;
    return;
  }

  if (selectedOutlier) {
    note.textContent = `Investigating 1 of ${outliers.length} candidates: ${selectedOutlier.machine} / ${selectedOutlier.product}`;
    return;
  }

  const points = outliers.reduce((total, item) =>
    total + outlierPoints(item).length, 0);
  note.innerHTML = `<span class="ring-key"></span>${points} points ${rule},
     across ${outliers.length} series`;
}

function renderWaferMap(evidence) {
  const plotEl = document.getElementById("wafer-plot");
  const noteEl = document.getElementById("wafer-note");

  if (!plotEl || !evidence) return;

  const rows = evidence.wafer_rows || [];
  // Keep the broadest (pre-approval) wafer preview around so the outlier dropdown
  // can show a live, candidate-scoped wafer map before the analyst approves anything.
  if (rows.length) {
    lastWaferRows = rows;
    lastAnomalousWafers = evidence.anomalous_wafers || [];
  }
  if (!rows.length) {
    noteEl.textContent = "No wafer data";
    Plotly.purge(plotEl);
    plotEl.style.height = "";
    return;
  }

  const anomalySet = new Set(evidence.anomalous_wafers || []);

  // A point's true wafer coordinate is the reticle field's center plus its
  // intrafield offset - using the intrafield offset alone collapses every field
  // (there can be dozens tiled across the wafer) onto the same handful of points.
  const trueX = (row) =>
    Number(row.exposureprocessjob_waferexposureprocessjob_exposurelogicalwafer_exposedfield_field_center_x ?? 0) +
    Number(row.measureprocessjob_wafermeasureprocessjob_measurement_intrafieldposition_position_x ?? row.position_x ?? 0);
  const trueY = (row) =>
    Number(row.exposureprocessjob_waferexposureprocessjob_exposurelogicalwafer_exposedfield_field_center_y ?? 0) +
    Number(row.measureprocessjob_wafermeasureprocessjob_measurement_intrafieldposition_position_y ?? row.position_y ?? 0);

  // Scale to the data instead of fixed constants, since a real wafer's field layout
  // and overlay magnitude can both be very different from the old mock's.
  const maxCoordMagnitude = rows.reduce((max, row) => Math.max(max, Math.abs(trueX(row)), Math.abs(trueY(row))), 0);
  const WAFER_RADIUS = maxCoordMagnitude > 0 ? maxCoordMagnitude * 1.08 : 27;
  const AXIS_RANGE = WAFER_RADIUS * 1.15;
  const maxOverlayMagnitude = rows.reduce((max, row) => {
    const magnitude = Math.max(Math.abs(Number(row.overlay_x ?? 0)), Math.abs(Number(row.overlay_y ?? 0)));
    return Number.isFinite(magnitude) ? Math.max(max, magnitude) : max;
  }, 0);
  // Arrows are meant to fit within one reticle field's footprint, not scale with
  // the whole wafer radius, so target length is a fixed fraction of field spacing.
  const TARGET_VECTOR_LENGTH = 10;
  const vectorScale = maxOverlayMagnitude > 0 ? TARGET_VECTOR_LENGTH / maxOverlayMagnitude : 1;

  // Index once because the broad outlier preview can contain tens of thousands of
  // points; repeatedly scanning all rows for every panel makes rendering quadratic.
  const rowsByPanel = new Map();
  rows.forEach((row) => {
    const lotId = row.lot_id ?? "UNKNOWN_LOT";
    const panelKey = `${lotId}\u0000${row.wafer_id}`;
    const panelRows = rowsByPanel.get(panelKey);
    if (panelRows) panelRows.push(row);
    else rowsByPanel.set(panelKey, [row]);
  });
  // Organize wafers by lot - one row of wafer panels per lot, matching how a wafer
  // analysis tool would lay out the wafers actually processed together in a lot.
  const lotIds = [...new Set(rows.map((row) => row.lot_id ?? "UNKNOWN_LOT"))];
  const waferIdsPerLot = new Map(
    lotIds.map((lotId) => [lotId, [...new Set(rows.filter((row) => (row.lot_id ?? "UNKNOWN_LOT") === lotId).map((row) => row.wafer_id))]])
  );
  const columns = Math.max(1, ...[...waferIdsPerLot.values()].map((ids) => ids.length));
  const gridRows = lotIds.length;
  const showVectors = lotIds.length === 1;

  const traces = [];
  const annotations = [];
  const shapes = [];
  const waferLayout = {};

  lotIds.forEach((lotId, rowIndex) => {
    const waferIdsForLot = waferIdsPerLot.get(lotId);
    waferIdsForLot.forEach((waferId, colIndex) => {
      const panelIndex = rowIndex * columns + colIndex;
      const axisNumber = panelIndex + 1;
      const axisSuffix = axisNumber === 1 ? "" : axisNumber;
      const axisRef = `x${axisSuffix}`;
      const yAxisRef = `y${axisSuffix}`;
      const panelRows = rowsByPanel.get(`${lotId}\u0000${waferId}`) || [];

      // A single lot's wafer has no duplicate sites, so every real point is plotted
      // as-is (no averaging) - averaging is only needed when multiple lots' samples
      // land on the same physical field/site, which doesn't happen within one lot.
      const measurementX = panelRows.map(trueX);
      const measurementY = panelRows.map(trueY);
      const pointColors = panelRows.map((row) => {
        const valid = row.overlay_valid_x !== false && row.overlay_valid_y !== false;
        return valid && anomalySet.has(waferId) ? "#f85149" : valid ? "#4c9aff" : "#667085";
      });
      const pointText = panelRows.map((row) => `${lotId} \u00b7 ${waferId}`);

      traces.push({
        type: showVectors ? "scattergl" : "scatter",
        mode: "markers",
        x: measurementX,
        y: measurementY,
        xaxis: axisRef,
        yaxis: yAxisRef,
        marker: { size: 4, color: pointColors, opacity: 0.75 },
        text: pointText,
        hovertemplate: "%{text}<br>x=%{x:.2f}, y=%{y:.2f}<extra></extra>",
        showlegend: false,
      });

      const xStart = colIndex / columns + 0.008;
      const xEnd = (colIndex + 1) / columns - 0.008;
      const yEnd = 1 - rowIndex / gridRows - 0.05;
      const yStart = 1 - (rowIndex + 1) / gridRows + 0.05;
      waferLayout[`xaxis${axisSuffix}`] = {
        domain: [xStart, xEnd],
        anchor: yAxisRef,
        range: [-AXIS_RANGE, AXIS_RANGE],
        zeroline: false,
        gridcolor: "#2a3441",
        showticklabels: false,
        fixedrange: true,
      };
      waferLayout[`yaxis${axisSuffix}`] = {
        domain: [yStart, yEnd],
        anchor: "free",
        position: 0,
        range: [-AXIS_RANGE, AXIS_RANGE],
        zeroline: false,
        gridcolor: "#2a3441",
        showticklabels: false,
        fixedrange: true,
      };
      annotations.push({
        x: 0,
        y: AXIS_RANGE * 0.96,
        xref: axisRef,
        yref: yAxisRef,
        text: `<b>${waferId}</b>${anomalySet.has(waferId) ? " · anomaly" : ""}`,
        showarrow: false,
        font: { color: anomalySet.has(waferId) ? "#f85149" : "#e4e8ee", size: 11 },
      });
      shapes.push({
        type: "circle",
        xref: axisRef,
        yref: yAxisRef,
        x0: -WAFER_RADIUS,
        y0: -WAFER_RADIUS,
        x1: WAFER_RADIUS,
        y1: WAFER_RADIUS,
        line: { color: "#667085", width: 1 },
      });

      if (showVectors) {
        panelRows.forEach((row) => {
          const px = trueX(row);
          const py = trueY(row);
          const ux = Number(row.overlay_x ?? 0);
          const uy = Number(row.overlay_y ?? 0);
          const valid = row.overlay_valid_x !== false && row.overlay_valid_y !== false;
          if (!valid || !Number.isFinite(px) || !Number.isFinite(py) || (ux === 0 && uy === 0)) return;
          annotations.push({
            x: px + ux * vectorScale,
            y: py + uy * vectorScale,
            ax: px,
            ay: py,
            xref: axisRef,
            yref: yAxisRef,
            axref: axisRef,
            ayref: yAxisRef,
            showarrow: true,
            arrowhead: 3,
            arrowsize: 1.1,
            arrowwidth: anomalySet.has(waferId) ? 2 : 1.5,
            arrowcolor: anomalySet.has(waferId) ? "#f85149" : "#4c9aff",
            text: "",
          });
        });
      }
    });

    // One rotated label per lot row, to the left of that row's wafer panels.
    const yEnd = 1 - rowIndex / gridRows - 0.05;
    const yStart = 1 - (rowIndex + 1) / gridRows + 0.05;
    annotations.push({
      x: -0.01,
      y: (yStart + yEnd) / 2,
      xref: "paper",
      yref: "paper",
      xanchor: "right",
      text: `<b>${lotId}</b>`,
      showarrow: false,
      textangle: -90,
      font: { color: "#8b97a8", size: 11 },
    });
  });

  Object.assign(waferLayout, {
    grid: { rows: gridRows, columns, pattern: "independent" },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    margin: { l: 28, r: 8, t: 12, b: 8 },
    height: Math.max(
      480,
      gridRows * (showVectors ? 520 : Math.max(150, Math.min(360, Math.round(plotEl.clientWidth / columns))))
    ),
    showlegend: false,
    hovermode: "closest",
    annotations,
    shapes,
    font: { color: "#8b97a8", size: 11 },
  });

  const totalWafers = [...waferIdsPerLot.values()].reduce((n, ids) => n + ids.length, 0);
  noteEl.textContent = `${rows.length} point measurements across ${totalWafers} wafer${totalWafers === 1 ? "" : "s"} in ${lotIds.length} lot${lotIds.length === 1 ? "" : "s"}`;
  // Responsive Plotly sizes to its div, so the div must carry the layout height.
  plotEl.style.height = `${waferLayout.height}px`;
  Plotly.react(plotEl, traces, waferLayout, PLOT_CONFIG);
}

function handleResponse(runtime) {
  conversationId = runtime.conversationId;
  conversationVersion = runtime.version ?? null;
  conversationInput.value = conversationId ?? "";

  const evidence = runtime.result || {};
  const agentId = runtime.agentId || selectedAgentId();
  const isV4 = isScopedAgent(agentId);
  if (!evidence.tdbb_run) {
    const runResults = Array.isArray(evidence.tdbb_runs) ? evidence.tdbb_runs : [];
    const beforeRun = Array.isArray(evidence.tdbb_before_run)
      ? evidence.tdbb_before_run[0]
      : evidence.tdbb_before_run || runResults[0];
    const afterRun = Array.isArray(evidence.tdbb_after_run)
      ? evidence.tdbb_after_run[0]
      : evidence.tdbb_after_run || runResults[1];
    const beforePeriod = beforeRun?.periods?.find((period) => period.period === "before")
      || beforeRun?.periods?.[0];
    const afterPeriod = afterRun?.periods?.find((period) => period.period === "after")
      || afterRun?.periods?.[0];
    if (beforePeriod && afterPeriod) {
      evidence.tdbb_run = {
        settings: beforeRun.settings,
        periods: [beforePeriod, afterPeriod],
        // Each run already covers the full before/after split internally (both tagged
        // "before" and "after"), so a naive concatenation lets a map lookup's .find() match
        // beforeRun's OWN "after" half instead of afterRun's true "after" data - keep only
        // the half each run is actually meant to contribute, matching beforePeriod/afterPeriod.
        maps: [
          ...(beforeRun.maps || []).filter((m) => m.period === "before"),
          ...(afterRun.maps || []).filter((m) => m.period === "after"),
        ],
      };
    }
  }
  document.getElementById("trend-title").textContent = isV4 ? "OPO performance trend" : "Daily overlay trend";
  document.querySelector(".wafer-panel").hidden = isV4;
  tdbbPanel.hidden = !isV4 || !evidence.comparison_scope;
  document.getElementById("tdbb-views").hidden = !isV4;
  // Fingerprint/EExy/residual wafer maps are step-3 evidence (the root-cause correlation),
  // not shown alongside the step-2 TDBB bars - revealed once that analysis exists.
  const ncePanelWasHidden = ncePanel.hidden;
  ncePanel.hidden = !isV4 || !evidence.nce_root_cause_analysis;
  if (evidence.trend_series) {
    trendSeries = Array.isArray(evidence.trend_series)
      ? evidence.trend_series
      : evidence.trend_series.series || [];
  }
  else if (isV4) trendSeries = [];
  if (isV4) {
    const filters = evidence.trend_filters || {};
    // Only draw the change-date line once the analyst has confirmed it via comparison_scope.
    const changeDate = evidence.comparison_scope?.change_date;
    const wafers = drawV3Trend(trendSeries, changeDate);
    document.getElementById("chart-note").textContent = filters.start_date
      ? `${filters.start_date} to ${filters.end_date || "?"} \u00b7 ${wafers} wafers \u00b7 overlay X / Y (nm)`
      : "Start date needed";
    if (evidence.comparison_scope) renderTdbb(evidence);
  } else {
    renderTrendChart(evidence);
  }
  renderWaferMap(evidence);
  renderEvidence(evidence);

  // Scroll to the step-3 wafer maps only on the transition into view, not on every re-render.
  // Plain synchronous call (not requestAnimationFrame): the plot containers' heights are
  // already set synchronously above via Plotly.react, and rAF can be throttled/paused
  // indefinitely in a backgrounded/non-visible tab, silently dropping the scroll.
  if (ncePanelWasHidden && !ncePanel.hidden) {
    ncePanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  if (isV4) {
    // Rendered as soon as each becomes available, independent of the review_tdbb approval
    // that produces both (tdbb_summary and nce_root_cause_analysis land in the same resume),
    // so the analyst sees both messages together, not gated behind a later step.
    if (evidence.tdbb_summary) renderTdbbSummaryMessage(evidence);
    if (evidence.nce_root_cause_analysis) renderNceRootCauseMessage(evidence);
    if (runtime.approvalRequest) {
      renderGate(runtime.approvalRequest);
      return;
    }
    interactionPanel.hidden = true;
    if (runtime.status === "completed" && evidence.comparison_scope && !evidence.comparison_scope.change_date) {
      addNode("msg agent", `<p>No change date could be used within the analysed window. ${escapeHtml(evidence.comparison_scope.interpretation || "")}</p>`);
    } else if (runtime.status === "cancelled") {
      addNode("msg agent", "<p>Finished without TDBB analysis.</p>");
    } else if (runtime.status === "completed" && !evidence.trend_filters?.start_date) {
      addNode("msg agent", "<p>No start date was found. Please include a date such as \"since 17 Aug\".</p>");
    } else if (runtime.status === "failed") {
      addNode("msg agent", "<p>Could not complete the TDBB comparison.</p>");
    }
    return;
  }

  const scope = effectiveScope(evidence);
  if (scope.mode) {
    const pending = evidence.confirmed_threshold == null && scope.suggested_limit_value != null
      && runtime.approvalRequest?.approval_id === "confirm_suggested_threshold";
    const badge = pending ? "Suggested limit" : scope.mode === "absolute" ? "Absolute limit" : "Per-machine baseline";
    const interpretation = evidence.trend_filters?.interpretation;
    const html = `<strong>${badge}</strong>: marking points ${escapeHtml(ruleLabel(scope))}` +
      (interpretation ? `<br><span class="interpretation">${escapeHtml(interpretation)}</span>` : "");
    const existing = timeline.querySelector(".msg.status.rule");
    if (existing) existing.innerHTML = html;
    else addNode("msg status rule", html);
  }

  if (runtime.approvalRequest) {
    renderGate(runtime.approvalRequest);
    return;
  }

  interactionPanel.hidden = true;

  if (runtime.status === "cancelled") {
    findingsPanel.hidden = true;
    addNode("msg agent", `<span class="badge cancelled">Cancelled</span>
      <p>Investigation stopped${evidence.cancelled_at
        ? ` at <code>${escapeHtml(evidence.cancelled_at)}</code>` : ""}.
      No downstream resources were provisioned.</p>`);
    return;
  }

  if (runtime.status === "failed") {
    findingsPanel.hidden = true;
    addNode("msg agent", `<span class="badge cancelled">Failed</span>
      <p>The agent could not complete this investigation.</p>`);
    return;
  }

  if (runtime.status !== "completed") return;

  if (!(evidence.outliers || []).length) {
    findingsPanel.hidden = true;
    addNode("msg agent", `<span class="badge ready">No outliers</span>
      <p>No points fall ${escapeHtml(scope.mode ? ruleLabel(scope) : "outside the detection rule")}.</p>`);
    return;
  }

  renderFindingsPanel(evidence.findings);
  addNode("msg agent", `<span class="badge ready">Complete</span>
    ${evidence.findings?.finding ? renderStructuredFindings(evidence.findings) :
      `<div class="findings">${renderMarkdown(evidence.findings || "")}</div>`}`);
}

async function send(call, busyLabel, callbacks = {}) {
  setBusy(true, busyLabel);
  try {
    const response = await call();
    handleResponse(response);
    callbacks.onSuccess?.(response);
  } catch (err) {
    callbacks.onError?.(err);
    addNode("msg agent", `<span class="badge cancelled">Error</span>
      <p>${escapeHtml(err.message)}</p>`);
  } finally {
    setBusy(false);
  }
}

document.getElementById("composer").onsubmit = (event) => {
  event.preventDefault();
  if (busy) return;
  const message = messageInput.value.trim();
  if (!message) return;
  conversationId = null;
  conversationVersion = null;
  timeline.innerHTML = "";
  interactionPanel.hidden = true;
  interactionPanel.innerHTML = "";
  findingsPanel.hidden = true;
  findingsContent.innerHTML = "";
  tdbbPanel.hidden = true;
  ncePanel.hidden = true;
  const isV4 = isScopedAgent(selectedAgentId());
  document.querySelector(".wafer-panel").hidden = isV4;
  messageInput.disabled = false;
  evidencePane.innerHTML = '<div class="empty-state small"><p>No evidence yet.</p></div>';
  if (isV4) Plotly.purge(document.getElementById("trend-plot"));
  else drawPlot(null, null);
  addNode("msg user", escapeHtml(message));
  send(() => window.OpoBff.startChat(
    message, registeredAgents[agentSelect.selectedIndex], availableTrendScopes()
  ), "Analysing trends\u2026");
};

toggleRightPanel.onclick = () => {
  setRightPanelCollapsed(!mainLayout.classList.contains("right-panel-collapsed"));
  ["trend-plot", "wafer-plot"].forEach((id) => {
    const el = document.getElementById(id);
    if (el.data) Plotly.Plots.resize(el);
  });
};

document.getElementById("reopen-btn").onclick = async () => {
  const id = conversationInput.value.trim();
  if (!id || busy) return;
  setBusy(true, "Reopening investigation…");
  try {
    const runtime = await window.OpoBff.getConversation(id);
    timeline.innerHTML = "";
    addNode("msg status", `Reopened conversation <code>${escapeHtml(id)}</code>`);
    handleResponse(runtime);
    if (!runtime.approvalRequest && runtime.status === "waiting_for_approval") {
      addNode("msg agent", "<p>This investigation has no pending decision.</p>");
    }
  } catch (err) {
    addNode("msg agent", `<span class="badge cancelled">Error</span>
      <p>Could not reopen: ${escapeHtml(err.message)}</p>`);
  } finally {
    setBusy(false);
  }
};

async function loadAgents() {
  try {
    registeredAgents = (await window.OpoBff.listAgents()).filter(
      (agent) => agent.agentId === "opo-analysis-agent-v1" || isScopedAgent(agent.agentId),
    );
  } catch (err) {
    registeredAgents = [];
    agentSelect.title = `Could not load agents: ${err.message}`;
  }
  agentSelect.innerHTML = registeredAgents.length
    ? registeredAgents
        .map((a) => `<option title="${escapeHtml(a.description)}">${escapeHtml(a.displayName || a.agentId)} (${escapeHtml(a.version)})</option>`)
        .join("")
    : "<option>No agents registered</option>";
  agentSelect.disabled = busy || !registeredAgents.length;
}

agentSelect.addEventListener("change", () => {
  const isV4 = isScopedAgent(selectedAgentId());
  document.querySelector(".wafer-panel").hidden = isV4;
  tdbbPanel.hidden = true;
  ncePanel.hidden = true;
  document.getElementById("trend-title").textContent = isV4 ? "OPO performance trend" : "Daily overlay trend";
  if (isV4) {
    Plotly.purge(document.getElementById("trend-plot"));
    document.getElementById("chart-note").textContent = "Awaiting scope";
  } else {
    trendSeries = availableTrendSeries;
    drawPlot(null, null);
    const points = (availableTrendSeries || []).reduce((total, series) => total + series.points.length, 0);
    document.getElementById("chart-note").textContent = `KPI X & KPI Y · ${points} points`;
  }
});

loadAgents();
loadTrends();
