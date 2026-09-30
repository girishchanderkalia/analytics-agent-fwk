(() => {
  const form = document.getElementById("overlay-filters");
  const status = document.getElementById("overlay-status");
  const error = document.getElementById("overlay-error");
  const plot = document.getElementById("overlay-plot");
  const tableBody = document.getElementById("overlay-rows");
  const exportButton = document.getElementById("export-csv");
  const axis = document.getElementById("horizontal-axis");
  const dimensions = { product: "product_id", layer: "layer_id", equipment: "exposure_equipment_id", lot: "lot_id" };
  const columns = ["lot_step_id", "lot_id", "product_id", "layer_id", "exposure_equipment_id", "metrology_equipment_id", "lot_metrology_step_id", "lot_start", "lot_end", "kpi_x", "kpi_y"];
  let result = { metric: "MEAN", points: [] };
  let requestVersion = 0;
  let optionsLoaded = false;
  let appliedQuery = null;
  window.OverlayAnalysis = {
    getContext: () => ({
      source: "overlay-data-analysis",
      overlay: appliedQuery ? { kpi: result.kpi, metric: result.metric, filters: appliedQuery, points: result.points } : null,
    }),
  };

  function timestamp(value) {
    return value ? new Date(value).toISOString().replace("T", " ").replace(/\.\d{3}Z$/, "") : "--";
  }

  function populateOptions(points) {
    for (const [id, field] of Object.entries(dimensions)) {
      const select = document.getElementById(id);
      const selected = select.value;
      while (select.options.length > 1) select.remove(1);
      const values = [...new Set(points.map(point => point[field]).filter(value => value != null))].sort();
      for (const value of values) select.add(new Option(value, value));
      select.value = selected;
    }
  }

  function renderTable() {
    tableBody.replaceChildren();
    if (!result.points.length) {
      const cell = tableBody.insertRow().insertCell();
      cell.colSpan = columns.length;
      cell.className = "empty-row";
      cell.textContent = "No measurements";
      return;
    }
    for (const point of result.points) {
      const row = tableBody.insertRow();
      for (const field of columns) {
        const cell = row.insertCell();
        const value = point[field];
        cell.textContent = field.startsWith("kpi_") ? (value == null ? "--" : value.toFixed(4)) : field === "lot_start" || field === "lot_end" ? timestamp(value) : value ?? "--";
        if (field.startsWith("kpi_")) cell.className = "number";
        if (value != null) cell.title = String(value);
      }
    }
  }

  function renderChart() {
    if (!window.Plotly) throw new Error("The chart library could not load. Check the connection and reload the page.");
    const timeAxis = axis.value === "time";
    const points = result.points.filter(point => !timeAxis || point.lot_start).slice();
    if (timeAxis) points.sort((first, second) => new Date(first.lot_start) - new Date(second.lot_start));
    const traces = ["x", "y"].map((coordinate, index) => ({
      name: `KPI ${coordinate.toUpperCase()}`,
      type: "scatter",
      mode: "markers",
      x: points.map(point => timeAxis ? point.lot_start : String(point.lot_step_id)),
      y: points.map(point => point[`kpi_${coordinate}`]),
      customdata: points.map(point => [point.lot_id ?? "--", point.product_id ?? "--", point.layer_id ?? "--", point.exposure_equipment_id ?? "--", point.lot_metrology_step_id]),
      marker: { color: index ? "#f0b35b" : "#46c9b0", size: 8, symbol: index ? "diamond" : "circle", line: { width: 1, color: "#0f1419" } },
      hovertemplate: "Lot: %{customdata[0]}<br>Product: %{customdata[1]}<br>Layer: %{customdata[2]}<br>Exposure: %{customdata[3]}<br>Metrology step: %{customdata[4]}<br>%{x}<br>%{y:.4f}<extra>%{fullData.name}</extra>",
    }));
    const omitted = result.points.length - points.length;
    const missing = result.points.filter(point => point.kpi_x == null || point.kpi_y == null).length;
    status.textContent = `${result.points.length} measurements | ${result.metric}${omitted ? ` | ${omitted} without exposure time` : ""}${missing ? ` | ${missing} with missing KPI values` : ""}`;
    const hasValues = points.some(point => point.kpi_x != null || point.kpi_y != null);
    return Plotly.react(plot, traces, {
      paper_bgcolor: "#0f1419", plot_bgcolor: "#0f1419",
      font: { color: "#e4e8ee", family: "Segoe UI, sans-serif", size: 12 },
      margin: { t: 40, r: 20, b: 65, l: 65 },
      legend: { orientation: "h", x: 0, y: 1.15 },
      xaxis: { title: timeAxis ? "Exposure start (UTC)" : "Lot step", type: timeAxis ? "date" : "category", gridcolor: "#2a3441", automargin: true },
      yaxis: { title: `Measured overlay (${result.metric})`, gridcolor: "#2a3441", zerolinecolor: "#687685", automargin: true },
      annotations: hasValues ? [] : [{ text: "No plottable measurements", x: 0.5, y: 0.5, xref: "paper", yref: "paper", showarrow: false }],
    }, { responsive: true, displaylogo: false, toImageButtonOptions: { filename: `overlay-${result.metric.toLowerCase()}` } });
  }

  async function load() {
    const version = ++requestVersion;
    const query = { metric: document.getElementById("metric").value };
    for (const [id, field] of Object.entries(dimensions)) {
      const value = document.getElementById(id).value;
      if (value) query[`${field}s`] = [value];
    }
    for (const id of ["start-date", "end-date"]) {
      const value = document.getElementById(id).value;
      if (value) query[id.replace("-", "_")] = value;
    }
    error.hidden = true;
    appliedQuery = null;
    status.textContent = "Loading...";
    form.setAttribute("aria-busy", "true");
    exportButton.disabled = true;
    axis.disabled = true;
    tableBody.replaceChildren();
    if (window.Plotly) Plotly.purge(plot);
    try {
      if (!optionsLoaded) {
        const all = await OpoBff.queryOverlayTrends({ metric: query.metric });
        if (version !== requestVersion) return;
        populateOptions(all.points);
        optionsLoaded = true;
        const response = Object.keys(query).length === 1 ? all : await OpoBff.queryOverlayTrends(query);
        if (version !== requestVersion) return;
        result = response;
      } else {
        const response = await OpoBff.queryOverlayTrends(query);
        if (version !== requestVersion) return;
        result = response;
      }
      if (version !== requestVersion) return;
      appliedQuery = query;
      renderTable();
      exportButton.disabled = !result.points.length;
      await renderChart();
    } catch (failure) {
      if (version !== requestVersion) return;
      status.textContent = "Unable to load overlay chart";
      error.textContent = failure.message;
      error.hidden = false;
    } finally {
      if (version === requestVersion) {
        form.removeAttribute("aria-busy");
        axis.disabled = false;
      }
    }
  }

  form.addEventListener("submit", event => {
    event.preventDefault();
    const start = document.getElementById("start-date");
    const end = document.getElementById("end-date");
    end.setCustomValidity(start.value && end.value && start.value > end.value ? "End date must be on or after start date." : "");
    if (form.reportValidity()) load();
  });
  form.addEventListener("input", () => document.getElementById("end-date").setCustomValidity(""));
  form.addEventListener("reset", () => {
    document.getElementById("end-date").setCustomValidity("");
    setTimeout(load, 0);
  });
  axis.addEventListener("change", () => renderChart().catch(failure => {
    error.textContent = failure.message;
    error.hidden = false;
  }));
  exportButton.addEventListener("click", () => {
    const csvValue = value => {
      let text = value == null ? "" : String(value);
      if (typeof value === "string" && /^[=+\-@\t\r\n]/.test(text)) text = "'" + text;
      return '"' + text.replace(/"/g, '""') + '"';
    };
    const rows = [columns, ...result.points.map(point => columns.map(field => point[field]))];
    const blob = new Blob([rows.map(row => row.map(csvValue).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `overlay-${result.metric.toLowerCase()}.csv`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 0);
  });
  load();
})();