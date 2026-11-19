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

function defaultWidth(name, index) {
  if (index === 0) return 30;
  const lower = name.toLowerCase();
  if (/(timestamp|date|time|created|modified)/.test(lower)) return 168;
  if (/(description|message|path|command|target)/.test(lower)) return 260;
  if (/(user|account|computer|host)/.test(lower)) return 130;
  if (/(ip|address|port)/.test(lower)) return 120;
  return Math.max(90, Math.min(200, name.length * 8 + 30));
}

/* ---------- cases ---------- */

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
  if (state.sort !== null) {
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
    renderGrid();
    renderPaneTabs();
  } catch (error) {
    say(error.message, true);
  }
}

function clearGrid(message) {
  $("head").innerHTML = "";
  $("body").innerHTML = "";
  $("cols").innerHTML = "";
  $("grid-empty").hidden = false;
  $("grid-empty").textContent = message;
  $("pageinfo").textContent = "";
}

function renderGrid() {
  const empty = $("grid-empty");
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
    const sorted = state.sort === index;
    const arrow = sorted ? (state.descending ? "▼" : "▲") : "▲▼";
    head.push(`<th class="${sorted ? "sorted" : ""}" data-column="${index}" title="${escapeHtml(name)}">
      ${index === 0 ? "Ro…" : escapeHtml(name)}<span class="sort">${arrow}</span>
      <span class="grip" data-grip="${index}"></span></th>`);
  });
  head.push("</tr>");
  // One leading cell for the checkbox column, then one per column.
  head.push('<tr class="colfilter"><th></th>');
  state.columns.forEach((name, index) => {
    if (index === 0) { head.push("<th></th>"); return; }
    const current = state.filters.find((item) => item.column === index - 1);
    head.push(`<th><input data-filter="${index - 1}" placeholder="Filter…" value="${escapeHtml(current ? current.value : "")}"></th>`);
  });
  head.push("</tr>");
  $("head").innerHTML = head.join("");

  $("body").innerHTML = state.rows.map((row) => {
    const id = row[0];
    // Column 0 is the row identifier: it gets its own cell, after the checkbox one.
    const cells = row.map((value, index) => {
      const text = value === null || value === "" ? "☐" : String(value);
      const cls = value === null || value === "" ? "cellnull" : (index === 0 ? "rowid" : "");
      return `<td class="${cls}">${escapeHtml(text)}</td>`;
    }).join("");
    return `<tr data-row="${escapeHtml(String(id))}" class="${state.selected === id ? "sel" : ""}">
      <td><span class="cb"></span></td>${cells}</tr>`;
  }).join("");

  const from = state.total ? state.offset + 1 : 0;
  const to = Math.min(state.offset + state.rows.length, state.total);
  $("pageinfo").textContent = `${from}–${to} / ${state.total} row(s)`;
  say(`${state.total} row(s) in this analysis${state.filters.length ? ` — ${state.filters.length} filter(s)` : ""}`);
}

function showDetails(row) {
  const box = $("details");
  if (!row) {
    box.innerHTML = '<div class="ph">Details of the selected row</div>';
    return;
  }
  const pairs = state.columns.map((name, index) => {
    const value = row[index];
    if (index === 0) return "";
    if (value === null || value === "") return "";
    return `<tr><td class="k">${escapeHtml(name)}</td><td>${escapeHtml(String(value))}</td></tr>`;
  }).join("");
  box.innerHTML = `<table>${pairs}</table>`;
}

/* ---------- tabs and panels ---------- */

function showTab(name) {
  document.querySelectorAll(".tab[data-tab]").forEach((tab) =>
    tab.classList.toggle("active", tab.dataset.tab === name));
  $("analysis-view").style.display = name === "analyses" ? "flex" : "none";
  $("cases-view").style.display = name === "cases" ? "flex" : "none";
  $("artifacts").style.display = name === "cases" && !state.openCase ? "none" : "flex";
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
  $("clear").addEventListener("click", () => {
    state.search = "";
    state.filters = [];
    state.sort = null;
    state.descending = false;
    $("search").value = "";
    loadRows(true);
  });

  $("head").addEventListener("click", (event) => {
    const th = event.target.closest("th[data-column]");
    if (!th || event.target.dataset.grip !== undefined) return;
    const index = Number(th.dataset.column);
    if (index === 0) return;
    if (state.sort === index - 1) state.descending = !state.descending;
    else { state.sort = index - 1; state.descending = false; }
    loadRows(true);
  });

  $("head").addEventListener("keydown", (event) => {
    const input = event.target.closest("input[data-filter]");
    if (!input) return;
    if (event.key !== "Enter") return;
    const column = Number(input.dataset.filter);
    const value = input.value.trim();
    state.filters = state.filters.filter((item) => item.column !== column);
    if (value) state.filters.push({ column, operator: "contains", value });
    loadRows(true);
  });

  $("head").addEventListener("input", (event) => {
    const input = event.target.closest("input[data-filter]");
    if (!input) return;
    const column = Number(input.dataset.filter);
    const value = input.value.trim();
    state.filters = state.filters.filter((item) => item.column !== column);
    if (value) state.filters.push({ column, operator: "contains", value });
  });

  $("body").addEventListener("click", (event) => {
    const tr = event.target.closest("tr[data-row]");
    if (!tr) return;
    $("body").querySelectorAll("tr.sel").forEach((node) => node.classList.remove("sel"));
    tr.classList.add("sel");
    const id = tr.dataset.row;
    const row = state.rows.find((item) => String(item[0]) === String(id));
    state.selected = row ? row[0] : null;
    showDetails(row);
  });

  $("first").addEventListener("click", () => { state.offset = 0; loadRows(false); });
  $("prev").addEventListener("click", () => {
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
