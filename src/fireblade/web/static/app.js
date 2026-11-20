/* Fireblade Host — grid client. Palette and density live in app.css. */
"use strict";

const PAGE = 200;
const $ = (id) => document.getElementById(id);

const state = {
  cases: [],
  openCase: null,      // case detail
  analysis: 0,         // index in the open case
  columns: [],
  rows: [],
  total: 0,
  offset: 0,
  search: "",
  filters: [],         // [{column, operator, value}]
  sort: null,
  descending: false,
  widths: {},
  selected: null,
  bookmarks: new Map(),
  bookmarksOnly: false,
  groups: [],          // column indexes, outer first
  path: [],            // drill-down values
  multiSort: [],       // [{column, descending}] in application order
  hidden: new Set(),    // column indexes hidden by the analyst
  pinned: new Set(),    // column indexes frozen on the left
};

/* ---------- small helpers ---------- */

async function api(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail || payload.error || detail;
    } catch (_) { /* keep the status text */ }
    throw new Error(detail);
  }
  return response.json();
}

function say(message, error) {
  const node = $("status");
  node.textContent = message;
  node.classList.toggle("err", Boolean(error));
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function parseFilterValue(raw) {
  const text = String(raw);
  const rules = [
    ["!=", "ne"], [">=", "ge"], ["<=", "le"], ["=", "eq"], [">", "gt"], ["<", "lt"],
    ["^", "starts"], ["$", "ends"], ["~", "contains"],
  ];
  for (const [prefix, operator] of rules) {
    if (text.startsWith(prefix)) return { operator, value: text.slice(prefix.length).trim() };
  }
  if (/^empty$/i.test(text.trim())) return { operator: "empty", value: "" };
  if (/^notempty$/i.test(text.trim())) return { operator: "not_empty", value: "" };
  return { operator: "contains", value: text.trim() };
}

function defaultWidth(name, index) {
  if (index === 0) return 30;
  const lower = name.toLowerCase();
  if (/(timestamp|date|time|created|modified)/.test(lower)) return 168;
  if (/(description|message|path|command|target)/.test(lower)) return 260;
  if (/(user|account|computer|host)/.test(lower)) return 130;
  if (/(ip|address|port)/.test(lower)) return 120;
  return Math.max(90, Math.min(200, name.length * 8 + 30));
}

/* ---------- import ---------- */

async function uploadFiles(files) {
  if (!state.openCase) { say("Open a case before importing", true); return; }
  const total = files.length;
  let done = 0;
  for (const file of files) {
    say(`Importing ${file.name} (${done + 1}/${total})…`);
    const body = new FormData();
    body.append("file", file);
    try {
      const response = await fetch(`/api/cases/${state.openCase.id}/upload`, { method: "POST", body });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || payload.error || response.statusText);
      if (!payload.analyses) {
        say(`${file.name}: ${payload.message || "not recognised"}`, true);
      }
      done += 1;
    } catch (error) {
      say(`${file.name}: ${error.message}`, true);
      return;
    }
  }
  await openCase(state.openCase.id);
  say(`${done} file(s) imported`);
}

/* ---------- cases ---------- */

let caseDialogMode = "create";

function openCaseDialog(mode) {
  caseDialogMode = mode;
  const current = state.openCase && mode === "rename" ? state.openCase : null;
  if (mode === "rename" && !current) { say("Open a case first", true); return; }
  $("case-modal-title").textContent = mode === "rename" ? "Rename the case" : "New case";
  $("case-name").value = current ? current.name : "";
  $("case-description").value = current ? current.description || "" : "";
  $("case-environment").value = current ? current.environment || "unspecified" : "unspecified";
  $("case-environment").disabled = mode === "rename";
  $("case-name").closest(".row").style.display = "flex";
  document.querySelector('[data-act="case-save"]').textContent = mode === "rename" ? "Save" : "Create";
  $("case-modal").classList.add("show");
}

async function saveCase() {
  const name = $("case-name").value.trim();
  if (!name) { say("A name is required", true); return; }
  closeModals();
  try {
    if (caseDialogMode === "rename") {
      await apiPatch(`/api/cases/${state.openCase.id}`, { name, description: $("case-description").value });
      await openCase(state.openCase.id);
      say(`Case renamed to ${name}`);
    } else {
      const created = await apiPost("/api/cases", { name, description: $("case-description").value,
                                                     environment: $("case-environment").value });
      say(`Case created: ${created.name}`);
    }
    await loadCases();
    showTab("cases");
  } catch (error) {
    say(error.message, true);
  }
}

function openDestroyDialog() {
  if (!state.openCase) { say("Open the case you want to destroy", true); return; }
  $("destroy-target").textContent = `Case: ${state.openCase.name} — type that name to confirm.`;
  $("destroy-confirm").value = "";
  $("destroy-modal").classList.add("show");
}

async function runDestroy() {
  const confirmation = $("destroy-confirm").value.trim();
  const body = {
    method: $("destroy-method").value,
    operator: $("destroy-operator").value,
    witness: $("destroy-witness").value,
    reason: $("destroy-reason").value,
    confirmation,
  };
  if (confirmation !== state.openCase.name) { say("The typed name does not match", true); return; }
  closeModals();
  say("Destroying the case — this takes a moment…");
  try {
    const response = await fetch(`/api/cases/${state.openCase.id}/destroy`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || response.statusText);
    state.openCase = null;
    await loadCases();
    showTab("cases");
    say(`Case destroyed: ${payload.files} file(s), certificate ${payload.certificate}`);
  } catch (error) {
    say(error.message, true);
  }
}

async function apiPost(path, body) {
  const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" },
                                       body: JSON.stringify(body) });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || response.statusText);
  return payload;
}

async function apiPatch(path, body) {
  const response = await fetch(path, { method: "PATCH", headers: { "Content-Type": "application/json" },
                                       body: JSON.stringify(body) });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || response.statusText);
  return payload;
}

async function loadCases() {
  try {
    const payload = await api("/api/cases");
    state.cases = payload.cases;
    $("caseroot").textContent = payload.root;
    renderCases();
    $("casecombo-label").textContent = state.openCase ? state.openCase.name : "No case open";
    say(`${payload.cases.length} case(s) in the library${payload.errors.length ? " — " + payload.errors.length + " unreadable" : ""}`);
  } catch (error) {
    say(error.message, true);
  }
}

function renderCases() {
  const term = ($("case-search").value || "").toLowerCase();
  const matches = state.cases.filter((item) =>
    !term || [item.name, item.environment, item.id, item.status].join(" ").toLowerCase().includes(term));
  const body = $("cases-body");
  body.innerHTML = matches.map((item) => `
    <tr data-case="${escapeHtml(item.id)}" class="${state.openCase && state.openCase.id === item.id ? "sel" : ""}">
      <td title="${escapeHtml(item.description || "")}">${escapeHtml(item.name || "(unnamed)")}</td>
      <td>${escapeHtml(item.environment || "—")}</td>
      <td>${escapeHtml(item.status || "—")}</td>
      <td>${escapeHtml(String(item.analysis_count ?? 0))}</td>
      <td>${escapeHtml(item.updated || "—")}</td>
    </tr>`).join("");
  $("cases-empty").hidden = matches.length > 0;
  $("cases-empty").textContent = state.cases.length
    ? "No case matches this filter."
    : "The library is empty. A case written by the Windows edition opens here as soon as its folder is in the library.";
}

async function openCase(identifier) {
  try {
    const detail = await api(`/api/cases/${identifier}`);
    state.openCase = detail;
    state.analysis = detail.analyses.length ? detail.analyses[0].index : 0;
    state.filters = [];
    state.search = "";
    state.sort = null;
    state.descending = false;
    state.offset = 0;
    state.selected = null;
    $("search").value = "";
    $("doctab").textContent = detail.name || "Case";
    $("doctab").classList.remove("docempty");
    $("casecombo-label").textContent = detail.name || "Case";
    showTab("analyses");
    renderTree();
    renderCases();
    if (!detail.analyses.length) {
      clearGrid("This case holds no analysis yet. Importing needs the desktop edition for now.");
      say("Case opened: no analysis inside", true);
      return;
    }
    await loadRows(true);
  } catch (error) {
    say(error.message, true);
  }
}

function closeCase() {
  state.openCase = null;
  state.columns = [];
  state.rows = [];
  state.total = 0;
  $("doctab").textContent = "Case";
  $("doctab").classList.add("docempty");
  $("casecombo-label").textContent = "No case open";
  $("tree").innerHTML = '<div class="empty">No case open.</div>';
  $("pane-tabs").innerHTML = "";
  clearGrid("Open a case from the Cases tab.");
  renderCases();
  say("Case closed");
}

/* ---------- process pivot ---------- */

let contextRow = null;

async function runPivot() {
  if (!contextRow) return;
  const rowId = contextRow.dataset.row;
  $("row-menu").hidden = true;
  try {
    const response = await fetch(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/pivot`,
      { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ row_id: Number(rowId) }) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || response.statusText);
    const anchor = payload.anchor;
    $("pivot-anchor").textContent =
      `Searched “${anchor.token}”${anchor.host ? " on " + anchor.host : ""}${anchor.moment ? " around " + anchor.moment : ""}` +
      `${anchor.parent ? " · parent process: " + anchor.parent : ""} — ${payload.total} row(s) across the case.`;
    $("pivot-results").innerHTML = payload.matches.map((match) =>
      `<div class="analysis-hit"><b>${escapeHtml(match.analysis)}</b> · row ${escapeHtml(String(match.row_id))}
        <div class="hit">${escapeHtml(match.cells.filter((c) => c !== null && c !== "").slice(0, 5).join(" · ")).slice(0, 200)}</div></div>`).join("")
      || '<div class="emptygrid">No other event mentions this process.</div>';
    $("pivot-modal").classList.add("show");
  } catch (error) {
    say(error.message, true);
  }
}

/* ---------- derived columns ---------- */

function openDerivedDialog() {
  if (!state.columns.length) { say("Open an analysis first", true); return; }
  $("derived-source").innerHTML = state.columns.slice(1)
    .map((name, index) => `<option value="${index}">${escapeHtml(name)}</option>`).join("");
  $("derived-name").value = "";
  $("derived-expression").value = "";
  $("derived-modal").classList.add("show");
}

function derivedOperationChanged() {
  const operation = $("derived-operation").value;
  const simple = operation === "timestamp" || operation === "category" || operation === "macb";
  $("derived-source-row").style.display = simple ? "flex" : "none";
  $("derived-format-row").style.display = operation === "timestamp" ? "flex" : "none";
  $("derived-expression-row").style.display = operation === "expression" ? "flex" : "none";
}

async function addDerived() {
  const name = $("derived-name").value.trim();
  if (!name) { say("A name is required", true); return; }
  const operation = $("derived-operation").value;
  const definition = { name, operation };
  if (operation === "expression") {
    definition.expression = $("derived-expression").value.trim();
    if (!definition.expression) { say("An expression is required", true); return; }
  } else {
    const source = state.columns[Number($("derived-source").value) + 1];
    definition.columns = [source];
    if (operation === "timestamp") definition.format = $("derived-format").value;
  }
  closeModals();
  try {
    const response = await fetch(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/derived`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(definition) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || response.statusText);
    await loadRows(true);
    say(`Derived column added: ${payload.added}`);
  } catch (error) {
    say(error.message, true);
  }
}

/* ---------- import history ---------- */

const importState = { collections: [] };

async function loadImports() {
  if (!state.openCase) return;
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/imports`);
    importState.collections = payload.collections;
    renderImports();
  } catch (error) {
    say(error.message, true);
  }
}

function renderImports() {
  const wanted = $("imports-status").value;
  const rows = [];
  let imported = 0, failed = 0;
  for (const collection of importState.collections) {
    for (const file of collection.files) {
      if (file.status === "complete" || file.status === "attention" || file.status === "duplicate") imported += 1;
      else failed += 1;
      if (wanted && file.status !== wanted) continue;
      rows.push(`<tr><td title="${escapeHtml(file.path)}">${escapeHtml(file.name)}</td>
        <td>${escapeHtml(file.status)}</td>
        <td>${escapeHtml((file.tools || []).join(", "))}</td>
        <td title="${escapeHtml(file.reason)}">${escapeHtml(file.reason)}</td></tr>`);
    }
  }
  $("imports-rows").innerHTML = rows.join("");
  $("imports-summary").textContent =
    `${importState.collections.length} import(s) — ${imported} file(s) read, ${failed} not read`;
  say($("imports-summary").textContent);
}

/* ---------- global search ---------- */

async function runGlobalSearch() {
  if (!state.openCase) { say("Open a case first", true); return; }
  const text = $("global-text").value.trim();
  if (!text) { say("Type something to search", true); return; }
  $("global-summary").textContent = "Searching…";
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/search?text=${encodeURIComponent(text)}`);
    $("global-summary").textContent = `${payload.total} hit(s) in ${payload.analyses.filter((a) => a.count).length} analysis(es)`;
    $("global-results").innerHTML = payload.analyses.map((analysis) => {
      if (!analysis.count) return "";
      const rows = analysis.rows.slice(0, 8).map((row) =>
        `<div class="hit">row ${escapeHtml(String(row.row_id))} · ${escapeHtml(row.cells.filter((c) => c !== null && c !== "").slice(0, 4).join(" · ")).slice(0, 160)}</div>`).join("");
      return `<div class="analysis-hit"><b>${escapeHtml(analysis.label)}</b> — ${analysis.count} hit(s)${rows}</div>`;
    }).join("") || '<div class="emptygrid">No hit.</div>';
  } catch (error) {
    $("global-summary").textContent = error.message;
  }
}

/* ---------- actions and tracking ---------- */

const actionState = { items: [] };

async function loadActions() {
  if (!state.openCase) return;
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/workspace`);
    actionState.items = payload.actions;
    renderActions();
  } catch (error) {
    say(error.message, true);
  }
}

function renderActions() {
  $("action-rows").innerHTML = actionState.items.map((item) => `
    <tr data-action="${escapeHtml(item.id)}">
      <td>${escapeHtml(item.date || "")}</td>
      <td title="${escapeHtml(item.detail || "")}">${escapeHtml(item.title)}</td>
      <td>${escapeHtml(item.owner || "")}</td>
      <td>${escapeHtml(item.priority || "")}</td>
      <td>${escapeHtml(item.status || "")}</td>
      <td><button class="btn" data-action-close="${escapeHtml(item.id)}">${
        item.status === "done" ? "Reopen" : "Done"}</button></td>
    </tr>`).join("");
  const open = actionState.items.filter((item) => item.status !== "done" && item.status !== "cancelled").length;
  $("action-summary").textContent = `${actionState.items.length} action(s), ${open} still open`;
}

async function addAction() {
  const title = $("action-title").value.trim();
  if (!title) { say("An action needs a title", true); return; }
  try {
    await apiPost(`/api/cases/${state.openCase.id}/actions`, {
      title, owner: $("action-owner").value, priority: $("action-priority").value,
    });
    $("action-title").value = "";
    await loadActions();
    say("Action added");
  } catch (error) {
    say(error.message, true);
  }
}

async function toggleAction(actionId) {
  const item = actionState.items.find((entry) => entry.id === actionId);
  if (!item) return;
  try {
    await apiPatch(`/api/cases/${state.openCase.id}/actions/${actionId}`,
      { status: item.status === "done" ? "todo" : "done" });
    await loadActions();
  } catch (error) {
    say(error.message, true);
  }
}

/* ---------- IOC hunting ---------- */

const iocState = { hits: [], summary: "" };

async function runIocScan() {
  if (!state.openCase) { say("Open a case first", true); return; }
  const text = $("ioc-input").value;
  if (!text.trim()) { say("Paste at least one indicator", true); return; }
  say("Scanning…");
  try {
    const response = await fetch(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/ioc`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || response.statusText);
    iocState.hits = payload.hits;
    const kinds = Object.entries(payload.by_kind || {}).map(([k, v]) => `${v} ${k}`).join(", ");
    const summary = `${payload.indicators} indicator(s), ${payload.scanned} row(s) scanned — ${payload.hits.length} hit(s)${kinds ? " : " + kinds : ""}${payload.truncated ? " (list truncated)" : ""}`;
    $("ioc-summary").textContent = summary;
    say(summary);
    renderIoc();
  } catch (error) {
    say(error.message, true);
    $("ioc-summary").textContent = error.message;
  }
}

function renderIoc() {
  $("ioc-rows").innerHTML = iocState.hits.map((hit) =>
    `<tr><td>${escapeHtml(String(hit.row_id))}</td><td>${escapeHtml(hit.indicator)}</td>
     <td>${escapeHtml(hit.observed)}</td><td>${escapeHtml(hit.rule)}</td>
     <td>${escapeHtml(state.columns[hit.column + 1] || String(hit.column))}</td></tr>`).join("");
}

/* ---------- timeline ---------- */

const TIMELINE_COLORS = ["#2d9cdb", "#e6a23c", "#27ae82", "#bb6bd9", "#eb6577", "#56bfc4", "#9fa8da", "#b4a34a"];
const timelineState = { offset: 0, text: "", kind: "text", payload: null };

function utcLabel(ns) {
  const ms = Number(ns) / 1e6;
  return new Date(ms).toISOString().replace("T", " ").replace(".000Z", "Z");
}

async function loadTimeline(reset) {
  if (!state.openCase) return;
  if (reset) timelineState.offset = 0;
  const params = new URLSearchParams({ offset: String(timelineState.offset) });
  if (timelineState.text) { params.set("text", timelineState.text); params.set("kind", timelineState.kind); }
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/timeline?${params}`);
    timelineState.payload = payload;
    renderTimeline(payload);
  } catch (error) {
    say(error.message, true);
  }
}

function renderTimeline(payload) {
  $("timeline-legend").innerHTML = payload.sources.map((source, index) =>
    `<span class="chip"><span class="swatch" style="background:${TIMELINE_COLORS[index % 8]}"></span>${escapeHtml(source.name)} — ${source.dated} dated / ${source.rows} row(s)</span>`).join("");

  const hist = payload.histogram;
  const box = $("timeline-hist");
  if (!hist || !hist.rows.length) {
    box.innerHTML = '<div class="emptygrid">No dated row to chart.</div>';
  } else {
    const totals = new Map();
    for (const [sourceIndex, bucket, count] of hist.rows) {
      if (!totals.has(bucket)) totals.set(bucket, []);
      totals.get(bucket).push([sourceIndex, count]);
    }
    const peak = Math.max(1, ...[...totals.values()].map((segments) => segments.reduce((sum, seg) => sum + seg[1], 0)));
    const bars = [];
    for (let bucket = 0; bucket < hist.bins; bucket += 1) {
      const segments = totals.get(bucket) || [];
      const height = segments.reduce((sum, seg) => sum + seg[1], 0);
      const inner = segments.map(([sourceIndex, count]) =>
        `<span class="seg" style="height:${Math.max(1, Math.round(count / peak * 56))}px;background:${TIMELINE_COLORS[sourceIndex % 8]}"></span>`).join("");
      bars.push(`<span class="bar" title="${height} event(s)" style="height:${Math.max(height ? 2 : 0, Math.round(height / peak * 56))}px">${inner}</span>`);
    }
    box.innerHTML = bars.join("");
  }

  $("timeline-rows").innerHTML = payload.rows.map((row) => {
    const [source, rowId, timeNs, sourceTime, summary, note, bookmarked] = row;
    return `<tr data-tl-row="${rowId}" data-tl-source="${source}">
      <td>${timeNs === null ? "(undated)" : escapeHtml(utcLabel(timeNs))}</td>
      <td>${payload.sources[source] ? escapeHtml(payload.sources[source].name) : source}</td>
      <td title="${escapeHtml(summary)}">${bookmarked ? "\u2605 " : ""}${escapeHtml(summary)}</td>
      <td>${escapeHtml(note)}</td></tr>`;
  }).join("");

  const from = payload.count ? timelineState.offset + 1 : 0;
  const to = Math.min(timelineState.offset + payload.rows.length, payload.count);
  $("timeline-info").textContent = `${from}\u2013${to} / ${payload.count} event(s) — ${payload.extent.dated} dated`;
  say(`Timeline: ${payload.extent.rows} row(s), ${payload.extent.dated} dated`);
}

/* ---------- artifacts tree ---------- */

function renderTree() {
  const tree = $("tree");
  if (!state.openCase) {
    tree.innerHTML = '<div class="empty">No case open.</div>';
    return;
  }
  const term = ($("tree-search").value || "").toLowerCase();
  const analyses = state.openCase.analyses.filter((item) =>
    !term || item.label.toLowerCase().includes(term));
  if (!analyses.length) {
    tree.innerHTML = '<div class="empty">' + (state.openCase.analyses.length ? "No analysis matches this filter." : "No analysis in this case.") + "</div>";
    return;
  }
  tree.innerHTML = '<div class="node grp"><span class="caret">▼</span>Analyses</div>' +
    analyses.map((item) => `
      <div class="node child ${item.index === state.analysis ? "sel" : ""}" data-analysis="${item.index}"
           title="${escapeHtml(item.source || item.path)}">
        <span class="caret"></span>${escapeHtml(item.label)}
      </div>`).join("");
}

function renderPaneTabs() {
  if (!state.openCase) { $("pane-tabs").innerHTML = ""; return; }
  const current = state.openCase.analyses.find((item) => item.index === state.analysis);
  $("pane-tabs").innerHTML = current
    ? `<div class="ptab active">${escapeHtml(current.label)} ✕</div>`
    : '<div class="ptab active">No analysis</div>';
}

/* ---------- grid ---------- */

function query() {
  const params = new URLSearchParams();
  params.set("offset", String(state.offset));
  params.set("limit", String(PAGE));
  if (state.search) params.set("search", state.search);
  if (state.bookmarksOnly) params.set("bookmarks_only", "true");
  for (const column of state.groups) params.append("group", String(column));
  for (const value of state.path) params.append("path", value === null ? "" : String(value));
  if (state.multiSort.length) {
    for (const key of state.multiSort) params.append("sortkey", `${key.column}:${key.descending ? "desc" : "asc"}`);
  } else if (state.sort !== null) {
    params.set("sort", String(state.sort));
    params.set("descending", state.descending ? "true" : "false");
  }
  for (const item of state.filters) params.append("filter", `${item.column}:${item.operator}:${item.value}`);
  return params;
}

function rowsUrl(extra) {
  const base = `/api/cases/${state.openCase.id}/analyses/${state.analysis}/rows`;
  const params = query();
  if (extra) extra(params);
  return `${base}?${params.toString()}`;
}

async function loadRows(reset) {
  if (!state.openCase) return;
  if (reset) state.offset = 0;
  try {
    const payload = await api(rowsUrl());
    state.columns = payload.columns;
    state.rows = payload.rows;
    state.total = payload.total;
    state.offset = payload.offset;
    state.grouped = Boolean(payload.grouped);
    await loadBookmarks();
    renderGrid();
    renderPaneTabs();
  } catch (error) {
    say(error.message, true);
  }
}

async function loadBookmarks() {
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/bookmarks`);
    state.bookmarks = new Map(payload.bookmarks.map((item) => [String(item.row_id), item.note]));
  } catch (_) {
    state.bookmarks = new Map();
  }
}

async function toggleBookmark(rowId, note) {
  const body = JSON.stringify({ row_id: Number(rowId), note: note ?? "" });
  const response = await fetch(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/bookmark`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || response.statusText);
  if ((payload.note || "").trim()) state.bookmarks.set(String(rowId), payload.note);
  else state.bookmarks.delete(String(rowId));
  renderGrid();
}

function clearGrid(message) {
  $("head").innerHTML = "";
  $("body").innerHTML = "";
  $("cols").innerHTML = "";
  $("grid-empty").hidden = false;
  $("grid-empty").textContent = message;
  $("pageinfo").textContent = "";
}

function visibleColumns() {
  return state.columns.map((name, index) => ({ name, index })).filter((item) => !state.hidden.has(item.index));
}

function renderGrid() {
  const empty = $("grid-empty");
  if (state.grouped) { renderGroupedGrid(); return; }
  const shown = visibleColumns();
  if (!state.columns.length) {
    clearGrid("No analysis open.");
    return;
  }
  empty.hidden = state.rows.length > 0;
  empty.textContent = state.total
    ? "No row on this page."
    : (state.search || state.filters.length ? "No row matches these filters." : "This analysis is empty.");

  $("cols").innerHTML = '<col style="width:30px">' + state.columns.map((name, index) =>
    `<col style="width:${state.widths[index] || defaultWidth(name, index)}px">`).join("");

  const head = ['<tr><th></th>'];
  state.columns.forEach((name, index) => {
    const multi = state.multiSort.findIndex((item) => item.column === index - 1);
    const sorted = state.sort === index || multi >= 0;
    const flag = state.sort === index ? state.descending : (multi >= 0 ? state.multiSort[multi].descending : false);
    const arrow = sorted ? (flag ? "▼" : "▲") + (multi >= 0 ? String(multi + 1) : "") : "▲▼";
    head.push(`<th class="${sorted ? "sorted" : ""}" data-column="${index}" title="${escapeHtml(name)}">
      ${index === 0 ? "Ro…" : escapeHtml(name)}<span class="sort">${arrow}</span>
      <span class="grip" data-grip="${index}"></span></th>`);
  });
  head.push("</tr>");
  // One leading cell for the checkbox column, then one per column.
  head.push('<tr class="colfilter"><th></th>');
  shown.forEach(({ index }) => {
    if (index === 0) { head.push("<th></th>"); return; }
    const current = state.filters.find((item) => item.column === index - 1);
    head.push(`<th><input data-filter="${index - 1}" placeholder="Filter…" value="${escapeHtml(current ? current.value : "")}"></th>`);
  });
  head.push("</tr>");
  $("head").innerHTML = head.join("");

  $("body").innerHTML = state.rows.map((row) => {
    const id = row[0];
    // Column 0 is the row identifier: it gets its own cell, after the checkbox one.
    const cells = shown.map(({ index }) => {
      const value = row[index];
      const text = value === null || value === "" ? "☐" : String(value);
      const cls = value === null || value === "" ? "cellnull" : (index === 0 ? "rowid" : "");
      return `<td class="${cls}">${escapeHtml(text)}</td>`;
    }).join("");
    const marked = state.bookmarks.has(String(id)) ? "marked" : "";
    return `<tr data-row="${escapeHtml(String(id))}" class="${state.selected === id ? "sel" : ""}">
      <td class="markcell"><span class="cb ${marked}" title="Bookmark this row"></span></td>${cells}</tr>`;
  }).join("");

  const from = state.total ? state.offset + 1 : 0;
  const to = Math.min(state.offset + state.rows.length, state.total);
  $("pageinfo").textContent = `${from}–${to} / ${state.total} row(s)`;
  say(`${state.total} row(s) in this analysis${state.filters.length ? ` — ${state.filters.length} filter(s)` : ""}`);
}

function renderGroupedGrid() {
  const column = state.groups[state.path.length];
  const name = state.columns?.[column + 1] || `column ${column + 1}`;
  const empty = $("grid-empty");
  empty.hidden = state.rows.length > 0;
  empty.textContent = "No group at this level.";

  $("cols").innerHTML = '<col style="width:30px"><col style="width:34px"><col style="width:52%"><col style="width:120px">';
  $("head").innerHTML = `<tr><th></th><th>Ro…</th><th>${escapeHtml(name)}</th><th style="width:120px">Rows</th></tr>`;

  $("body").innerHTML = state.rows.map((row, position) => {
    const value = row[0];
    const count = row[1];
    const text = value === null || value === "" ? "(empty)" : String(value);
    return `<tr data-group="${escapeHtml(text)}" data-value="${escapeHtml(String(value ?? ""))}">
      <td><span class="cb"></span></td>
      <td class="rowid">${state.offset + position + 1}</td>
      <td title="${escapeHtml(text)}">▸ ${escapeHtml(text)}</td>
      <td>${count}</td></tr>`;
  }).join("");

  const from = state.total ? state.offset + 1 : 0;
  const to = Math.min(state.offset + state.rows.length, state.total);
  $("pageinfo").textContent = `${from}–${to} / ${state.rows.length} group(s) — ${state.total} row(s)`;
  say(`Grouped by ${name} — ${state.rows.length} group(s) on this page, ${state.total} row(s) in the analysis`);
}

function showDetails(row) {
  const box = $("details");
  if (!row) {
    box.innerHTML = '<div class="ph">Details of the selected row</div>';
    return;
  }
  const pairs = visibleColumns().map(({ name, index }) => {
    const value = row[index];
    if (index === 0) return "";
    if (value === null || value === "") return "";
    return `<tr><td class="k">${escapeHtml(name)}</td><td>${escapeHtml(String(value))}</td></tr>`;
  }).join("");
  const id = String(row[0]);
  const note = state.bookmarks.get(id) || "";
  box.innerHTML = `<table>${pairs}</table>
    <div class="note-editor">
      <label>Bookmark note</label>
      <input id="note-input" value="${escapeHtml(note)}" placeholder="What to remember about this row…">
      <button class="btn" id="note-save">Save</button>
      <button class="btn" id="note-clear">Remove</button>
    </div>`;
  $("note-save").addEventListener("click", () => toggleBookmark(id, $("note-input").value));
  $("note-clear").addEventListener("click", () => toggleBookmark(id, ""));
  $("note-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") toggleBookmark(id, $("note-input").value);
  });
}

/* ---------- tabs and panels ---------- */

function showTab(name) {
  document.querySelectorAll(".tab[data-tab]").forEach((tab) =>
    tab.classList.toggle("active", tab.dataset.tab === name));
  $("analysis-view").style.display = name === "analyses" ? "flex" : "none";
  $("cases-view").style.display = name === "cases" ? "flex" : "none";
  $("timeline-view").style.display = name === "timeline" ? "flex" : "none";
  $("ioc-view").style.display = name === "ioc" ? "flex" : "none";
  $("actions-view").style.display = name === "actions" ? "flex" : "none";
  $("imports-view").style.display = name === "imports" ? "flex" : "none";
  if (name === "imports" && state.openCase) loadImports();
  if (name === "actions" && state.openCase) loadActions();
  $("artifacts").style.display = name === "cases" && !state.openCase ? "none" : "flex";
  if (name === "timeline" && state.openCase) loadTimeline(!timelineState.payload);
}

function openGroupPicker() {
  if (!state.columns.length) { say("Open an analysis first", true); return; }
  const select = $("group-select");
  select.innerHTML = state.columns.slice(1).map((name, index) =>
    `<option value="${index}">${escapeHtml(name)}</option>`).join("");
  if (state.groups.length) select.value = String(state.groups[0]);
  $("group-modal").classList.add("show");
}

function openColumnManager() {
  if (!state.columns.length) { say("Open an analysis first", true); return; }
  const list = $("columns-list");
  list.innerHTML = state.columns.map((name, index) => `
    <label>
      <input type="checkbox" data-col="${index}" ${state.hidden.has(index) ? "" : "checked"}>
      <span>${escapeHtml(index === 0 ? "Row number" : name)}</span>
      ${index ? `<span class="pin"><input type="checkbox" data-pin="${index}" ${state.pinned.has(index) ? "checked" : ""}> pin</span>` : ""}
    </label>`).join("");
  list.querySelectorAll("input[data-col]").forEach((box) => {
    box.addEventListener("change", () => {
      const index = Number(box.dataset.col);
      if (box.checked) state.hidden.delete(index); else state.hidden.add(index);
      renderGrid();
    });
  });
  list.querySelectorAll("input[data-pin]").forEach((box) => {
    box.addEventListener("change", () => {
      const index = Number(box.dataset.pin);
      if (box.checked) state.pinned.add(index); else state.pinned.delete(index);
      applyPinning();
    });
  });
  $("columns-modal").classList.add("show");
}

function applyPinning() {
  $("grid").querySelectorAll("th").forEach((th) => {
    const index = Number(th.dataset.column);
    const pinned = state.pinned.has(index - 1);
    th.style.position = "sticky";
    th.style.left = pinned ? `${30 + 0}px` : "";
    th.style.zIndex = pinned ? "3" : "";
    th.classList.toggle("pinned", pinned);
  });
}

function applyGrouping() {
  const column = Number($("group-select").value);
  state.groups = [column];
  state.path = [];
  $("group-label").textContent = `Grouped by ${state.columns[column + 1]}`;
  closeModals();
  loadRows(true);
}

/* ---------- display settings ---------- */

function applyScale() {
  const value = localStorage.getItem("fireblade.scale") || "1";
  document.documentElement.style.setProperty("--ui-scale", value);
  $("scale").value = value;
}

/* ---------- events ---------- */

function wire() {
  document.querySelectorAll('.menubar .m').forEach((node) => {
    node.addEventListener("mousedown", (event) => {
      event.stopPropagation();
      const name = node.dataset.menu;
      const menu = document.querySelector(`.menu[data-for="${name}"]`);
      const open = menu && menu.classList.contains("show");
      document.querySelectorAll(".menu").forEach((m) => m.classList.remove("show"));
      document.querySelectorAll(".menubar .m").forEach((m) => m.classList.remove("open"));
      if (menu && !open) {
        const left = node.getBoundingClientRect().left;
        menu.style.left = `${left}px`;
        menu.classList.add("show");
        node.classList.add("open");
      }
    });
  });
  document.addEventListener("mousedown", () => {
    document.querySelectorAll(".menu").forEach((m) => m.classList.remove("show"));
    document.querySelectorAll(".menubar .m").forEach((m) => m.classList.remove("open"));
  });

  document.querySelectorAll("[data-act]").forEach((node) => {
    node.addEventListener("click", () => act(node.dataset.act));
  });

  document.querySelectorAll(".tab[data-tab]").forEach((tab) => {
    tab.addEventListener("click", () => showTab(tab.dataset.tab));
  });

  $("cases-body").addEventListener("click", (event) => {
    const row = event.target.closest("tr[data-case]");
    if (row) openCase(row.dataset.case);
  });
  $("case-search").addEventListener("input", renderCases);

  $("tree").addEventListener("click", (event) => {
    const node = event.target.closest("[data-analysis]");
    if (!node) return;
    state.analysis = Number(node.dataset.analysis);
    state.filters = [];
    state.offset = 0;
    state.selected = null;
    renderTree();
    loadRows(true);
  });
  $("tree-search").addEventListener("input", renderTree);

  $("search").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      state.search = $("search").value.trim();
      loadRows(true);
    }
  });
  $("bookmarks-only").addEventListener("click", () => {
    state.bookmarksOnly = !state.bookmarksOnly;
    $("bookmarks-only").classList.toggle("active", state.bookmarksOnly);
    loadRows(true);
  });

  $("clear").addEventListener("click", () => {
    state.search = "";
    state.filters = [];
    state.sort = null;
    state.descending = false;
    state.bookmarksOnly = false;
    $("bookmarks-only").classList.remove("active");
    $("search").value = "";
    loadRows(true);
  });

  let resizing = null;
  $("head").addEventListener("mousedown", (event) => {
    const grip = event.target.closest("[data-grip]");
    if (!grip) return;
    event.preventDefault();
    const index = Number(grip.dataset.grip);
    const th = grip.closest("th");
    resizing = { index, startX: event.clientX, startWidth: th.getBoundingClientRect().width };
    document.body.style.cursor = "col-resize";
  });
  document.addEventListener("mousemove", (event) => {
    if (!resizing) return;
    const width = Math.max(24, Math.round(resizing.startWidth + event.clientX - resizing.startX));
    state.widths[resizing.index] = width;
    const cols = $("cols").children;
    if (cols[resizing.index]) cols[resizing.index].style.width = width + "px";
  });
  document.addEventListener("mouseup", () => {
    if (!resizing) return;
    resizing = null;
    document.body.style.cursor = "";
  });

  $("head").addEventListener("click", (event) => {
    const th = event.target.closest("th[data-column]");
    if (!th || event.target.closest("[data-grip]")) return;
    const index = Number(th.dataset.column);
    if (index === 0) return;
    const column = index - 1;
    if (event.shiftKey) {
      const existing = state.multiSort.find((item) => item.column === column);
      if (existing) existing.descending = !existing.descending;
      else state.multiSort.push({ column, descending: false });
      state.sort = null;
    } else {
      state.multiSort = [];
      if (state.sort === column) state.descending = !state.descending;
      else { state.sort = column; state.descending = false; }
    }
    loadRows(true);
  });

  $("head").addEventListener("keydown", (event) => {
    const input = event.target.closest("input[data-filter]");
    if (!input) return;
    if (event.key !== "Enter") return;
    loadRows(true);
  });

  $("head").addEventListener("input", (event) => {
    const input = event.target.closest("input[data-filter]");
    if (!input) return;
    const column = Number(input.dataset.filter);
    const parsed = parseFilterValue(input.value);
    state.filters = state.filters.filter((item) => item.column !== column);
    if (input.value.trim() || parsed.operator === "empty" || parsed.operator === "not_empty") {
      state.filters.push({ column, ...parsed });
    }
  });

  $("body").addEventListener("contextmenu", (event) => {
    const tr = event.target.closest("tr[data-row]");
    if (!tr) return;
    event.preventDefault();
    contextRow = tr;
    const menu = $("row-menu");
    menu.style.left = `${event.clientX}px`;
    menu.style.top = `${event.clientY}px`;
    menu.hidden = false;
  });
  document.addEventListener("click", () => { $("row-menu").hidden = true; });

  $("body").addEventListener("click", (event) => {
    const group = event.target.closest("tr[data-group]");
    if (group) {
      const raw = group.dataset.value;
      state.path.push(raw === "" ? null : raw);
      loadRows(true);
      return;
    }
    const tr = event.target.closest("tr[data-row]");
    if (!tr) return;
    if (event.target.closest(".markcell")) {
      const id = tr.dataset.row;
      const current = state.bookmarks.get(String(id)) || "";
      toggleBookmark(id, current ? "" : "bookmarked").catch((error) => say(error.message, true));
      return;
    }
    $("body").querySelectorAll("tr.sel").forEach((node) => node.classList.remove("sel"));
    tr.classList.add("sel");
    const id = tr.dataset.row;
    const row = state.rows.find((item) => String(item[0]) === String(id));
    state.selected = row ? row[0] : null;
    showDetails(row);
  });

  $("first").addEventListener("click", () => {
    state.offset = 0;
    if (state.path.length) { state.path = []; loadRows(true); } else { loadRows(false); }
  });
  $("prev").addEventListener("click", () => {
    if (state.path.length) { state.path.pop(); state.offset = 0; loadRows(true); return; }
    state.offset = Math.max(0, state.offset - PAGE);
    loadRows(false);
  });
  $("next").addEventListener("click", () => {
    if (state.offset + PAGE < state.total) { state.offset += PAGE; loadRows(false); }
  });
  $("details-toggle").addEventListener("click", () => {
    const box = $("details");
    box.style.display = box.style.display === "none" ? "block" : "none";
  });

  $("import-input").addEventListener("change", (event) => {
    const files = [...(event.target.files || [])];
    event.target.value = "";
    if (files.length) uploadFiles(files);
  });

  document.addEventListener("dragover", (event) => {
    if (!state.openCase) return;
    event.preventDefault();
    document.body.classList.add("dropping");
  });
  document.addEventListener("dragleave", () => document.body.classList.remove("dropping"));
  document.addEventListener("drop", (event) => {
    if (!state.openCase || !event.dataTransfer?.files?.length) return;
    event.preventDefault();
    document.body.classList.remove("dropping");
    uploadFiles([...event.dataTransfer.files]);
  });

  $("ioc-scan").addEventListener("click", runIocScan);
  $("derived-operation").addEventListener("change", derivedOperationChanged);
  $("imports-refresh").addEventListener("click", loadImports);
  $("imports-status").addEventListener("change", renderImports);
  $("action-add").addEventListener("click", addAction);
  $("action-rows").addEventListener("click", (event) => {
    const button = event.target.closest("[data-action-close]");
    if (button) toggleAction(button.dataset.actionClose);
  });
  $("timeline-build").addEventListener("click", () => loadTimeline(false));
  $("timeline-search").addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    timelineState.text = $("timeline-search").value.trim();
    timelineState.kind = $("timeline-kind").value;
    loadTimeline(true);
  });
  $("timeline-prev").addEventListener("click", () => {
    timelineState.offset = Math.max(0, timelineState.offset - (timelineState.payload?.page_size || 250));
    loadTimeline(false);
  });
  $("timeline-next").addEventListener("click", () => {
    const size = timelineState.payload?.page_size || 250;
    if (timelineState.offset + size < (timelineState.payload?.count || 0)) { timelineState.offset += size; loadTimeline(false); }
  });

  $("scale").addEventListener("change", (event) => {
    localStorage.setItem("fireblade.scale", event.target.value);
    applyScale();
  });
  $("settings-modal").addEventListener("click", (event) => {
    if (event.target.id === "settings-modal") closeModals();
  });
  $("about-modal").addEventListener("click", (event) => {
    if (event.target.id === "about-modal") closeModals();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "F5") { event.preventDefault(); loadCases(); }
    if (event.key === "Escape") closeModals();
    if (event.key === "/" && document.activeElement.tagName !== "INPUT") {
      event.preventDefault();
      $("search").focus();
    }
  });
}

function closeModals() {
  document.querySelectorAll(".modal").forEach((node) => node.classList.remove("show"));
  document.querySelectorAll(".menu").forEach((node) => node.classList.remove("show"));
}

async function buildReport() {
  if (!state.openCase) { say("Open a case first", true); return; }
  const body = JSON.stringify({
    title: $("report-title").value || "Investigation report",
    description: $("report-description").value || "",
    bookmarks_only: $("report-bookmarks").value === "true",
  });
  closeModals();
  say("Generating the report…");
  try {
    const response = await fetch(`/api/cases/${state.openCase.id}/report`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || response.statusText);
    say(`Report: ${payload.records} finding(s) -> ${payload.name}`);
    window.open(payload.url, "_blank");
  } catch (error) {
    say(error.message, true);
  }
}

async function act(name) {
  closeModals();
  switch (name) {
    case "refresh-cases": await loadCases(); if (state.openCase) await loadRows(true); break;
    case "close-case": closeCase(); break;
    case "reload-analysis": await loadRows(true); break;
    case "export-csv":
      if (!state.openCase) { say("No case open", true); break; }
      window.location.href = rowsUrl().replace("/rows?", "/export?");
      break;
    case "import-file": $("import-input").click(); break;
    case "group-column": openGroupPicker(); break;
    case "global-search": $("search-modal").classList.add("show"); break;
    case "global-run": await runGlobalSearch(); $("search-modal").classList.add("show"); break;
    case "new-case": openCaseDialog("create"); break;
    case "rename-case": openCaseDialog("rename"); break;
    case "case-save": await saveCase(); break;
    case "destroy-case": openDestroyDialog(); break;
    case "destroy-run": await runDestroy(); break;
    case "report": $("report-modal").classList.add("show"); break;
    case "report-build": await buildReport(); break;
    case "columns": openColumnManager(); break;
    case "pivot": await runPivot(); break;
    case "bookmark-row": if (contextRow) toggleBookmark(contextRow.dataset.row, "bookmarked"); break;
    case "derived": openDerivedDialog(); break;
    case "derived-add": await addDerived(); break;
    case "columns-reset": state.hidden.clear(); renderGrid(); openColumnManager(); break;
    case "group-apply": applyGrouping(); break;
    case "group-remove":
      state.groups = []; state.path = []; $("group-label").textContent = "Filters apply to the whole analysis, not just the page on screen.";
      loadRows(true); break;
    case "group-none":
      state.groups = []; state.path = []; $("group-label").textContent = "Glissez un en-tête ici pour regrouper les résultats";
      loadRows(true); break;
    case "display-settings": $("settings-modal").classList.add("show"); break;
    case "settings-close": closeModals(); break;
    case "about":
      $("about-text").textContent =
        `Fireblade Host ${$("version").textContent.replace("Fireblade ", "")} — the same core as the Windows edition, ` +
        "served over HTTP. The palette, the density and the grid behaviour are carried over from the desktop window. " +
        "Importing artifacts and the other tabs are not wired yet in this edition.";
      $("about-modal").classList.add("show");
      break;
    case "about-close": closeModals(); break;
    case "toggle-artifacts":
      $("artifacts").style.display = $("artifacts").style.display === "none" ? "flex" : "none";
      break;
    default: break;
  }
}

/* ---------- boot ---------- */

async function boot() {
  applyScale();
  wire();
  try {
    const health = await api("/health");
    $("version").textContent = `Fireblade ${health.version}`;
  } catch (_) { /* the version is cosmetic */ }
  await loadCases();
  showTab(state.cases.length === 1 ? "analyses" : "cases");
  clearGrid(state.cases.length
    ? "Open a case from the Cases tab."
    : "The library is empty. A case written by the Windows edition opens here as soon as its folder is in the library.");
  $("tree").innerHTML = '<div class="empty">No case open.</div>';
}

document.addEventListener("DOMContentLoaded", boot);
