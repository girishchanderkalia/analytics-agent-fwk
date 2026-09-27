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

let conversationId = null;
let conversationVersion = null;
let busy = false;

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
  legend: { orientation: "h", y: -0.2, font: { size: 11 } },
  hoverlabel: { bgcolor: "#1e2631", bordercolor: "#2a3441", font: { color: "#e4e8ee" } },
};

const PLOT_CONFIG = { displaylogo: false, responsive: true, displayModeBar: false };

let trendSeries = null;

function drawPlot(outliers, selectedMachine) {
  if (!trendSeries) return;

  const flaggedByMachine = new Map(
    (outliers || []).map((o) => [`${o.machine}::${o.product}`, new Set(o.outlier_dates)])
  );

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

  // Points matching the analyst's request, ringed in red. Keys are "index#date" (not
  // bare dates) since several points in a series can share the same timestamp - e.g.
  // multiple wafers from one lot - and a bare date would ring every point sharing it.
  if (flaggedByMachine.size) {
    const rings = { x: [], y: [], text: [] };
    trendSeries.forEach((s) => {
      const keys = flaggedByMachine.get(`${s.machine}::${s.product}`);
      if (!keys) return;
      s.points
        .filter((p, i) => keys.has(`${i}#${p.date}`))
        .forEach((p) => {
          rings.x.push(p.date);
          rings.y.push(p.kpi_value);
          rings.text.push(`${s.machine} / ${s.product}`);
        });
    });

    traces.push({
      type: "scatter",
      mode: "markers",
      name: "Outlier",
      x: rings.x,
      y: rings.y,
      text: rings.text,
      marker: {
        size: 15,
        color: "rgba(0,0,0,0)",
        line: { color: OUTLIER_COLOUR, width: 2.5 },
      },
      hovertemplate: "<b>Outlier</b><br>%{text}<br>%{x} — %{y:.2f} absolute OPO KPI<extra></extra>",
    });
  }

  Plotly.react(document.getElementById("trend-plot"), traces, PLOT_LAYOUT, PLOT_CONFIG);
}

async function loadTrends() {
  try {
    trendSeries = await window.OpoBff.loadTrends();
    drawPlot(null, null);
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
  document.querySelectorAll(".gate-actions button").forEach((b) => (b.disabled = value));
  messageInput.disabled = value || !interactionPanel.hidden;

  const existing = document.getElementById("busy-node");
  if (existing) existing.remove();
  if (value) {
    addNode("msg status", `<span id="busy-inner"><span class="spinner"></span>${escapeHtml(label)}</span>`)
      .id = "busy-node";
  }
}

// The runtime exposes one approval contract: approve or reject an investigation
// for a candidate outlier chosen from the request payload.
function renderGate(request) {
  const payload = request.payload || {};
  const candidates = payload.detected_outliers || [];
  const selected = payload.selected_outlier;

  const detail = selected
    ? `Most extreme: <code>${escapeHtml(selected.machine)}</code> /
       <code>${escapeHtml(selected.product)}</code> &mdash;
       <code>${escapeHtml(selected.extreme_kpi_value)}</code> absolute OPO KPI,
       <code>${escapeHtml((selected.outlier_dates || []).length)}</code> marked points`
    : "No candidate was preselected.";

  const selector = candidates.length
    ? `<select id="outlier-select" aria-label="Candidate outlier to investigate">${candidates
        .map((candidate) => `<option value="${escapeHtml(candidate.id)}"${
          selected && candidate.id === selected.id ? " selected" : ""
        }>
          ${escapeHtml(candidate.machine)} / ${escapeHtml(candidate.product)} —
          ${escapeHtml(candidate.extreme_kpi_value)} absolute OPO KPI
        </option>`).join("")}</select>`
    : "";

  interactionPanel.hidden = false;
  interactionPanel.innerHTML = `
    <div class="gate">
      <div class="gate-label">Approval required</div>
      <h3>${escapeHtml(gateQuestion(request))}</h3>
      <div class="gate-detail">${detail}</div>
      ${selector}
      <div class="gate-actions">
        <button data-action="approve">Investigate</button>
        <button data-action="reject" class="reject">Reject</button>
      </div>
    </div>`;

  const gate = interactionPanel;
  gate.querySelector('[data-action="approve"]').onclick = () => {
    const select = gate.querySelector("#outlier-select");
    resolveGate(gate, "Approved", {
      approved: true,
      selectedOutlierId: select?.value ?? null,
    });
  };
  gate.querySelector('[data-action="reject"]').onclick = () =>
    resolveGate(gate, "Rejected", { approved: false });
}

function gateQuestion(request) {
  return request.approval_id === "investigate_outlier"
    ? "Investigate the selected outlier?"
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
  ].filter(([, value]) => value);
  if (scope.length) {
    html += `<div class="card"><h3>Scope</h3>${scope
      .map(([label, value]) => `<div class="kv"><span>${escapeHtml(label)}</span><span>${escapeHtml(value)}</span></div>`)
      .join("")}</div>`;
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
    html += `<div class="card"><h3>Wafers</h3><table>
      <tr><th>Wafer</th><th>Overlay X</th><th>Overlay Y</th><th>Magnitude</th></tr>
      ${evidence.wafer_rows.map((r) => `
        <tr class="${anomalous.has(r.wafer_id) ? "anomalous" : ""}">
          <td>${escapeHtml(r.wafer_id)}</td>
          <td>${escapeHtml(r.overlay_x_um)}</td>
          <td>${escapeHtml(r.overlay_y_um)}</td>
          <td>${escapeHtml(r.overlay_magnitude_um)}</td>
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

  drawPlot(evidence.outliers, selected);

  const scope = evidence.detection_scope || {};
  if (!scope.mode) return;
  const rule = ruleLabel(scope);

  if (!evidence.outliers?.length) {
    note.textContent = `No points ${rule}`;
    return;
  }

  const points = evidence.outliers.reduce((n, o) => n + (o.outlier_dates || []).length, 0);
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
  Plotly.react(plotEl, traces, waferLayout, PLOT_CONFIG);
}

function handleResponse(runtime) {
  conversationId = runtime.conversationId;
  conversationVersion = runtime.version ?? null;
  conversationInput.value = conversationId ?? "";

  const evidence = runtime.result || {};
  if (evidence.trend_series) trendSeries = evidence.trend_series;
  renderTrendChart(evidence);
  renderWaferMap(evidence);
  renderEvidence(evidence);

  const scope = evidence.detection_scope || {};
  if (scope.mode && !timeline.querySelector(".msg.status.rule")) {
    const badge = scope.mode === "absolute" ? "Absolute limit" : "Per-machine baseline";
    const interpretation = evidence.trend_filters?.interpretation;
    addNode("msg status rule",
      `<strong>${badge}</strong>: marking points ${escapeHtml(ruleLabel(scope))}` +
      (interpretation ? `<br><span class="interpretation">${escapeHtml(interpretation)}</span>` : ""));
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
  messageInput.disabled = false;
  evidencePane.innerHTML = '<div class="empty-state small"><p>No evidence yet.</p></div>';
  drawPlot(null, null);
  addNode("msg user", escapeHtml(message));
  send(() => window.OpoBff.startChat(message), "Analysing trends\u2026");
};

toggleRightPanel.onclick = () => {
  setRightPanelCollapsed(!mainLayout.classList.contains("right-panel-collapsed"));
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

loadTrends();
