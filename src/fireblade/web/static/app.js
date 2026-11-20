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
  cellNotes: new Map(),
  bookmarksOnly: false,
  groups: [],          // column indexes, outer first
  interval: "",        // date interval applied to the grouped column
  expression: null,    // FilterGroup sent to the core
  path: [],            // drill-down values
  multiSort: [],       // [{column, descending}] in application order
  hidden: new Set(),    // column indexes hidden by the analyst
  pinned: new Set(),    // column indexes frozen on the left
  pinnedRight: new Set(), // column indexes frozen on the right
  selection: new Set(), // row ids selected on this page (Shift extends, Ctrl toggles)
  anchor: null,         // the row a Shift-click extends from
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

const FILTER_PREFIX = { eq: "= ", ne: "!= ", gt: "> ", ge: ">= ", lt: "< ", le: "<= ",
                       starts: "^ ", ends: "$ ", contains: "", empty: "empty", not_empty: "notempty" };

function filterPrefix(operator) {
  return FILTER_PREFIX[operator] === undefined ? "" : FILTER_PREFIX[operator];
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

/* ---------- import preview ---------- */

const previewState = { items: [] };

const DELIMITER_NAMES = { ",": "comma", "\t": "tab", ";": "semicolon", "|": "pipe" };

/* The desktop's import dialog offers a separator and an encoding; the preview must
   answer with the same choices, and the import must read the file with them. */
async function fillCsvOptions() {
  const delimiter = $("preview-delimiter");
  if (delimiter.dataset.ready) return;
  let payload = {};
  try { payload = await api("/api/settings"); } catch (_) { payload = {}; }
  const delimiters = payload.csv_delimiters || [",", "\t", ";", "|"];
  delimiter.innerHTML = ['<option value="">automatic</option>'].concat(delimiters.map((code) =>
    `<option value="${escapeHtml(code)}">${escapeHtml(DELIMITER_NAMES[code] || code)}</option>`)).join("");
  const encodings = payload.csv_encodings || ["auto", "utf-8", "utf-16", "utf-32", "cp1252", "latin-1"];
  $("preview-encoding").innerHTML = encodings.map((code) =>
    `<option value="${escapeHtml(code)}">${code === "auto" ? "automatic (BOM)" : escapeHtml(code)}</option>`).join("");
  delimiter.dataset.ready = "1";
}

function csvOptions() {
  return { delimiter: $("preview-delimiter").value || null,
           encoding: $("preview-encoding").value || "auto" };
}

function openImportDialog() {
  if (!state.openCase) { say("Open a case before importing", true); return; }
  previewState.items = [];
  $("preview-input").value = "";
  $("preview-server").value = "";
  $("preview-delimiter").value = "";
  $("preview-encoding").value = "auto";
  fillCsvOptions();
  $("preview-note").textContent = "Choose a file, or give a path on the server: the columns and the recognised profile are shown before anything is read.";
  $("preview-note").classList.remove("err");
  renderPreview();
  $("import-modal").classList.add("show");
}

async function previewFiles(files) {
  if (!state.openCase) { say("Open a case before importing", true); return; }
  $("import-modal").classList.add("show");
  renderPreview();
  let done = 0;
  for (const file of files) {
    done += 1;
    $("preview-note").textContent = `Reading ${file.name} (${done}/${files.length})…`;
    const body = new FormData();
    body.append("file", file);
    const options = csvOptions();
    if (options.delimiter) body.append("delimiter", options.delimiter);
    if (options.encoding) body.append("encoding", options.encoding);
    try {
      const response = await fetch(`/api/cases/${state.openCase.id}/preview-upload`, { method: "POST", body });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || payload.error || response.statusText);
      previewState.items.push({ name: file.name, payload });
    } catch (error) {
      previewState.items.push({ name: file.name, error: error.message });
    }
  }
  $("preview-note").textContent = `${previewState.items.length} file(s) ready. Nothing has been read into the case yet.`;
  $("preview-note").classList.remove("err");
  renderPreview();
}

async function previewServerPath() {
  const source = $("preview-server").value.trim();
  if (!source) { $("preview-note").textContent = "Give a path on the server first."; return; }
  try {
    const payload = await apiPost(`/api/cases/${state.openCase.id}/preview`, { source, ...csvOptions() });
    previewState.items.push({ name: payload.name, payload });
    $("preview-note").textContent = "Preview ready. Nothing has been read into the case yet.";
    $("preview-note").classList.remove("err");
    renderPreview();
  } catch (error) {
    $("preview-note").textContent = error.message;
    $("preview-note").classList.add("err");
  }
}

function previewRoleLabel(role) {
  return { timestamp: "timestamp", boolean: "boolean", column: "text" }[role] || "text";
}

function renderPreview() {
  const box = $("preview-body");
  $("preview-import").disabled = !previewState.items.length;
  if (!previewState.items.length) { box.innerHTML = ""; return; }
  box.innerHTML = previewState.items.map((item, index) => {
    if (item.error) {
      return `<div class="preview-card"><div class="preview-head"><b>${escapeHtml(item.name)}</b>
        <span class="preview-bad">not readable</span></div>
        <div class="note">${escapeHtml(item.error)}</div></div>`;
    }
    const payload = item.payload || {};
    const size = payload.size === undefined ? "" : `${Math.max(1, Math.round(payload.size / 1024))} KB`;
    if (payload.kind === "folder") {
      return `<div class="preview-card"><div class="preview-head"><b>${escapeHtml(payload.name)}</b>
        <span class="preview-ok">folder · ${payload.count} file(s)</span></div>
        <div class="note">${escapeHtml(payload.note || "")}</div>
        <div class="preview-files">${(payload.files || []).slice(0, 12).map((entry) =>
          `<div>${escapeHtml(entry.name)} — ${entry.readers.length ? escapeHtml(entry.readers.join(", ")) : "no reader"}</div>`).join("")}
          ${payload.count > 12 ? `<div>… ${payload.count - 12} more</div>` : ""}</div></div>`;
    }
    if (payload.kind !== "table") {
      return `<div class="preview-card"><div class="preview-head"><b>${escapeHtml(payload.name)}</b>
        <span class="preview-neutral">${escapeHtml(payload.kind)} · ${size}</span></div>
        <div class="note">${escapeHtml(payload.note || "")}</div>
        <div class="note">Readers that would run: ${(payload.readers || []).length ? escapeHtml(payload.readers.join(", ")) : "none"}</div></div>`;
    }
    const mapping = payload.mapping || {};
    const columns = (payload.columns || []).map((column) =>
      `<tr><td>${column.index + 1}</td><td>${escapeHtml(column.name)}</td><td>${previewRoleLabel(column.role)}</td></tr>`).join("");
    const rows = payload.rows || [];
    const sample = rows.length
      ? `<table class="preview-table preview-sample"><thead><tr>${(payload.columns || []).map((column) =>
          `<th>${escapeHtml(column.name)}</th>`).join("")}</tr></thead>
          <tbody>${rows.map((row) => `<tr>${(payload.columns || []).map((_, cell) =>
            `<td>${escapeHtml(String(row[cell] ?? "")).slice(0, 120)}</td>`).join("")}</tr>`).join("")}</tbody></table>`
      : "<div class=\"note\">No sample row in the first block.</div>";
    const derived = (mapping.derived || []).map((item) =>
      `<li>${escapeHtml(item.name || "")} — ${escapeHtml(item.operation || "")}${item.format ? " (" + escapeHtml(item.format) + ")" : ""}</li>`).join("");
    return `<div class="preview-card">
      <div class="preview-head"><b>${escapeHtml(payload.name)}</b>
        <span class="${payload.profile ? "preview-ok" : "preview-neutral"}">${payload.profile ? "profile: " + escapeHtml(payload.profile) : "no declared profile"}</span>
        <span class="preview-size">${size}</span></div>
      <div class="note">${escapeHtml(payload.note || "")}</div>
      <div class="preview-columns"><table class="preview-table"><thead>
        <tr><th>#</th><th>Column</th><th>Role</th></tr></thead><tbody>${columns}</tbody></table></div>
      <div class="preview-facts">
        <span>Delimiter: ${escapeHtml(payload.delimiter || "")}</span>
        <span>Encoding: ${escapeHtml(payload.encoding || "")}</span>
        <span>Sort: ${escapeHtml(mapping.sort || "none")}</span>
        <span>Timestamps: ${escapeHtml((mapping.timestamps || []).join(", ") || "none")}</span>
        <span>Booleans: ${escapeHtml((mapping.booleans || []).join(", ") || "none")}</span>
        <span>Colour rules: ${mapping.format_rules || 0}</span>
      </div>
      ${derived ? `<div class="note">Derived on import:<ul>${derived}</ul></div>` : ""}
      ${(mapping.missing || []).length ? `<div class="note">Profile fields absent from this file: ${escapeHtml(mapping.missing.join(", "))}</div>` : ""}
      ${sample}
      <input type="hidden" class="preview-source" value="${escapeHtml(payload.path || "")}">
    </div>`;
  }).join("");
}

/* A new separator or encoding changes what the file would become: re-read the
   previews already on screen rather than importing under the old reading. */
async function refreshPreviews() {
  if (!previewState.items.length) return;
  const options = csvOptions();
  for (const item of previewState.items) {
    const source = item.payload && item.payload.path;
    if (!source) continue;
    try {
      item.payload = await apiPost(`/api/cases/${state.openCase.id}/preview`, { source, ...options });
      delete item.error;
    } catch (error) {
      item.error = error.message;
    }
  }
  $("preview-note").textContent = `Re-read with the chosen options: ${previewState.items.length} file(s). Nothing has been read into the case yet.`;
  $("preview-note").classList.remove("err");
  renderPreview();
}

async function confirmImport() {
  if (!previewState.items.length) return;
  const layout = $("import-layout").value;
  const options = csvOptions();
  let imported = 0;
  for (const item of previewState.items) {
    if (item.error) continue;
    const source = item.payload && item.payload.path;
    if (!source) continue;
    say(`Importing ${item.name}…`);
    try {
      const payload = await apiPost(`/api/cases/${state.openCase.id}/import`,
        { source, organization: layout, ...options });
      if (payload.analyses) imported += 1;
      else say(`${item.name}: ${payload.message || "not recognised"}`, true);
    } catch (error) {
      say(`${item.name}: ${error.message}`, true);
      return;
    }
  }
  closeModals();
  await openCase(state.openCase.id);
  say(`${imported} file(s) imported`);
}

/* ---------- import ---------- */

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

async function archiveCase() {
  if (!state.openCase) { say("Open the case to archive first", true); return; }
  if (!window.confirm(`Archive "${state.openCase.name}" and free its working folder?`)) return;
  say("Archiving the case…");
  try {
    const payload = await apiPost(`/api/cases/${state.openCase.id}/archive`, {});
    state.openCase = null;
    await loadCases();
    showTab("cases");
    say(`Archived: ${Math.round(payload.bytes / 1024 / 1024)} MB kept, ${Math.round(payload.removed_bytes / 1024 / 1024)} MB freed`);
  } catch (error) { say(error.message, true); }
}

async function restoreCase() {
  if (!state.openCase) { say("Open the archived case first", true); return; }
  say("Restoring…");
  try {
    const payload = await apiPost(`/api/cases/${state.openCase.id}/restore`, {});
    await loadCases();
    say(`Case restored: ${payload.analyses} analysis(es)`);
  } catch (error) { say(error.message, true); }
}

async function apiPut(path, body) {
  const response = await fetch(path, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}) });
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

async function apiDelete(path) {
  const response = await fetch(path, { method: "DELETE", headers: { Accept: "application/json" } });
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
      clearGrid("This case holds no analysis yet. Import a file to begin.");
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

/* ---------- column layout ---------- */

let layoutTimer = null;

async function loadLayout() {
  if (!state.openCase) return;
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/display`);
    state.widths = payload.widths || {};
    state.hidden = new Set(payload.hidden || []);
    state.pinned = new Set(payload.pinned || []);
    state.pinnedRight = new Set(payload.pinned_right || []);
    renderGrid();
  } catch (_) { /* no saved layout is not an error */ }
}

function saveLayoutSoon() {
  clearTimeout(layoutTimer);
  layoutTimer = setTimeout(async () => {
    if (!state.openCase) return;
    try {
      await apiPost(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/display`,
        { widths: state.widths, hidden: [...state.hidden], pinned: [...state.pinned],
          pinned_right: [...state.pinnedRight] });
    } catch (_) { /* a layout that cannot be saved must not interrupt the work */ }
  }, 600);
}

/* ---------- advanced filter ---------- */

const EXPR_OPERATORS = ["contains", "ne", "eq", "starts", "ends", "gt", "ge", "lt", "le", "empty", "not_empty"];
const EXPR_MAX_DEPTH = 3;

function exprConditionNode(condition = {}) {
  const row = document.createElement("div");
  row.className = "row expr-row";
  row.dataset.kind = "condition";
  row.innerHTML = `<select data-expr-col>${state.columns.slice(1).map((name, index) =>
      `<option value="${index}" ${index === (condition.column ?? 0) ? "selected" : ""}>${escapeHtml(name)}</option>`).join("")}</select>
    <select data-expr-op>${EXPR_OPERATORS.map((code) =>
      `<option value="${code}" ${code === (condition.operator || "contains") ? "selected" : ""}>${code}</option>`).join("")}</select>
    <input data-expr-value value="${escapeHtml(condition.value ?? "")}" placeholder="value">
    <button class="btn" data-expr-remove title="Remove this condition">✕</button>`;
  row.querySelector("[data-expr-remove]").addEventListener("click", () => {
    const box = row.closest(".expr-children");
    row.remove();
    if (box && !box.querySelector(":scope > *")) box.appendChild(exprConditionNode());
  });
  return row;
}

function exprGroupNode(group = { logic: "and", children: [] }, depth = 0) {
  const box = document.createElement("div");
  box.className = "expr-group";
  box.dataset.kind = "group";
  box.dataset.depth = String(depth);
  const label = depth === 0 ? "Match" : "Match this group";
  const head = document.createElement("div");
  head.className = "expr-head";
  head.innerHTML = `<label>${label}</label>
    <select data-expr-logic>
      <option value="and">all of them (AND)</option>
      <option value="or">any of them (OR)</option>
      <option value="not">none of them (NOT)</option>
    </select>
    ${depth === 0 ? "" : '<button class="btn" data-expr-group-remove title="Remove this group">✕</button>'}`;
  head.querySelector("[data-expr-logic]").value = group.logic || "and";
  const children = document.createElement("div");
  children.className = "expr-children";
  box.append(head, children);
  if (depth > 0) {
    head.querySelector("[data-expr-group-remove]").addEventListener("click", () => {
      const parent = box.parentElement && box.parentElement.closest(".expr-group");
      box.remove();
      if (parent && !parent.querySelector(".expr-children > *")) {
        parent.querySelector(".expr-children").appendChild(exprConditionNode());
      }
    });
  }
  for (const child of group.children || []) {
    children.appendChild(child && child.children ? exprGroupNode(child, depth + 1) : exprConditionNode(child || {}));
  }
  if (!children.children.length) children.appendChild(exprConditionNode());
  const actions = document.createElement("div");
  actions.className = "row expr-actions";
  actions.innerHTML = `<button class="btn" data-expr-add>Add a condition</button>
    <button class="btn" data-expr-group-add ${depth >= EXPR_MAX_DEPTH ? "disabled" : ""}>Add a group</button>`;
  actions.querySelector("[data-expr-add]").addEventListener("click", () => {
    children.appendChild(exprConditionNode());
  });
  actions.querySelector("[data-expr-group-add]").addEventListener("click", () => {
    const nested = exprGroupNode({ logic: "or", children: [] }, depth + 1);
    children.appendChild(nested);
  });
  box.appendChild(actions);
  return box;
}

function readExpressionGroup(node) {
  const logic = node.querySelector(":scope > .expr-head [data-expr-logic]").value;
  const children = [];
  for (const child of node.querySelectorAll(":scope > .expr-children > *")) {
    if (child.dataset.kind === "group") {
      const nested = readExpressionGroup(child);
      if (nested.children.length) children.push(nested);
      continue;
    }
    const operator = child.querySelector("[data-expr-op]").value;
    const value = child.querySelector("[data-expr-value]").value;
    if (operator !== "empty" && operator !== "not_empty" && value === "") continue;
    children.push({ column: Number(child.querySelector("[data-expr-col]").value), operator, value });
  }
  return { logic, children };
}

function openExpressionDialog() {
  if (!state.columns.length) { say("Open an analysis first", true); return; }
  let group = { logic: "and", children: [] };
  if (state.expression && Array.isArray(state.expression.children) && state.expression.children.length) {
    group = state.expression;
  }
  const root = $("expr-root");
  root.innerHTML = "";
  root.appendChild(exprGroupNode(group, 0));
  $("expression-modal").classList.add("show");
}

function applyExpression() {
  const root = $("expr-root").firstElementChild;
  if (!root) return;
  const expression = readExpressionGroup(root);
  state.expression = expression.children.length ? expression : null;
  closeModals();
  loadRows(true);
  const count = state.expression ? countConditions(state.expression) : 0;
  say(state.expression
    ? `Advanced filter: ${count} condition(s), ${state.expression.logic.toUpperCase()} at the top`
    : "Advanced filter cleared");
}

function countConditions(group) {
  return (group.children || []).reduce((sum, child) =>
    sum + (child.children ? countConditions(child) : 1), 0);
}

/* ---------- row actions ---------- */

let contextCell = null;

function selectedRowValues() {
  const id = contextRow ? contextRow.dataset.row : null;
  const row = state.rows.find((item) => String(item[0]) === String(id));
  return row || null;
}

function rowSelected(id) {
  return state.selection.has(String(id));
}

function paintSelection() {
  $("body").querySelectorAll("tr[data-row]").forEach((node) => {
    node.classList.toggle("sel", rowSelected(node.dataset.row));
  });
}

/* The desktop selects a range with Shift and adds one row with Ctrl; the actions
   that follow (copy, mark, note) apply to the whole selection. */
function selectRow(tr, event) {
  const id = String(tr.dataset.row);
  const row = state.rows.find((item) => String(item[0]) === id);
  if (event.shiftKey && state.anchor !== null) {
    const ids = state.rows.map((item) => String(item[0]));
    const from = ids.indexOf(String(state.anchor));
    const to = ids.indexOf(id);
    if (from >= 0 && to >= 0) {
      state.selection = new Set(ids.slice(Math.min(from, to), Math.max(from, to) + 1));
    }
  } else if (event.ctrlKey || event.metaKey) {
    if (state.selection.has(id)) state.selection.delete(id); else state.selection.add(id);
    state.anchor = id;
  } else {
    state.selection = new Set([id]);
    state.anchor = id;
  }
  state.selection.add(id);
  state.selected = row ? row[0] : null;
  paintSelection();
  showDetails(row);
  say(state.selection.size > 1 ? `${state.selection.size} rows selected` : "1 row selected");
}

function selectedIds() {
  const ids = [...state.selection];
  if (ids.length) return ids;
  return state.selected === null || state.selected === undefined ? [] : [String(state.selected)];
}

async function copySelectedRows() {
  const ids = selectedIds();
  if (!ids.length) { say("Select a row first", true); return; }
  const blocks = ids.map((id) => {
    const row = state.rows.find((item) => String(item[0]) === id);
    return row ? state.columns.map((name, index) => `${name}: ${row[index] ?? ""}`).join("\n") : "";
  }).filter(Boolean);
  try {
    await navigator.clipboard.writeText(blocks.join("\n\n"));
    say(`${blocks.length} row(s) copied to the clipboard`);
  } catch (_) {
    say("The browser refused clipboard access", true);
  }
}

async function postBookmark(rowId, note) {
  const body = JSON.stringify({ row_id: Number(rowId), note: note ?? "" });
  const response = await fetch(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/bookmark`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || response.statusText);
  if ((note || "").trim()) state.bookmarks.set(String(rowId), note);
  else state.bookmarks.delete(String(rowId));
  return payload;
}

/* A mark is a note: the core removes it when the note is empty. One call per row,
   capped so a selection of a whole page cannot hang the window. */
async function markSelection(note) {
  const ids = selectedIds();
  if (!ids.length) { say("Select a row first", true); return; }
  const limited = ids.slice(0, 200);
  try {
    for (const id of limited) await postBookmark(id, note ?? "");
  } catch (error) {
    say(error.message, true);
    renderGrid();
    return;
  }
  renderGrid();
  say((note || "").trim()
    ? `${limited.length} row(s) marked`
    : `${limited.length} row(s) unmarked`);
}

/* An alert analysis carries the EVTX reference of the event it came from: only
   there do the two EVTX actions mean anything. */
function isAlertAnalysis() {
  return state.columns.some((name) => name === "Fireblade_EVTX_Source");
}

async function showAlertContext() {
  if (!state.openCase || contextRow === null) { say("Right-click an alert first", true); return; }
  try {
    const payload = await apiPost(
      `/api/cases/${state.openCase.id}/analyses/${state.analysis}/rows/${contextRow.dataset.row}/context`);
    state.analysis = payload.analysis;
    state.groups = []; state.path = []; state.interval = ""; state.expression = null;
    state.filters = []; state.search = ""; state.sort = null; state.multiSort = [];
    showTab("analyses");
    // The context is a new analysis of the case: refresh the tree before naming it.
    state.openCase = await api(`/api/cases/${state.openCase.id}`);
    renderTree();
    await loadRows(true);
    const notes = (payload.notes || []).length ? ` — ${payload.notes.join(" · ")}` : "";
    say(`Context of "${payload.rule}" ±${payload.minutes} min: ${payload.events} event(s), `
      + `${payload.references} reference(s), association ${payload.association}${notes}`);
  } catch (error) {
    say(error.message, true);
  }
}

async function openSourceEvent() {
  if (!state.openCase || contextRow === null) { say("Right-click an alert first", true); return; }
  try {
    const payload = await apiPost(
      `/api/cases/${state.openCase.id}/analyses/${state.analysis}/rows/${contextRow.dataset.row}/source`);
    state.analysis = payload.analysis;
    state.groups = []; state.path = []; state.interval = "";
    state.filters = []; state.search = ""; state.sort = null; state.multiSort = [];
    showTab("analyses");
    await loadRows(true);
    const column = state.columns.findIndex((name) => name === payload.column);
    if (column > 0) {
      state.filters = [{ column: column - 1, operator: "eq", value: payload.value }];
      await loadRows(true);
    }
    say(`Source event ${payload.column} = ${payload.value} — ${state.total} row(s) in ${payload.source.split("/").pop()}`);
  } catch (error) {
    say(error.message, true);
  }
}

function contextColumnIndex() {
  return contextCell === null || contextCell === undefined ? null : Number(contextCell);
}

async function copyCellValue() {
  const column = contextColumnIndex();
  if (column === null) { say("Right-click a cell first", true); return; }
  const row = selectedRowValues();
  const value = row ? String(row[column + 1] ?? "") : "";
  try {
    await navigator.clipboard.writeText(value);
    say("Value copied to the clipboard");
  } catch (_) {
    say("The browser refused clipboard access", true);
  }
}

function filterFromCell(operator) {
  const column = contextColumnIndex();
  if (column === null) { say("Right-click a cell first", true); return; }
  const row = selectedRowValues();
  const value = row ? String(row[column + 1] ?? "") : "";
  state.filters = state.filters.filter((item) => item.column !== column);
  if (operator === "empty" || operator === "not_empty" || value !== "") {
    state.filters.push({ column, operator, value });
  }
  const input = document.querySelector(`input[data-filter="${column}"]`);
  if (input) input.value = filterPrefix(operator) + value;
  loadRows(true);
  say(`${operator === "ne" ? "Excluding" : "Filtering on"} ${state.columns[column + 1]} ${operator === "ne" ? "≠" : "="} ${value || "(empty)"}`);
}

function sortFromCell(descending) {
  const column = contextColumnIndex();
  if (column === null) { say("Right-click a cell first", true); return; }
  state.multiSort = [];
  state.sort = column;
  state.descending = Boolean(descending);
  loadRows(true);
  say(`Sorted by ${state.columns[column + 1]} ${descending ? "descending" : "ascending"}`);
}

function groupFromCell() {
  const column = contextColumnIndex();
  if (column === null) { say("Right-click a cell first", true); return; }
  state.groups = [column];
  state.interval = "";
  state.path = [];
  $("group-label").textContent = `Grouped by ${state.columns[column + 1]}`;
  loadRows(true);
}

function pinFromCell(side = "left") {
  const column = contextColumnIndex();
  if (column === null) { say("Right-click a cell first", true); return; }
  const set = side === "left" ? state.pinned : state.pinnedRight;
  const other = side === "left" ? state.pinnedRight : state.pinned;
  const pinned = !set.has(column);
  if (pinned) { set.add(column); other.delete(column); } else set.delete(column);
  saveLayoutSoon();
  renderGrid();
  say(`${pinned ? `Pinned to the ${side}` : "Unpinned"} ${state.columns[column + 1]}`);
}

function hideFromCell() {
  const column = contextColumnIndex();
  if (column === null) { say("Right-click a cell first", true); return; }
  state.hidden.add(column);
  saveLayoutSoon();
  renderGrid();
  say(`Hid ${state.columns[column + 1]} — Columns… brings it back`);
}

function showCellJson() {
  const row = selectedRowValues();
  if (!row) { say("Select a row first", true); return; }
  const column = contextCell === null ? 0 : Number(contextCell);
  const name = state.columns[column + 1] || `column ${column + 1}`;
  $("cell-modal-title").textContent = name;
  $("cell-full").value = String(row[column + 1] ?? "");
  $("cell-modal").classList.add("show");
}

async function ruleFromCell() {
  const row = selectedRowValues();
  if (!row) { say("Select a row first", true); return; }
  const column = Number(contextCell || 0);
  const value = String(row[column + 1] ?? "");
  if (!value) { say("This cell is empty", true); return; }
  rulesCache.push({ column, operator: "eq", value, background: "#ffe08a", foreground: "#202020",
                    bold: false, enabled: true });
  try {
    await persistRules();
    say(`Colour rule added for ${state.columns[column + 1]} = ${value}`);
  } catch (error) {
    rulesCache.pop();
    say(error.message, true);
  }
}

/* ---------- attack graph ---------- */

/* A node the data does not carry: the desktop's "Nœud libre…". */
function openGraphNode() {
  if (!state.openCase) { say("Open a case first", true); return; }
  $("graph-node-label").value = "";
  $("graph-node-tags").value = "";
  $("graph-node-modal").classList.add("show");
  $("graph-node-label").focus();
}

async function saveGraphNode() {
  const label = $("graph-node-label").value.trim();
  if (!label) { say("Give the node a name first", true); return; }
  try {
    const payload = await apiPost(`/api/cases/${state.openCase.id}/graph/nodes`,
      { label, tags: $("graph-node-tags").value });
    closeModals();
    say(`Node added: ${payload.label}${payload.tags.length ? " — " + payload.tags.join(", ") : ""}`);
    await buildGraph();
  } catch (error) {
    say(error.message, true);
  }
}

async function buildGraph() {
  if (!state.openCase) { say("Open a case first", true); return; }
  $("graph-summary").textContent = "Building…";
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/graph`);
    renderGraph(payload);
  } catch (error) {
    $("graph-summary").textContent = error.message;
    say(error.message, true);
  }
}

async function exportGraphPng() {
  if (!state.openCase) { say("Open a case first", true); return; }
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/graph`);
    const nodes = payload.nodes || [];
    if (!nodes.length) { say("The graph is empty", true); return; }
    const width = Math.max(...nodes.map((node) => node.x), 400) + 260;
    const height = Math.max(...nodes.map((node) => node.y), 200) + 80;
    const canvas = document.createElement("canvas");
    const scale = 2;
    canvas.width = width * scale;
    canvas.height = height * scale;
    const context = canvas.getContext("2d");
    context.scale(scale, scale);
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, width, height);
    const positions = new Map(nodes.map((node) => [node.id, node]));
    context.strokeStyle = "#8a9bb0";
    for (const edge of payload.edges || []) {
      const a = positions.get(edge.source);
      const b = positions.get(edge.target);
      if (!a || !b) continue;
      context.beginPath();
      context.moveTo(a.x + 60, a.y + 12);
      context.lineTo(b.x, b.y + 12);
      context.stroke();
    }
    const palette = { host: "#e8f4ea", technique: "#fdf0e3", stage: "#eae6f5", account: "#f7ecf2" };
    context.font = "11px 'Segoe UI', sans-serif";
    for (const node of nodes) {
      const label = String(node.label || "");
      const textWidth = context.measureText(label).width;
      const boxWidth = Math.min(210, textWidth + 16);
      context.fillStyle = palette[node.kind] || "#eaf1f7";
      context.strokeStyle = "#9fb3c8";
      context.fillRect(node.x, node.y, boxWidth, 24);
      context.strokeRect(node.x, node.y, boxWidth, 24);
      context.fillStyle = "#202020";
      context.fillText(label.slice(0, 34), node.x + 6, node.y + 16);
    }
    canvas.toBlob((blob) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `fireblade-graph-${state.openCase.id.slice(0, 8)}.png`;
      link.click();
      URL.revokeObjectURL(url);
      say("Graph exported as PNG");
    }, "image/png");
  } catch (error) {
    say(error.message, true);
  }
}

async function exportNavigator() {
  if (!state.openCase) { say("Open a case first", true); return; }
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/graph?navigator=true`);
    say(`ATT&CK layer written: ${payload.techniques} technique(s), ${Math.round(payload.bytes / 1024)} kB`);
  } catch (error) {
    say(error.message, true);
  }
}

function renderGraph(payload) {
  const nodes = payload.nodes;
  const box = $("graph-nodes");
  const wrap = $("graph-wrap");
  const width = Math.max(...nodes.map((node) => node.x), 400) + 260;
  const height = Math.max(...nodes.map((node) => node.y), 200) + 80;
  wrap.querySelector("#graph-nodes").style.width = width + "px";
  wrap.querySelector("#graph-nodes").style.height = height + "px";
  box.innerHTML = nodes.map((node) =>
    `<div class="gnode ${escapeHtml(node.kind)}" data-node="${escapeHtml(node.id)}"
       style="left:${node.x}px;top:${node.y}px" title="${escapeHtml(node.label)}">${escapeHtml(node.label)}</div>`).join("");

  const positions = new Map(nodes.map((node) => [node.id, node]));
  const svg = $("graph-edges");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("width", width);
  svg.setAttribute("height", height);
  svg.innerHTML = payload.edges.filter((edge) => positions.has(edge.source) && positions.has(edge.target))
    .map((edge) => {
      const a = positions.get(edge.source);
      const b = positions.get(edge.target);
      return `<line x1="${a.x + 60}" y1="${a.y + 12}" x2="${b.x}" y2="${b.y + 12}"
        stroke="#8a9bb0" stroke-width="1" marker-end="url(#arrow)"/>`;
    }).join("") + '<defs><marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#8a9bb0"/></marker></defs>';

  const kinds = {};
  for (const node of nodes) kinds[node.kind] = (kinds[node.kind] || 0) + 1;
  $("graph-summary").textContent = `${nodes.length} node(s), ${payload.edges.length} edge(s) — ` +
    Object.entries(kinds).map(([kind, count]) => `${count} ${kind}`).join(", ");
}

/* ---------- Hayabusa ---------- */

const hayabusaState = { findings: [], runs: [] };

async function runHayabusa() {
  if (!state.openCase) { say("Open a case first", true); return; }
  const level = $("hayabusa-level").value;
  $("hayabusa-summary").textContent = "Running the detection engine — this can take a minute…";
  say("Hayabusa: running…");
  try {
    const payload = await apiPost(`/api/cases/${state.openCase.id}/detect`, { min_level: level });
    hayabusaState.runs = payload.runs || [];
    // Every finding keeps the run it came from: the alert analysis is per run.
    hayabusaState.findings = hayabusaState.runs.flatMap((run, position) =>
      (run.findings || []).map((finding) => ({ ...finding, _run: position })));
    const runs = hayabusaState.runs.map((run) => `${escapeHtml(run.collection)}: ${run.summary?.detections ?? 0} detection(s)` +
      (run.analysis === null || run.analysis === undefined ? "" :
        ` · <a href="#" class="lnk" data-sources="${escapeHtml(run.collection)}">export the sources</a>`)).join(" · ");
    $("hayabusa-summary").innerHTML = `${payload.total} finding(s) — ${runs}`;
    // The run adds its alert analysis to the case: refresh the tree without
    // leaving the findings the analyst just asked for.
    state.openCase = await api(`/api/cases/${state.openCase.id}`);
    renderTree();
    renderHayabusa();
    say(`Hayabusa: ${payload.total} finding(s) at level ${level}+`);
  } catch (error) {
    $("hayabusa-summary").textContent = error.message;
    say(error.message, true);
  }
}

function renderHayabusa() {
  $("hayabusa-rows").innerHTML = hayabusaState.findings.map((finding, position) => `
    <tr><td>${escapeHtml(finding.Timestamp || "")}</td>
      <td>${escapeHtml(finding.Level || "")}</td>
      <td title="${escapeHtml(finding.Details || "")}">${escapeHtml(finding.RuleTitle || "")}</td>
      <td>${escapeHtml(finding.Computer || "")}</td>
      <td>${escapeHtml(finding.Channel || "")}</td>
      <td>${escapeHtml(String(finding.EventID || ""))}</td>
      <td title="${escapeHtml(finding.MitreTags || "")}">${escapeHtml(finding.MitreTactics || "")}</td>
      <td><button class="btn" data-finding="${position}" data-want="show"
          title="Open the alerts of this rule in the grid">Show</button>
        <button class="btn" data-finding="${position}" data-want="mark"
          title="Mark every alert of this finding">Mark</button></td></tr>`).join("");
}

/* The alert analysis of the run, filtered on the rule that fired. */
async function showFindingInGrid(item) {
  const run = hayabusaState.runs[item._run] || {};
  if (run.analysis === null || run.analysis === undefined) {
    say("The alert analysis of this run is not open in the case", true);
    return;
  }
  state.analysis = run.analysis;
  state.groups = []; state.path = []; state.interval = ""; state.expression = null;
  state.filters = []; state.search = ""; state.sort = null; state.multiSort = [];
  showTab("analyses");
  await loadRows(true);
  const position = state.columns.findIndex((name) => name.toLowerCase() === "ruletitle");
  if (position > 0 && item.RuleTitle) {
    state.filters = [{ column: position - 1, operator: "eq", value: item.RuleTitle }];
    await loadRows(true);
  }
  say(`${state.total} alert(s) of this rule — ${item.RuleTitle}`);
}

async function markFinding(item) {
  const run = hayabusaState.runs[item._run] || {};
  if (run.analysis === null || run.analysis === undefined) {
    say("The alert analysis of this run is not open in the case", true);
    return;
  }
  const { _run, ...finding } = item;
  try {
    const payload = await apiPost(
      `/api/cases/${state.openCase.id}/analyses/${run.analysis}/bookmark-finding`, { finding });
    const capped = payload.matched > payload.marked ? ` of ${payload.matched}` : "";
    say(`${payload.marked} alert(s) marked${capped}`);
  } catch (error) {
    say(error.message, true);
  }
}

/* ---------- detection rules ---------- */

const rulesState = { rules: [], selected: null, filter: "" };
const RULES_SHOWN = 400;   // 5 000 rules in a table is a scrollbar, not a list

async function openDetectionRules() {
  rulesState.selected = null;
  $("detrules-text").value = "";
  $("detrules-name").textContent = "No rule selected";
  for (const id of ["detrules-toggle", "detrules-reset", "detrules-save"]) $(id).disabled = true;
  $("detrules-modal").classList.add("show");
  await loadDetectionRules();
}

async function loadDetectionRules() {
  try {
    const changed = $("detrules-changed").checked ? "?changed=true" : "";
    const payload = await api(`/api/rules${changed}`);
    rulesState.rules = payload.rules || [];
    rulesState.total = payload.count;
    rulesState.base = payload.base;
    rulesState.overrides = payload.overrides;
    rulesState.disabled = payload.disabled;
    renderRules();
  } catch (error) {
    say(error.message, true);
    $("detrules-summary").textContent = error.message;
  }
}

function renderRules() {
  const needle = rulesState.filter.trim().toLowerCase();
  const matching = needle
    ? rulesState.rules.filter((rule) => `${rule.name} ${rule.title}`.toLowerCase().includes(needle))
    : rulesState.rules;
  const shown = matching.slice(0, RULES_SHOWN);
  $("detrules-rows").innerHTML = shown.length
    ? shown.map((rule) => `<tr data-rule="${escapeHtml(rule.name)}"
        class="${rulesState.selected === rule.name ? "sel" : ""}">
        <td title="${escapeHtml(rule.name)}">${escapeHtml(rule.title || rule.name)}</td>
        <td>${escapeHtml(rule.level || "")}</td>
        <td>${escapeHtml(rule.source === "user" ? "edited" : "pack")}</td>
        <td>${rule.enabled ? "✔" : "✖"}</td></tr>`).join("")
    : '<tr><td colspan="4" class="cellnull">No rule matches this filter.</td></tr>';
  $("detrules-summary").textContent = `${matching.length} of ${rulesState.total} rule(s), `
    + `${rulesState.overrides} edited, ${rulesState.disabled} disabled`
    + (matching.length > shown.length ? ` — ${shown.length} shown, narrow the filter` : "")
    + ` — ${rulesState.base}`;
  $("detrules-rows").querySelectorAll("tr[data-rule]").forEach((row) => {
    row.addEventListener("click", () => selectDetectionRule(row.dataset.rule));
  });
}

async function selectDetectionRule(name) {
  try {
    const payload = await api(`/api/rules/${encodeURIComponent(name)}`);
    rulesState.selected = payload.name;
    $("detrules-name").textContent = payload.name;
    $("detrules-text").value = payload.text;
    const rule = rulesState.rules.find((item) => item.name === payload.name);
    $("detrules-toggle").textContent = rule && rule.enabled === false ? "Enable" : "Disable";
    for (const id of ["detrules-toggle", "detrules-reset", "detrules-save"]) $(id).disabled = false;
    $("detrules-rows").querySelectorAll("tr[data-rule]").forEach((row) =>
      row.classList.toggle("sel", row.dataset.rule === payload.name));
  } catch (error) {
    say(error.message, true);
  }
}

async function saveDetectionRule() {
  if (!rulesState.selected) return;
  try {
    await apiPut(`/api/rules/${encodeURIComponent(rulesState.selected)}`,
      { text: $("detrules-text").value });
    $("detrules-note").textContent = "Saved beside the tool pack: the next detection uses this version.";
    await loadDetectionRules();
    say("Rule saved");
  } catch (error) {
    $("detrules-note").textContent = error.message;
    say(error.message, true);
  }
}

async function resetDetectionRule() {
  if (!rulesState.selected) return;
  try {
    await apiPost(`/api/rules/${encodeURIComponent(rulesState.selected)}/reset`, {});
    await loadDetectionRules();
    await selectDetectionRule(rulesState.selected);
    say("Rule reset to the pack's version");
  } catch (error) {
    say(error.message, true);
  }
}

async function toggleDetectionRule() {
  if (!rulesState.selected) return;
  const rule = rulesState.rules.find((item) => item.name === rulesState.selected);
  // The button offers the opposite of the current state, so the request is its negation.
  const enabled = rule ? rule.enabled === false : true;
  try {
    await apiPost(`/api/rules/${encodeURIComponent(rulesState.selected)}/enabled`, { enabled });
    await loadDetectionRules();
    await selectDetectionRule(rulesState.selected);
    say(`Rule ${enabled ? "enabled" : "disabled"}`);
  } catch (error) {
    say(error.message, true);
  }
}

/* ---------- preferences ---------- */

async function openPreferences() {
  $("prefs-scale").value = localStorage.getItem("fireblade.scale") || "1";
  $("prefs-runtime").innerHTML = '<div class="emptygrid">Reading the runtime…</div>';
  $("prefs-modal").classList.add("show");
  try {
    const payload = await api("/api/settings");
    const readers = Object.entries(payload.readers || {})
      .map(([name, ready]) => `<label><span>${ready ? "✔" : "✖"} ${escapeHtml(name)}</span></label>`).join("");
    $("prefs-runtime").innerHTML = `
      <label><span>Cases folder</span><span class="pin">${escapeHtml(payload.cases_root)}</span></label>
      <label><span>Tool pack</span><span class="pin">${escapeHtml(payload.tools_root || "none")}</span></label>
      <label><span>Rows per page</span><span class="pin">${payload.page_size}</span></label>
      <label><span>Hayabusa</span><span class="pin">${payload.hayabusa ? "present" : "absent"}</span></label>
      <label><span>Readers</span><span class="pin">${payload.readers_ready}/${Object.keys(payload.readers || {}).length} present</span></label>
      ${readers}`;
  } catch (error) {
    $("prefs-runtime").innerHTML = `<div class="emptygrid">${escapeHtml(error.message)}</div>`;
  }
  $("prefs-profiles").innerHTML = '<div class="emptygrid">Reading the import profiles…</div>';
  try {
    const payload = await api("/api/profiles");
    $("prefs-profiles").innerHTML = payload.profiles.map((profile) => {
      const head = profile.signature.slice(0, 3).join(" + ");
      const more = profile.signature.length > 3 ? ` +${profile.signature.length - 3}` : "";
      return `<label title="${escapeHtml(profile.signature.join(" + "))}"><span>${escapeHtml(profile.name)}</span><span class="pin">${escapeHtml(head)}${more}</span></label>`;
    }).join("");
  } catch (error) {
    $("prefs-profiles").innerHTML = `<div class="emptygrid">${escapeHtml(error.message)}</div>`;
  }
}

/* ---------- profiles and plugins ---------- */

/* The desktop's "Profils et plugins" dialog: what the core recognises, what this
   instance loads, and the two ways to add one. */
async function openCompatibility() {
  closeModals();
  $("compat-note").hidden = true;
  $("compat-note").textContent = "";
  $("compat-profiles").innerHTML = '<div class="emptygrid">Reading…</div>';
  $("compat-plugins").innerHTML = "";
  $("compat-modal").classList.add("show");
  await loadCompatibility();
}

async function loadCompatibility() {
  try {
    const [profiles, plugins] = await Promise.all([api("/api/profiles"), api("/api/plugins")]);
    $("compat-where").textContent = `Presentation plugins folder: ${plugins.directory}` +
      (plugins.exists ? "" : " (not created yet)");
    $("compat-profiles").innerHTML = profiles.profiles.map((profile) =>
      `<label><span>${escapeHtml(profile.name)}</span><span class="pin">${profile.signature.length} field(s)
        · ${profile.columns.length} column(s) · ${profile.timestamps.length} date(s)
        · ${profile.booleans.length} boolean(s)</span></label>`).join("");
    $("compat-plugins").innerHTML = (plugins.plugins || []).length
      ? plugins.plugins.map((plugin) => `<label><span>${escapeHtml(plugin.name)}</span>
          <span class="pin">${(plugin.signature || []).length} field(s) · ${(plugin.columns || []).length} column(s)
          · ${(plugin.transforms || []).length} transform(s)</span></label>`).join("")
      : '<div class="emptygrid">No presentation plugin installed on this instance.</div>';
    const errors = plugins.errors || [];
    $("compat-note").hidden = !errors.length;
    $("compat-note").textContent = errors.join("\n");
  } catch (error) {
    $("compat-note").hidden = false;
    $("compat-note").textContent = error.message;
  }
}

async function installPluginFile(file) {
  try {
    const text = await file.text();
    if (text.length > 2 * 1024 * 1024) throw new Error("A presentation plugin is limited to 2 MB.");
    const plugin = JSON.parse(text);
    const payload = await apiPost("/api/plugins", { plugin });
    say(`Plugin installed: ${payload.name}`);
    await loadCompatibility();
  } catch (error) {
    $("compat-note").hidden = false;
    $("compat-note").textContent = error.message;
  }
}

async function createProfileFromAnalysis() {
  if (!state.openCase || !state.columns.length) { say("Open an analysis first", true); return; }
  const name = $("compat-name").value.trim();
  if (!name) { say("Give the profile a name first", true); return; }
  try {
    const payload = await apiPost(
      `/api/cases/${state.openCase.id}/analyses/${state.analysis}/profiles`, { name });
    $("compat-name").value = "";
    say(`Profile created: ${payload.name} (${payload.fields.columns} column(s))`);
    await loadCompatibility();
  } catch (error) {
    $("compat-note").hidden = false;
    $("compat-note").textContent = error.message;
  }
}

/* ---------- saved views ---------- */

async function loadViews() {
  if (!state.openCase) return [];
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/views`);
    return payload.views || [];
  } catch (_) {
    return [];
  }
}

async function openViewsDialog() {
  if (!state.columns.length) { say("Open an analysis first", true); return; }
  const names = await loadViews();
  $("views-list").innerHTML = names.map((name) => `
    <label><span>${escapeHtml(name)}</span>
      <span class="pin"><button class="btn" data-view-apply="${escapeHtml(name)}">Apply</button></span></label>`).join("")
    || '<div class="emptygrid">No saved view yet.</div>';
  $("views-list").querySelectorAll("[data-view-apply]").forEach((button) => {
    button.addEventListener("click", () => applyView(button.dataset.viewApply));
  });
  $("views-modal").classList.add("show");
}

async function saveCurrentView() {
  const name = $("view-name").value.trim();
  if (!name) { say("A name is required", true); return; }
  try {
    await apiPost(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/views`, {
      name,
      view: {
        search: state.search,
        filters: state.filters,
        groups: state.groups,
        sort: state.sort,
        descending: state.descending,
        bookmarks_only: state.bookmarksOnly,
      },
    });
    say(`View saved: ${name}`);
    $("view-name").value = "";
    await openViewsDialog();
  } catch (error) {
    say(error.message, true);
  }
}

async function applyView(name) {
  try {
    const view = await api(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/views/${encodeURIComponent(name)}`);
    state.search = view.search || "";
    $("search").value = state.search;
    state.filters = (view.filters || []).map((item) => ({ column: item.column, operator: item.operator, value: item.value }));
    state.groups = view.groups || [];
    state.path = [];
    state.sort = view.sort === undefined ? null : view.sort;
    state.descending = Boolean(view.descending);
    state.bookmarksOnly = Boolean(view.bookmarks_only);
    $("bookmarks-only").classList.toggle("active", state.bookmarksOnly);
    closeModals();
    await loadRows(true);
    say(`View applied: ${name}`);
  } catch (error) {
    say(error.message, true);
  }
}

/* ---------- colour rules ---------- */

let rulesCache = [];

function matchesRule(rule, values) {
  if (!rule.enabled) return false;
  const raw = values[rule.column + 1];
  const text = raw === null || raw === undefined ? "" : String(raw);
  const value = rule.value ?? "";
  switch (rule.operator) {
    case "eq": return text.toLowerCase() === String(value).toLowerCase();
    case "ne": return text.toLowerCase() !== String(value).toLowerCase();
    case "starts": return text.toLowerCase().startsWith(String(value).toLowerCase());
    case "ends": return text.toLowerCase().endsWith(String(value).toLowerCase());
    case "gt": case "ge": case "lt": case "le": {
      const a = Number(text), b = Number(value);
      if (Number.isNaN(a) || Number.isNaN(b)) return false;
      if (rule.operator === "gt") return a > b;
      if (rule.operator === "ge") return a >= b;
      if (rule.operator === "lt") return a < b;
      return a <= b;
    }
    case "empty": return text === "";
    case "not_empty": return text !== "";
    default: return text.toLowerCase().includes(String(value).toLowerCase());
  }
}

async function loadRules() {
  if (!state.openCase) return;
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/rules`);
    rulesCache = payload.rules || [];
    renderGrid();
  } catch (_) {
    rulesCache = [];
  }
}

function openRulesDialog() {
  if (!state.columns.length) { say("Open an analysis first", true); return; }
  $("rule-column").innerHTML = state.columns.slice(1)
    .map((name, index) => `<option value="${index}">${escapeHtml(name)}</option>`).join("");
  renderRulesList();
  $("rules-modal").classList.add("show");
}

function renderRulesList() {
  $("rules-list").innerHTML = rulesCache.map((rule, index) => `
    <label><span class="swatch" style="background:${rule.background};width:12px;height:12px;display:inline-block;border:1px solid #999"></span>
      <span>${escapeHtml(state.columns[rule.column + 1] || "")} ${escapeHtml(rule.operator)} “${escapeHtml(rule.value)}”</span>
      <span class="pin"><button class="btn" data-rule-remove="${index}">Remove</button></span></label>`).join("")
    || '<div class="emptygrid">No rule yet.</div>';
  $("rules-list").querySelectorAll("[data-rule-remove]").forEach((button) => {
    button.addEventListener("click", async () => {
      rulesCache.splice(Number(button.dataset.ruleRemove), 1);
      await persistRules();
      renderRulesList();
    });
  });
}

async function persistRules() {
  const response = await fetch(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/rules`,
    { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rules: rulesCache }) });
  if (!response.ok) throw new Error((await response.json()).detail || response.statusText);
  renderGrid();
}

async function addRule() {
  const rule = {
    column: Number($("rule-column").value),
    operator: $("rule-operator").value,
    value: $("rule-value").value,
    background: $("rule-colour").value,
    foreground: "#202020",
    bold: false,
    enabled: true,
  };
  rulesCache.push(rule);
  try {
    await persistRules();
    renderRulesList();
  } catch (error) {
    rulesCache.pop();
    say(error.message, true);
  }
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

const workspaceState = { entities: [], indicators: [], selected: null };

async function loadActions() {
  if (!state.openCase) return;
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/workspace`);
    actionState.items = payload.actions;
    workspaceState.entities = payload.entities || [];
    workspaceState.indicators = payload.iocs || [];
    renderActions();
    renderEntities();
    renderIndicators();
  } catch (error) {
    say(error.message, true);
  }
}

function showWorkspaceSub(name) {
  document.querySelectorAll(".subtab[data-sub]").forEach((tab) =>
    tab.classList.toggle("active", tab.dataset.sub === name));
  for (const view of ["actions", "indicators", "entities"]) {
    const box = $(`sub-${view}`);
    if (box) box.style.display = view === name ? "flex" : "none";
  }
}

function renderEntities() {
  $("entity-rows").innerHTML = workspaceState.entities.length
    ? workspaceState.entities.map((item) => `<tr>
        <td>${escapeHtml(item.kind || "")}</td>
        <td>${escapeHtml(item.label || "")}</td>
        <td>${escapeHtml(item.hostname || "")}</td>
        <td>${escapeHtml(item.ip || "")}</td>
        <td>${escapeHtml(item.os || "")}</td></tr>`).join("")
    : '<tr><td colspan="5" class="cellnull">No machine or account declared in this case.</td></tr>';
  const hosts = workspaceState.entities.filter((item) => item.kind === "machine").length;
  const accounts = workspaceState.entities.filter((item) => item.kind === "account").length;
  const total = workspaceState.entities.length;
  $("entity-summary").textContent = `${total} entr${total === 1 ? "y" : "ies"} — `
    + `${hosts} machine(s), ${accounts} account(s)`;
}

function renderIndicators() {
  $("indicator-rows").innerHTML = workspaceState.indicators.length
    ? workspaceState.indicators.map((item) => `<tr data-indicator="${escapeHtml(item.id)}"
        class="${workspaceState.selected === item.id ? "sel" : ""}">
        <td>${escapeHtml(item.kind || "")}</td>
        <td title="${escapeHtml(item.value || "")}">${escapeHtml(item.value || "")}</td>
        <td>${escapeHtml(item.label || "")}</td>
        <td>${escapeHtml(item.status || "")}</td></tr>`).join("")
    : '<tr><td colspan="4" class="cellnull">No indicator tracked in this case.</td></tr>';
  $("indicator-remove").disabled = !workspaceState.selected;
  $("indicator-summary").textContent = `${workspaceState.indicators.length} indicator(s) tracked`;
  $("indicator-rows").querySelectorAll("tr[data-indicator]").forEach((row) => {
    row.addEventListener("click", () => {
      workspaceState.selected = (workspaceState.selected === row.dataset.indicator)
        ? null : row.dataset.indicator;
      renderIndicators();
    });
  });
}

async function addEntity() {
  if (!state.openCase) { say("Open a case first", true); return; }
  const label = $("entity-label").value.trim();
  if (!label) { say("Give the machine or the account a name", true); return; }
  try {
    const payload = await apiPost(`/api/cases/${state.openCase.id}/entities`, {
      kind: $("entity-kind").value, label,
      hostname: $("entity-hostname").value.trim(),
      ip: $("entity-ip").value.trim(),
      os: $("entity-os").value.trim(),
    });
    $("entity-label").value = "";
    $("entity-hostname").value = "";
    $("entity-ip").value = "";
    $("entity-os").value = "";
    await loadActions();
    say(`${payload.kind} added: ${payload.label}`);
  } catch (error) {
    say(error.message, true);
  }
}

async function addIndicators() {
  if (!state.openCase) { say("Open a case first", true); return; }
  const values = $("indicator-values").value.trim();
  if (!values) { say("Paste at least one indicator", true); return; }
  try {
    const payload = await apiPost(`/api/cases/${state.openCase.id}/iocs`, {
      values, label: $("indicator-label").value.trim(), source: "typed in the Host edition",
    });
    $("indicator-values").value = "";
    $("indicator-label").value = "";
    await loadActions();
    say(`${payload.added} indicator(s) tracked`
      + (payload.skipped ? `, ${payload.skipped} skipped (already there or unreadable)` : ""));
  } catch (error) {
    say(error.message, true);
  }
}

async function removeIndicator() {
  if (!state.openCase || !workspaceState.selected) return;
  try {
    await apiDelete(`/api/cases/${state.openCase.id}/iocs/${encodeURIComponent(workspaceState.selected)}`);
    workspaceState.selected = null;
    await loadActions();
    say("Indicator removed");
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
    loadHuntHistory();
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

async function loadHuntHistory() {
  if (!state.openCase) return;
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/hunts`);
    $("ioc-history").innerHTML = '<option value="">Saved hunts…</option>' +
      payload.hunts.map((hunt) => `<option value="${escapeHtml(hunt.name)}">${escapeHtml(hunt.started)} · ${hunt.hits} hit(s) · ${escapeHtml(hunt.status)}</option>`).join("");
  } catch (_) { /* an empty list is not an error worth a banner */ }
}

async function openHunt(name) {
  if (!name) return;
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/hunts/${encodeURIComponent(name)}`);
    iocState.hits = payload.hits || [];
    $("ioc-input").value = payload.text || "";
    $("ioc-summary").textContent = `${payload.indicators} indicator(s) · ${payload.scanned} row(s) scanned — ${iocState.hits.length} hit(s) (replayed hunt)`;
    renderIoc();
  } catch (error) {
    say(error.message, true);
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
const timelineState = { offset: 0, text: "", kind: "text", payload: null, dates: {} };

/* The desktop chooses, per analysis, how its dates are read. The choice travels
   with every timeline request, so a rebuild reads the case the same way. */
function timelineDatesParam() {
  const chosen = {};
  document.querySelectorAll('#timeline-dates select[data-source]').forEach((select) => {
    if (select.value && select.value !== "auto") chosen[select.dataset.source] = select.value;
  });
  timelineState.dates = chosen;
  return Object.keys(chosen).length ? JSON.stringify(chosen) : "";
}

function renderTimelineDates(payload) {
  const box = $("timeline-dates");
  box.innerHTML = (payload.sources || []).map((source) => {
    const chosen = timelineState.dates[String(source.id)] || "auto";
    const options = [
      `<option value="auto" ${chosen === "auto" ? "selected" : ""}>detected${source.column_name ? ": " + escapeHtml(source.column_name) : ""}</option>`,
      `<option value="none" ${chosen === "none" ? "selected" : ""}>no date (correlation only)</option>`,
    ];
    if (source.split) {
      options.push(`<option value="split" ${chosen === "split" ? "selected" : ""}>date + time (separate columns)</option>`);
    }
    for (const name of source.headers || []) {
      options.push(`<option value="${escapeHtml(name)}" ${chosen === name ? "selected" : ""}>${escapeHtml(name)}</option>`);
    }
    return `<div class="tsrc"><span class="tname" title="${escapeHtml(source.original || source.name)}">${escapeHtml(source.name)}</span>
      <select class="select" data-source="${source.id}">${options.join("")}</select></div>`;
  }).join("");
}

function applyTimelineDates() {
  const chosen = {};
  document.querySelectorAll('#timeline-dates select[data-source]').forEach((select) => {
    if (select.value && select.value !== "auto") chosen[select.dataset.source] = select.value;
  });
  timelineState.dates = chosen;
  loadTimeline(true);
}

function utcLabel(ns) {
  const ms = Number(ns) / 1e6;
  return new Date(ms).toISOString().replace("T", " ").replace(".000Z", "Z");
}

async function loadTimeline(reset) {
  if (!state.openCase) return;
  if (reset) timelineState.offset = 0;
  const params = new URLSearchParams({ offset: String(timelineState.offset) });
  if (timelineState.text) { params.set("text", timelineState.text); params.set("kind", timelineState.kind); }
  const dates = timelineDatesParam();
  if (dates) params.set("dates", dates);
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/timeline?${params}`);
    timelineState.payload = payload;
    renderTimeline(payload);
  } catch (error) {
    say(error.message, true);
  }
}

function renderTimeline(payload) {
  renderTimelineDates(payload);
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
    ? `<div class="ptab active" title="${escapeHtml(current.label)}">${escapeHtml(current.label)}
         <span class="ptab-close" id="close-analysis" title="Close this analysis — the file stays in the case">✕</span></div>`
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
  if (state.interval && state.groups.length) params.set("interval", state.interval);
  if (state.expression) params.set("expression_json", JSON.stringify(state.expression));
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
  // A new page is a new set of rows: a selection of ids that are no longer on
  // screen must not survive into "copy the selected rows".
  state.selection.clear();
  state.anchor = null;
  try {
    const payload = await api(rowsUrl());
    state.columns = payload.columns;
    state.rows = payload.rows;
    state.total = payload.total;
    state.offset = payload.offset;
    state.grouped = Boolean(payload.grouped);
    await loadBookmarks();
    await loadCellNotes();
    await loadRules();
    await loadLayout();
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

async function loadCellNotes() {
  state.cellNotes = new Map();
  if (!state.rows.length) return;
  try {
    const payload = await apiPost(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/cellnotes`,
      { row_ids: state.rows.map((row) => Number(row[0])) });
    state.cellNotes = new Map(Object.entries(payload.notes || {}));
  } catch (_) {
    state.cellNotes = new Map();
  }
}

function notesForRow(rowId) {
  return state.cellNotes.get(String(rowId)) || {};
}

async function toggleBookmark(rowId, note) {
  await postBookmark(rowId, note);
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
  if (!state.grouped) $("group-chart").hidden = true;
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
    // The input carries the operator's prefix, so editing the text keeps the
    // intent: a value filtered with "=" must not silently become "contains".
    const shownValue = current ? filterPrefix(current.operator) + current.value : "";
    head.push(`<th><input data-filter="${index - 1}" placeholder="Filter…" value="${escapeHtml(shownValue)}"></th>`);
  });
  head.push("</tr>");
  $("head").innerHTML = head.join("");

  $("body").innerHTML = state.rows.map((row) => {
    const id = row[0];
    // Column 0 is the row identifier: it gets its own cell, after the checkbox one.
    const rowNotes = notesForRow(id);
    const cells = shown.map(({ index }) => {
      const value = row[index];
      const text = value === null || value === "" ? "☐" : String(value);
      const noted = rowNotes[String(index - 1)];
      const cls = [value === null || value === "" ? "cellnull" : (index === 0 ? "rowid" : ""),
                   noted ? "noted" : ""].filter(Boolean).join(" ");
      const title = noted ? ` title="${escapeHtml(noted)}"` : "";
      return `<td class="${cls}"${title} data-cell="${index - 1}">${renderBoolean(index - 1, text)}${noted ? '<span class="notemark"></span>' : ""}</td>`;
    }).join("");
    const marked = state.bookmarks.has(String(id)) ? "marked" : "";
    const rule = rulesCache.find((item) => matchesRule(item, row));
    const style = rule ? ` style="background:${rule.background};color:${rule.foreground}${rule.bold ? ";font-weight:600" : ""}"` : "";
    return `<tr data-row="${escapeHtml(String(id))}" class="${rowSelected(id) ? "sel" : ""}"${style}>
      <td class="markcell"><span class="cb ${marked}" title="Bookmark this row"></span></td>${cells}</tr>`;
  }).join("");

  const from = state.total ? state.offset + 1 : 0;
  const to = Math.min(state.offset + state.rows.length, state.total);
  $("pageinfo").textContent = `${from}–${to} / ${state.total} row(s)`;
  say(`${state.total} row(s) in this analysis${state.filters.length ? ` — ${state.filters.length} filter(s)` : ""}`);
  applyPinning();
}

/* The desktop charts the grouped counts; this is the same page of groups as the
   grid, so the bars and the table can never disagree. */
const CHART_ROWS = 14;

function renderGroupChart() {
  const box = $("group-chart");
  if (!state.grouped || !state.rows.length) { box.hidden = true; box.innerHTML = ""; return; }
  const name = state.columns?.[state.groups[state.path.length] + 1] || "group";
  const entries = state.rows.slice(0, CHART_ROWS).map((row) => ({
    label: row[0] === null || row[0] === "" ? "(empty)" : String(row[0]),
    count: Number(row[1]) || 0,
  }));
  const peak = Math.max(1, ...entries.map((entry) => entry.count));
  const bars = entries.map((entry) => `<div class="bar" title="${escapeHtml(entry.label)}">
      <span class="label">${escapeHtml(entry.label)}</span>
      <span class="track"><span class="fill" style="width:${Math.round(entry.count / peak * 100)}%"></span></span>
      <span class="count">${entry.count}</span></div>`).join("");
  const more = state.rows.length > CHART_ROWS
    ? `<div class="more">… ${state.rows.length - CHART_ROWS} more group(s) on this page</div>` : "";
  box.hidden = false;
  box.innerHTML = `<div class="bar"><span class="label"><b>${escapeHtml(name)}</b></span>
      <span class="track"></span><span class="count">rows</span></div>${bars}${more}`;
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
  renderGroupChart();
  $("pageinfo").textContent = `${from}–${to} / ${state.rows.length} group(s) — ${state.total} row(s)`;
  say(`Grouped by ${name} — ${state.rows.length} group(s) on this page, ${state.total} row(s) in the analysis`);
}

function showDetails(row) {
  const box = $("details");
  if (!row) {
    box.innerHTML = '<div class="ph">Details of the selected row</div>';
    return;
  }
  const rowNotes = notesForRow(row[0]);
  const pairs = visibleColumns().map(({ name, index }) => {
    const value = row[index];
    if (index === 0) return "";
    if (value === null || value === "") return "";
    const note = rowNotes[String(index - 1)];
    return `<tr><td class="k">${escapeHtml(name)}</td>
      <td>${escapeHtml(String(value))}</td>
      <td class="k"><button class="btn" data-cellnote="${index - 1}">${note ? "edit note" : "note"}</button>
      ${note ? `<span class="cellnote">${escapeHtml(note)}</span>` : ""}</td></tr>`;
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
  box.querySelectorAll("[data-cellnote]").forEach((button) => {
    button.addEventListener("click", async () => {
      const column = Number(button.dataset.cellnote);
      const current = notesForRow(id)[String(column)] || "";
      const note = window.prompt("Cell note", current);
      if (note === null) return;
      try {
        await apiPost(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/cellnote`,
          { row_id: Number(id), column, note });
        await loadCellNotes();
        await loadRules();
        say(note ? "Cell note saved" : "Cell note removed");
      } catch (error) {
        say(error.message, true);
      }
    });
  });
  const saveNote = (value) => {
    const promise = selectedIds().length > 1 ? markSelection(value) : toggleBookmark(id, value);
    promise.catch((error) => say(error.message, true));
  };
  $("note-save").addEventListener("click", () => saveNote($("note-input").value));
  $("note-clear").addEventListener("click", () => saveNote(""));
  $("note-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") saveNote($("note-input").value);
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
  $("hayabusa-view").style.display = (name === "hayabusa" || name === "evtx") ? "flex" : "none";
  $("graph-view").style.display = name === "graph" ? "flex" : "none";
  if (name === "graph" && state.openCase) buildGraph();
  if (name === "evtx") {
    $("hayabusa-summary").textContent = "EVTX detection: the engine reads the imported event logs of this case.";
  }
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
      ${index ? `<span class="pin"><input type="checkbox" data-bool="${index - 1}" ${booleanColumns().has(index - 1) ? "checked" : ""}> boolean
        <input type="checkbox" data-pin="${index - 1}" ${state.pinned.has(index - 1) ? "checked" : ""}> pin left
        <input type="checkbox" data-pinright="${index - 1}" ${state.pinnedRight.has(index - 1) ? "checked" : ""}> pin right</span>` : ""}
    </label>`).join("");
  list.querySelectorAll("input[data-col]").forEach((box) => {
    box.addEventListener("change", () => {
      const index = Number(box.dataset.col);
      if (box.checked) state.hidden.delete(index); else state.hidden.add(index);
      renderGrid();
      saveLayoutSoon();
    });
  });
  list.querySelectorAll("input[data-bool]").forEach((box) => {
    box.addEventListener("change", () => {
      const column = Number(box.dataset.bool);
      const set = booleanColumns();
      if (box.checked) set.add(column); else set.delete(column);
      localStorage.setItem("fireblade.boolean", JSON.stringify([...set]));
      renderGrid();
    });
  });
  list.querySelectorAll("input[data-pin]").forEach((box) => {
    box.addEventListener("change", () => {
      const column = Number(box.dataset.pin);
      if (box.checked) { state.pinned.add(column); state.pinnedRight.delete(column); }
      else state.pinned.delete(column);
      openColumnManager();
      applyPinning();
      saveLayoutSoon();
    });
  });
  list.querySelectorAll("input[data-pinright]").forEach((box) => {
    box.addEventListener("change", () => {
      const column = Number(box.dataset.pinright);
      if (box.checked) { state.pinnedRight.add(column); state.pinned.delete(column); }
      else state.pinnedRight.delete(column);
      openColumnManager();
      applyPinning();
      saveLayoutSoon();
    });
  });
  $("columns-modal").classList.add("show");
}

/* A pinned column freezes on its edge. The offsets accumulate the real widths, so
   two pinned columns sit side by side instead of on top of each other. */
function pinOffsets() {
  const shown = visibleColumns();
  const widthOf = (index) => state.widths[index] || defaultWidth(state.columns[index], index);
  const left = new Map();
  const right = new Map();
  let offset = 30;                       // the mark cell, which stays on the left
  for (const { index } of shown) {
    if (!state.pinned.has(index - 1)) continue;
    left.set(index - 1, offset);
    offset += widthOf(index);
  }
  offset = 0;
  for (let position = shown.length - 1; position >= 0; position -= 1) {
    const index = shown[position].index;
    if (!state.pinnedRight.has(index - 1)) continue;
    right.set(index - 1, offset);
    offset += widthOf(index);
  }
  return { left, right };
}

function applyPinning() {
  if (!state.columns.length) return;
  const grid = $("grid");
  const { left, right } = pinOffsets();
  const place = (node, column) => {
    const side = left.has(column) ? "left" : (right.has(column) ? "right" : null);
    node.style.left = side === "left" ? `${left.get(column)}px` : "";
    node.style.right = side === "right" ? `${right.get(column)}px` : "";
    node.classList.toggle("pinned-left", side === "left");
    node.classList.toggle("pinned-right", side === "right");
    return side;
  };
  grid.querySelectorAll("thead th[data-column]").forEach((th) => {
    place(th, Number(th.dataset.column) - 1);
  });
  const shown = visibleColumns();
  grid.querySelectorAll(".colfilter th").forEach((th, position) => {
    if (position === 0) return;
    const entry = shown[position - 1];
    if (entry) place(th, entry.index - 1);
  });
  grid.querySelectorAll("tbody td[data-cell]").forEach((td) => {
    place(td, Number(td.dataset.cell));
  });
}

function applyGrouping() {
  const column = Number($("group-select").value);
  state.groups = [column];
  state.interval = $("group-interval").value;
  state.path = [];
  $("group-label").textContent = `Grouped by ${state.columns[column + 1]}`;
  closeModals();
  loadRows(true);
}

/* ---------- palette ---------- */

/* The desktop offers presets and a custom palette of six colours. The Host keeps
   the same six, in the browser: a preset swaps the variables, a custom palette
   overrides them, and the choice belongs to the analyst's browser. */
const PALETTE_KEYS = [["window", "--window"], ["text", "--text"], ["base", "--base"],
                      ["alternate", "--alt"], ["highlight", "--sel"],
                      ["selection_text", "--sel-text"]];
const paletteState = { theme: "light", custom: {} };

function currentPalette() {
  const computed = getComputedStyle(document.documentElement);
  const values = {};
  for (const [key, variable] of PALETTE_KEYS) {
    values[key] = computed.getPropertyValue(variable).trim() || "#ffffff";
  }
  return values;
}

function applyPalette() {
  const root = document.documentElement;
  root.dataset.theme = paletteState.theme === "dark" ? "dark" : "";
  for (const [key, variable] of PALETTE_KEYS) {
    if (paletteState.theme === "custom" && paletteState.custom[key]) {
      root.style.setProperty(variable, paletteState.custom[key]);
    } else {
      root.style.removeProperty(variable);
    }
  }
  const select = $("palette-theme");
  if (select) select.value = paletteState.theme;
  const colours = $("palette-colours");
  if (colours) {
    colours.hidden = paletteState.theme !== "custom";
    for (const [key] of PALETTE_KEYS) {
      const input = colours.querySelector(`input[data-colour="${key}"]`);
      if (input && paletteState.custom[key]) input.value = paletteState.custom[key];
    }
  }
}

function savePalette() {
  try {
    localStorage.setItem("fireblade.palette", JSON.stringify(paletteState));
  } catch (_) { /* a full quota must not break the window */ }
}

function loadPalette() {
  try {
    const saved = JSON.parse(localStorage.getItem("fireblade.palette") || "{}");
    if (["light", "dark", "custom"].includes(saved.theme)) paletteState.theme = saved.theme;
    if (saved.custom && typeof saved.custom === "object") paletteState.custom = saved.custom;
  } catch (_) { /* a broken preference falls back to the light theme */ }
  applyPalette();
}

function choosePalette(theme) {
  paletteState.theme = theme;
  if (theme === "custom" && !Object.keys(paletteState.custom).length) {
    // Start from what is on screen: the analyst edits colours, not guesses them.
    paletteState.custom = currentPalette();
  }
  applyPalette();
  savePalette();
}

/* ---------- display settings ---------- */

function applyRowHeight() {
  const value = localStorage.getItem("fireblade.rowHeight") || "20";
  document.documentElement.style.setProperty("--row-height", value + "px");
  const select = $("row-height");
  if (select) select.value = value;
}

function booleanColumns() {
  try { return new Set(JSON.parse(localStorage.getItem("fireblade.boolean") || "[]")); }
  catch (_) { return new Set(); }
}

function renderBoolean(column, text) {
  if (!booleanColumns().has(column)) return escapeHtml(text);
  if (/^(true|vrai|1)$/i.test(text)) return "✓";
  if (/^(false|faux|0)$/i.test(text)) return "✗";
  return escapeHtml(text);
}

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
    node.addEventListener("click", () => act(node.dataset.act, node));
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
    saveLayoutSoon();
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
    const cell = event.target.closest("td[data-cell]");
    contextCell = cell ? cell.dataset.cell : null;
    event.preventDefault();
    contextRow = tr;
    const menu = $("row-menu");
    // The two EVTX actions only mean something in an alert analysis.
    const alerts = isAlertAnalysis();
    for (const action of ["alert-context", "alert-source"]) {
      const item = menu.querySelector(`[data-act="${action}"]`);
      if (item) item.hidden = !alerts;
    }
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
    selectRow(tr, event);
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
  $("pane-tabs").addEventListener("click", async (event) => {
    if (!event.target.closest("#close-analysis") || !state.openCase) return;
    try {
      await apiDelete(`/api/cases/${state.openCase.id}/analyses/${state.analysis}`);
      say("Analysis closed — its file stays in the case");
      await openCase(state.openCase.id);
    } catch (error) {
      say(error.message, true);
    }
  });

  $("details-toggle").addEventListener("click", () => {
    const box = $("details");
    box.style.display = box.style.display === "none" ? "block" : "none";
  });

  $("import-input").addEventListener("change", (event) => {
    const files = [...(event.target.files || [])];
    event.target.value = "";
    if (files.length) { openImportDialog(); previewFiles(files); }
  });
  $("palette-theme").addEventListener("change", (event) => choosePalette(event.target.value));
  $("palette-reset").addEventListener("click", () => {
    paletteState.custom = {};
    if (paletteState.theme === "custom") paletteState.theme = "light";
    applyPalette();
    savePalette();
  });
  $("palette-colours").addEventListener("input", (event) => {
    const key = event.target.dataset.colour;
    if (!key) return;
    paletteState.custom[key] = event.target.value;
    applyPalette();
    savePalette();
  });
  $("plugin-input").addEventListener("change", (event) => {
    const file = (event.target.files || [])[0];
    event.target.value = "";
    if (file) installPluginFile(file);
  });
  $("preview-input").addEventListener("change", (event) => {
    const files = [...(event.target.files || [])];
    event.target.value = "";
    if (files.length) previewFiles(files);
  });
  for (const id of ["preview-delimiter", "preview-encoding"]) {
    $(id).addEventListener("change", refreshPreviews);
  }

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
    openImportDialog();
    previewFiles([...event.dataTransfer.files]);
  });

  $("ioc-scan").addEventListener("click", runIocScan);
  $("ioc-history").addEventListener("change", (event) => openHunt(event.target.value));
  $("ioc-history").addEventListener("focus", loadHuntHistory);
  $("derived-operation").addEventListener("change", derivedOperationChanged);
  $("hayabusa-run").addEventListener("click", runHayabusa);
  $("detrules-open").addEventListener("click", openDetectionRules);
  $("detrules-reload").addEventListener("click", loadDetectionRules);
  $("detrules-changed").addEventListener("change", loadRules);
  $("detrules-filter").addEventListener("input", (event) => {
    rulesState.filter = event.target.value;
    renderRules();
  });
  $("detrules-save").addEventListener("click", saveDetectionRule);
  $("detrules-reset").addEventListener("click", resetDetectionRule);
  $("detrules-toggle").addEventListener("click", toggleDetectionRule);
  $("hayabusa-rows").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-finding]");
    if (!button) return;
    const item = hayabusaState.findings[Number(button.dataset.finding)];
    if (!item) return;
    if (button.dataset.want === "mark") markFinding(item);
    else showFindingInGrid(item);
  });
  $("hayabusa-summary").addEventListener("click", (event) => {
    const link = event.target.closest("a[data-sources]");
    if (!link || !state.openCase) return;
    event.preventDefault();
    window.location = `/api/cases/${state.openCase.id}/detection/${encodeURIComponent(link.dataset.sources)}/sources`;
  });
  $("graph-build").addEventListener("click", buildGraph);
  $("graph-navigator").addEventListener("click", exportNavigator);
  $("graph-png").addEventListener("click", exportGraphPng);
  $("graph-node").addEventListener("click", openGraphNode);
  $("imports-refresh").addEventListener("click", loadImports);
  $("imports-status").addEventListener("change", renderImports);
  $("action-add").addEventListener("click", addAction);
  document.querySelectorAll(".subtab[data-sub]").forEach((tab) => {
    tab.addEventListener("click", () => showWorkspaceSub(tab.dataset.sub));
  });
  $("entity-add").addEventListener("click", addEntity);
  $("indicator-add").addEventListener("click", addIndicators);
  $("indicator-remove").addEventListener("click", removeIndicator);
  $("action-export").addEventListener("click", () => {
    if (!state.openCase) { say("Open a case first", true); return; }
    window.location.href = `/api/cases/${state.openCase.id}/actions/export`;
  });
  $("action-rows").addEventListener("click", (event) => {
    const button = event.target.closest("[data-action-close]");
    if (button) toggleAction(button.dataset.actionClose);
  });
  $("timeline-dates").addEventListener("change", applyTimelineDates);
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

  $("row-height").addEventListener("change", (event) => {
    localStorage.setItem("fireblade.rowHeight", event.target.value);
    applyRowHeight();
  });
  $("prefs-scale").addEventListener("change", (event) => {
    localStorage.setItem("fireblade.scale", event.target.value);
    applyScale();
    $("scale").value = event.target.value;
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

async function act(name, node) {
  // A button inside a dialog belongs to that dialog: closing every modal first
  // used to make "Add a condition" dismiss the filter it was editing.
  if (!node || !node.closest(".dialog")) closeModals();
  switch (name) {
    case "refresh-cases": await loadCases(); if (state.openCase) await loadRows(true); break;
    case "close-case": closeCase(); break;
    case "reload-analysis": await loadRows(true); break;
    case "export-csv":
      if (!state.openCase) { say("No case open", true); break; }
      window.location.href = rowsUrl().replace("/rows?", "/export?");
      break;
    case "import-file": openImportDialog(); break;
    case "preview-choose": $("preview-input").click(); break;
    case "preview-path": await previewServerPath(); break;
    case "preview-import": await confirmImport(); break;
    case "copy-value": await copyCellValue(); break;
    case "filter-value": filterFromCell("eq"); break;
    case "exclude-value": filterFromCell("ne"); break;
    case "sort-asc": sortFromCell(false); break;
    case "sort-desc": sortFromCell(true); break;
    case "group-by-column": groupFromCell(); break;
    case "pin-column": pinFromCell("left"); break;
    case "graph-node-save": await saveGraphNode(); break;
    case "alert-context": await showAlertContext(); break;
    case "alert-source": await openSourceEvent(); break;
    case "pin-column-right": pinFromCell("right"); break;
    case "hide-column": hideFromCell(); break;
    case "unmark-selection": await markSelection(""); break;
    case "group-column": openGroupPicker(); break;
    case "global-search": $("search-modal").classList.add("show"); break;
    case "global-run": await runGlobalSearch(); $("search-modal").classList.add("show"); break;
    case "new-case": openCaseDialog("create"); break;
    case "rename-case": openCaseDialog("rename"); break;
    case "case-save": await saveCase(); break;
    case "archive-case": await archiveCase(); break;
    case "restore-case": await restoreCase(); break;
    case "destroy-case": openDestroyDialog(); break;
    case "destroy-run": await runDestroy(); break;
    case "report": $("report-modal").classList.add("show"); break;
    case "report-build": await buildReport(); break;
    case "columns": openColumnManager(); break;
    case "preferences": await openPreferences(); break;
    case "expression": openExpressionDialog(); break;
    case "expr-apply": applyExpression(); break;
    case "expr-clear":
      state.expression = null;
      $("expr-root").innerHTML = "";
      $("expr-root").appendChild(exprGroupNode({ logic: "and", children: [] }, 0));
      loadRows(true);
      say("Advanced filter cleared");
      break;
    case "views": await openViewsDialog(); break;
    case "view-save": await saveCurrentView(); break;
    case "rules": openRulesDialog(); break;
    case "rule-add": await addRule(); break;
    case "pivot": await runPivot(); break;
    case "copy-row": await copySelectedRows(); break;
    case "cell-json": showCellJson(); break;
    case "rule-from-cell": await ruleFromCell(); break;
    case "cell-copy": await navigator.clipboard.writeText($("cell-full").value).then(() => say("Cell copied")); break;
    case "bookmark-row": await markSelection("bookmarked"); break;
    case "derived": openDerivedDialog(); break;
    case "derived-add": await addDerived(); break;
    case "columns-reset": state.hidden.clear(); renderGrid(); openColumnManager(); break;
    case "group-apply": applyGrouping(); break;
    case "group-remove":
      state.groups = []; state.path = []; state.interval = "";
      $("group-label").textContent = "Filters apply to the whole analysis, not just the page on screen.";
      loadRows(true); break;
    case "group-none":
      state.groups = []; state.path = []; $("group-label").textContent = "Drag a header here to group the results";
      loadRows(true); break;
    case "display-settings": $("settings-modal").classList.add("show"); break;
    case "settings-close": closeModals(); break;
    case "compat-open": await openCompatibility(); break;
    case "compat-reload": await loadCompatibility(); break;
    case "plugin-install": $("plugin-input").click(); break;
    case "profile-create": await createProfileFromAnalysis(); break;
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
  loadPalette();
  applyScale();
  applyRowHeight();
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
