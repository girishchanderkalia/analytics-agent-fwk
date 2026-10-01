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
const agentSelect = document.getElementById("agent-select");
const tdbbPanel = document.getElementById("tdbb-panel");
const ncePanel = document.getElementById("nce-panel");
const V2_AGENT = "opo-monitoring-v2";
const V3_AGENT = "opo-monitoring-v3";
const V4_AGENT = "opo-monitoring-v4";
const selectedAgentId = () => registeredAgents[agentSelect.selectedIndex]?.agentId;
const isScopedAgent = (agentId) => agentId === V2_AGENT || agentId === V3_AGENT || agentId === V4_AGENT;

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

const SERIES_COLOURS = [
  "#4c9aff", "#a371f7", "#3fb950", "#f78166", "#e3b341",
  "#39c5cf", "#db61a2", "#8ddb8c", "#79c0ff", "#d29922",
  "#f47067", "#56d4dd",
];
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

function availableTrendScopes() {
  return (availableTrendSeries || []).map((series) => ({
    product: series.product,
    layer: series.layer_id,
    scanner: series.exposure_equipment_id || series.machine,
    months: [...new Set((series.points || []).map((point) => String(point.date).slice(0, 7)))].sort(),
  }));
}

function v2StarterPrompt() {
  const observed = (availableTrendSeries || []).filter((series) =>
    series.product && series.layer_id && (series.exposure_equipment_id || series.machine) && series.points?.length
  ).map((series) => ({
    series,
    month: series.points.map((point) => String(point.date).slice(0, 7)).sort().at(-1),
  })).sort((left, right) => right.month.localeCompare(left.month) || right.series.points.length - left.series.points.length)[0];
  if (!observed) return "Show OPO performance by product, layer, and scanner since a date";
  const { product, layer_id: layer, exposure_equipment_id, machine } = observed.series;
  return `Show OPO performance of product ${product}, layer ${layer} on scanner ${exposure_equipment_id || machine} since ${observed.month}-01`;
}

// Series are grouped per lot, so pick the product/layer/scanner scope with the most wafers.
function v3StarterPrompt() {
  const scopes = new Map();
  (availableTrendSeries || []).forEach((series) => {
    const scanner = series.exposure_equipment_id || series.machine;
    if (!series.product || !series.layer_id || !scanner || !series.points?.length) return;
    const key = `${series.product}\u0000${series.layer_id}\u0000${scanner}`;
    const scope = scopes.get(key) || { product: series.product, layer: series.layer_id, scanner, dates: [] };
    scope.dates.push(...series.points.map((point) => String(point.date).slice(0, 10)));
    scopes.set(key, scope);
  });
  const observed = [...scopes.values()].sort((left, right) => right.dates.length - left.dates.length)[0];
  if (!observed) return "Show OPO performance by product, layer, and scanner since a date";
  const first = new Date(`${observed.dates.sort()[0]}T00:00:00Z`);
  const since = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth(), 17))
    .toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
  return `Show OPO performance of product ${observed.product}, layer ${observed.layer} on scanner ${observed.scanner} since ${since} ${first.getUTCFullYear()}`;
}

function starterPrompt(agentId) {
  if (agentId === V2_AGENT) return v2StarterPrompt();
  if (agentId === V3_AGENT || agentId === V4_AGENT) return v3StarterPrompt();
  return "Show me trends and outliers";
}

function drawPlot(scope, selectedMachine) {
  if (!trendSeries) return;
  document.getElementById("trend-plot").style.height = "";
  if (!trendSeries.length) {
    Plotly.purge(document.getElementById("trend-plot"));
    return;
  }

  const traces = trendSeries.map((s, idx) => {
    const dimmed = selectedMachine && s.machine !== selectedMachine;
    return {
      type: "scatter",
      mode: "markers",
      name: `${s.machine} / ${s.product}`,
      x: s.points.map((p) => p.date),
      y: s.points.map((p) => p.kpi_value),
      marker: { size: 8, color: SERIES_COLOURS[idx % SERIES_COLOURS.length] },
      opacity: dimmed ? 0.3 : 1,
      hovertemplate: `%{x}<br>%{y:.2f} absolute OPO KPI<extra>${s.machine} / ${s.product}</extra>`,
    };
  });

  const rings = { x: [], y: [], text: [] };
  if (scope?.mode) {
    trendSeries.forEach((series) => {
      const values = (series.points || [])
        .map((point) => Number(point.kpi_value))
        .filter(Number.isFinite)
        .sort((left, right) => left - right);
      if (!values.length) return;

      const middle = Math.floor(values.length / 2);
      const baseline = values.length % 2
        ? values[middle]
        : (values[middle - 1] + values[middle]) / 2;
      const direction = scope.direction || "below";
      const limit = Number(scope.limit_value);
      const applied = scope.mode === "absolute"
        ? scope.threshold_unit === "percent"
          ? baseline * (1 + (direction === "above" ? limit : -limit) / 100)
          : limit
        : baseline * (1 + Number(scope.baseline_deviation_pct ?? 3) / 100);
      if (!Number.isFinite(applied)) return;

      (series.points || []).forEach((point) => {
        const value = Number(point.kpi_value);
        const matches = scope.mode === "baseline" || direction === "above"
          ? value >= applied
          : value <= applied;
        if (!Number.isFinite(value) || !matches) return;
        rings.x.push(point.date);
        rings.y.push(value);
        rings.text.push(`${series.machine} / ${series.product}`);
      });
    });
  }

  if (rings.x.length) {
    traces.push({
      type: "scatter",
      mode: "markers",
      name: "Outlier",
      x: rings.x,
      y: rings.y,
      text: rings.text,
      marker: {
        size: 12,
        color: "rgba(0,0,0,0)",
        line: { color: OUTLIER_COLOUR, width: 2.5 },
      },
      hovertemplate: "<b>Outlier</b><br>%{text}<br>%{x} — %{y:.2f} absolute OPO KPI<extra></extra>",
    });
  }

  Plotly.react(document.getElementById("trend-plot"), traces, PLOT_LAYOUT, PLOT_CONFIG);
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
      [["before", before, "#8fb8de"], ["after", after, "#f0883e"]].forEach(([name, period, color]) => {
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

// Wafer metrics map per field center, field metrics per intrafield position; before/after share scales.
function drawTdbbMaps(budget) {
  const plot = document.getElementById("tdbb-maps");
  if (!tdbbRun || !budget) return;
  const level = tdbbRun.maps.find((m) => m.budget === budget)?.level || "wafer";
  const panels = [[level, "before"], [level, "after"]];
  const mapFor = (l, period) => tdbbRun.maps.find((m) => m.budget === budget && m.level === l && m.period === period)?.points || [];
  const magnitude = (p) => Math.max(p.m3s_x ?? 0, p.m3s_y ?? 0);
  const all = panels.flatMap(([l, period]) => mapFor(l, period));
  const colorMax = Math.max(...all.map(magnitude), 0.001);
  const longest = () => Math.max(...all.map((p) => Math.hypot(p.dx, p.dy)), 1e-6);
  const target = { wafer: 14, field: 4 };
  const traces = [];
  const layout = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: "#8b97a8", size: 11 },
    margin: { l: 8, r: 8, t: 22, b: 8 },
    height: 320,
    showlegend: false,
    hovermode: "closest",
    annotations: [],
    shapes: [],
  };
  panels.forEach(([l, period], index) => {
    const suffix = index ? index + 1 : "";
    const points = mapFor(l, period);
    const scale = target[l] / longest();
    const range = l === "wafer" ? 160 : 20;
    layout[`xaxis${suffix}`] = { domain: [index * 0.5 + 0.01, index * 0.5 + 0.45], range: [-range, range], visible: false, fixedrange: true, constrain: "domain" };
    layout[`yaxis${suffix}`] = { domain: [0, 0.92], range: [-range, range], visible: false, fixedrange: true, scaleanchor: `x${suffix}`, constrain: "domain" };
    layout.annotations.push({
      xref: "paper", yref: "paper", x: index * 0.5 + 0.23, y: 1, showarrow: false,
      text: `<b>${l === "wafer" ? "Wafer" : "Field"} \u00b7 ${period}</b>`, font: { color: "#e4e8ee", size: 11 },
    });
    if (l === "wafer") {
      layout.shapes.push({ type: "circle", xref: `x${suffix}`, yref: `y${suffix}`, x0: -150, y0: -150, x1: 150, y1: 150, line: { color: "#667085", width: 1 } });
    } else {
      layout.shapes.push({ type: "rect", xref: `x${suffix}`, yref: `y${suffix}`, x0: -13, y0: -16.5, x1: 13, y1: 16.5, line: { color: "#667085", width: 1 } });
    }
    traces.push({
      type: "scatter",
      mode: "lines",
      xaxis: `x${suffix}`,
      yaxis: `y${suffix}`,
      x: points.flatMap((p) => [p.x, p.x + p.dx * scale, null]),
      y: points.flatMap((p) => [p.y, p.y + p.dy * scale, null]),
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
        size: level === "wafer" ? 7 : 12,
        color: points.map(magnitude),
        cmin: 0,
        cmax: colorMax,
        colorscale: "Viridis",
        showscale: index === 1,
        colorbar: { title: { text: "3\u03c3 nm", side: "right" }, thickness: 10, len: 0.9 },
      },
      hovertemplate: "(%{x:.1f}, %{y:.1f}) mm<br>mean %{customdata[0]:.3f} / %{customdata[1]:.3f} nm<br>|m|+3\u03c3 X %{customdata[2]:.2f} Y %{customdata[3]:.2f} nm<extra></extra>",
    });
  });
  plot.style.height = `${layout.height}px`;
  Plotly.react(plot, traces, layout, PLOT_CONFIG);
}

async function loadTrends() {
  try {
    trendSeries = await window.OpoBff.loadTrends();
    availableTrendSeries = trendSeries;
    drawPlot(null, null);
    if (isScopedAgent(selectedAgentId())) {
      messageInput.value = starterPrompt(selectedAgentId());
      Plotly.purge(document.getElementById("trend-plot"));
    }
    const points = trendSeries.reduce((total, series) => total + series.points.length, 0);
    document.getElementById("chart-note").textContent =
      `${trendSeries.length} series \u00b7 ${points} points`;
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
       <code>${escapeHtml(selected.extreme_kpi_value)}</code> absolute OPO KPI,
       <code>${escapeHtml((selected.outlier_dates || []).length)}</code> marked points`
      : candidates.length ? "Select the candidate to investigate." : "";

  const selector = candidates.length
    ? `<select id="outlier-select" aria-label="Candidate outlier to investigate">${candidates
        .map((candidate) => `<option value="${escapeHtml(candidate.id)}"${
          selected && candidate.id === selected.id ? " selected" : ""
        }>
          ${escapeHtml(candidate.machine)} / ${escapeHtml(candidate.product)} —
          ${escapeHtml(candidate.extreme_kpi_value)} absolute OPO KPI
        </option>`).join("")}</select>`
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
         value="${escapeHtml(field.value ?? "")}" autocomplete="off" />`
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
        <button data-action="approve"${actionOptions ? " disabled" : ""}>${escapeHtml(payload.approve_label || "Approve")}</button>
        <button data-action="reject" class="reject">${escapeHtml(payload.reject_label || "Reject")}</button>
      </div>
    </div>`;

  const gate = interactionPanel;
  const actionSelect = gate.querySelector("#action-select");
  actionSelect?.addEventListener("change", () => {
    gate.querySelector('[data-action="approve"]').disabled = !actionSelect.value;
  });
  gate.querySelector('[data-action="approve"]').onclick = () => {
    const select = gate.querySelector("#outlier-select");
    const values = {};
    const inputEl = gate.querySelector("#gate-input");
    if (actionSelect) values.selected_action = actionSelect.value;
    if (inputEl) {
      const raw = inputEl.value.trim();
      if (field.type === "number") {
        const number = Number(raw);
        if (!raw || !Number.isFinite(number)) {
          inputEl.focus();
          inputEl.classList.add("invalid");
          return;
        }
        values[field.name] = number;
      } else {
        if (!raw) {
          inputEl.focus();
          inputEl.classList.add("invalid");
          return;
        }
        values[field.name] = raw;
      }
    }
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
  gateNode.querySelector(".gate").classList.add("resolved");
  gateNode.querySelector(".gate-actions").innerHTML =
    `<span class="gate-label">${escapeHtml(label)}</span>`;
  const select = gateNode.querySelector("select");
  if (select) select.disabled = true;
  const input = gateNode.querySelector("input");
  if (input) input.disabled = true;
  send(
    () => window.OpoBff.resume(conversationId, decision, conversationVersion),
    "Continuing investigation\u2026",
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
  const selected = evidence.selected_outlier?.machine || null;
  const scope = effectiveScope(evidence);
  const hasAppliedRule = evidence.confirmed_threshold != null || evidence.outliers?.length > 0;
  drawPlot(hasAppliedRule ? scope : null, selected);
  if (!scope.mode) return;
  const rule = ruleLabel(scope);

  if (!evidence.outliers?.length) {
    note.textContent = `No points ${rule}`;
    return;
  }

  const points = evidence.outliers.reduce((total, item) =>
    total + (item.outlier_dates || []).length, 0);
  note.innerHTML = `<span class="ring-key"></span>${points} points ${rule},
     across ${evidence.outliers.length} series`;
}

function renderWaferMap(evidence) {
  const plotEl = document.getElementById("wafer-plot");
  const noteEl = document.getElementById("wafer-note");

  if (!plotEl || !evidence) return;

  const rows = evidence.wafer_rows || [];
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
  const isV3 = agentId === V3_AGENT || agentId === V4_AGENT;
  const isV2 = isScopedAgent(agentId);
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
        maps: [...(beforeRun.maps || []), ...(afterRun.maps || [])],
      };
    }
  }
  document.getElementById("trend-title").textContent = isV2 ? "OPO performance trend" : "Daily overlay trend";
  document.querySelector(".wafer-panel").hidden = isV2;
  tdbbPanel.hidden = !isV2 || !evidence.comparison_scope;
  document.getElementById("tdbb-views").hidden = !isV3;
  ncePanel.hidden = !isV3 || !evidence.tdbb_run;
  if (evidence.trend_series) {
    trendSeries = Array.isArray(evidence.trend_series)
      ? evidence.trend_series
      : evidence.trend_series.series || [];
  }
  else if (isV2) trendSeries = [];
  if (isV3) {
    const filters = evidence.trend_filters || {};
    const wafers = drawV3Trend(trendSeries, evidence.comparison_scope?.change_date);
    document.getElementById("chart-note").textContent = filters.start_date
      ? `${filters.start_date} to ${filters.end_date || "?"} \u00b7 ${wafers} wafers \u00b7 overlay X / Y (nm)`
      : "Start date needed";
    if (evidence.comparison_scope) renderTdbb(evidence);
  } else if (isV2) {
    renderTrendChart(evidence);
    const filters = evidence.trend_filters || {};
    const points = (trendSeries || []).reduce((total, series) => total + (series.points || []).length, 0);
    document.getElementById("chart-note").textContent = filters.start_date
      ? `${filters.start_date} to ${filters.end_date || "?"} \u00b7 ${points} KPI points \u00b7 X/Y unavailable`
      : "Year needed for this scope";
    if (evidence.comparison_scope) {
      document.getElementById("tdbb-period").textContent = evidence.comparison_scope.change_date
        ? `Before / after ${evidence.comparison_scope.change_date}`
        : "Change date unavailable";
      document.getElementById("tdbb-note").textContent =
        "Budget bars and wafer/field plots are unavailable in v2: Analytics Foundation TDBB data is not connected to this agent.";
    }
  } else {
    renderTrendChart(evidence);
  }
  renderWaferMap(evidence);
  renderEvidence(evidence);

  if (isV2) {
    if (runtime.approvalRequest) {
      renderGate(runtime.approvalRequest);
      return;
    }
    interactionPanel.hidden = true;
    if (!isV3) {
      if (runtime.status === "completed" && evidence.comparison_scope) {
        addNode("msg agent", `<span class="badge ready">Comparison set up</span>
          <p>Before/after TDBB budgets and wafer/field plots are waiting for Analytics Foundation data. No TDBB measurements or cause can be reported yet.</p>`);
      } else if (runtime.status === "cancelled") {
        addNode("msg agent", "<p>Comparison finished without TDBB analysis.</p>");
      } else if (runtime.status === "completed" && !evidence.trend_filters?.start_date) {
        addNode("msg agent", "<p>No matching trend data was available to determine a year. Please include a year in the date and try again.</p>");
      } else if (runtime.status === "failed") {
        addNode("msg agent", "<p>Could not set up the comparison.</p>");
      }
      return;
    }
    if (runtime.status === "completed" && evidence.tdbb_summary) {
      const summary = evidence.tdbb_summary;
      const limits = (summary.limitations || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
      addNode("msg agent", `<span class="badge ready">TDBB comparison</span>
        ${renderMarkdown(summary.message || "")}
        ${evidence.tdbb_comparison?.headline ? `<p><strong>${escapeHtml(evidence.tdbb_comparison.headline)}</strong></p>` : ""}
        ${limits ? `<ul>${limits}</ul>` : ""}`);
    } else if (runtime.status === "completed" && evidence.comparison_scope && !evidence.comparison_scope.change_date) {
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

async function send(call, busyLabel) {
  setBusy(true, busyLabel);
  try {
    handleResponse(await call());
  } catch (err) {
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
  const isV2 = isScopedAgent(selectedAgentId());
  document.querySelector(".wafer-panel").hidden = isV2;
  messageInput.disabled = false;
  evidencePane.innerHTML = '<div class="empty-state small"><p>No evidence yet.</p></div>';
  if (isV2) Plotly.purge(document.getElementById("trend-plot"));
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
    registeredAgents = await window.OpoBff.listAgents();
  } catch (err) {
    registeredAgents = [];
    agentSelect.title = `Could not load agents: ${err.message}`;
  }
  agentSelect.innerHTML = registeredAgents.length
    ? registeredAgents
        .map((a) => `<option title="${escapeHtml(a.description)}">${escapeHtml(a.displayName || a.agentId)} (v${escapeHtml(a.version)})</option>`)
        .join("")
    : "<option>No agents registered</option>";
  agentSelect.disabled = busy || !registeredAgents.length;
  if (availableTrendSeries && selectedAgentId()) {
    messageInput.value = starterPrompt(selectedAgentId());
  }
}

agentSelect.addEventListener("change", () => {
  const isV2 = isScopedAgent(selectedAgentId());
  messageInput.value = starterPrompt(selectedAgentId());
  document.querySelector(".wafer-panel").hidden = isV2;
  tdbbPanel.hidden = true;
  ncePanel.hidden = true;
  document.getElementById("trend-title").textContent = isV2 ? "OPO performance trend" : "Daily overlay trend";
  if (isV2) {
    Plotly.purge(document.getElementById("trend-plot"));
    document.getElementById("chart-note").textContent = "Awaiting scope";
  } else {
    trendSeries = availableTrendSeries;
    drawPlot(null, null);
    const points = (availableTrendSeries || []).reduce((total, series) => total + series.points.length, 0);
    document.getElementById("chart-note").textContent = `${(availableTrendSeries || []).length} series · ${points} points`;
  }
});

loadAgents();
loadTrends();
