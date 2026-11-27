/* Kagarasu Host — grid client. Palette and density live in app.css. */
"use strict";

const PAGE = 200;
let filterTimer = null;
const $ = (id) => document.getElementById(id);

/* A case is served by its own container under /case/<32 hex>/. Every absolute path
   the client asks for goes through url(), which leaves it alone when there is no
   prefix: the one-container Host behaves exactly as before. */
const CASE_PREFIX = (window.location.pathname.match(/^\/case\/[0-9a-f]{32}/) || [""])[0];
function url(path) {
  return typeof path === "string" && path.startsWith("/") && !path.startsWith("//")
    ? CASE_PREFIX + path
    : path;
}

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
  expandAll: false,    // paginated outline of group headers and evidence rows
  interval: "",        // date interval applied to the grouped column
  expression: null,    // FilterGroup sent to the core
  path: [],            // drill-down values
  multiSort: [],       // [{column, descending, kind}] in application order
  sortType: "text",    // how a click on a header compares: text, number or timestamp
  hidden: new Set(),    // column indexes hidden by the analyst
  pinned: new Set(),    // column indexes frozen on the left
  pinnedRight: new Set(), // column indexes frozen on the right
  colOrder: [],         // the order the analyst gave the columns (header indexes; the row id stays first)
  selection: new Set(), // row ids selected on this page (Shift extends, Ctrl toggles)
  anchor: null,         // the row a Shift-click extends from
  summaries: [],        // [{column, operation, kind, footer}] shown beside each group
  totalSummaries: [],   // the same, over the whole filtered analysis (the totals line)
  footerMode: "hidden", // a group's summaries under its rows: hidden, expanded or always
  showTotal: true,      // show the totals line
  order: "",            // how the groups are ordered: count, value or a summary
  orderDesc: true,
  orderSummary: 0,
  payload: null,        // the last rows answer, kept for its summary labels
  timestamps: [],       // columns the case marks as dates
  filterOps: {},        // column -> the comparison its filter field uses
  styles: {},           // {row id: [indexes into ruleSet]} — the rules each row of the page matched
  ruleSet: [],          // the rules the page was evaluated against, as each paints
};

/* ---------- the recognised import profile ---------- */

async function applyDetectedProfile() {
  if (!state.openCase) { say("Open a case first", true); return; }
  const note = $("profile-note");
  note.textContent = "Reading the profile…";
  try {
    const found = await api(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/profile`);
    if (!found.matched) {
      note.textContent = "No import profile matches this analysis: its columns are read as a plain table.";
      return;
    }
    const applied = await apiPost(
      `/api/cases/${state.openCase.id}/analyses/${state.analysis}/profile`, {});
    note.textContent = `${applied.profile}: ${applied.timestamps.length} date column(s), `
      + `${applied.booleans.length} boolean(s)`
      + (applied.sort ? `, sorted by ${applied.sort}` : "")
      + `, ${applied.rules} colour rule(s) added`;
    await loadRows(true);
    say(`Profile applied: ${applied.profile}`);
  } catch (error) {
    note.textContent = error.message;
    say(error.message, true);
  }
}

/* ---------- analysing a disk ---------- */

let diskCapacity = null;
let diskSpaceFree = null;

function openDiskDialog() {
  if (!state.openCase) { say("Open a case first", true); return; }
  const caseId = state.openCase.id;
  const capacity = { loading: true };
  diskCapacity = capacity;
  diskSpaceFree = null;
  $("disk-source").value = "";
  $("disk-kind").value = "mounted";
  $("disk-modal").classList.add("show");
  $("disk-start").disabled = true;
  const current = () => diskCapacity === capacity && state.openCase?.id === caseId;
  loadImportCapacity("disk", capacity, current).then(() => {
    if (current()) $("disk-start").disabled = false;
  });
  refreshDiskSpace(0);
}

async function startDiskAnalysis() {
  if (diskCapacity?.loading) return;
  const source = $("disk-source").value.trim();
  if (!source) { say("Give the volume or image to analyse", true); return; }
  const kind = $("disk-kind").value;
  const options = { source, kind };
  if (diskCapacity?.available) options.parsing_threads = $("disk-threads").valueAsNumber;
  closeModals();
  say("Preparing the disk walk…");
  try {
    const started = await apiPost(`/api/cases/${state.openCase.id}/disk-jobs`, options);
    const outcome = await followImportJob(started.job);
    await openCase(state.openCase.id);
    if (outcome.status === "complete") {
      const disk = (outcome.result && outcome.result.disk) || {};
      say(`Disk analysed: ${disk.visited ?? 0} path(s) visited, ${disk.extracted ?? 0} artifact(s), `
        + `${(outcome.result && outcome.result.analyses_added) || 0} analysis(es) added`
        + ((disk.errors || []).length ? `, ${disk.errors.length} error(s)` : ""));
    } else {
      say(outcome.message || outcome.error || outcome.status, true);
    }
  } catch (error) {
    say(error.message, true);
  }
}

/* ---------- reading a file again ---------- */

const retryState = { files: [], readers: [] };

function reportFilter() {
  return $("report-filter").value || "unread";
}

function renderRetryList() {
  const filter = reportFilter();
  const files = retryState.files.filter((item) => {
    if (filter === "all") return true;
    if (filter === "aside") return item.ignored;
    if (filter === "imported") return item.status === "complete" && !item.ignored;
    if (filter === "duplicate") return item.status === "duplicate";
    if (item.ignored) return false;
    // A file only the generic reader read stays here: a reader the analyst names may read it better.
    const generic = (item.tools || []).length === 1 && ["Files", "Inventory"].includes(item.tools[0]);
    return generic || (item.status !== "complete" && item.status !== "companion");
  });
  const aside = retryState.files.filter((item) => item.ignored).length;
  $("report-summary").textContent = `${retryState.files.length} file(s) in the reports`
    + (aside ? `, ${aside} set aside` : "");
  $("retry-list").innerHTML = files.length
    ? files.map((item) => `<div class="retry-line${item.ignored ? " aside" : ""}">
        <input type="checkbox" data-retry-tick="${escapeHtml(item.path)}" title="Tick to read it with the reader chosen above">
        <span class="retry-path" title="${escapeHtml(item.path)}">${escapeHtml(item.path.split(/[\\/]/).pop())}
          <em>${escapeHtml(["Files", "Inventory"].includes((item.tools || []).join()) && item.status === "complete" ? "read generically" : item.status)}${item.ignored ? " · set aside" : ""}${item.reason ? " — " + escapeHtml(item.reason) : ""}</em></span>
        <span class="pin">
          <select data-retry-reader="${escapeHtml(item.path)}">${retryState.readers.map((reader) =>
            `<option value="${reader}">${reader}</option>`).join("")}</select>
          <button class="btn" data-retry-run="${escapeHtml(item.path)}">Read</button>
          <button class="btn" data-report-aside="${escapeHtml(item.path)}"
            data-collection="${escapeHtml(item.collection)}" data-ignored="${item.ignored ? "1" : ""}"
            >${item.ignored ? "Bring back" : "Set aside"}</button>
          <button class="btn" data-report-remove="${escapeHtml(item.path)}"
            data-collection="${escapeHtml(item.collection)}">Remove</button>
        </span></div>`).join("")
    : '<div class="emptygrid">Nothing matches this filter in the collection reports.</div>';
  $("retry-bulk-reader").innerHTML = retryState.readers.map((reader) => `<option value="${reader}">${reader}</option>`).join("");
  $("retry-list").querySelectorAll("[data-retry-run]").forEach((node) => {
    node.addEventListener("click", () => runRetry(node.dataset.retryRun,
      node.parentElement.querySelector("[data-retry-reader]").value));
  });
  $("retry-list").querySelectorAll("[data-report-aside]").forEach((node) => {
    node.addEventListener("click", () => setFileAside(node.dataset.collection,
      node.dataset.reportAside, !node.dataset.ignored));
  });
  $("retry-list").querySelectorAll("[data-report-remove]").forEach((node) => {
    node.addEventListener("click", async () => {
      const outcome = await removeCollectedFile(node.dataset.collection, node.dataset.reportRemove);
      if (outcome) say(outcome.text, Boolean(outcome.error));
    });
  });
}

async function loadReports() {
  const [unread, files] = await Promise.all([
    api(`/api/cases/${encodeURIComponent(state.openCase.id)}/unread`),
    api(`/api/cases/${encodeURIComponent(state.openCase.id)}/collection-files`),
  ]);
  retryState.files = (files.files || []).length ? files.files : (unread.files || []);
  retryState.readers = unread.readers || ["text"];
  renderRetryList();
}

async function setFileAside(collection, path, ignored) {
  try {
    await apiPost(`/api/cases/${state.openCase.id}/collection-files/aside`,
      { collection, path, ignored });
    await loadReports();
    say(ignored ? `Set aside: ${path.split(/[\\/]/).pop()}` : `Back in the counts: ${path.split(/[\\/]/).pop()}`);
  } catch (error) {
    say(error.message, true);
  }
}

async function removeCollectedFile(collection, path) {
  const name = path.split(/[\\/]/).pop();
  if (!window.confirm(`Delete ${name} from the evidence tree? Its hash stays in the report, and the `
    + `deletion is refused if the file changed since the collection.`)) return null;
  try {
    const payload = await apiPost(`/api/cases/${state.openCase.id}/collection-files/remove`,
      { collection, path });
    await loadReports();
    return { text: `Deleted: ${name} (${payload.status}, ${String(payload.sha256).slice(0, 12)}…)` };
  } catch (error) {
    return { text: error.message, error: true };
  }
}

async function openRetry() {
  if (!state.openCase) { say("Open a case first", true); return; }
  $("retry-list").innerHTML = '<div class="emptygrid">Reading the collection reports…</div>';
  $("retry-modal").classList.add("show");
  try {
    await loadReports();
  } catch (error) {
    $("retry-list").innerHTML = "";
    say(error.message, true);
  }
}

/* Tick all / none, and one reader for every ticked file, as the desktop's import history does. */
async function runRetryTicked() {
  const ticked = [...$("retry-list").querySelectorAll("input[data-retry-tick]:checked")].map((box) => box.dataset.retryTick);
  if (!ticked.length) { say("Tick at least one file first", true); return; }
  const reader = $("retry-bulk-reader").value;
  let done = 0;
  for (const path of ticked) {
    const item = retryState.files.find((entry) => entry.path === path);
    if (!item) continue;
    try {
      await apiPost(`/api/cases/${state.openCase.id}/collections/${encodeURIComponent(item.collection)}/retry`, { path, reader });
      done += 1;
    } catch (error) {
      say(`${path.split(/[\\/]/).pop()}: ${error.message}`, true);
    }
  }
  closeModals();
  await openCase(state.openCase.id);
  say(`${done} of ${ticked.length} file(s) read with ${reader}`);
}

async function runRetry(path, reader) {
  const item = retryState.files.find((entry) => entry.path === path);
  if (!item) return;
  say(`Reading ${item.path.split(/[\\/]/).pop()} with ${reader}…`);
  try {
    const payload = await apiPost(
      `/api/cases/${state.openCase.id}/collections/${encodeURIComponent(item.collection)}/retry`,
      { path: item.path, reader });
    closeModals();
    await openCase(state.openCase.id, payload.first_analysis);
    say(`Read with ${payload.reader}: ${payload.status}`
      + (payload.error ? ` — ${payload.error}` : "")
      + `, ${payload.analyses_added} analysis(es) added`);
  } catch (error) {
    say(error.message, true);
  }
}

/* ---------- display preferences ---------- */

/* Kept in the browser: they say how this analyst reads the data, not what the
   case contains. The desktop stores the same three choices in its profile. */
const copyPrefs = { headers: true, dateFormat: "source", pattern: "", rightCopy: false, details: "bottom", tree: "right", pins: [] };

function loadCopyPrefs() {
  try {
    const stored = JSON.parse(localStorage.getItem("fireblade.display") || "{}");
    if (typeof stored.headers === "boolean") copyPrefs.headers = stored.headers;
    if (["source", "iso", "iso7", "custom"].includes(stored.dateFormat)) copyPrefs.dateFormat = stored.dateFormat;
    if (typeof stored.pattern === "string") copyPrefs.pattern = stored.pattern.slice(0, 120);
    if (typeof stored.rightCopy === "boolean") copyPrefs.rightCopy = stored.rightCopy;
    if (["bottom", "right", "top"].includes(stored.details)) copyPrefs.details = stored.details;
    if (["left", "right"].includes(stored.tree)) copyPrefs.tree = stored.tree;
    if (Array.isArray(stored.pins)) copyPrefs.pins = stored.pins.filter((name) => typeof name === "string").slice(0, 32);
  } catch (_) { /* a first visit, or storage disabled */ }
}

function applyTreePosition() {
  const work = document.querySelector(".work");
  if (work) work.classList.toggle("tree-left", copyPrefs.tree === "left");
}

function applyDetailsPosition() {
  const view = $("analysis-view");
  if (!view) return;
  view.classList.toggle("details-right", copyPrefs.details === "right");
  view.classList.toggle("details-top", copyPrefs.details === "top");
}

function saveCopyPrefs() {
  try {
    localStorage.setItem("fireblade.display", JSON.stringify(copyPrefs));
  } catch (_) { /* nothing to do: the choice lives for this page only */ }
}

/* One timestamp, written the way the analyst asked for it. A value that is not a
   date is left exactly as the source wrote it. */
const DATE_TEXT = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}/;

function formatTimestamp(text, mode) {
  if (mode === "source" || text === null || text === undefined) return text;
  const raw = String(text).trim();
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:?\d{2})?$/);
  if (!match) return text;
  const [, year, month, day, hour, minute, second, fraction = "", zone] = match;
  const stamp = `${year}-${month}-${day}T${hour}:${minute}:${second}`;
  const tail = mode === "iso7" ? "." + (fraction + "0000000").slice(0, 7) : "";
  return `${stamp}${tail}${zone || "Z"}`;
}

/* ---------- messages ---------- */

/* The window's own log: every line the status bar showed, newest first. */
const messageLog = [];

function rememberMessage(text, error) {
  messageLog.unshift({ when: new Date().toISOString().replace("T", " ").slice(0, 19),
                       text: String(text || ""), error: Boolean(error) });
  if (messageLog.length > 500) messageLog.length = 500;
}

function openMessages() {
  $("messages-list").innerHTML = messageLog.length
    ? messageLog.map((item) => `<div class="message ${item.error ? "bad" : ""}">
        <span class="when">${escapeHtml(item.when)}</span>
        <span>${escapeHtml(item.text)}</span></div>`).join("")
    : '<div class="emptygrid">Nothing reported yet.</div>';
  $("messages-modal").classList.add("show");
}

/* ---------- commands ---------- */

/* Index the menu commands and the active workspace once per opening. Actions that
   have several entry points share a result, but retain their alternative search terms. */
function paletteEntries() {
  const entries = new Map();
  const views = { "cases-list": "cases", "show-timeline": "timeline", "show-imports": "imports", "show-ioc": "ioc" };
  function add(key, node, label, context, shortcut = "") {
    label = label.replace(/\s+/g, " ").trim();
    if (!label) return;
    const terms = [label, context, shortcut].join(" ").toLowerCase();
    const previous = entries.get(key);
    if (previous) {
      previous.terms += " " + terms;
    } else {
      entries.set(key, { node, label, context, shortcut, terms });
    }
  }
  for (const tab of workspaceTabs()) {
    add("view-" + tab.dataset.tab, tab, "Show " + tab.textContent, "Workspace");
  }
  for (const item of document.querySelectorAll(".menubar .menu [data-act]")) {
    if (item.hidden || item.matches(".disabled, [aria-disabled=true]") || item.dataset.act === "palette") continue;
    const key = item.dataset.act;
    const shortcut = item.querySelector(".key")?.textContent || "";
    const label = shortcut ? item.textContent.slice(0, -shortcut.length) : item.textContent;
    const menu = item.closest("[data-for]").dataset.for;
    const menuLabel = document.querySelector(`.menubar [data-menu="${menu}"]`).textContent.trim();
    add(views[key] ? "view-" + views[key] : key, item, label, menuLabel, shortcut);
  }
  for (const node of document.querySelectorAll(".app button[data-act], .app button[id]")) {
    if (node.disabled || node.closest(".modal, .menu, #doctabs") || !node.getClientRects().length) continue;
    const key = node.dataset.act || node.id;
    const tab = node.closest("[role=tabpanel]")?.getAttribute("aria-labelledby");
    add(views[key] ? "view-" + views[key] : key, node,
        node.getAttribute("aria-label") || node.textContent, tab ? $(tab).textContent : "Workspace");
  }
  return [...entries.values()];
}

const commandState = { entries: [], shown: [], active: -1 };

function selectPaletteItem(position) {
  const list = $("palette-list");
  list.querySelector('[aria-selected=true]')?.setAttribute("aria-selected", "false");
  commandState.active = position;
  const item = list.children[position];
  const input = $("palette-input");
  if (!item?.hasAttribute("data-palette")) {
    input.removeAttribute("aria-activedescendant");
    return;
  }
  item.setAttribute("aria-selected", "true");
  input.setAttribute("aria-activedescendant", item.id);
  item.scrollIntoView({ block: "nearest" });
}

function renderPalette() {
  const query = $("palette-input").value.trim().toLowerCase();
  const words = query.split(/\s+/);
  commandState.shown = commandState.entries.filter(entry => words.every(word => entry.terms.includes(word)));
  if (query) {
    const rank = entry => entry.label.toLowerCase().startsWith(query) ? 0
      : entry.label.toLowerCase().includes(query) || entry.shortcut.toLowerCase() === query ? 1 : 2;
    commandState.shown.sort((left, right) => rank(left) - rank(right));
  }
  $("palette-list").innerHTML = commandState.shown.length
    ? commandState.shown.map((item, index) => `<div class="palette-item" role="option" aria-selected="false"
        id="palette-item-${index}" data-palette="${index}"><span>${escapeHtml(item.label)}</span>
        <small>${escapeHtml(item.context)}</small>${item.shortcut ? `<kbd>${escapeHtml(item.shortcut)}</kbd>` : ""}</div>`).join("")
    : '<div class="emptygrid">No command matches.</div>';
  selectPaletteItem(commandState.shown.length ? 0 : -1);
}

function runPalette(position) {
  const entry = commandState.shown[position];
  if (!entry) return;
  closeModals();
  entry.node.click();
}

function openPalette() {
  commandState.entries = paletteEntries();
  $("palette-input").value = "";
  $("palette-modal").classList.add("show");
  renderPalette();
  $("palette-input").focus();
}

/* ---------- open analyses ---------- */

const analysesState = { order: [] };

async function openAnalysesDialog() {
  if (!state.openCase) { say("Open a case first", true); return; }
  const answers = await api(`/api/cases/${encodeURIComponent(state.openCase.id)}`);
  analysesState.order = (answers.analyses || []).map((item) => item.index);
  renderAnalysesDialog(answers.analyses || []);
  $("analyses-modal").classList.add("show");
}

function renderAnalysesDialog(entries) {
  $("analyses-list").innerHTML = entries.map((item) => `
    <div class="analysis-line" data-analysis-line="${item.index}">
      <span class="analysis-name${item.index === state.analysis ? " sel" : ""}"
        title="${escapeHtml(item.path || "")}">${escapeHtml(item.label)}</span>
      <span class="pin">
        <button class="btn" data-analysis-open="${item.index}">Open</button>
        <button class="btn" data-analysis-up="${item.index}">↑</button>
        <button class="btn" data-analysis-close="${item.index}">Close</button>
      </span></div>`).join("")
    || '<div class="emptygrid">No analysis in this case.</div>';
  $("analyses-list").querySelectorAll("[data-analysis-open]").forEach((node) => {
    node.addEventListener("click", async () => {
      closeModals();
      await selectReviewAnalysis(Number(node.dataset.analysisOpen));
      say(`Analysis ${state.analysis + 1} opened`);
    });
  });
  $("analyses-list").querySelectorAll("[data-analysis-up]").forEach((node) => {
    node.addEventListener("click", () => {
      const index = Number(node.dataset.analysisUp);
      const position = analysesState.order.indexOf(index);
      if (position > 0) {
        [analysesState.order[position - 1], analysesState.order[position]] =
          [analysesState.order[position], analysesState.order[position - 1]];
        const lines = [...$("analyses-list").querySelectorAll("[data-analysis-line]")];
        const line = lines[position];
        if (line && lines[position - 1]) line.parentElement.insertBefore(line, lines[position - 1]);
        analysesState.order = [...$("analyses-list").querySelectorAll("[data-analysis-line]")]
          .map((item) => Number(item.dataset.analysisLine));
        say("Order changed — save it to keep it");
      }
    });
  });
  $("analyses-list").querySelectorAll("[data-analysis-close]").forEach((node) => {
    node.addEventListener("click", async () => {
      const index = Number(node.dataset.analysisClose);
      try {
        // The service closes with DELETE on the analysis itself; there is no
        // "/close" route, and posting to one answered 404 while the tree kept
        // listing the tab.
        const response = await fetch(url(`/api/cases/${state.openCase.id}/analyses/${index}`),
                                     { method: "DELETE", headers: { Accept: "application/json" } });
        if (!response.ok) {
          const detail = await response.json().catch(() => ({}));
          throw new Error(detail.detail || response.statusText);
        }
        closeModals();
        await openCase(state.openCase.id);
        say("Analysis closed in the case");
      } catch (error) {
        say(error.message, true);
      }
    });
  });
}

async function saveAnalysesOrder() {
  const order = [...$("analyses-list").querySelectorAll("[data-analysis-line]")]
    .map((item) => Number(item.dataset.analysisLine));
  try {
    const payload = await apiPost(`/api/cases/${state.openCase.id}/analyses/reorder`, { order });
    await openCase(state.openCase.id);
    closeModals();
    say(`Order saved: ${payload.analyses} analysis(es)`);
  } catch (error) {
    say(error.message, true);
  }
}

/* ---------- case history ---------- */

async function openCaseHistory(identifier = state.openCase?.id) {
  if (!identifier) { say("Open a case first", true); return; }
  $("history-modal").dataset.caseId = identifier;
  $("history-list").innerHTML = '<div class="emptygrid">Reading the history…</div>';
  $("history-modal").classList.add("show");
  try {
    const payload = await api(`/api/cases/${encodeURIComponent(identifier)}/history`);
    if ($("history-modal").dataset.caseId !== identifier) return;
    $("history-list").innerHTML = (payload.entries || []).length
      ? payload.entries.map((item) => `<div class="analysis-line">
          <span class="analysis-name" title="${escapeHtml(payload.folder + "/" + item.name)}">${escapeHtml(item.when)} — ${escapeHtml(item.label || item.name)}</span>
          <span class="pin"><button class="btn" data-history-restore="${escapeHtml(item.name)}">Restore</button></span>
        </div>`).join("")
      : '<div class="emptygrid">No recorded state for this case yet.</div>';
    $("history-list").querySelectorAll("[data-history-restore]").forEach((node) => {
      node.addEventListener("click", () => restoreHistory(identifier, node.dataset.historyRestore));
    });
  } catch (error) {
    $("history-list").innerHTML = "";
    say(error.message, true);
  }
}

async function restoreHistory(identifier, name) {
  if (!window.confirm(`Restore the state ${name}? The present state is kept in the same folder first.`)) return;
  try {
    await flushLayouts();
    const payload = await apiPost(
      `/api/cases/${identifier}/history/${encodeURIComponent(name)}/restore`, {});
    closeModals();
    await openCase(identifier);
    say(`State restored: ${payload.analyses} analysis(es), updated ${payload.updated}`);
  } catch (error) {
    say(error.message, true);
  }
}

/* ---------- small helpers ---------- */

async function api(path) {
  const response = await fetch(url(path), { headers: { Accept: "application/json" } });
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

async function apiAbortable(path, signal) {
  const response = await fetch(url(path), { headers: { Accept: "application/json" }, signal });
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

function say(message, error, view = "") {
  if (view && !$(`tab-${view}`).classList.contains("active")) return;
  const node = $("status");
  node.dataset.view = view;
  node.textContent = message;
  node.title = message;
  node.classList.toggle("err", Boolean(error));
  // The Messages window is the same log, kept: nothing is reported nowhere.
  rememberMessage(message, error);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const FILTER_PREFIX = { eq: "= ", ne: "!= ", gt: "> ", ge: ">= ", lt: "< ", le: "<= ",
                       starts: "^ ", ends: "$ ", contains: "", empty: "empty", not_empty: "notempty" };

function filterPrefix(operator) {
  return FILTER_PREFIX[operator] === undefined ? "" : FILTER_PREFIX[operator];
}

/* The comparisons a column filter offers: the core's own, with the glyph the small button shows. */
const FILTER_GLYPHS = { contains: "≈", not_contains: "≉", eq: "=", ne: "≠", starts: "^", ends: "$",
  regex: ".*", gt: ">", ge: "≥", lt: "<", le: "≤", empty: "∅", not_empty: "●" };
const FILTER_OPERATORS = [
  ["contains", "≈", "contains"], ["not_contains", "≉", "does not contain"],
  ["eq", "=", "equals (exact)"], ["ne", "≠", "differs from (exact)"],
  ["starts", "^", "starts with"], ["ends", "$", "ends with"],
  ["regex", ".*", "matches the regular expression"],
  ["gt", ">", "number greater than"], ["ge", "≥", "number at least"],
  ["lt", "<", "number less than"], ["le", "≤", "number at most"],
  ["empty", "∅", "is empty"], ["not_empty", "●", "is not empty"],
];

function parseFilterValue(raw, fallback = "contains") {
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
  return { operator: fallback, value: text.trim() };
}

/* The small list under a filter's icon: choosing a comparison re-filters at once. */
function openFilterOperators(button) {
  const column = Number(button.dataset.fop);
  const box = $("filter-operators");
  box.innerHTML = FILTER_OPERATORS.map(([code, glyph, label]) =>
    `<div class="item" data-fop-choose="${code}"><span class="fglyph">${glyph}</span> ${escapeHtml(label)}</div>`).join("");
  const rect = button.getBoundingClientRect();
  box.hidden = false;
  placePopup(box, rect.left, rect.bottom);
  box.querySelectorAll("[data-fop-choose]").forEach((item) => {
    item.addEventListener("click", async () => {
      const operator = item.dataset.fopChoose;
      box.hidden = true;
      state.filterOps[column] = operator;
      const current = state.filters.find((entry) => entry.column === column);
      const value = current ? current.value : "";
      state.filters = state.filters.filter((entry) => entry.column !== column);
      if (operator === "empty" || operator === "not_empty" || value) {
        state.filters.push({ column, operator, value: operator === "empty" || operator === "not_empty" ? "" : value });
      }
      const label = (FILTER_OPERATORS.find(([code]) => code === operator) || [])[2];
      if (current || operator === "empty" || operator === "not_empty") {
        await loadRows(true);
      } else {
        button.textContent = FILTER_GLYPHS[operator];
        button.title = `Comparison: ${label}`;
      }
      say(`Column filter: ${label}`);
    });
  });
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

/* ---------- one bar for the long commands ---------- */

/* An import, a scan, a timeline, a detection, a report, a portable case: they all
   run as a job on the service, and the window shows the percentage the job knows.
   Without a count the bar slides — a fake number is worse than no number. */
const taskState = { job: null, title: "", seq: 0 };

function progressOpen(title) {
  // The progress window replaces whatever dialog asked for the work: an import
  // dialog left behind made the bar overlap the form it came from.
  closeModals();
  taskState.title = title || "Working…";
  $("import-progress-title").textContent = taskState.title;
  $("import-progress-message").textContent = "Starting…";
  $("import-progress-info").textContent = "Starting…";
  const bar = $("import-progress-bar");
  bar.style.width = "0%";
  bar.classList.add("indeterminate");
  $("import-progress-log").innerHTML = "";
  // The footnote belongs to what is running: an import keeps what it wrote, a
  // task is a command on the service and only Stop ends it.
  $("import-progress-note").textContent = title === "Importing"
    ? "Stopping an import keeps what was already written in the case: nothing is "
      + "deleted, the half-read file stays visible in the collection report."
    : "The command runs on the service: closing this window does not stop it — "
      + "Stop does, at the next checkpoint.";
  $("import-progress-stop").disabled = false;
  $("import-progress-modal").classList.add("show");
}

function progressPaint(payload) {
  const progress = payload.progress || {};
  const bar = $("import-progress-bar");
  const message = payload.message || payload.status || "";
  $("import-progress-message").textContent = message;
  const percent = typeof progress.percent === "number" ? progress.percent : null;
  if (percent === null) {
    bar.classList.add("indeterminate");
    bar.style.width = "35%";
    $("import-progress-info").textContent =
      [progress.total ? `${progress.done}/${progress.total}` : "",
       progress.rows ? `${progress.rows} row(s)` : "",
       progress.elapsed ? `${Math.round(progress.elapsed)} s` : ""].filter(Boolean).join(" · ")
      || "Working…";
  } else {
    bar.classList.remove("indeterminate");
    bar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
    $("import-progress-info").textContent =
      [ `${percent}%`,
        progress.total ? `${progress.done}/${progress.total}` : "",
        progress.rows ? `${progress.rows} row(s)` : "",
        progress.elapsed ? `${Math.round(progress.elapsed)} s` : "",
        progress.remaining ? `~${Math.round(progress.remaining)} s left` : "" ].filter(Boolean).join(" · ");
  }
  $("import-progress-log").innerHTML = (payload.log || []).slice(-8).reverse()
    .map((line) => `<div>${escapeHtml(line)}</div>`).join("");
}

async function runTask(kind, params, title, caseId = state.openCase?.id) {
  if (!caseId) { say("Open a case first", true); return null; }
  const token = ++taskState.seq;
  taskState.job = null;
  progressOpen(title);
  let started;
  try {
    started = await apiPost(`/api/cases/${caseId}/tasks`, { kind, params: params || {} });
  } catch (error) {
    if (token !== taskState.seq) return null;
    $("import-progress-modal").classList.remove("show");
    say(error.message, true);
    throw error;
  }
  if (token !== taskState.seq) return null;
  taskState.job = started.job;
  for (;;) {
    await new Promise((resolve) => setTimeout(resolve, 500));
    if (token !== taskState.seq) return null;      // another command took the window
    let payload;
    try { payload = await api(`/api/tasks/${started.job}`); }
    catch (error) {
      if (token !== taskState.seq) return null;
      // A job the service no longer knows cannot finish: stop asking.
      $("import-progress-message").textContent = error.message;
      $("import-progress-modal").classList.remove("show");
      taskState.job = null;
      say(error.message, true);
      return null;
    }
    if (token !== taskState.seq) return null;
    progressPaint(payload);
    if (payload.status === "done") {
      $("import-progress-modal").classList.remove("show");
      taskState.job = null;
      return payload.result;
    }
    if (payload.status === "failed") {
      $("import-progress-modal").classList.remove("show");
      taskState.job = null;
      say(payload.error || "The task failed", true);
      throw new Error(payload.error || "The task failed");
    }
    if (payload.status === "cancelled") {
      $("import-progress-modal").classList.remove("show");
      taskState.job = null;
      say(`${taskState.title}: stopped`);
      return null;
    }
  }
}

/* ---------- import preview ---------- */

const previewState = { items: [], capacity: null, folder: false };

function currentPreview(caseId, items) {
  return state.openCase?.id === caseId && previewState.items === items &&
    $("import-modal").classList.contains("show");
}


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

/* The action types are the core's, not the window's: the first version offered
   "containment"/"investigation", which the service refuses, so the New action
   button could never succeed with the type it opened on. */
async function fillActionTypes() {
  const select = $("action-type");
  if (!select || select.dataset.ready) return;
  let payload = {};
  try { payload = await api("/api/settings"); } catch (_) { payload = {}; }
  const types = Array.isArray(payload.action_types) ? payload.action_types : [];
  if (types.length) {
    const current = select.value;
    select.innerHTML = types.map((name) =>
      `<option value="${escapeHtml(name)}">${escapeHtml(String(name).replace(/_/g, " "))}</option>`).join("");
    if (types.includes(current)) select.value = current;
  }
  select.dataset.ready = "1";
}

const EXCEL_SUFFIX = /\.(xlsx|xlsm|xls)$/i;

/* The desktop's import asks which sheet; a workbook is a table, not an artefact. */
async function offerSheets(payload, caseId, items) {
  const row = $("preview-sheet-row");
  if (!payload || !EXCEL_SUFFIX.test(String(payload.name || ""))) {
    row.style.display = "none";
    $("preview-sheet").innerHTML = "";
    return;
  }
  try {
    const sheets = await apiPost(`/api/cases/${caseId}/sheets`, { path: payload.path });
    if (!currentPreview(caseId, items)) return;
    $("preview-sheet").innerHTML = (sheets.sheets || []).map((name) =>
      `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
    row.style.display = "";
    if (sheets.sheets && sheets.sheets.length > 1) {
      $("preview-note").textContent = `${sheets.sheets.length} sheet(s) in this workbook: the first is chosen.`;
    }
  } catch (error) {
    if (!currentPreview(caseId, items)) return;
    row.style.display = "none";
    say(error.message, true);
  }
}

function chosenSheet(payload) {
  if (!payload || !EXCEL_SUFFIX.test(String(payload.name || ""))) return "";
  return $("preview-sheet").value || "";
}

function openImportSourceChooser() {
  if (!state.openCase) { say("Open a case before importing", true); return; }
  const chooser = $("import-source-modal");
  chooser.classList.add("show");
}

function openImportDialog(folder = false) {
  if (!state.openCase) { say("Open a case before importing", true); return; }
  previewState.items = [];
  previewState.capacity = null;
  previewState.folder = folder;
  $("import-title").textContent = folder ? "Parse a folder" : "Import a file";
  $("preview-source-label").textContent = folder ? "Folder" : "Files";
  $("preview-choose").textContent = folder ? "Choose a folder…" : "Choose a file…";
  $("preview-input").value = "";
  $("preview-server").value = "";
  $("preview-delimiter").value = "";
  $("preview-encoding").value = "auto";
  $("preview-sheet-row").style.display = "none";
  $("preview-sheet").replaceChildren();
  fillCsvOptions();
  $("preview-note").textContent = folder
    ? "Choose a folder or enter its path on the server to preview its files."
    : "Choose a file or enter its path on the server to preview its columns and recognised profile.";
  $("preview-note").classList.remove("err");
  renderPreview();
  $("import-modal").classList.add("show");
  importSpaceRequests.import = null;
  $("import-space").hidden = true;
  if (folder) refreshImportSpace("import", { kind: "folder" });
}

const importSpaceRequests = { import: null, disk: null };

function storageSize(bytes) {
  const units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"];
  let unit = 0;
  while (bytes >= 1024 && unit < units.length - 1) {
    bytes /= 1024;
    unit += 1;
  }
  return `${bytes.toLocaleString(undefined, { maximumFractionDigits: 1 })} ${units[unit]}`;
}

function showImportSpace(id, space, checking = false, prompt = "") {
  const panel = $(`${id}-space`);
  panel.hidden = false;
  const warning = space?.status === "tight" || space?.status === "insufficient";
  panel.classList.toggle("space-warning", warning);
  if (checking) {
    panel.textContent = "Checking available case storage…";
    return;
  }
  const available = Number.isFinite(space?.free) ? storageSize(space.free) : "unavailable";
  const details = [`Available case storage: ${available}`];
  if (Number.isFinite(space?.recommended)) {
    details.push(`Recommended free space: ${storageSize(space.recommended)}`);
  }
  const basis = {
    upload: "Includes upload staging",
    mounted: "Based on recognized artifacts",
    "image-logical": "Based on the full logical image size",
    "image-segments": "Based on stored image segments and may underestimate",
    "physical-unknown": "A physical device cannot be estimated before scanning",
  }[space?.basis];
  if (basis) details.push(basis);
  if (warning) details.push(
    space.status === "insufficient" ? "Below the minimum free space" : "Below the recommendation");
  if (prompt) details.push(prompt);
  panel.textContent = details.join(" · ");
}

async function refreshImportSpace(id, fields, debounce = 0) {
  const caseId = state.openCase?.id;
  if (!caseId) return;
  const request = {};
  const modal = $(`${id}-modal`);
  importSpaceRequests[id] = request;
  const current = () => importSpaceRequests[id] === request &&
    state.openCase?.id === caseId && modal.classList.contains("show");
  showImportSpace(id, null, true);
  if (debounce) await new Promise(resolve => setTimeout(resolve, debounce));
  if (!current()) return;
  let estimate = null;
  try {
    estimate = await apiPost(`/api/cases/${caseId}/import-space`, fields, AbortSignal.timeout(8000));
  } catch (_) { /* the import's normal checks still apply */ }
  if (current()) {
    if (id === "disk" && Number.isFinite(estimate?.free)) diskSpaceFree = estimate.free;
    const prompt = !fields.source && fields.size === undefined
      ? "Choose a source to see a recommendation" : "";
    showImportSpace(id, estimate, false, prompt);
  }
}

function refreshDiskSpace(debounce = 350) {
  const kind = $("disk-kind").value;
  const source = $("disk-source").value.trim();
  refreshImportSpace("disk", source ? { kind, source } : { kind }, debounce);
}

function diskSourceEdited() {
  importSpaceRequests.disk = null;
  const prompt = $("disk-source").value.trim()
    ? "Press Enter or leave the path field to estimate the required space"
    : "Enter a source path to see a recommendation";
  showImportSpace("disk", { free: diskSpaceFree }, false, prompt);
}

function showFolderPreviewSpace(payload) {
  if (payload?.kind !== "folder") return;
  importSpaceRequests.import = null;
  if (payload.space) showImportSpace("import", payload.space);
  else refreshImportSpace("import", { kind: "folder", source: payload.path });
}

function showImportThreadCount(id) {
  const slider = $(`${id}-threads`);
  const count = `${slider.value} of ${slider.max} threads selected`;
  $(`${id}-thread-count`).textContent = count;
  slider.setAttribute("aria-valuetext", count);
}

async function loadImportCapacity(id, capacity, current) {
  const slider = $(`${id}-threads`);
  const info = $(`${id}-capacity-info`);
  slider.disabled = true;
  $(`${id}-thread-count`).textContent = "";
  info.textContent = "Checking the server’s import capacity…";
  try {
    const settings = await apiAbortable("/api/import-capacity", AbortSignal.timeout(8000));
    if (!current()) return;
    const { max_threads, recommended_threads, cpu_threads, memory_mb } = settings;
    if (!Number.isInteger(max_threads) || max_threads < 1 ||
        !Number.isInteger(recommended_threads) || recommended_threads < 1 ||
        recommended_threads > max_threads) throw new Error("Invalid import capacity");
    capacity.available = true;
    slider.max = max_threads;
    slider.value = recommended_threads;
    slider.disabled = max_threads === 1;
    const details = [`${recommended_threads} recommended`];
    if (cpu_threads > 0) details.push(`${cpu_threads} server CPU threads`);
    if (memory_mb > 0) details.push(`${memory_mb.toLocaleString()} MiB RAM`);
    info.textContent = details.join(" · ");
    showImportThreadCount(id);
  } catch (_) {
    if (current()) info.textContent = "Capacity unavailable. The server’s default will be used.";
  } finally {
    capacity.loading = false;
  }
}

function renderFolderCapacity() {
  const panel = $("import-capacity");
  const folder = previewState.folder ||
    previewState.items.some((item) => !item.error && item.payload?.kind === "folder");
  panel.hidden = !folder;
  if (!folder || previewState.capacity) return;

  const capacity = { loading: true };
  previewState.capacity = capacity;
  const caseId = state.openCase?.id;
  const current = () => previewState.capacity === capacity && state.openCase?.id === caseId;
  loadImportCapacity("import", capacity, current).then(() => {
    if (current()) renderPreview();
  });
}

/* A collection is a tree. The browser hands a directory over one file at a time, each
   with its relative path; the case rebuilds that tree under evidence/, then the folder is
   previewed and imported exactly as a folder on the server. */
async function importFolder(files) {
  if (!state.openCase) { say("Open a case before importing", true); return; }
  const identifier = state.openCase.id;
  $("import-modal").classList.add("show");
  previewState.items = [];
  renderPreview();
  const note = $("preview-note");
  note.classList.remove("err");
  const items = previewState.items;
  const current = () => currentPreview(identifier, items);
  const size = files.reduce((total, file) => total + file.size, 0);
  note.textContent = `Estimating storage for ${files.length} file(s)…`;
  await refreshImportSpace("import", { kind: "folder", size, files: files.length });
  if (!current()) return;
  let root = "";
  let batch = "new";
  let index = 0;
  for (const file of files) {
    if (!current()) return;
    index += 1;
    note.textContent = `Sending ${index}/${files.length} — ${file.webkitRelativePath || file.name}`;
    const body = new FormData();
    body.append("file", file);
    body.append("relative", file.webkitRelativePath || file.name);
    body.append("batch", batch);
    try {
      const response = await fetch(url(`/api/cases/${identifier}/upload-folder`), { method: "POST", body });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || response.statusText);
      if (!current()) return;
      root = payload.root;
      batch = payload.batch;
    } catch (error) {
      if (!current()) return;
      previewState.items = [{ name: file.name, error: error.message }];
      note.textContent = error.message;
      note.classList.add("err");
      renderPreview();
      return;
    }
  }
  note.textContent = `${files.length} file(s) sent — reading the folder…`;
  try {
    const payload = await apiPost(`/api/cases/${identifier}/preview`, { source: root, ...csvOptions() });
    if (!current()) return;
    previewState.items = [{ name: payload.name || root, payload }];
    showFolderPreviewSpace(payload);
    note.textContent = `${files.length} file(s) ready. Nothing has been read into the case yet.`;
  } catch (error) {
    if (!current()) return;
    previewState.items = [{ name: root, error: error.message }];
    note.textContent = error.message;
    note.classList.add("err");
  }
  renderPreview();
}

async function previewFiles(files) {
  if (!state.openCase) { say("Open a case before importing", true); return; }
  $("import-modal").classList.add("show");
  renderPreview();
  const identifier = state.openCase.id;
  const items = previewState.items;
  let done = 0;
  for (const file of files) {
    if (!currentPreview(identifier, items)) return;
    done += 1;
    $("preview-note").textContent = `Reading ${file.name} (${done}/${files.length})…`;
    const body = new FormData();
    body.append("file", file);
    const options = csvOptions();
    if (options.delimiter) body.append("delimiter", options.delimiter);
    if (options.encoding) body.append("encoding", options.encoding);
    try {
      const response = await fetch(url(`/api/cases/${identifier}/preview-upload`), { method: "POST", body });
      const payload = await response.json().catch(() => ({}));
      if (!currentPreview(identifier, items)) return;
      if (!response.ok) throw new Error(payload.detail || payload.error || response.statusText);
      items.push({ name: file.name, payload });
    } catch (error) {
      if (!currentPreview(identifier, items)) return;
      items.push({ name: file.name, error: error.message });
    }
  }
  $("preview-note").textContent = `${previewState.items.length} file(s) ready. Nothing has been read into the case yet.`;
  $("preview-note").classList.remove("err");
  await offerSheets(items.at(-1).payload, identifier, items);
  renderPreview();
}

async function previewServerPath() {
  const source = $("preview-server").value.trim();
  if (!source) { $("preview-note").textContent = "Give a path on the server first."; return; }
  const identifier = state.openCase.id;
  const items = previewState.items;
  try {
    const payload = await apiPost(`/api/cases/${identifier}/preview`, { source, ...csvOptions() });
    if (!currentPreview(identifier, items)) return;
    previewState.items.push({ name: payload.name, payload });
    showFolderPreviewSpace(payload);
    $("preview-note").textContent = "Preview ready. Nothing has been read into the case yet.";
    $("preview-note").classList.remove("err");
    await offerSheets(payload, identifier, items);
    renderPreview();
  } catch (error) {
    if (!currentPreview(identifier, items)) return;
    $("preview-note").textContent = error.message;
    $("preview-note").classList.add("err");
  }
}

function previewRoleLabel(role) {
  return { timestamp: "timestamp", boolean: "boolean", column: "text" }[role] || "text";
}

function renderPreview() {
  const box = $("preview-body");
  renderFolderCapacity();
  $("preview-import").disabled = previewState.capacity?.loading ||
    !previewState.items.some((item) => !item.error && item.payload?.path);
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
  const identifier = state.openCase?.id;
  const items = previewState.items;
  const options = csvOptions();
  for (const item of items) {
    if (!currentPreview(identifier, items)) return;
    const source = item.payload && item.payload.path;
    if (!source) continue;
    try {
      item.payload = await apiPost(`/api/cases/${identifier}/preview`, { source, ...options });
      delete item.error;
    } catch (error) {
      item.error = error.message;
    }
  }
  if (!currentPreview(identifier, items)) return;
  $("preview-note").textContent = `Re-read with the chosen options: ${previewState.items.length} file(s). Nothing has been read into the case yet.`;
  $("preview-note").classList.remove("err");
  renderPreview();
}

const importJobState = { job: null, stopped: false };

/* An import runs on the server, in the background: the window stays usable, the
   progress is visible, and the run can be stopped without losing what was read. */
async function startImportJob(source, layout, options, sheet, parsingThreads) {
  const body = new FormData();
  body.append("organization", layout);
  if (Array.isArray(source)) source.forEach((item) => body.append("sources", item));
  else body.append("source", source);
  if (options.delimiter) body.append("delimiter", options.delimiter);
  if (options.encoding) body.append("encoding", options.encoding);
  if (sheet) body.append("sheet", sheet);
  if (Number.isInteger(parsingThreads)) body.append("parsing_threads", String(parsingThreads));
  const response = await fetch(url(`/api/cases/${state.openCase.id}/import-jobs`), { method: "POST", body });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || response.statusText);
  return payload.job;
}

async function followImportJob(job) {
  importJobState.job = job;
  importJobState.stopped = false;
  progressOpen("Importing");
  taskState.job = null;               // an import job, not a task: the stop differs
  taskState.seq += 1;                 // no earlier poll may paint this window
  for (;;) {
    let payload = null;
    try {
      payload = await api(`/api/import-jobs/${job}`);
    } catch (error) {
      $("import-progress-message").textContent = error.message;
      return { status: "error", error: error.message };
    }
    // The collection counts files, bytes and records: the bar shows that number.
    progressPaint({ message: payload.message || payload.status,
                    progress: payload.progress || null, log: payload.log || [] });
    if (payload.status !== "running" && payload.status !== "cancelling") {
      importJobState.job = null;
      // The job is over: the progress window goes with it, whatever the outcome.
      $("import-progress-modal").classList.remove("show");
      return payload;
    }
    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
}

async function stopImportJob() {
  if (taskState.job) {
    $("import-progress-stop").disabled = true;
    $("import-progress-message").textContent = "Stopping at the next checkpoint…";
    try { await apiPost(`/api/tasks/${taskState.job}/cancel`, {}); }
    catch (error) { say(error.message, true); }
    return;
  }
  if (!importJobState.job) return;
  $("import-progress-stop").disabled = true;
  $("import-progress-message").textContent = "Stopping…";
  try {
    await apiPost(`/api/import-jobs/${importJobState.job}/cancel`, {});
  } catch (error) {
    say(error.message, true);
  }
}

/* What a stopped import leaves in the case, said the way the analyst needs it. */
function importStoppedMessage(files, kept) {
  const parts = [];
  if (files) parts.push(`${files} file(s) imported`);
  if (kept) parts.push(`${kept} analysis(es) written before the stop kept`);
  return "Import stopped — " + (parts.length ? parts.join(", ") : "nothing had been written yet");
}

async function confirmImport() {
  if (!previewState.items.length || previewState.capacity?.loading) return;
  const parsingThreads = previewState.capacity?.available ? $("import-threads").valueAsNumber : null;
  const layout = $("import-layout").value;
  const options = csvOptions();
  let imported = 0;
  let kept = 0;
  let stopped = false;
  let interruption = "";
  let notice = "";
  const failures = [];
  const finishedMessage = () => interruption || (stopped ? importStoppedMessage(imported, kept)
    : failures.length ? `${imported ? `Import finished with errors — ${imported} file(s) imported` : "Import failed"} — ${failures.join(" · ")}`
    : `${imported} file(s) imported${notice ? " — " + notice : ""}`);
  const failedMessage = (outcome) => outcome.error || outcome.result?.message
    || "No analysis could be read. See Imports for file diagnostics.";
  const ready = previewState.items.filter((item) => !item.error && item.payload && item.payload.path);
  // Files chosen together are one collection: the layout (per file, per artifact family, or one
  // grid for everything) is how that collection is laid out, so it is imported in one go. A
  // workbook is read sheet by sheet and keeps its own import.
  const together = layout !== "files" && ready.length > 1 &&
    ready.every((item) => item.payload.kind !== "folder" && !/\.(xlsx|xlsm|xls)$/i.test(item.payload.path));
  if (together) {
    say(`Importing ${ready.length} files…`);
    try {
      const job = await startImportJob(ready.map((item) => item.payload.path), layout, options, "");
      const outcome = await followImportJob(job);
      if (outcome.status === "complete" && outcome.result && outcome.result.analyses) {
        imported = outcome.result.read_files ?? ready.length;
        if (outcome.result.failed_files) failures.push(`${outcome.result.failed_files} file(s) could not be read; see Imports`);
        notice = outcome.result.notice || notice;
      }
      else if (outcome.status === "cancelled" || outcome.status === "interrupted") {
        stopped = true;
        kept = (outcome.result && outcome.result.analyses) || 0;
        if (outcome.status === "interrupted") interruption = outcome.message || "";
      } else failures.push(failedMessage(outcome));
    } catch (error) {
      say(error.message, true);
      return;
    }
    closeModals();
    await openCase(state.openCase.id);
    say(finishedMessage(), stopped || failures.length > 0);
    return;
  }
  for (const item of ready) {
    const source = item.payload && item.payload.path;
    if (!source) continue;
    say(`Importing ${item.name}…`);
    try {
      const job = await startImportJob(source, layout, options, chosenSheet(item.payload),
        item.payload.kind === "folder" ? parsingThreads : null);
      const outcome = await followImportJob(job);
      // A folder is one source holding several files: say how many were read, not "1".
      if (outcome.status === "complete" && outcome.result && outcome.result.analyses) {
        notice = outcome.result.notice || notice;
        imported += outcome.result.read_files ?? Math.max(1, Number((item.payload && item.payload.count) || 0));
        if (outcome.result.failed_files) failures.push(`${item.name}: ${outcome.result.failed_files} file(s) could not be read; see Imports`);
      } else if (outcome.status === "cancelled" || outcome.status === "interrupted") {
        stopped = true;
        kept = (outcome.result && outcome.result.analyses) || 0;
        if (outcome.status === "interrupted") interruption = outcome.message || "";
        break;
      } else {
        failures.push(`${item.name}: ${failedMessage(outcome)}`);
      }
    } catch (error) {
      say(`${item.name}: ${error.message}`, true);
      return;
    }
  }
  closeModals();
  await openCase(state.openCase.id);
  say(finishedMessage(), stopped || failures.length > 0);
}

/* ---------- import ---------- */

/* ---------- cases ---------- */

let caseDialogMode = "create";

function openCaseDialog(mode) {
  caseDialogMode = mode;
  const current = mode === "rename" ? targetCase() : null;
  if (mode === "rename" && !current) { say("Select or open a case first", true); return; }
  $("case-modal-title").textContent = mode === "rename" ? "Edit the case" : "New case";
  $("case-name").value = current ? current.name : "";
  $("case-description").value = current ? current.description || "" : "";
  $("case-environment").value = current ? current.environment || "unspecified" : "unspecified";
  $("case-status").value = current ? current.status || "open" : "open";
  $("case-status-row").style.display = mode === "rename" ? "flex" : "none";
  $("case-name").closest(".row").style.display = "flex";
  $("case-confirm").textContent = mode === "rename" ? "Save" : "Create";
  $("case-modal").dataset.target = current ? current.id : "";
  $("case-modal").classList.add("show");
}

async function saveCase() {
  // Save case: everything the case holds is written as it changes; what is still only on
  // screen is the layout of the analysis in view, so that is written now, and said.
  if (!state.openCase) { say("No case is open", true); return; }
  const identifier = state.openCase.id;
  const payload = state.openCase.analyses.length
    ? { analysis: state.analysis, display: currentDisplay() } : {};
  try {
    await flushLayouts();
    const saved = await apiPost(`/api/cases/${identifier}/save`, payload);
    const now = new Date();
    say(`Case saved at ${now.toLocaleTimeString([], { hour12: false })} — `
      + `${saved.recovery_points} recovery point(s) in History`);
  } catch (error) {
    say(error.message, true);
  }
}

async function confirmCaseDialog() {
  const name = $("case-name").value.trim();
  if (!name) { say("A name is required", true); return; }
  const target = $("case-modal").dataset.target;
  closeModals();
  try {
    if (caseDialogMode === "rename") {
      await apiPatch(`/api/cases/${target}`, {
        name, description: $("case-description").value,
        environment: $("case-environment").value, status: $("case-status").value });
      if (state.openCase && state.openCase.id === target) await openCase(target);
      say(`Case saved: ${name}`);
    } else {
      const created = await apiPost("/api/cases", { name, description: $("case-description").value,
                                                     environment: $("case-environment").value });
      await loadCases();
      // Like the desktop, a case that has just been created is the one being worked on.
      await openCase(created.id);
      say(`Case created: ${created.name}`);
      return;
    }
    await loadCases();
    showTab("cases");
  } catch (error) {
    say(error.message, true);
  }
}

/* Archive / Reactivate: the status of the case, as the desktop's Archive button sets it. */
async function toggleArchive() {
  const target = targetCase();
  if (!target) { say("Select or open a case first", true); return; }
  const status = target.status === "archived" ? "open" : "archived";
  try {
    await apiPatch(`/api/cases/${target.id}`, { status });
    await loadCases();
    say(status === "archived"
      ? `${target.name} is archived: it leaves the list unless “Include archived” is ticked`
      : `${target.name} is back in progress`);
  } catch (error) {
    say(error.message, true);
  }
}

/* Archive and free the space: the case is packed outside its folder, the folder is emptied, and
   the catalogue keeps the entry, which Restore brings back as a working case. */
async function freeCaseSpace() {
  const target = targetCase();
  if (!target) { say("Select or open a case first", true); return; }
  if (!window.confirm(`Pack “${target.name}” into an archive outside its folder and free the folder?\n`
    + "The case stays in the list; Restore brings it back.")) return;
  try {
    if (state.openCase && state.openCase.id === target.id) closeCase();
    const result = await apiPost(`/api/cases/${target.id}/archive`, {});
    await loadCases();
    say(`Archived: ${Math.round(result.removed_bytes / 1024)} kB freed, archive of ${Math.round(result.bytes / 1024)} kB at ${result.archive}`);
  } catch (error) {
    say(error.message, true);
  }
}

async function restoreCaseFromArchive() {
  const target = targetCase();
  if (!target || !target.storage_archive) { say("Select a case kept in an archive first", true); return; }
  try {
    const result = await apiPost(`/api/cases/${target.id}/restore`, {});
    await loadCases();
    state.selectedCase = result.id;
    renderCases();
    say(`Restored as “${result.name}”: ${result.analyses} analysis(es)`);
  } catch (error) {
    say(error.message, true);
  }
}

let destructionDraft = null;

async function openDestroyDialog() {
  const target = targetCase();
  if (!target) { say("Select a case to erase", true); return; }
  const caseId = target.id;
  const name = target.name;
  const dialog = $("destroy-modal");
  const draft = { caseId, name, attachments: [] };
  destructionDraft = draft;
  $("destroy-photos").value = "";
  $("destroy-photos").disabled = false;
  dialog.querySelector('[data-act="destroy-run"]').disabled = false;
  $("destroy-photo-count").textContent = "";
  $("destroy-certificate").value = "";
  $("destroy-reason").value = "";
  $("destroy-confirm").value = "";
  $("destroy-method").value = "dod3";
  $("destroy-target").textContent = `Case: ${name} — type that name to confirm.`;
  $("destroy-modal").classList.add("show");
  /* Where the certificate goes: the analyst decides, because a document nobody can find
     was not written. The service gives its own default; the driver's folder cannot move. */
  try {
    const settings = await api("/api/settings");
    if (destructionDraft !== draft) return;
    const field = $("destroy-certificate");
    field.value = settings.certificate_folder || "";
    field.readOnly = settings.certificate_choice === false;
    $("destroy-certificate-note").textContent = settings.certificate_choice === false
      ? "the driver writes it there, outside the case volume"
      : "an absolute path on the server, outside the case";
  } catch (_) { /* the service's default stands */ }
  /* A portable package or an archive of this case is the case: the dialog says
     how much of it lives outside the folder, before the analyst commits. */
  try {
    const response = await fetch(url(`/api/cases/${caseId}/residue`));
    if (!response.ok) return;
    const residue = await response.json();
    if (destructionDraft !== draft) return;
    const names = (residue.items || []).map(item => `${item.folder}/${item.name}`);
    const shown = names.slice(0, 3).join(", ") + (names.length > 3 ? ", …" : "");
    $("destroy-target").textContent = residue.files
      ? `Case: ${name} — type that name to confirm. ${residue.files} file(s) outside the folder (${shown}) are erased with it.`
      : `Case: ${name} — type that name to confirm. Nothing was left outside the folder.`;
  } catch (error) {
    /* The destruction still works without the inventory; the note stays plain. */
  }
}

/* The photos go with the case, not with the browser: they are stored beside it and
   fingerprinted, then embedded in the certificate by the core generator. */
async function uploadDestroyPhotos(files, draft) {
  const {caseId} = draft;
  const sources = [];
  for (const file of files) {
    const data = new FormData();
    data.append("file", file);
    const response = await fetch(url(`/api/cases/${caseId}/preview-upload`),
                                 { method: "POST", body: data });
    if (!response.ok) throw new Error(await response.text());
    const saved = await response.json();
    sources.push(saved.path || saved.source);
  }
  const response = await fetch(url(`/api/cases/${caseId}/destruction/attachments`), {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sources }),
  });
  if (!response.ok) throw new Error(await response.text());
  const kept = await response.json();
  if (destructionDraft !== draft) return;
  draft.attachments = kept.attachments || [];
  $("destroy-photo-count").textContent = `${kept.count} photo(s)`;
  say(`${kept.count} photo(s) for the certificate`);
}

async function runDestroy() {
  if (!destructionDraft) return;
  const {caseId, name, attachments} = destructionDraft;
  const confirmation = $("destroy-confirm").value.trim();
  const body = {
    method: $("destroy-method").value,
    operator: $("destroy-operator").value,
    witness: $("destroy-witness").value,
    reason: $("destroy-reason").value,
    confirmation,
    attachments,
    certificate_folder: $("destroy-certificate").value.trim(),
  };
  if (confirmation !== name) { say("The typed name does not match", true); return; }
  closeModals();
  say("Erasing the case — this takes a moment…");
  try {
    const response = await fetch(url(`/api/cases/${caseId}/destroy`),
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || response.statusText);
    if (state.openCase?.id === caseId) closeCase();
    await loadCases();
    showTab("cases");
    const outside = payload.outside ? `, ${payload.outside} outside the folder` : "";
    const word = payload.certificate_word ? ` · Word: ${payload.certificate_word}` : "";
    const error = payload.certificate_word_error ? ` · Word export failed: ${payload.certificate_word_error}` : "";
    const partial = payload.status === "partial";
    const outcome = partial ? "Erasure incomplete" : "Case erased";
    const files = payload.method === "quick"
      ? `${payload.deleted_files}/${payload.files} file(s) deleted without overwrite`
      : `${payload.verified_files ?? payload.files}/${payload.files} file(s) verified and removed`;
    say(`${outcome}: ${files}${outside}, certificate ${payload.certificate}${word}${error}`, partial || Boolean(error));
  } catch (error) {
    say(error.message, true);
  }
}

async function apiPut(path, body) {
  const response = await fetch(url(path), {
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
  const response = await fetch(url(path), { method: "DELETE", headers: { Accept: "application/json" } });
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

async function apiPost(path, body, signal) {
  const response = await fetch(url(path), { method: "POST", headers: { "Content-Type": "application/json" },
                                       body: JSON.stringify(body), signal });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || response.statusText);
  return payload;
}

async function apiPatch(path, body) {
  const response = await fetch(url(path), { method: "PATCH", headers: { "Content-Type": "application/json" },
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

const CASE_STATUS = { open: "In progress", closed: "Finished", archived: "Archived" };

/* Library actions follow the visible selection. Elsewhere the workspace belongs
   to the open case, even if a different library row was selected earlier. */
function targetCase() {
  return $("tab-cases").getAttribute("aria-selected") === "true"
    ? state.cases.find(item => item.id === state.selectedCase)
    : state.openCase;
}

function renderCases() {
  const term = ($("case-search").value || "").toLowerCase();
  const archived = $("case-archived").checked;
  const matches = state.cases.filter((item) => {
    if (!archived && item.status === "archived") return false;
    return !term || [item.name, item.description, item.environment, item.id, item.status]
      .join(" ").toLowerCase().includes(term);
  });
  if (!matches.some(item => item.id === state.selectedCase)) state.selectedCase = null;
  const body = $("cases-body");
  const when = (value) => (value ? String(value).replace("T", " ").slice(0, 19) : "—");
  body.innerHTML = matches.map((item) => `
    <tr data-case="${escapeHtml(item.id)}" tabindex="-1" class="${
      [state.openCase && state.openCase.id === item.id ? "sel" : "",
       state.selectedCase === item.id ? "selected" : ""].filter(Boolean).join(" ")}">
      <td title="${escapeHtml([item.name, item.description].filter(Boolean).join(" — "))}">${escapeHtml(item.name || "(unnamed)")}</td>
      <td>${escapeHtml(String(item.collection_count ?? (item.collections || []).length ?? 0))}</td>
      <td>${escapeHtml(CASE_STATUS[item.status] || item.status || "—")}${item.storage_archive ? " · kept in an archive" : ""}</td>
      <td>${escapeHtml(String(item.analysis_count ?? 0))}</td>
      <td>${escapeHtml(when(item.created))}</td>
      <td>${escapeHtml(when(item.updated))}</td>
      <td>${escapeHtml(item.environment && item.environment !== "unspecified" ? item.environment : "—")}</td>
    </tr>`).join("");
  $("case-count").textContent = `${matches.length} case(s) displayed`;
  renderCaseSelection();
  $("cases-empty").hidden = matches.length > 0;
  const empty = $("cases-empty");
  if (state.cases.length) {
    empty.textContent = "No case matches this filter.";
  } else {
    empty.innerHTML = "<h2>Your case library is empty</h2><p>Create a case or import a portable case to begin. Desktop cases appear here when their folders are added to the library.</p>";
  }
}

/* What depends on the selected case, without rebuilding the table: a click must not replace the
   rows, or the second click of a double click lands on a row that is no longer there. */
function renderCaseSelection() {
  const target = state.cases.find(item => item.id === state.selectedCase);
  const rows = $("cases-body").querySelectorAll("tr[data-case]");
  const focusable = target?.id || rows[0]?.dataset.case;
  rows.forEach((row) => {
    row.tabIndex = row.dataset.case === focusable ? 0 : -1;
    row.classList.toggle("selected", row.dataset.case === state.selectedCase);
    row.classList.toggle("sel", Boolean(state.openCase) && row.dataset.case === state.openCase.id);
  });
  for (const button of $("cases-view").querySelectorAll("button[data-case-selection]")) button.disabled = !target;
  $("case-footer-description").textContent = target
    ? (target.description || "No description for this case.")
    : "Select a case to read its description.";
  $("archive-case").textContent = target && target.status === "archived" ? "Reactivate" : "Archive";
  $("restore-case").hidden = !(target && target.storage_archive);
}

let caseOpenRevision = 0;

async function openCase(identifier, analysisIndex = null) {
  const revision = ++caseOpenRevision;
  try {
    const kept = state.cases.find((item) => item.id === identifier);
    if (kept && kept.storage_archive) {
      state.selectedCase = identifier;
      renderCaseSelection();
      say("This case is kept in an archive: press Restore… to bring it back", true);
      return;
    }
    const [detail, closed] = await Promise.all([
      api(`/api/cases/${identifier}`),
      api(`/api/cases/${identifier}/closed`).catch(() => ({})),
    ]);
    if (revision !== caseOpenRevision) return false;
    detail.closed = closed.closed || [];
    state.selectedCase = identifier;
    const changedCase = state.openCase?.id !== detail.id;
    if (changedCase) rememberReviewPlace();
    state.openCase = detail;
    if (changedCase) {
      resetTimeline();
      resetFindings();
      resetGraph();
      resetWorkspace();
      resetIoc();
      resetImports();
    } else {
      // A layout rebuild can assign different grid indices to the same case.
      resetScenario();
    }
    const analysis = detail.analyses.find(item => item.index === analysisIndex)
      || detail.analyses.find(item => item.active && item.session_view) || detail.analyses[0];
    state.analysis = analysis?.index ?? 0;
    resetAnalysisQuery();
    if (analysis?.session_view) applyViewFields(analysis.session_view);
    const layout = $("import-layout");
    if ([...layout.options].some((option) => option.value === detail.layout)) {
      layout.value = detail.layout;
    }
    $("casecombo-label").textContent = detail.name || "Case";
    showTab("analyses");
    renderTree();
    renderCases();
    if (!detail.analyses.length) {
      clearGrid("Import the first evidence", [["Import evidence…", "import-evidence"]],
        "Choose a file, a collection folder or a disk image for this case.");
      say("Case opened");
      return true;
    }
    return await loadRows(true);
  } catch (error) {
    if (revision === caseOpenRevision) say(error.message, true);
  }
}

function closeCase() {
  rememberReviewPlace();
  caseOpenRevision += 1;
  state.openCase = null;
  syncArtifacts();
  resetTimeline();
  resetFindings();
  resetGraph();
  resetWorkspace();
  resetIoc();
  resetImports();
  resetAnalysisQuery();
  state.columns = [];
  state.rows = [];
  state.total = 0;
  $("casecombo-label").textContent = "No case open";
  $("tree").innerHTML = '<div class="empty">No case open.</div>';
  $("pane-tabs").innerHTML = "";
  showCaseStart();
  renderCases();
  say("Case closed");
}

/* ---------- column layout ---------- */

const pendingLayouts = new Map();
let layoutWrite = Promise.resolve();

function currentDisplay() {
  return {
    widths: { ...state.widths }, hidden: [...state.hidden], pinned: [...state.pinned],
    pinned_right: [...state.pinnedRight], order: [...state.colOrder],
  };
}

async function loadLayout(signal) {
  if (!state.openCase) return;
  const { id } = state.openCase;
  const analysis = state.analysis;
  try {
    const path = `/api/cases/${id}/analyses/${analysis}/display`;
    const stored = pendingLayouts.get(path)?.display
      || (signal ? await apiAbortable(path, signal) : await api(path));
    if (signal?.aborted || state.openCase?.id !== id || state.analysis !== analysis) return;
    const payload = familyDisplay(stored);
    state.widths = payload.widths || {};
    state.hidden = new Set(payload.hidden || []);
    state.pinned = new Set(payload.pinned || []);
    state.pinnedRight = new Set(payload.pinned_right || []);
    state.colOrder = Array.isArray(payload.order) ? payload.order : [];
    if (!state.pinned.size && !state.pinnedRight.size && copyPrefs.pins.length) {
      // Preferences > default pinning: the named columns start frozen on the left of an analysis nobody has laid out.
      state.columns.slice(1).forEach((name, index) => { if (copyPrefs.pins.includes(name)) state.pinned.add(index); });
    }
    renderGrid();
  } catch (_) { /* no saved layout is not an error */ }
}

function flushLayouts() {
  for (const [path, entry] of pendingLayouts) {
    if (!entry.timer) continue;
    clearTimeout(entry.timer);
    queueLayoutWrite(path, entry);
  }
  return layoutWrite;
}

function queueLayoutWrite(path, entry) {
  entry.timer = null;
  layoutWrite = layoutWrite.then(async () => {
    try { await apiPost(path, entry.display); }
    catch (error) { say(error.message, true); }
    finally { if (pendingLayouts.get(path) === entry) pendingLayouts.delete(path); }
  });
}

function saveLayoutSoon() {
  if (!state.openCase) return;
  const path = `/api/cases/${state.openCase.id}/analyses/${state.analysis}/display`;
  const display = { ...currentDisplay(), configured: true };
  clearTimeout(pendingLayouts.get(path)?.timer);
  const entry = { display };
  pendingLayouts.set(path, entry);
  entry.timer = setTimeout(() => queueLayoutWrite(path, entry), 300);
}

/* A layout leaves as a file and comes back the same way: the desktop exports and
   imports its own, and the shape here is the one the display endpoint stores. */
function layoutDocument() {
  return {
    format: "fireblade-layout",
    version: 1,
    analysis: state.openCase ? state.openCase.analyses[state.analysis]?.label || "" : "",
    widths: state.widths,
    hidden: [...state.hidden],
    pinned: [...state.pinned],
    pinned_right: [...state.pinnedRight],
    sort: state.sort,
    descending: state.descending,
    multiSort: state.multiSort,
    sortType: state.sortType,
    groups: state.groups,
  };
}

function exportLayout() {
  if (!state.openCase) { say("Open a case first", true); return; }
  const document_ = layoutDocument();
  const blob = new Blob([JSON.stringify(document_, null, 1)], { type: "application/json" });
  const link = window.document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${(document_.analysis || "layout").replace(/[^\w.-]+/g, "-")}.layout.json`;
  link.click();
  URL.revokeObjectURL(link.href);
  say(`Layout exported: ${Object.keys(document_.widths || {}).length} column width(s)`);
}

async function importLayout(file) {
  if (!state.openCase) { say("Open a case first", true); return; }
  let document_ = null;
  try {
    document_ = JSON.parse(await file.text());
  } catch (error) {
    say(`This file is not a layout: ${error.message}`, true);
    return;
  }
  if (!document_ || document_.format !== "fireblade-layout") {
    say("This file is not a Kagarasu layout", true);
    return;
  }
  state.widths = document_.widths || {};
  state.hidden = new Set(document_.hidden || []);
  state.pinned = new Set(document_.pinned || []);
  state.pinnedRight = new Set(document_.pinned_right || []);
  state.colOrder = Array.isArray(document_.order) ? document_.order.filter(Number.isInteger) : [];
  if (Number.isInteger(document_.sort)) state.sort = document_.sort;
  state.descending = Boolean(document_.descending);
  state.multiSort = Array.isArray(document_.multiSort) ? document_.multiSort : [];
  state.sortType = ["text", "number", "timestamp"].includes(document_.sortType) ? document_.sortType : "text";
  if (Array.isArray(document_.groups)) state.groups = document_.groups;
  state.path = [];
  await saveDisplayNow();
  await loadRows(true);
  say(`Layout imported: ${Object.keys(state.widths).length} column width(s), `
    + `${state.hidden.size} hidden, ${state.pinned.size + state.pinnedRight.size} pinned`);
}

async function saveDisplayNow() {
  const path = `/api/cases/${state.openCase.id}/analyses/${state.analysis}/display`;
  const display = currentDisplay();
  try {
    await flushLayouts();
    await apiPost(path, display);
  } catch (_) { /* a layout that cannot be saved must not interrupt the work */ }
}

/* ---------- advanced filter ---------- */

/* The operators of the engine, named as the desktop names them. */
const EXPR_OPERATORS = [
  ["contains", "Contains"], ["not_contains", "Does not contain"], ["eq", "Equals (exact)"],
  ["ne", "Differs (exact)"], ["starts", "Starts with"], ["ends", "Ends with"],
  ["regex", "Regular expression (RE2)"], ["empty", "Empty / NULL"], ["not_empty", "Not empty"],
  ["gt", "Number >"], ["ge", "Number ≥"], ["lt", "Number <"], ["le", "Number ≤"],
  ["after", "Date ≥ (ISO)"], ["before", "Date ≤ (ISO)"], ["date_before", "Date < (ISO)"],
  ["date_after", "Date > (ISO)"], ["date_eq", "Date equals"], ["date_ne", "Date differs"],
  ["text_gt", "Text >"], ["text_ge", "Text ≥"], ["text_lt", "Text <"], ["text_le", "Text ≤"],
  ["expression", "Named expression"],
];
const EXPR_MAX_DEPTH = 3;

function exprConditionNode(condition = {}) {
  const row = document.createElement("div");
  row.className = "row expr-row";
  row.dataset.kind = "condition";
  row.innerHTML = `<select data-expr-col aria-label="Condition column">${state.columns.slice(1).map((name, index) =>
      `<option value="${index}" ${index === (condition.column ?? 0) ? "selected" : ""}>${escapeHtml(name)}</option>`).join("")}</select>
    <select data-expr-op aria-label="Condition operator">${EXPR_OPERATORS.map(([code, label]) =>
      `<option value="${code}" ${code === (condition.operator || "contains") ? "selected" : ""}>${label}</option>`).join("")}</select>
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
    <select data-expr-logic aria-label="${depth === 0 ? "Filter" : "Group"} logic">
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

/* "Text expression…": Contains([Column], 'text') And [ID] >= 10, parsed by the desktop's own parser. */
async function openTextExpression() {
  if (!state.columns.length) { say("Open an analysis first", true); return; }
  const text = await ask({
    title: "Filter expression",
    label: "Expression",
    note: "Syntax: Contains([Column], 'text') And [ID] >= 10. Functions: Contains, Iif, InRange, DateTimeFromParts, AddTimeSpan, GetYear…" });
  if (text === null || !text.trim()) return;
  try {
    const payload = await apiPost(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/filter-text`, { text });
    state.filters = [];
    state.expression = payload.expression;
    await loadRows(true);
    say(`Text expression applied: ${state.total} row(s)`);
  } catch (error) {
    say(error.message, true);
  }
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

/* ---------- the window's own commands, the ones a menu carries ---------- */

/* A row height is a reading comfort, not case data: it lives in the browser. */
function toggleDetails() {
  const box = $("details");
  box.style.display = box.style.display === "none" ? "" : "none";
}

/* The desktop's RowHeightDialog: two behaviours and three heights, each one kept as
   a browser preference and never written into the case. */
function openRowHeight() {
  const prefs = rowHeightPrefs();
  $("rowheight-wrap").checked = Boolean(prefs.wrap);
  $("rowheight-fit").checked = Boolean(prefs.fit);
  $("rowheight-rows").value = prefs.rows;
  $("rowheight-groups").value = prefs.groups;
  $("rowheight-headers").value = prefs.headers;
  $("rowheight-modal").classList.add("show");
}

function rowHeightPrefs() {
  let stored = {};
  try { stored = JSON.parse(localStorage.getItem("fireblade.rowHeightBox") || "{}"); } catch (_) { stored = {}; }
  return { rows: stored.rows || 20, groups: stored.groups || 22, headers: stored.headers || 22,
           wrap: Boolean(stored.wrap), fit: Boolean(stored.fit) };
}

function applyRowHeightPrefs() {
  const clamp = (value, low, high, fallback) =>
    Math.max(low, Math.min(high, Number(value) || fallback));
  const prefs = {
    rows: clamp($("rowheight-rows").value, 14, 120, 20),
    groups: clamp($("rowheight-groups").value, 14, 120, 22),
    headers: clamp($("rowheight-headers").value, 14, 120, 22),
    wrap: $("rowheight-wrap").checked,
    fit: $("rowheight-fit").checked,
  };
  localStorage.setItem("fireblade.rowHeightBox", JSON.stringify(prefs));
  document.documentElement.style.setProperty("--row-height", `${prefs.rows}px`);
  document.documentElement.style.setProperty("--group-height", `${prefs.groups}px`);
  document.documentElement.style.setProperty("--head-height", `${prefs.headers}px`);
  document.documentElement.style.setProperty("--wrap", prefs.wrap || prefs.fit ? "normal" : "nowrap");
  document.documentElement.classList.toggle("rowclip", prefs.wrap && !prefs.fit);
  renderGrid();
  closeModals();
  say(`Row height: ${prefs.rows} px${prefs.wrap || prefs.fit ? " — text wrapped" : ""}`);
}

function applyStoredRowHeight() {
  const prefs = rowHeightPrefs();
  document.documentElement.style.setProperty("--row-height", `${prefs.rows}px`);
  document.documentElement.style.setProperty("--group-height", `${prefs.groups}px`);
  document.documentElement.style.setProperty("--head-height", `${prefs.headers}px`);
  document.documentElement.style.setProperty("--wrap", prefs.wrap || prefs.fit ? "normal" : "nowrap");
  document.documentElement.classList.toggle("rowclip", prefs.wrap && !prefs.fit);
}

/* Query indexes only have meaning for the analysis that supplied the columns. */
function resetAnalysisQuery() {
  rowsRequest?.abort();
  clearTimeout(filterTimer);
  showDetails(null);
  state.columnContext = null;
  resetGridReview();
  $("gridbody").scrollLeft = 0;
  state.filters = []; state.search = ""; state.expression = null; state.bookmarksOnly = false;
  state.sort = null; state.descending = false; state.multiSort = []; state.groups = []; state.path = [];
  state.expandAll = false;
  state.interval = ""; state.summaries = []; state.totalSummaries = []; state.order = ""; state.filterOps = {};
  state.sortType = "text"; state.footerMode = "hidden"; state.showTotal = true;
  state.offset = 0; state.selected = null;
  $("search").value = "";
  $("bookmarks-only").classList.remove("active");
  renderGroupBar();
}

/* "Reset the view": the desktop's reset: no filter, no sort, no group, nothing hidden or pinned. */
function resetView() {
  if (!state.columns.length) { say("Open an analysis first", true); return; }
  resetAnalysisQuery();
  state.hidden = new Set(); state.pinned = new Set(); state.pinnedRight = new Set(); state.widths = {}; state.colOrder = [];
  saveLayoutSoon();
  loadRows(true);
  say("View reset");
}

function resetWidths() {
  state.widths = {};
  saveLayoutSoon();
  renderGrid();
  say("Column widths reset to their defaults");
}

async function openAddFilter() {
  if (!state.columns.length) { say("Open an analysis first", true); return; }
  const names = state.columns.map((name, index) => `${index - 1}=${name}`).join(", ");
  const answer = await ask({ title: "Add a filter", label: "Column, by name or by index",
                             note: names, placeholder: "Score" });
  if (!answer) return;
  const text = answer.trim();
  let column = state.columns.findIndex((name) => name.toLowerCase() === text.toLowerCase()) - 1;
  if (column < -1 && /^\d+$/.test(text)) column = Number(text);
  if (column < 0 || column >= state.columns.length - 1) {
    say(`No column is named ${text}`, true);
    return;
  }
  const value = await ask({ title: "Add a filter",
                            label: `Value to find in ${state.columns[column + 1]}` });
  if (value === null) return;
  state.filters = state.filters.filter((item) => item.column !== column);
  if (value.trim()) state.filters.push({ column, operator: "contains", value: value.trim() });
  state.offset = 0;
  loadRows(true);
  say(`Filter added on ${state.columns[column + 1]}`);
}

/* Everything that narrows the grid, as the desktop's own command clears it: the search, the column
   filters, the advanced filter (the date windows live there) and the bookmarks-only switch. */
function clearEveryFilter() {
  state.filters = [];
  state.search = "";
  state.expression = null;
  state.bookmarksOnly = false;
  state.offset = 0;
  $("search").value = "";
  $("bookmarks-only").classList.remove("active");
  $("expr-root").innerHTML = "";
  $("expr-root").appendChild(exprGroupNode({ logic: "and", children: [] }, 0));
  loadRows(true);
  say("Filters cleared");
}

/* ---- the IOC hunt leaves as two files, as the desktop offers ---- */

function downloadCsv(name, lines) {
  const csv = lines.map((line) => line.map((cell) =>
    '"' + String(cell === null || cell === undefined ? "" : cell).replace(/"/g, '""') + '"').join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = name;
  link.click();
  URL.revokeObjectURL(link.href);
}

function exportIocMatches() { exportHunt(false); }
function exportIocSummary() { exportHunt(true); }

/* ---- the imports table's own commands, one file at a time ---- */

function selectedCollectedFile() {
  for (const collection of importState.collections) {
    for (const file of collection.files || []) {
      if (file.path === importState.selected) return { file, collection };
    }
  }
  return null;
}

async function viewCollectedFile() {
  const chosen = selectedCollectedFile();
  if (!chosen) { say("Select a file first", true); return; }
  try {
    const payload = await apiPost(`/api/cases/${state.openCase.id}/preview`,
      { source: chosen.file.path });
    $("preview-body").innerHTML = `<div class="preview-card"><div class="preview-head">
        <b>${escapeHtml(payload.name)}</b><span class="preview-neutral">${escapeHtml(payload.kind)}</span></div>
      <div class="note">${escapeHtml(payload.note || "")}</div>
      <table class="preview-table preview-sample"><thead><tr>${(payload.columns || []).map((column) =>
        `<th>${escapeHtml(column.name)}</th>`).join("")}</tr></thead><tbody>${(payload.rows || []).map((row) =>
        `<tr>${row.map((cell) => `<td>${escapeHtml(cell === null ? "" : String(cell))}</td>`).join("")}</tr>`).join("")}
      </tbody></table></div>`;
    previewState.items = [];
    $("preview-import").disabled = true;
    // The same window shows a preview: saying "Import a file" over a read-only
    // view of an already collected file was the wrong title.
    $("import-title").textContent = "Preview of a collected file";
    $("import-modal").classList.add("show");
  } catch (error) {
    say(error.message, true);
  }
}

async function copyUnprocessedFiles() {
  const paths = [];
  for (const collection of importState.collections) {
    for (const file of collection.files || []) {
      if (["unread", "partial"].includes(importReadState(file))) paths.push(file.path);
    }
  }
  if (!paths.length) { say("Every collected file was read", true); return; }
  try {
    await navigator.clipboard.writeText(paths.join("\n"));
    say(`${paths.length} unprocessed path(s) copied`);
  } catch (error) {
    say(error.message, true);
  }
}

function exportCollectedList() {
  const lines = [["collection", "status", "path", "readers", "reason", "sha256", "parked"]];
  for (const collection of importState.collections) {
    for (const file of collection.files || []) {
      lines.push([collection.name, file.status, file.path, (file.tools || []).join(" "),
                  file.reason || "", file.sha256 || "", file.ignored ? "yes" : ""]);
    }
  }
  const csv = lines.map((line) => line.map((cell) =>
    '"' + String(cell === null || cell === undefined ? "" : cell).replace(/"/g, '""') + '"').join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "imports.csv";
  link.click();
  URL.revokeObjectURL(link.href);
  say(`${lines.length - 1} file(s) exported`);
}

async function parkCollectedFile() {
  const chosen = selectedCollectedFile();
  if (!chosen) { say("Select a file first", true); return; }
  await setFileAside(chosen.collection.name || chosen.file.collection,
                     chosen.file.path, !chosen.file.ignored);
  await loadImports();
}

async function deleteCollectedFile() {
  const chosen = selectedCollectedFile();
  if (!chosen) { say("Select a file first", true); return; }
  const outcome = await removeCollectedFile(chosen.collection.name || chosen.file.collection, chosen.file.path);
  importState.selected = null;
  await loadImports();
  // said after the table is read again: loading the report writes its own summary to the status
  if (outcome) say(outcome.text, Boolean(outcome.error));
}

/* The bookmarks and their notes, as a CSV the analyst can keep outside the case. */
async function exportAnnotations() {
  if (!state.openCase) { say("Open a case first", true); return; }
  // The desktop's own export: the bookmarked rows of the filtered view, with their notes in columns.
  if (await exportRows({ annotations: true })) say("Bookmarks and notes exported");
}

/* The desktop's export: the view as the grid shows it (filters, sorts and their types, groups),
   the visible columns only, the rows or the counts per group. */
function exportRows(options) {
  if (!state.openCase) { say("No case open", true); return; }
  const params = query();
  params.delete("offset"); params.delete("limit"); params.delete("path");
  if (options.annotations) {
    params.delete("group");
  } else {
    const shown = visibleColumns().map((item) => item.index - 1).filter((index) => index >= 0);
    if (!shown.length) { say("Choose at least one visible column to export", true); return; }
    if (shown.length !== state.columns.length - 1 || shown.some((column, index) => column !== index)) {
      for (const index of shown) params.append("column", String(index));
    }
  }
  if (options.grouped) {
    if (!state.groups.length) { say("Group the analysis first: the counts are per group", true); return; }
    params.set("grouped", "true");
  }
  if (options.annotations) params.set("annotations", "true");
  if (options.format) params.set("format", options.format);
  const path = `/api/cases/${state.openCase.id}/analyses/${state.analysis}/export`;
  if (params.toString().length <= 6000) return downloadFrom(`${path}?${params.toString()}`);
  const body = {};
  const repeated = new Set(["column", "filter", "group", "sortkey", "summary", "total"]);
  for (const [key, value] of params) {
    if (repeated.has(key)) { (body[key] ||= []).push(value); }
    else body[key] = value;
  }
  return downloadFrom(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

/* A file the server writes: fetched, so a refusal is said in the status line instead of replacing the page. */
async function downloadFrom(path, options) {
  try {
    const response = await fetch(url(path), options);
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || response.statusText);
    }
    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const named = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = named ? decodeURIComponent(named[1]) : "fireblade-export";
    link.click();
    URL.revokeObjectURL(link.href);
    return true;
  } catch (error) {
    say(error.message, true);
    return false;
  }
}

/* A portable case comes in as a file the browser sends: the server verifies every
   byte before it becomes a case, so a truncated archive never half-opens. */
async function uploadPortableCase(event) {
  const file = event.target.files && event.target.files[0];
  event.target.value = "";
  if (!file) return;
  const body = new FormData();
  body.append("file", file);
  say(`Importing ${file.name}…`);
  try {
    const response = await fetch(url("/api/cases/import-package"), { method: "POST", body });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || response.statusText);
    await loadCases();
    say(`Portable case imported: ${payload.name} (${payload.analyses} analysis(es))`);
  } catch (error) {
    say(error.message, true);
  }
}

/* The session file is the desktop's own: the same tabs, the same views, read by the
   same core module on either side. */
async function saveSession() {
  if (!state.openCase) { say("Open a case first", true); return; }
  try {
    const saved = await apiPost(`/api/cases/${state.openCase.id}/session`, {
      analysis: state.analysis, view: currentViewFields(), display: currentDisplay(),
    });
    const bytes = Uint8Array.from(atob(saved.content), (char) => char.charCodeAt(0));
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([bytes], { type: "application/octet-stream" }));
    link.download = saved.name;
    link.click();
    URL.revokeObjectURL(link.href);
    say(`Session saved: ${saved.documents} analysis(es), ${saved.bytes} bytes`);
  } catch (error) { say(`The session was not saved: ${error.message}`, true); }
}

function openSessionFile() {
  if (!state.openCase) { say("Open a case first", true); return; }
  $("session-file").value = "";
  $("session-file").click();
}

async function readSessionFile(file) {
  const caseId = state.openCase?.id;
  const revision = caseOpenRevision;
  if (!caseId) return;
  try {
    if (file.size > 64 * 1024 * 1024) throw new Error("The session file exceeds 64 MiB.");
    const bytes = new Uint8Array(await file.arrayBuffer());
    const chunks = [];
    for (let i = 0; i < bytes.length; i += 32768) {
      chunks.push(String.fromCharCode(...bytes.subarray(i, i + 32768)));
    }
    await flushLayouts();
    if (caseOpenRevision !== revision) return;
    const result = await apiPost(`/api/cases/${caseId}/session/open`, { content: btoa(chunks.join("")) });
    if (caseOpenRevision !== revision || !(await openCase(caseId, result.active))) return;
    const missing = result.missing.length ? ` — ${result.missing.length} missing from this case` : "";
    say(`Session opened: ${result.added} analysis(es)${missing}`);
  } catch (error) {
    if (state.openCase?.id === caseId) say(`The session was not opened: ${error.message}`, true);
  }
}

async function exportPortable(caseId = state.openCase?.id) {
  if (!caseId) { say("Open a case first", true); return; }
  try {
    const payload = await runTask("package", { include_sources: true }, "Portable case", caseId);
    if (!payload) return;
    const refreshed = (payload.repaired || []).length
      ? ` — ${payload.repaired.length} analysis fingerprint(s) refreshed from their file`
      : "";
    say(`Portable case: ${payload.name} — ${(payload.bytes / 1048576).toFixed(1)} MB${refreshed}`);
    window.location.href = url(payload.url);
  } catch (error) {
    say(error.message, true);
  }
}

/* A note on the first cell of each selected row: added to what is there, or
   replacing it — the desktop offers both, and they are not the same promise. */
async function noteSelection(mode) {
  const ids = selectedIds();
  if (!ids.length) { say("Select a row first", true); return; }
  const limited = ids.slice(0, 200);
  const path = activeAnalysisPath();
  const bookmarks = state.bookmarks;
  const text = await ask({
    title: mode === "replace" ? "Replace the selection's notes" : "Add a note to the selection",
    label: mode === "replace"
      ? "Note that replaces the one on the selected rows"
      : "Note to add to the selected rows",
    note: `${limited.length} row(s)` });
  if (text === null || !text.trim()) return;
  // As in the desktop, the note of a selection is the note of its bookmarks: the rows are
  // marked, a note is added after the existing one or replaces it, and the export of the
  // bookmarks and notes carries it. A plain mark's own text is not a note.
  const plain = (note) => (note === "bookmarked" ? "" : note || "");
  const edits = limited.map(id => {
    const before = plain(bookmarks.get(String(id)));
    return [id, mode === "append" && before ? `${before}\n${text.trim()}` : text.trim()];
  });
  await saveBookmarkEdits(path, edits, "noted");
}

async function bookmarkNote() {
  const ids = selectedIds();
  if (!ids.length) { say("Select a row first", true); return; }
  const path = activeAnalysisPath();
  const text = await ask({ title: "Bookmark / note",
                           label: "Note for this bookmark",
                           note: "Empty keeps a plain mark." });
  if (text === null) return;
  await markSelection(text.trim() || "bookmarked", ids, path);
}

/* Next and previous analysis, the way the desktop walks its tabs. */
function stepAnalysis(direction) {
  const analyses = (state.openCase && state.openCase.analyses) || [];
  if (analyses.length < 2) { say("This case holds a single analysis", true); return; }
  const here = analyses.findIndex((item) => item.index === state.analysis);
  const next = analyses[(here + direction + analyses.length) % analyses.length];
  selectReviewAnalysis(next.index);
  say(`Analysis: ${next.label}`);
}

function collapseEveryGroup() {
  if (!state.groups.length) { say("This analysis is not grouped", true); return; }
  state.expandAll = false;
  state.path = [];
  loadRows(true);
}

async function expandEveryGroup() {
  if (!state.groups.length) { say("This analysis is not grouped", true); return; }
  state.expandAll = true;
  state.path = [];
  if (await loadRows(true)) say("All group levels expanded in a paginated view");
}

/* Every analysis is a file the case holds: its source, its hash, its rows. */
async function openIntegrity() {
  if (!state.openCase || state.analysis === null) { say("Open an analysis first", true); return; }
  const entry = state.openCase.analyses.find((item) => item.index === state.analysis);
  const box = $("integrity-body");
  box.innerHTML = '<div class="emptygrid">Reading the collection reports…</div>';
  $("integrity-modal").classList.add("show");
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/collection-files`);
    const source = String((entry && entry.source) || "");
    const match = (payload.files || []).find((item) => item.path === source)
      || (payload.files || []).find((item) => source.endsWith("/" + item.name));
    const { parser, working_path: working } = entry?.source_info || {};
    const lines = [
      ["Analysis", entry ? entry.label : ""],
      ["Source", source || "(nothing recorded)"],
      ["Reader", parser || ""],
      ...(parser === "RECmd" ? [["Registry batch", "Kroll_Batch.reb — reads keys and values from the selected registry hive."]] : []),
      ...(working ? [["Parser output", working]] : []),
      ["SHA-256", match ? match.sha256 || "(not recorded)" : "(this source is not in a collection report)"],
      ["Status", match ? match.status : "unknown"],
      ["Reason", match ? match.reason || "" : ""],
      ["Rows read", entry ? String((entry.source_info && entry.source_info.rows) ?? entry.rows ?? "") : ""],
      ["Bytes", entry && entry.source_info && entry.source_info.size
        ? String(entry.source_info.size) : ""],
      ["Analysis file", entry ? entry.path : ""],
    ];
    box.innerHTML = `<table class="integrity-table">${lines.map(([name, value]) =>
      `<tr><th>${escapeHtml(name)}</th><td>${escapeHtml(value)}</td></tr>`).join("")}</table>`;
  } catch (error) {
    box.innerHTML = `<div class="emptygrid">${escapeHtml(error.message)}</div>`;
  }
}

function showHelp(name) {
  const pages = {
    guide: ["Kagarasu Host — user guide", [
      "A case holds the evidence of one investigation: imported files, the analyses the",
      "readers produced, the indicators, the machines and the actions taken.",
      "Case > Import evidence… reads a file or a folder; the same dialog shows the columns",
      "and the recognised profile before anything is written.",
      "The grid filters, sorts, groups and colours rows; the rules live with the analysis,",
      "the colour book is shared by every analysis.",
      "The timeline correlates every dated row of the case; Reports produces the technical",
      "report and the document the client receives.",
    ]],
    coverage: ["Collection coverage and diagnostics", [
      "Analysis > Collection coverage reopens every analysis and checks what can be attested:",
      "hashes, empty columns, dates without a timezone, rows declared against rows read.",
      "Imports > Import report lists every collected file with its status and its reason,",
      "and lets a file be read again, set aside, or removed after its hash is verified.",
    ]],
    ioc: ["IOC hunting", [
      "The IOC tab scans one analysis or the whole case for indicators, domains and hashes.",
      "Sub-domains are followed, the grid's filters are respected, and the format of the",
      "list can be declared instead of guessed.",
    ]],
    timeline: ["Timeline, backups and reports", [
      "The timeline draws every dated row of the case, by source, and exports a verified CSV",
      "with its receipt. Drag on the chart to select a duration, shift-drag to pan.",
      "History and recovery keeps a state of the case each time it changes and restores it.",
      "Reports writes the technical report and the client report, as HTML or PDF.",
    ]],
    autosave: ["Case autosave", [
      "There is no autosave toggle here, because there is nothing to toggle: every change",
      "to a case — an import, a bookmark, a rule, a note, a tab closed — is written at once,",
      "and History and recovery keeps the state it replaced.",
    ]],
    tutorial: ["Kagarasu Host — full tutorial", [
      "1. A case. Case > New case… creates one; History and recovery keeps a state of it",
      "each time it changes. Case > Import evidence… reads a file or a folder.",
      "2. The grid. Click a header to sort, type in the filter row to filter, right-click a",
      "cell to copy, filter, group, pin or colour. View > Columns…, Row height…, Reset the",
      "widths, Group by… and Group summaries… shape what you read.",
      "3. Colour rules. Analysis > Colour rules… writes rules with this analysis; the second",
      "tab of the same dialog edits the book shared by every analysis of the instance.",
      "Visual formats (bar, two- and three-colour scale, icons) are set in the same rule.",
      "4. Detection. Hayabusa findings runs the local detection, its rules are edited beside the",
      "pack, and its findings open as a table, a clock, a heat map or a chain.",
      "5. Timeline. Every dated row of the case, by source: drag to select a duration,",
      "shift-drag to pan, wheel to zoom, export a verified CSV with its receipt.",
      "6. Investigation. Actions and tracking holds the machines, the accounts, the",
      "indicators and the actions; the attack graph draws them.",
      "7. Reports. Reports… writes the technical report and the document the client",
      "receives, as HTML or as PDF.",
      "8. Verification. Imports > Import report lists every collected file with its reason;",
      "Analysis > Collection coverage reopens every analysis and says what it cannot attest.",
    ]],
    legend: ["Supertimeline legend", [
      "These rules apply with recognised timeline profiles. A colour alone does not prove",
      "the nature of an event: it says which family the row belongs to.",
      "Execution / registry — processes launched, services installed, keys written.",
      "File / folder opening — files read, written, renamed or deleted.",
      "Suppression — logs cleared, services stopped, accounts disabled.",
      "Navigation Web — browsing, downloads, user agents.",
      "Event logs — the records the machine wrote itself, by channel and event id.",
      "Each colour in the chart is one source: the analysis the rows come from. The legend",
      "above the chart names them and their counts, and a click on a chip hides that source.",
    ]],
    workspace: ["Workspace", [
      "The window holds one case at a time. The artifacts tree on the right lists the",
      "analyses of that case; the tabs above describe it: Analyses, Imports, Cases,",
      "Timeline and correlations, IOC hunting, Hayabusa, Actions and tracking, Attack graph,",
      "EVTX detection.",
      "View > Preferences sets the theme, the language and the reading comfort;",
      "View > Columns, Row height and Reset the widths shape the grid, and the layout",
      "travels as a file through Analysis > Export the layout….",
    ]],
    licenses: ["Licences", [
      "Kagarasu Host — internal edition. Python, FastAPI, DuckDB, openpyxl and PySide6",
      "(the desktop edition only) are distributed under their own licences; the case data",
      "never leaves the machine that serves it.",
    ]],
  };
  const page = pages[name] || pages.guide;
  $("help-title").textContent = page[0];
  $("help-body").innerHTML = page[1].map((line) => `<p>${escapeHtml(line)}</p>`).join("");
  $("help-modal").classList.add("show");
}

/* ---------- the findings, and their three maps ---------- */

const LEVEL_COLOURS = { critical: "#8b1c1c", high: "#c05621", medium: "#b7791f",
                        low: "#2b6cb0", informational: "#4a5568" };
const findingState = { groups: [], incidents: [], source: "", analysis: null, shown: [], loaded: false };

function resetFindings() {
  Object.assign(findingState, { groups: [], incidents: [], source: "", analysis: null, shown: [], loaded: false });
  $("finding-search").value = "";
  $("hayabusa-summary").textContent = "No detection run yet.";
  renderFindingView();
}

function findingLevelColour(level) {
  return LEVEL_COLOURS[String(level || "informational").toLowerCase()] || LEVEL_COLOURS.informational;
}

function findingGroupKey(group) {
  const field = $("finding-group").value;
  const value = group[field] === undefined ? group.title : group[field];
  return value === null || value === "" ? "(none)" : String(value);
}

async function loadFindings(force) {
  if (!state.openCase) return;
  if (findingState.loaded && !force) { renderFindingView(); return; }
  const { id } = state.openCase;
  try {
    const payload = await api(`/api/cases/${encodeURIComponent(id)}/findings`);
    if (state.openCase?.id !== id) return;
    findingState.groups = payload.groups || [];
    findingState.incidents = payload.incidents || [];
    findingState.source = payload.source || "";
    findingState.analysis = payload.analysis === undefined ? null : payload.analysis;
    findingState.loaded = true;
    if (payload.error) say(payload.error, true);
    renderFindingView();
  } catch (error) {
    if (state.openCase?.id !== id) return;
    findingState.groups = [];
    say(error.message, true);
    renderFindingView();
  }
}

/* The event logs the detection will read: the analyses that came from an .evtx file. */
function eventLogCount() {
  const analyses = (state.openCase && state.openCase.analyses) || [];
  return analyses.filter((item) => /\.evtx/i.test(String(item.source || "")) || /\.evtx/i.test(String(item.label || ""))).length;
}

function renderFindingView() {
  const view = $("finding-view").value;
  $("finding-table").style.display = view === "table" ? "" : "none";
  $("finding-map-box").style.display = view === "table" ? "none" : "";
  const hits = findingState.groups.reduce((sum, group) => sum + (group.count || 0), 0);
  $("finding-summary").textContent = findingState.groups.length
    ? `${findingState.groups.length} finding(s), ${hits} alert(s)`
      + (findingState.source ? ` — ${findingState.source}` : "")
    : `${eventLogCount()} event log(s) in the case — no finding yet: run the detection, or open the alert analysis.`;
  // Findings kept in the case from an earlier run are not "no detection yet".
  const ran = $("hayabusa-summary");
  if (findingState.groups.length && ran.textContent.startsWith("No detection run yet")) {
    ran.textContent = `${hits} alert(s) kept from the last detection: run it again to refresh them.`;
  }
  if (view === "table") { renderFindingSeverity(shownFindings()); renderFindingTable(); return; }
  drawFindingMap(view);
}

/* The findings on screen: the filter reads the rule, the host and the event ids,
   the way the desktop's own field does. */
const FINDING_RANK = { critical: 4, high: 3, medium: 2, low: 1, informational: 0 };

function shownFindings() {
  const term = ($("finding-search").value || "").trim().toLowerCase();
  const floor = $("finding-level").value;
  const base = floor
    ? findingState.groups.filter((group) => (FINDING_RANK[String(group.level || "").toLowerCase()] ?? 0) >= FINDING_RANK[floor])
    : findingState.groups;
  if (!term) return base;
  return base.filter((group) =>
    [group.title, group.host, (group.event_ids || []).join(" "), group.tactics,
     group.techniques, group.level].join(" ").toLowerCase().includes(term));
}

function renderFindingTable() {
  const groups = shownFindings();
  findingState.shown = groups;
  $("hayabusa-rows").innerHTML = groups.length
    ? groups.map((group, position) => `<tr>
        <td>${escapeHtml(group.start || "(undated)")}</td>
        <td>${escapeHtml(group.level || "")}</td>
        <td title="${escapeHtml(group.details || "")}">${escapeHtml(group.title || "")}</td>
        <td>${escapeHtml(group.host || "")}</td>
        <td>${group.count || 0}</td>
        <td>${escapeHtml((group.event_ids || []).join(", "))}</td>
        <td title="${escapeHtml(group.tactics || "")}">${escapeHtml(group.techniques || "")}</td>
        <td><button class="btn" data-finding="${position}" data-want="show"
            title="Open the alerts of this rule on this host in the grid">Show</button>
          <button class="btn" data-finding="${position}" data-want="mark"
            title="Mark every alert of this finding">Mark</button></td>
      </tr>`).join("")
    : '<tr><td colspan="8" class="cellnull">No finding matches this filter.</td></tr>';
  renderFindingSeverity(groups);
}

/* The severity bar the desktop keeps under its table: one count per level, and how
   many findings the filter left on screen. */
function renderFindingSeverity(groups) {
  const levels = ["critical", "high", "medium", "low", "informational"];
  const counts = new Map(levels.map((level) => [level, 0]));
  for (const group of groups) {
    const level = String(group.level || "informational").toLowerCase();
    counts.set(level, (counts.get(level) || 0) + 1);
  }
  $("finding-counts").innerHTML = levels.map((level) =>
    `<span class="chip" style="opacity:${counts.get(level) ? 1 : 0.45}">`
    + `<span class="swatch" style="background:${findingLevelColour(level)}"></span>`
    + `${level} ${counts.get(level) || 0}</span>`).join("")
    + `<span class="note" style="margin-left:auto">showing ${groups.length} of ${findingState.groups.length}</span>`;
}

function findingCanvas() {
  const canvas = $("finding-map");
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 900;
  const height = canvas.clientHeight || 380;
  canvas.width = Math.round(width * ratio);
  canvas.height = Math.round(height * ratio);
  const context = canvas.getContext("2d");
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, width, height);
  context.font = "11px Segoe UI, Arial, sans-serif";
  context.textBaseline = "middle";
  return { context, width, height };
}

function findingDates(group) {
  const start = group.start ? new Date(group.start) : null;
  const end = group.end ? new Date(group.end) : null;
  const ok = start && !Number.isNaN(start.getTime());
  return { start: ok ? start : null, end: end && !Number.isNaN(end.getTime()) ? end : null };
}

function drawFindingMap(view) {
  const { context, width, height } = findingCanvas();
  findingState.visible = shownFindings();
  if (!findingState.visible.length) {
    context.fillStyle = "#666";
    context.fillText("No finding to draw: run the detection first.", 16, 24);
    return;
  }
  if (view === "clock") drawClockMap(context, width, height);
  if (view === "heat") drawHeatMap(context, width, height);
  if (view === "chain") drawChainMap(context, width, height);
}

function drawFindingLegend(context, width, keys) {
  let x = 16;
  context.fillStyle = "#333";
  context.fillText("Levels:", x, 18);
  x += 52;
  for (const level of ["critical", "high", "medium", "low", "informational"]) {
    context.fillStyle = LEVEL_COLOURS[level];
    context.fillRect(x, 12, 10, 10);
    context.fillStyle = "#333";
    context.fillText(level, x + 14, 18);
    x += 20 + context.measureText(level).width;
  }
  if (keys && keys.length) {
    context.fillStyle = "#666";
    const note = `grouped by ${$("finding-group").value} · ${keys.length} value(s)`;
    context.fillText(note, Math.max(x + 24, width - context.measureText(note).width - 16), 18);
  }
}

function drawClockMap(context, width, height) {
  const centreX = width / 2;
  const centreY = height / 2 + 10;
  const keys = [...new Set((findingState.visible || findingState.groups).map(findingGroupKey))].sort();
  const outer = Math.min(width, height) / 2 - 46;
  const ringStep = keys.length > 1 ? Math.min(26, (outer - 90) / keys.length) : 0;
  drawFindingLegend(context, width, keys);
  // The dial: hours radiate from midnight at the top, clockwise.
  context.strokeStyle = "#dfe4ea";
  for (let hour = 0; hour < 24; hour += 1) {
    const angle = (hour / 24) * Math.PI * 2 - Math.PI / 2;
    context.beginPath();
    context.moveTo(centreX + Math.cos(angle) * (outer - 8), centreY + Math.sin(angle) * (outer - 8));
    context.lineTo(centreX + Math.cos(angle) * outer, centreY + Math.sin(angle) * outer);
    context.stroke();
    if (hour % 3 === 0) {
      context.fillStyle = "#666";
      const labelX = centreX + Math.cos(angle) * (outer + 12);
      const labelY = centreY + Math.sin(angle) * (outer + 12);
      context.fillText(`${String(hour).padStart(2, "0")}h`, labelX - 10, labelY);
    }
  }
  context.strokeStyle = "#c3cad4";
  context.beginPath();
  context.arc(centreX, centreY, outer - 8, 0, Math.PI * 2);
  context.stroke();
  let undated = 0;
  for (const group of (findingState.visible || findingState.groups)) {
    const { start } = findingDates(group);
    if (!start) { undated += 1; continue; }
    const key = findingGroupKey(group);
    const ring = keys.indexOf(key);
    const hour = start.getUTCHours() + start.getUTCMinutes() / 60;
    const angle = (hour / 24) * Math.PI * 2 - Math.PI / 2;
    const radius = Math.max(34, outer - 24 - ring * ringStep);
    const size = Math.max(3.5, Math.min(14, 3.5 + Math.log2(1 + (group.count || 1)) * 2.6));
    context.beginPath();
    context.fillStyle = findingLevelColour(group.level);
    context.globalAlpha = 0.85;
    context.arc(centreX + Math.cos(angle) * radius, centreY + Math.sin(angle) * radius,
                size, 0, Math.PI * 2);
    context.fill();
    context.globalAlpha = 1;
  }
  context.fillStyle = "#333";
  context.fillText(`${findingState.groups.length} group(s) on the dial`
    + (undated ? ` · ${undated} without a date` : ""), 16, height - 14);
}

function drawHeatMap(context, width, height) {
  const keys = [...new Set((findingState.visible || findingState.groups).map(findingGroupKey))].sort();
  const rows = Math.max(1, keys.length);
  const left = 16;
  const labelWidth = Math.min(220, Math.max(90, width * 0.22));
  const top = 58;   // below the legend, which owns the first line
  const gridWidth = width - left - labelWidth - 20;
  const gridHeight = height - top - 40;
  const columnWidth = gridWidth / 24;
  const rowHeight = gridHeight / rows;
  drawFindingLegend(context, width, keys);
  const cells = new Map();
  let peak = 1;
  for (const group of (findingState.visible || findingState.groups)) {
    const { start } = findingDates(group);
    if (!start) continue;
    const cell = `${findingGroupKey(group)}|${start.getUTCHours()}`;
    const value = (cells.get(cell) || 0) + (group.count || 1);
    cells.set(cell, value);
    peak = Math.max(peak, value);
  }
  context.fillStyle = "#666";
  for (let hour = 0; hour < 24; hour += 3) {
    context.fillText(`${String(hour).padStart(2, "0")}h`, left + labelWidth + hour * columnWidth, top - 10);
  }
  keys.forEach((key, row) => {
    const y = top + row * rowHeight;
    context.fillStyle = "#333";
    const text = key.length > 24 ? `${key.slice(0, 24)}…` : key;
    context.fillText(text, left, y + rowHeight / 2);
    for (let hour = 0; hour < 24; hour += 1) {
      const value = cells.get(`${key}|${hour}`) || 0;
      const x = left + labelWidth + hour * columnWidth;
      context.fillStyle = value ? "#174b73" : "#eef1f4";
      context.globalAlpha = value ? 0.25 + 0.75 * (value / peak) : 1;
      context.fillRect(x + 1, y + 2, columnWidth - 2, Math.max(4, rowHeight - 4));
      context.globalAlpha = 1;
      if (value && rowHeight > 22) {
        context.fillStyle = "#fff";
        context.fillText(String(value), x + columnWidth / 2 - 3, y + rowHeight / 2);
      }
    }
  });
  const undated = findingState.groups.filter((group) => !findingDates(group).start).length;
  context.fillStyle = "#333";
  context.fillText(`${findingState.groups.length} group(s), hour by hour`
    + (undated ? ` · ${undated} without a date (not placed)` : ""), 16, height - 12);
}

function drawChainMap(context, width, height) {
  const dated = (findingState.visible || findingState.groups).filter((group) => findingDates(group).start);
  drawFindingLegend(context, width, [...new Set(findingState.groups.map(findingGroupKey))]);
  if (!dated.length) {
    context.fillStyle = "#666";
    context.fillText("No dated finding: the chain needs a timestamp.", 16, 60);
    return;
  }
  const stamps = dated.flatMap((group) => {
    const { start, end } = findingDates(group);
    return [start.getTime(), (end || start).getTime()];
  });
  const low = Math.min(...stamps);
  const high = Math.max(...stamps);
  const span = Math.max(1, high - low);
  const left = 40;
  const right = width - 24;
  const axisY = Math.round(height * 0.45);
  const position = (value) => left + ((value - low) / span) * (right - left);

  context.strokeStyle = "#c3cad4";
  context.beginPath();
  context.moveTo(left, axisY);
  context.lineTo(right, axisY);
  context.stroke();

  // The marks first: a bar per group, on the side its label will take.
  const lanes = { up: [], down: [] };
  let index = 0;
  for (const group of dated) {
    const { start, end } = findingDates(group);
    const x = position(start.getTime());
    const width2 = Math.max(2, position((end || start).getTime()) - x);
    const up = index % 2 === 0;
    index += 1;
    context.fillStyle = findingLevelColour(group.level);
    context.globalAlpha = 0.85;
    context.fillRect(x, up ? axisY - 10 : axisY, Math.max(2, width2), 10);
    context.globalAlpha = 1;
    context.strokeStyle = findingLevelColour(group.level);
    context.beginPath();
    context.moveTo(x, axisY);
    context.lineTo(x, axisY + (up ? -22 : 22));
    context.stroke();
    (up ? lanes.up : lanes.down).push({ x, group, end: x + width2 });
  }

  // Then the labels, lane by lane, skipping any that would overprint the previous one.
  const label = (group) => {
    const text = `${group.title} (${group.count})`;
    return text.length > 34 ? `${text.slice(0, 34)}…` : text;
  };
  // Two rows per side: a neighbour too close moves up (or down) one row instead of
  // losing its label.
  let drawn = 0;
  for (const [side, items] of Object.entries(lanes)) {
    const cursors = [-Infinity, -Infinity];
    for (const item of items) {
      const text = label(item.group);
      const textWidth = context.measureText(text).width;
      const row = item.x >= cursors[0] + 8 ? 0 : (item.x >= cursors[1] + 8 ? 1 : -1);
      if (row < 0) continue;
      cursors[row] = item.x + textWidth;
      context.fillStyle = "#333";
      const offset = side === "up" ? -(30 + row * 18) : 34 + row * 18;
      const x = Math.min(item.x, right - textWidth - 2);
      context.fillText(text, x, axisY + offset);
      drawn += 1;
    }
  }

  // The dates go under everything, where nothing else is written.
  context.fillStyle = "#666";
  for (const stamp of [low, low + span / 2, high]) {
    const text = new Date(stamp).toISOString().slice(0, 16).replace("T", " ");
    context.fillText(text, Math.min(position(stamp), right - context.measureText(text).width),
                     axisY + 76);
  }
  context.fillStyle = "#333";
  context.fillText(`${dated.length} dated group(s) from `
    + `${new Date(low).toISOString().slice(0, 16).replace("T", " ")} to `
    + `${new Date(high).toISOString().slice(0, 16).replace("T", " ")}`
    + (drawn < dated.length ? ` · ${dated.length - drawn} label(s) left out for room` : ""),
    16, height - 12);
}

/* ---------- the desktop's visual formats, on a cell ----------
   Exactly the desktop's arithmetic: a bounded colour scale, a data bar that fills
   from the left, an icon set whose level comes from the thresholds. The bounds
   arrive already resolved by the server; nothing is guessed here. */

function colourOf(text) {
  const raw = String(text || "").trim();
  const match = raw.match(/^#([0-9a-f]{6})$/i);
  if (!match) return [200, 200, 200];
  const value = parseInt(match[1], 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

function mixColour(from, to, weight) {
  const a = colourOf(from);
  const b = colourOf(to);
  const rgb = a.map((value, index) => Math.round(value + (b[index] - value) * weight));
  return `rgb(${rgb.join(",")})`;
}

function visualNumber(rule) {
  const low = Number(rule.minimum);
  const high = Number(rule.maximum);
  if (!Number.isFinite(low) || !Number.isFinite(high) || low > high) return null;
  return { low, high };
}

function visualCell(rule, columnIndex, raw) {
  const visual = rule.visual || "none";
  if (visual === "none") return null;
  // A visual is about one column: the one the rule names, or its target.
  const target = rule.target === null || rule.target === undefined ? rule.column : rule.target;
  if (target !== null && target !== undefined && Number(target) !== Number(columnIndex)) return null;
  const number = Number(String(raw === null || raw === undefined ? "" : raw).trim());
  if (String(raw === null || raw === undefined ? "" : raw).trim() === "" || !Number.isFinite(number)) {
    return null;
  }
  const bounds = visualNumber(rule);
  if (!bounds) return null;
  const { low, high } = bounds;
  let fraction = low === high ? 0.5 : (number - low) / (high - low);
  fraction = Math.max(0, Math.min(1, fraction));
  if (visual === "bar") {
    const colour = number < 0 ? (rule.negative_color || "#d64c4c") : mixColour(rule.background, rule.foreground, fraction);
    return { cls: "vbar", style: `background:linear-gradient(90deg, ${colour} ${Math.round(fraction * 100)}%, transparent ${Math.round(fraction * 100)}%)`, ink: "" };
  }
  if (visual === "scale2") {
    const colour = mixColour(rule.background, rule.foreground, fraction);
    return { cls: "", style: `background:${colour}`, ink: "" };
  }
  if (visual === "scale3") {
    let middle = Number(rule.middle_value);
    if (rule.middle_mode === "percent") middle = low + (high - low) * middle / 100;
    let colour;
    if (low === high) colour = rule.middle_color;
    else if (low < middle && middle < high) {
      colour = number <= middle
        ? mixColour(rule.background, rule.middle_color, (number - low) / (middle - low))
        : mixColour(rule.middle_color, rule.foreground, (number - middle) / (high - middle));
    } else if (middle <= low) colour = rule.middle_color;
    else colour = rule.middle_color;
    return { cls: "", style: `background:${colour}`, ink: "" };
  }
  if (visual === "icon") {
    const colours = (rule.icon_colors && rule.icon_colors.length) ? rule.icon_colors : ["#c62828", "#c58b00", "#218739"];
    const thresholds = (rule.icon_thresholds || []).map(Number);
    let level = Math.min(colours.length - 1, Math.max(0, Math.floor(fraction * colours.length)));
    if (thresholds.length) {
      level = 0;
      for (let index = thresholds.length - 1; index >= 0; index -= 1) {
        const threshold = rule.icon_threshold_mode === "number" ? thresholds[index] : fraction * 100;
        if (rule.icon_threshold_mode === "number" ? number >= threshold : number >= threshold) {
          level = Math.min(colours.length - 1, index + 1);
          break;
        }
      }
    }
    const ink = colours[Math.min(level, colours.length - 1)];
    const glyph = ["▼", "●", "▲"][Math.min(2, level)] || "●";
    return { cls: "viconcell", style: `background:${ink}22`, ink, icon: glyph };
  }
  return null;
}

/* ---------- sort priority ---------- */

const SORT_TYPES = [["text", "Text"], ["number", "Number"], ["timestamp", "ISO date"]];

function sortRow(key = { column: 0, descending: false, kind: "text" }) {
  const row = document.createElement("tr");
  row.innerHTML = `<td><select data-sort-column>${state.columns.slice(1).map((name, index) =>
      `<option value="${index}" ${index === key.column ? "selected" : ""}>${escapeHtml(name)}</option>`).join("")}</select></td>
    <td><select data-sort-direction>
      <option value="asc" ${key.descending ? "" : "selected"}>A → Z</option>
      <option value="desc" ${key.descending ? "selected" : ""}>Z → A</option></select></td>
    <td><select data-sort-kind>${SORT_TYPES.map(([code, label]) =>
      `<option value="${code}" ${code === (key.kind || state.sortType) ? "selected" : ""}>${label}</option>`).join("")}</select></td>
    <td><button class="btn" data-sort-up title="Move up">↑</button></td>
    <td><button class="btn" data-sort-remove title="Remove this key">✕</button></td>`;
  const table = $("sort-rows");
  row.querySelector("[data-sort-up]").addEventListener("click", () => {
    const previous = row.previousElementSibling;
    if (previous) table.insertBefore(row, previous);
  });
  row.querySelector("[data-sort-remove]").addEventListener("click", () => row.remove());
  return row;
}

function openSortPriority() {
  if (!state.columns.length) { say("Open an analysis first", true); return; }
  $("sort-rows").innerHTML = "";
  const keys = state.multiSort.length
    ? state.multiSort
    : (state.sort !== null ? [{ column: state.sort, descending: state.descending, kind: state.sortType }] : []);
  $("sort-header-type").value = state.sortType;
  for (const key of keys) $("sort-rows").appendChild(sortRow(key));
  $("sort-modal").classList.add("show");
}

async function applySortPriority() {
  const keys = [];
  $("sort-rows").querySelectorAll("tr").forEach((row) => {
    keys.push({ column: Number(row.querySelector("[data-sort-column]").value),
                descending: row.querySelector("[data-sort-direction]").value === "desc",
                kind: row.querySelector("[data-sort-kind]").value });
  });
  state.multiSort = keys;
  state.sortType = keys.length ? keys[0].kind : $("sort-header-type").value;
  state.sort = keys.length ? keys[0].column : null;
  state.descending = keys.length ? keys[0].descending : false;
  closeModals();
  await loadRows(true);
  say(keys.length ? `${keys.length} sort key(s), the first one decides` : "Sorting cleared");
}

/* ---------- group summaries ---------- */

const SUMMARY_OPERATIONS = [
  ["rows", "Rows"], ["count", "Not empty"], ["distinct", "Distinct values"],
  ["sum", "Sum"], ["avg", "Average"], ["min", "Minimum"], ["max", "Maximum"],
];
const SUMMARY_KINDS = [["number", "Number"], ["text", "Text"], ["timestamp", "ISO date"]];

function summaryRow(summary = { column: 0, operation: "count", kind: "number", footer: -1 }, withFooter = true) {
  const row = document.createElement("tr");
  const footer = summary.footer === undefined ? -1 : summary.footer;
  const footerChoice = withFooter
    ? `<td><select data-summary-footer aria-label="Summary placement">
        <option value="-1" ${footer === -1 ? "selected" : ""}>In the group header</option>
        <option value="none" ${footer === null ? "selected" : ""}>In the value column</option>
        ${state.columns.slice(1).map((name, index) =>
          `<option value="${index}" ${footer === index ? "selected" : ""}>${escapeHtml(name)}</option>`).join("")}</select></td>`
    : "";
  row.innerHTML = `<td><select data-summary-column aria-label="Summary column">${state.columns.slice(1).map((name, index) =>
      `<option value="${index}" ${index === summary.column ? "selected" : ""}>${escapeHtml(name)}</option>`).join("")}</select></td>
    <td><select data-summary-operation aria-label="Summary operation">${SUMMARY_OPERATIONS.map(([code, label]) =>
      `<option value="${code}" ${code === summary.operation ? "selected" : ""}>${escapeHtml(label)}</option>`).join("")}</select></td>
    <td><select data-summary-kind aria-label="Summary value type">${SUMMARY_KINDS.map(([code, label]) =>
      `<option value="${code}" ${code === summary.kind ? "selected" : ""}>${escapeHtml(label)}</option>`).join("")}</select></td>
    ${footerChoice}<td><button class="btn" data-summary-remove title="Remove this summary">✕</button></td>`;
  row.querySelector("[data-summary-remove]").addEventListener("click", () => {
    row.remove();
    refreshSummaryOrderChoices();
  });
  return row;
}

function openSummaries() {
  if (!state.columns.length) { say("Open an analysis first", true); return; }
  $("summary-rows").innerHTML = "";
  const chosen = state.summaries.length ? state.summaries
    : (state.groups.length ? [{ column: 0, operation: "count", kind: "number" }] : []);
  for (const summary of chosen) $("summary-rows").appendChild(summaryRow(summary));
  $("total-rows").innerHTML = "";
  for (const summary of state.totalSummaries) $("total-rows").appendChild(summaryRow(summary, false));
  $("summary-footer-mode").value = state.footerMode;
  $("summary-show-total").checked = state.showTotal;
  $("summary-order").value = state.order || "";
  $("summary-desc").checked = state.orderDesc !== false;
  refreshSummaryOrderChoices();
  $("summaries-modal").classList.add("show");
}

function refreshSummaryOrderChoices() {
  const count = $("summary-rows").querySelectorAll("tr").length;
  $("summary-which").style.display = $("summary-order").value === "summary" ? "" : "none";
  $("summary-which").innerHTML = Array.from({ length: count }, (_, index) =>
    `<option value="${index}">summary ${index + 1}</option>`).join("")
    || '<option value="0">no summary yet</option>';
  $("summary-which").value = String(Math.min(state.orderSummary || 0, Math.max(0, count - 1)));
}

async function applySummaries() {
  const summaries = [];
  $("summary-rows").querySelectorAll("tr").forEach((row) => {
    summaries.push({
      column: Number(row.querySelector("[data-summary-column]").value),
      operation: row.querySelector("[data-summary-operation]").value,
      kind: row.querySelector("[data-summary-kind]").value,
      footer: (() => { const value = row.querySelector("[data-summary-footer]").value; return value === "none" ? null : Number(value); })(),
    });
  });
  state.summaries = summaries;
  state.totalSummaries = [...$("total-rows").querySelectorAll("tr")].map((row) => ({
    column: Number(row.querySelector("[data-summary-column]").value),
    operation: row.querySelector("[data-summary-operation]").value,
    kind: row.querySelector("[data-summary-kind]").value,
    footer: -1,
  }));
  state.footerMode = $("summary-footer-mode").value;
  state.showTotal = $("summary-show-total").checked;
  state.order = $("summary-order").value;
  state.orderDesc = $("summary-desc").checked;
  state.orderSummary = Number($("summary-which").value || 0);
  closeModals();
  await loadRows(true);
  say(summaries.length
    ? `${summaries.length} group summar${summaries.length === 1 ? "y" : "ies"}`
    : "Group summaries cleared");
}

/* ---------- date windows ---------- */

const dateState = { ranges: [], columns: [] };

async function openDateFilter() {
  if (!state.columns.length) { say("Open an analysis first", true); return; }
  const looksLikeDate = (name) => /date|time|jour|créé|created|modified|timestamp/i.test(name);
  const columns = state.columns.slice(1).map((name, index) => ({ name, index }));
  dateState.columns = columns;
  $("date-column").innerHTML = columns
    .map((item) => `<option value="${item.index}">${escapeHtml(item.name)}</option>`)
    .join("");
  // A date column first: the others are still offered, the analyst knows the data.
  const first = columns.find((item) => looksLikeDate(item.name));
  if (first) $("date-column").value = String(first.index);
  await loadDateRanges();
  if (!$("date-day").value) $("date-day").value = new Date().toISOString().slice(0, 10);
  showDateMode();
  $("date-summary").textContent = state.expression
    ? `${countConditions(state.expression)} condition(s) already in the advanced filter`
    : "The advanced filter is empty.";
  $("date-modal").classList.add("show");
}

/* The core names its windows in CamelCase ("EarlierThisWeek", "MonthAgo3"): the list reads them. */
function dateRangeLabel(name) {
  const months = name.match(/^Month(Ago|After)(\d+)$/);
  if (months) {
    const count = Number(months[2]);
    const unit = count === 1 ? "month" : "months";
    return months[1] === "Ago" ? `${count} ${unit} ago` : `In ${count} ${unit}`;
  }
  const words = name.replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

async function loadDateRanges() {
  if (dateState.ranges.length) return;
  try {
    const payload = await api("/api/date-ranges");
    dateState.ranges = payload.ranges || [];
    $("date-range").innerHTML = dateState.ranges
      .map((item) => `<option value="${escapeHtml(item.name)}">${escapeHtml(dateRangeLabel(item.name))}</option>`)
      .join("");
  } catch (error) {
    say(error.message, true);
  }
}

function showDateMode() {
  const mode = $("date-mode").value;
  $("date-range-row").style.display = mode === "range" ? "flex" : "none";
  $("date-day-row").style.display = mode === "range" ? "none" : "flex";
}

function dateCondition() {
  const column = Number($("date-column").value);
  const name = state.columns[column + 1] || "";
  const mode = $("date-mode").value;
  const quoted = `[${String(name).replace("]", "]]")}]`;
  if (mode === "range") {
    const range = $("date-range").value || "Today";
    // One condition, wrapped in a list: the caller walks a list in both branches.
    return [[{ column, operator: "expression", value: `InDateRange(${quoted}, '${range}')` }],
            `${name} in ${range}`];
  }
  const chosen = $("date-day").value;
  if (!chosen) return [null, ""];
  const [year, month, day] = chosen.split("-").map(Number);
  const pad = (value) => String(value).padStart(2, "0");
  const start = `${year}-${pad(month)}-${pad(day)}`;
  let end;
  if (mode === "year") end = `${year + 1}-01-01`;
  else if (mode === "month") end = month === 12 ? `${year + 1}-01-01` : `${year}-${pad(month + 1)}-01`;
  else {
    const next = new Date(Date.UTC(year, month - 1, day + 1));
    end = next.toISOString().slice(0, 10);
  }
  return [[{ column, operator: "after", value: start }, { column, operator: "date_before", value: end }],
          `${name} from ${start} to ${end}`];
}

async function addDateCondition() {
  try {
    const [atoms, label] = dateCondition();
    if (!atoms || !atoms.length) { say("Pick a date first", true); return; }
    const expression = state.expression && Array.isArray(state.expression.children)
      ? state.expression : { logic: "and", children: [] };
    for (const atom of atoms) expression.children.push(atom);
    state.expression = expression;
    closeModals();
    await loadRows(true);
    say(`Date filter: ${label}`);
  } catch (error) {
    say(error.message, true);
  }
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
    // Ctrl toggles one row: a row already selected leaves the selection.
    if (state.selection.has(id)) state.selection.delete(id); else state.selection.add(id);
    state.anchor = id;
  } else {
    state.selection = new Set([id]);
    state.anchor = id;
  }
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

/* Rows leave as a tab-separated table, the way the desktop copies them: a
   spreadsheet takes it directly. The header line is the analyst's choice. */
async function copySelectedRows() {
  const ids = selectedIds();
  if (!ids.length) { say("Select a row first", true); return; }
  // As the desktop copies: the columns on screen, without the row number, one tab-separated
  // line per row, a cell quoted when it holds a tab, a quote or a line break.
  const shown = visibleColumns().filter((item) => item.index > 0);
  const cell = (value) => {
    const text = value === null || value === undefined ? "" : String(value);
    return /[\t\n\r"]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const lines = [];
  if (copyPrefs.headers) lines.push(shown.map((item) => cell(item.name)).join("\t"));
  for (const id of ids) {
    let row = state.rows.find((item) => String(item[0]) === id);
    if (!row) continue;
    try { row = await completeRow(row); }
    catch (error) { say(error.message, true); return; }
    if (!row) return;
    lines.push(shown.map((item) => cell(row[item.index])).join("\t"));
  }
  try {
    await navigator.clipboard.writeText(lines.join("\n"));
    say(`${ids.length} row(s) copied as a table`);
  } catch (_) {
    say("The browser refused clipboard access", true);
  }
}

function activeAnalysisPath() {
  return state.openCase && `/api/cases/${state.openCase.id}/analyses/${state.analysis}`;
}

async function postBookmark(path, rowId, note) {
  await apiPost(`${path}/bookmark`, { row_id: Number(rowId), note });
  if (path !== activeAnalysisPath()) return;
  if (note.trim()) state.bookmarks.set(String(rowId), note);
  else state.bookmarks.delete(String(rowId));
}

/* A selection belongs to the analysis in which the analyst made it, even if
   they open another grid while the writes are in flight. */
async function saveBookmarkEdits(path, edits, action) {
  let written = 0;
  let failure = "";
  try {
    for (const [id, note] of edits) {
      await postBookmark(path, id, note);
      written++;
    }
  } catch (error) {
    failure = error.message;
  }
  const message = failure ? `${written} of ${edits.length} row(s) ${action}. ${failure}`
    : `${written} row(s) ${action}`;
  if (path === activeAnalysisPath()) await refreshBookmarksView();
  if (path === activeAnalysisPath()) say(message, Boolean(failure));
  else rememberMessage(message, Boolean(failure));
}

async function markSelection(note, ids = selectedIds(), path = activeAnalysisPath()) {
  if (!ids.length) { say("Select a row first", true); return; }
  const edits = ids.slice(0, 200).map(id => [id, note]);
  await saveBookmarkEdits(path, edits, note.trim() ? "marked" : "unmarked");
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
    rememberReviewPlace();
    state.analysis = payload.analysis;
    state.groups = []; state.path = []; state.interval = ""; state.expression = null;
    state.summaries = []; state.order = "";
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
    rememberReviewPlace();
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

/* The right-click commands that act on the cell under the pointer, as the desktop's cell menu does. */
async function editCellNote() {
  const column = contextColumnIndex();
  const row = contextRow ? contextRow.dataset.row : null;
  if (column === null || row === null) { say("Right-click a cell first", true); return; }
  const current = notesForRow(row)[String(column)] || "";
  const note = await ask({ title: "Cell note", label: `Note for ${state.columns[column + 1] || "this cell"}`, value: current });
  if (note === null) return;
  try {
    await apiPost(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/cellnote`,
      { row_id: Number(row), column, note });
    await loadCellNotes();
    renderGrid();
    say(note ? "Cell note saved" : "Cell note removed");
  } catch (error) {
    say(error.message, true);
  }
}

function valueOfActiveCell() {
  const column = contextColumnIndex();
  const row = selectedRowValues();
  return column === null || !row ? "" : String(row[column + 1] ?? "");
}

async function searchValueEverywhere() {
  const value = valueOfActiveCell();
  if (!value) { say("Right-click a cell with a value first", true); return; }
  openReviewSearch("case", value);
  await runGlobalSearch();
}

async function correlateValue() {
  const value = valueOfActiveCell();
  const column = contextColumnIndex();
  if (!value) { say("Right-click a cell with a value first", true); return; }
  const name = String(state.columns[column + 1] || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  const kind = /user|account/.test(name) ? "user" : /ip(address)?$|sourceip|destinationip/.test(name) ? "ip"
    : /path|filename/.test(name) ? "path" : /sha|md5|hash/.test(name) ? "hash" : "text";
  showTab("timeline");
  $("timeline-kind").value = kind;
  $("timeline-search").value = value;
  timelineState.kind = kind;
  timelineState.text = value;
  // The desktop compares the whole value when the field is an identity, an address, a path or a hash.
  $("timeline-exact").checked = kind !== "text";
  await loadTimeline(true);
  say(`Correlating ${value} across the case`);
}

function filterFromCell(operator) {
  const column = contextColumnIndex();
  if (column === null) { say("Right-click a cell first", true); return; }
  const row = selectedRowValues();
  const value = row ? String(row[column + 1] ?? "") : "";
  // The desktop appends: excluding two values of one column keeps both exclusions. The same
  // condition twice is one condition.
  const same = (item) => item.column === column && item.operator === operator && String(item.value || "") === value;
  if ((operator === "empty" || operator === "not_empty" || value !== "") && !state.filters.some(same)) {
    state.filters.push({ column, operator, value });
  }
  const input = document.querySelector(`input[data-filter="${column}"]`);
  if (input) input.value = value;
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
  if (state.groups.includes(column)) { say("This column is already grouped", true); return; }
  state.groups.push(column);
  state.interval = "";
  state.path = [];
  renderGroupBar();
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
  state.hidden.add(column + 1);  // hidden columns are numbered with the row id first
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
  const revision = ++graphReadRevision;
  $("graph-summary").textContent = "Building…";
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/graph`);
    if (graphReadRevision !== revision) return;
    if (payload.empty) {
      // Nothing to draw yet: say what to do, as a hint rather than an error.
      renderGraph({ nodes: [], edges: [] });
      $("graph-summary").textContent = payload.message;
      return;
    }
    renderGraph(payload);
  } catch (error) {
    if (graphReadRevision !== revision) return;
    $("graph-summary").textContent = error.message;
    say(error.message, true);
  }
}

/* The graph is laid out and drawn in the window (see renderGraph); a zoom scales the whole
   stage, edges and cards together, and Recentre puts it back to 1. */
let graphScale = 1;
let graphFit = 1; // the scale that shows the whole chain in the window: Recentre goes back to it

function graphZoom(factor) {
  const stage = $("graph-stage");
  if (!stage || !$("graph-nodes").children.length) { say("Build the graph first", true); return; }
  graphScale = Math.max(0.4, Math.min(3, graphScale * factor));
  stage.style.transform = `scale(${graphScale})`;
  $("graph-summary").textContent = `Zoom ${Math.round(graphScale * 100)} %`;
}

function graphReset() {
  graphScale = graphFit;
  const stage = $("graph-stage");
  if (stage) stage.style.transform = graphFit === 1 ? "" : `scale(${graphFit})`;
  const wrap = $("graph-wrap");
  if (wrap) wrap.scrollTo({ left: 0, top: 0 });
  say("Graph recentred");
}

async function exportGraphPng() {
  if (!state.openCase) { say("Open a case first", true); return; }
  try {
    const payload = graphVisible(await api(`/api/cases/${state.openCase.id}/graph`));
    if (!(payload.nodes || []).length) { say("The graph is empty", true); return; }
    const layout = graphLayout(payload);
    const canvas = document.createElement("canvas");
    const scale = 2;
    canvas.width = layout.width * scale;
    canvas.height = (layout.height + 28) * scale;
    const context = canvas.getContext("2d");
    context.scale(scale, scale);
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, layout.width, layout.height + 28);
    context.textBaseline = "alphabetic";
    context.font = "600 10px 'Segoe UI', Arial, sans-serif";
    context.fillStyle = "#6b7a8a";
    for (const column of layout.columns) context.fillText(column.title.toUpperCase(), column.x, 18);
    for (const edge of layout.edges) {
      context.beginPath();
      context.moveTo(edge.x1, edge.y1);
      context.bezierCurveTo(edge.cx1, edge.y1, edge.cx2, edge.y2, edge.x2, edge.y2);
      context.strokeStyle = "#9aa9ba";
      context.lineWidth = edge.width;
      context.stroke();
    }
    for (const node of layout.nodes) {
      context.fillStyle = "#ffffff";
      context.strokeStyle = "#b5b5b5";
      context.lineWidth = 1;
      context.beginPath();
      context.roundRect(node.x, node.y, GRAPH_CARD_W, GRAPH_CARD_H, 7);
      context.fill();
      context.stroke();
      context.fillStyle = node.colour;
      context.fillRect(node.x, node.y + 1, 6, GRAPH_CARD_H - 2);
      context.fillStyle = "#6b7a8a";
      context.font = "9px 'Segoe UI', Arial, sans-serif";
      context.fillText(graphKindLabel(node).toUpperCase(), node.x + 14, node.y + 15);
      context.fillStyle = "#202020";
      context.font = "600 12px 'Segoe UI', Arial, sans-serif";
      context.fillText(String(node.label || "").slice(0, 30), node.x + 14, node.y + 31);
      context.fillStyle = "#6b7a8a";
      context.font = "10.5px 'Segoe UI', Arial, sans-serif";
      context.fillText(graphMeta(node).slice(0, 38), node.x + 14, node.y + 46);
    }
    context.fillStyle = "#6b7a8a";
    context.font = "10px 'Segoe UI', Arial, sans-serif";
    context.fillText(`Kagarasu — ${state.openCase.name || "case"} — open the graph to inspect the evidence behind each node.`,
      GRAPH_LEFT, layout.height + 14);
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
    const blob = new Blob([JSON.stringify(payload.layer, null, 2)], { type: "application/json" });
    const link = window.document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `fireblade-attack-layer-${state.openCase.id.slice(0, 8)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
    say(`ATT&CK Navigator layer: ${payload.techniques} technique(s), ${Math.round(payload.bytes / 1024)} kB`);
  } catch (error) {
    say(error.message, true);
  }
}

let graphPayload = { nodes: [], edges: [] };
let graphSelection = null;
let graphReadRevision = 0;

function resetGraph() {
  graphReadRevision += 1;
  graphSelection = null;
  $("graph-tag-filter").value = "";
  renderGraph({ nodes: [], edges: [] });
  $("graph-summary").textContent = "";
}

const GRAPH_CARD_W = 200;
const GRAPH_CARD_H = 58;
const GRAPH_GAP_X = 70;
const GRAPH_GAP_Y = 14;
const GRAPH_TOP = 34;
const GRAPH_LEFT = 24;
const GRAPH_KIND = { host: "Host", account: "Account", technique: "Technique", stage: "Tactic", ioc: "Indicator", custom: "Free node", tag: "Saved tag" };
const GRAPH_COLOUR = { host: "#4c9a5e", account: "#4c9a5e", technique: "#d28a3c", stage: "#7b6cc4", ioc: "#c4506e", custom: "#6f7f90", tag: "#6a49b2" };

/* "Which levels of the chain to show": hosts, techniques or indicators; free nodes always stay. */
function graphVisible(payload) {
  const level = $("graph-level").value;
  const tag = $("graph-tag-filter").value;
  if (!level && !tag) return payload;
  const related = new Set([tag]);
  for (const edge of payload.edges) {
    if (edge.source === tag) related.add(edge.target);
    if (edge.target === tag) related.add(edge.source);
  }
  const nodes = payload.nodes.filter(node => (!tag || related.has(node.id))
    && (!level || node.kind === level || !["host", "technique", "ioc"].includes(node.kind)));
  const kept = new Set(nodes.map((node) => node.id));
  return { ...payload, nodes, edges: payload.edges.filter((edge) => kept.has(edge.source) && kept.has(edge.target)) };
}

function graphKindLabel(node) {
  const base = GRAPH_KIND[node.kind] || "Node";
  return node.kind === "technique" && node.code ? `${base} ${node.code}` : (node.kind === "ioc" && node.code ? `${base} · ${node.code}` : base);
}

function graphMeta(node) {
  if (node.kind === "tag") return `${node.records} marked record(s)`;
  const labels = (node.tags || []).join(" · ");
  if (labels) return labels;
  const alerts = Number(node.alerts || 0);
  if (alerts) return `${alerts} alert(s)${node.level ? " · " + node.level : ""}`;
  if (node.kind === "ioc") return node.level ? `status ${node.level}` : "tracked indicator";
  return node.auto === false ? "declared by you" : "no alert";
}

function graphNodeColour(node) {
  return node.level && node.alerts ? findingLevelColour(node.level) : (GRAPH_COLOUR[node.kind] || "#6f7f90");
}

/* Columns along the chain: indicators, hosts and accounts, then one column per tactic with its
   techniques under it, then what the analyst added by hand. Deterministic: the same data gives
   the same picture, which is what makes a screenshot in a report reproducible. */
function graphLayout(payload) {
  const nodes = payload.nodes || [];
  const rank = (node) => [-(Number(node.alerts) || 0), String(node.label || "")];
  const order = (a, b) => (rank(a)[0] - rank(b)[0]) || rank(a)[1].localeCompare(rank(b)[1]);
  const stageOf = new Map();
  for (const edge of payload.edges || []) {
    if (edge.label === "tactic") stageOf.set(edge.source, edge.target);
  }
  const columns = [];
  const add = (title, members) => { if (members.length) columns.push({ title, members }); };
  add("Saved tags and row marks", nodes.filter(node => node.kind === "tag").sort(order));
  add("Indicators", nodes.filter((node) => node.kind === "ioc").sort(order));
  add("Hosts and accounts", nodes.filter((node) => node.kind === "host" || node.kind === "account").sort(order));
  const stages = nodes.filter((node) => node.kind === "stage").sort((a, b) => (a.order ?? 99) - (b.order ?? 99));
  for (const stage of stages) {
    const techniques = nodes.filter((node) => node.kind === "technique" && stageOf.get(node.id) === stage.id).sort(order);
    add("ATT&CK tactic", [stage, ...techniques]);
  }
  const placed = new Set(columns.flatMap((column) => column.members.map((node) => node.id)));
  add("Technique without tactic", nodes.filter((node) => node.kind === "technique" && !placed.has(node.id)).sort(order));
  add("Added by hand", nodes.filter((node) => !placed.has(node.id) && !["technique", "ioc", "host", "account", "stage", "tag"].includes(node.kind)).sort(order));
  const where = new Map();
  columns.forEach((column, index) => {
    column.x = GRAPH_LEFT + index * (GRAPH_CARD_W + GRAPH_GAP_X);
    column.members.forEach((node, row) => {
      where.set(node.id, { ...node, x: column.x, y: GRAPH_TOP + row * (GRAPH_CARD_H + GRAPH_GAP_Y), colour: graphNodeColour(node) });
    });
  });
  const placedNodes = [...where.values()];
  const edges = [];
  const taken = []; // the badges already placed
  for (const edge of payload.edges || []) {
    if (edge.label === "tactic") continue; // a technique sits in the column of its tactic
    const a = where.get(edge.source);
    const b = where.get(edge.target);
    if (!a || !b || a === b) continue;
    const forward = a.x < b.x;
    const x1 = forward ? a.x + GRAPH_CARD_W : a.x;
    const x2 = forward ? b.x : b.x + GRAPH_CARD_W;
    const y1 = a.y + GRAPH_CARD_H / 2;
    const y2 = b.y + GRAPH_CARD_H / 2;
    const pull = Math.max(40, Math.abs(x2 - x1) / 2);
    const cx1 = x1 + (forward ? pull : -pull);
    const cx2 = x2 - (forward ? pull : -pull);
    const mix = (t, a0, a1, a2, a3) => (1 - t) ** 3 * a0 + 3 * (1 - t) ** 2 * t * a1 + 3 * (1 - t) * t ** 2 * a2 + t ** 3 * a3;
    // The badge sits in the gap beside a card, where no card can hide it, at the first spot no other badge holds.
    const labelWidth = (edge.alerts ? String(edge.alerts) : (edge.label === "observed on" ? "on" : (edge.label || ""))).length * 6 + 14;
    const sourceGap = (x) => (forward ? x > x1 + labelWidth / 2 && x < x1 + GRAPH_GAP_X - labelWidth / 2 : x < x1 - labelWidth / 2 && x > x1 - GRAPH_GAP_X + labelWidth / 2);
    const targetGap = (x) => (forward ? x < x2 - labelWidth / 2 && x > x2 - GRAPH_GAP_X + labelWidth / 2 : x > x2 + labelWidth / 2 && x < x2 + GRAPH_GAP_X - labelWidth / 2);
    let spot = null;
    for (let t = 0.01; t < 0.99 && !spot; t += 0.01) {
      const x = mix(t, x1, cx1, cx2, x2);
      const y = mix(t, y1, y1, y2, y2);
      if (!sourceGap(x) && !targetGap(x)) continue;
      if (taken.some((box) => Math.abs(box.x - x) < (box.w + labelWidth) / 2 + 2 && Math.abs(box.y - y) < 20)) continue;
      spot = { x, y };
    }
    if (!spot) { const t = 0.5; spot = { x: mix(t, x1, cx1, cx2, x2), y: mix(t, y1, y1, y2, y2) }; }
    taken.push({ x: spot.x, y: spot.y, w: labelWidth });
    edges.push({
      ...edge, x1, y1, x2, y2, cx1, cx2, bx: spot.x, by: spot.y,
      width: 1.2 + Math.min(4, Math.log2(1 + (Number(edge.alerts) || 0))),
    });
  }
  const rows = Math.max(1, ...columns.map((column) => column.members.length));
  return {
    nodes: placedNodes, edges, columns,
    width: GRAPH_LEFT * 2 + columns.length * (GRAPH_CARD_W + GRAPH_GAP_X) - GRAPH_GAP_X,
    height: GRAPH_TOP + rows * (GRAPH_CARD_H + GRAPH_GAP_Y) + 20,
  };
}

function renderGraph(whole) {
  graphPayload = whole;
  const tags = $("graph-tag-filter");
  const selectedTag = tags.value;
  const nodesWithTags = whole.nodes.filter(node => node.kind === "tag");
  tags.replaceChildren(new Option("All saved tags", ""), ...nodesWithTags.map(node => new Option(node.label, node.id)));
  tags.value = nodesWithTags.some(node => node.id === selectedTag) ? selectedTag : "";
  tags.disabled = !nodesWithTags.length;
  const payload = graphVisible(whole);
  const layout = graphLayout(payload);
  const width = Math.max(layout.width, 420);
  const height = Math.max(layout.height, 220);
  const stage = $("graph-stage");
  stage.style.width = width + "px";
  stage.style.height = height + "px";
  $("graph-nodes").style.width = width + "px";
  $("graph-nodes").style.height = height + "px";
  $("graph-nodes").innerHTML = layout.nodes.map((node) =>
    `<div class="gnode ${escapeHtml(node.kind)}" data-node="${escapeHtml(node.id)}" tabindex="0" role="button"
       style="left:${node.x}px;top:${node.y}px;--gcolor:${node.colour}"
       title="${escapeHtml(node.label)} — click to see what it rests on">
       <span class="gkind">${escapeHtml(graphKindLabel(node))}</span>
       <span class="gtitle">${escapeHtml(node.label)}</span>
       <span class="gmeta">${escapeHtml(graphMeta(node))}</span></div>`).join("");
  const svg = $("graph-edges");
  svg.setAttribute("width", width);
  svg.setAttribute("height", height);
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  const heads = layout.columns.map((column) =>
    `<text class="gcol" x="${column.x}" y="20">${escapeHtml(column.title)}</text>`).join("");
  const labelOf = (edge) => (edge.alerts ? String(edge.alerts) : (edge.label === "observed on" ? "on" : (edge.label || "")));
  const lines = layout.edges.map((edge) => {
    const d = `M${edge.x1},${edge.y1} C${edge.cx1},${edge.y1} ${edge.cx2},${edge.y2} ${edge.x2},${edge.y2}`;
    return `<g class="gedge" data-edge="${escapeHtml(edge.id)}" data-from="${escapeHtml(edge.source)}" data-to="${escapeHtml(edge.target)}">
      <path class="line" d="${d}" stroke-width="${edge.width}" marker-end="url(#garrow)"/>
      <path class="hit" d="${d}"><title>${escapeHtml(edge.evidence ? edge.evidence.what : edge.label)} — click for the evidence</title></path></g>`;
  }).join("");
  // The badges are drawn last, above every link, so a link never hides the badge of another.
  const pills = layout.edges.map((edge) => {
    const label = labelOf(edge);
    return label ? `<g class="gpill" data-edge="${escapeHtml(edge.id)}" data-from="${escapeHtml(edge.source)}" data-to="${escapeHtml(edge.target)}">
      <rect x="${edge.bx - (6 + 3 * label.length)}" y="${edge.by - 9}" width="${12 + 6 * label.length}" height="18" rx="9"/>
      <text x="${edge.bx}" y="${edge.by + 3.5}" text-anchor="middle">${escapeHtml(label)}</text>
      <title>${escapeHtml(edge.evidence ? edge.evidence.what : label)} — click for the evidence</title></g>` : "";
  }).join("");
  svg.innerHTML = `<defs><marker id="garrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
    <path d="M0,0 L7,3.5 L0,7 z" fill="#9aa9ba"/></marker></defs>${heads}${lines}${pills}`;

  const kinds = {};
  for (const node of payload.nodes) kinds[node.kind] = (kinds[node.kind] || 0) + 1;
  $("graph-summary").textContent = `${payload.nodes.length} node(s), ${payload.edges.length} edge(s) — ` +
    Object.entries(kinds).map(([kind, count]) => `${count} ${kind}`).join(", ")
    + (whole.tags_omitted ? ` · ${whole.tags_omitted} additional tags beyond the graph limit` : "");
  $("graph-legend").innerHTML = payload.nodes.length
    ? graphLegendItems() + '<span class="gnote">Click a card or a link: its evidence opens, with the exact lines it rests on. The colour bar is the worst alert level; the badge on a link is its alert count.</span>' : "";
  const known = graphSelection && (graphSelection.type === "node"
    ? payload.nodes.some((node) => node.id === graphSelection.id)
    : payload.edges.some((edge) => edge.id === graphSelection.id));
  if (!known) graphSelection = null;
  const room = $("graph-wrap").clientWidth;
  graphFit = room && width > room ? Math.max(0.7, (room - 8) / width) : 1;
  graphScale = graphFit;
  stage.style.transform = graphFit === 1 ? "" : `scale(${graphFit})`;
  graphHighlight();
  renderGraphEvidence();
}

/* The selection lights its own links and dims the rest, so the chain around one claim reads at a glance. */
function graphHighlight() {
  const nodes = [...$("graph-nodes").children];
  const edges = [...$("graph-edges").querySelectorAll(".gedge, .gpill")];
  const chosen = graphSelection;
  const near = new Set();
  for (const edge of edges) {
    const mine = chosen && ((chosen.type === "edge" && edge.dataset.edge === chosen.id)
      || (chosen.type === "node" && (edge.dataset.from === chosen.id || edge.dataset.to === chosen.id)));
    edge.classList.toggle("hot", Boolean(mine));
    edge.classList.toggle("selected", Boolean(chosen && chosen.type === "edge" && edge.dataset.edge === chosen.id));
    edge.classList.toggle("dim", Boolean(chosen && !mine));
    if (mine) { near.add(edge.dataset.from); near.add(edge.dataset.to); }
  }
  for (const node of nodes) {
    const id = node.dataset.node;
    node.classList.toggle("selected", Boolean(chosen && chosen.type === "node" && chosen.id === id));
    node.classList.toggle("dim", Boolean(chosen && chosen.id !== id && !near.has(id)));
  }
}

function graphSelect(type, id) {
  graphSelection = graphSelection && graphSelection.type === type && graphSelection.id === id ? null : { type, id };
  graphHighlight();
  renderGraphEvidence();
  if (graphSelection && graphSelection.type === "node") graphReveal(graphSelection.id);
}

/* The evidence drawer covers the right of the picture: a card it would hide is scrolled into the clear part. */
function graphReveal(id) {
  const wrap = $("graph-wrap");
  const card = [...$("graph-nodes").children].find((node) => node.dataset.node === id);
  if (!card || !wrap) return;
  const box = card.getBoundingClientRect();
  const view = wrap.getBoundingClientRect();
  const clear = view.right - Math.min(410, view.width * 0.88) - 12;
  if (box.right > clear) wrap.scrollLeft += box.right - clear;
  if (box.left < view.left) wrap.scrollLeft -= view.left - box.left + 12;
}

function graphMoment(value) {
  return value ? String(value).replace("T", " ").replace("+00:00", "Z").replace(/\.\d+/, "").slice(0, 20) : "";
}

function graphLegendItems() {
  const kinds = [["host", "Host or account"], ["technique", "ATT&CK technique"], ["stage", "ATT&CK tactic"], ["ioc", "Tracked indicator"], ["custom", "Free node"], ["tag", "Saved tag or mark"]];
  return kinds.map(([kind, label]) => `<span style="--gcolor:${GRAPH_COLOUR[kind]}"><i></i>${label}</span>`).join("");
}

function graphItemHtml(item, analysis) {
  const rows = (item.rows || []).map((row) => analysis !== null && analysis !== undefined
    ? `<button class="btn" data-act="graph-line" data-analysis="${analysis}" data-row="${row}"
         title="Show this line exactly as the detection engine wrote it">row ${row}</button>`
    : `<span class="gm">line ${row}</span>`).join("");
  const more = item.rows_total > (item.rows || []).length
    ? `<span class="gm">… ${item.rows_total - item.rows.length} more row(s) in the grid</span>` : "";
  const when = item.start ? `${graphMoment(item.start)}${item.end && item.end !== item.start ? " → " + graphMoment(item.end) : ""}` : "";
  return `<div class="gitem" style="--gcolor:${findingLevelColour(item.level)}">
    <div class="gt">${escapeHtml(item.title)}</div>
    <div class="gm">${escapeHtml(item.level || "")} · ${escapeHtml(item.host || "")} · ${escapeHtml(item.channel || "")}
      ${item.event_ids && item.event_ids.length ? "· event " + escapeHtml(item.event_ids.join(", ")) : ""}
      · ${item.count} alert(s)${when ? " · " + escapeHtml(when) : ""}</div>
    <div class="gm">${item.rule_id ? "rule " + escapeHtml(item.rule_id) : ""}${item.rule_file ? " · " + escapeHtml(item.rule_file) : ""}
      ${item.techniques ? " · " + escapeHtml(item.techniques) : ""}</div>
    <div class="grows">${rows}${more}
      ${analysis !== null && analysis !== undefined ? `<button class="btn gshow" data-act="graph-show"
        data-title="${escapeHtml(item.title)}" data-host="${escapeHtml(item.host || "")}"
        title="Open the alerts of this rule on this host in the grid">Show in the grid</button>` : ""}</div>
    <div class="gslot"></div></div>`;
}

function renderGraphEvidence() {
  const box = $("graph-evidence");
  box.hidden = !graphSelection;
  if (!graphSelection) { box.innerHTML = ""; return; }
  const node = graphSelection.type === "node" ? graphPayload.nodes.find((item) => item.id === graphSelection.id) : null;
  const edge = graphSelection.type === "edge" ? graphPayload.edges.find((item) => item.id === graphSelection.id) : null;
  const entity = node || edge;
  if (!entity) { box.hidden = true; box.innerHTML = ""; return; }
  const evidence = entity.evidence || {};
  const analysis = graphPayload.source ? graphPayload.source.analysis : null;
  const names = new Map(graphPayload.nodes.map((item) => [item.id, item.label]));
  const title = node ? node.label : `${names.get(edge.source) || edge.source} → ${names.get(edge.target) || edge.target}`;
  const kind = node ? graphKindLabel(node) : `Link${edge.label ? " · " + edge.label : ""}`;
  const stats = [["alerts", evidence.alerts], ["rules", evidence.rules], ["machines", evidence.hosts]]
    .filter(([, value]) => value).map(([label, value]) => `<div><b>${value}</b>${label}</div>`).join("");
  const declared = evidence.declared
    ? `<h4>Recorded by the analyst</h4><div class="gdecl">${Object.entries(evidence.declared).map(([key, value]) =>
      `<div><span class="gm">${escapeHtml(key)}</span> ${escapeHtml(Array.isArray(value) ? value.join(", ") : String(value))}</div>`).join("")}</div>` : "";
  const items = (evidence.items || []).map((item) => graphItemHtml(item, analysis)).join("");
  const records = (evidence.records || []).map(item => `<div class="graph-record">
    ${item.event ? `<button class="btn" data-graph-observation="${escapeHtml(item.event)}">Open observation</button>` : ""}
    ${item.record ? `<button class="btn" data-graph-record="${escapeHtml(item.record)}" data-graph-record-line="${item.line}">Open source row</button>` : ""}
    <b>${escapeHtml(item.description || "")}</b>
    <div class="note">${escapeHtml([item.machine, item.file, `row ${item.line}`].filter(Boolean).join(" · "))}</div>
    </div>`).join("");
  const span = evidence.first ? `<p class="gm">First alert ${escapeHtml(graphMoment(evidence.first))} · last ${escapeHtml(graphMoment(evidence.last))}</p>` : "";
  box.innerHTML = `<button class="gclose" data-act="graph-close" title="Close the evidence">✕</button><h3>${escapeHtml(title)}</h3>
    <p><span class="gk">${escapeHtml(kind)}</span>${evidence.level ? `<span class="gk" style="border-color:${findingLevelColour(evidence.level)}">worst: ${escapeHtml(evidence.level)}</span>` : ""}</p>
    <h4>What this is</h4><p>${escapeHtml(evidence.what || "")}</p>
    <h4>How Kagarasu got it</h4><p>${escapeHtml(evidence.how || "")}</p>
    ${stats ? `<div class="gstats">${stats}</div>` : ""}${span}${declared}
    ${records ? `<h4>Marked evidence · ${evidence.records.length} of ${evidence.records_total}</h4>${records}` : ""}
    ${items ? `<h4>Evidence — ${evidence.items_total} alert group(s)${evidence.items_total > evidence.items.length ? `, ${evidence.items.length} shown` : ""}</h4>${items}` : ""}`;
}

/* One row, exactly as the alert analysis holds it: every column the engine wrote. */
async function graphOpenLine(analysis, row, button) {
  const target = button && button.closest(".gitem") ? button.closest(".gitem").querySelector(".gslot") : null;
  if (!target || !state.openCase) return;
  const caseId = state.openCase.id;
  const panel = target.closest("#graph-evidence, #scenario-edges");
  panel.querySelectorAll(".gslot").forEach((slot) => { if (slot !== target) slot.innerHTML = ""; });
  target.innerHTML = '<div class="gm">Reading the row…</div>';
  try {
    const payload = await api(`/api/cases/${caseId}/timeline/row/${analysis}/${row}`);
    if (state.openCase?.id !== caseId || !target.isConnected) return;
    const lines = payload.columns.map((name, position) => [name, payload.values[position]])
      .filter(([, value]) => value !== null && value !== "");
    const hidden = payload.columns.length - lines.length;
    target.innerHTML = `<div class="gline"><header>${escapeHtml(payload.label)} — row ${payload.row_id}</header>
      <table>${lines.map(([name, value]) => `<tr><td>${escapeHtml(name)}</td><td>${escapeHtml(String(value))}</td></tr>`).join("")}</table>
      ${hidden ? `<div class="gm" style="padding:3px 8px">${hidden} empty column(s) not shown</div>` : ""}</div>`;
  } catch (error) {
    target.innerHTML = "";
    say(error.message, true);
  }
}

async function graphShowAlerts(title, host) {
  const analysis = graphPayload.source ? graphPayload.source.analysis : null;
  if (analysis === null || analysis === undefined) { say("The alert analysis is not open in the case", true); return; }
  findingState.analysis = analysis;
  await showFindingInGrid({ title, host });
}

/* ---------- Hayabusa ---------- */

const hayabusaState = { runs: [] };

async function runHayabusa() {
  if (!state.openCase) { say("Open a case first", true); return; }
  const { id } = state.openCase;
  const level = $("hayabusa-level").value;
  $("hayabusa-summary").textContent = "Running the detection engine — this can take a minute…";
  say("Hayabusa: running…");
  try {
    const payload = await runTask("detect", { min_level: level }, "Hayabusa");
    if (!payload || state.openCase?.id !== id) return;
    hayabusaState.runs = payload.runs || [];
    const runs = hayabusaState.runs.map((run) => `${escapeHtml(run.collection)}: ${run.summary?.detections ?? 0} detection(s)` +
      (run.analysis === null || run.analysis === undefined ? "" :
        ` · <a href="#" class="lnk" data-sources="${escapeHtml(run.collection)}">export the sources</a>`)).join(" · ");
    $("hayabusa-summary").innerHTML = `${payload.total} finding(s) — ${runs}`;
    // The run adds its alert analysis to the case: refresh the tree without
    // leaving the findings the analyst just asked for.
    const detail = await api(`/api/cases/${id}`);
    if (state.openCase?.id !== id) return;
    state.openCase = detail;
    renderTree();
    await loadFindings(true);
    if (state.openCase?.id !== id) return;
    say(`Hayabusa: ${payload.total} finding(s) at level ${level}+`);
  } catch (error) {
    if (state.openCase?.id !== id) return;
    $("hayabusa-summary").textContent = error.message;
    say(error.message, true);
  }
}

/* A finding is one rule on one host: its alerts are the rows of the alert analysis that name both. */
async function showFindingInGrid(group) {
  if (findingState.analysis === null || findingState.analysis === undefined) {
    say("The alert analysis of this detection is not open in the case", true);
    return;
  }
  rememberReviewPlace();
  state.analysis = findingState.analysis;
  state.groups = []; state.path = []; state.interval = ""; state.expression = null;
  state.summaries = []; state.order = "";
  state.filters = []; state.search = ""; state.sort = null; state.multiSort = [];
  showTab("analyses");
  renderTree();
  await loadRows(true);
  const filters = [];
  for (const [name, value] of [["ruletitle", group.title], ["computer", group.host]]) {
    const position = state.columns.findIndex((column) => column.toLowerCase() === name);
    if (position > 0 && value) filters.push({ column: position - 1, operator: "eq", value });
  }
  if (filters.length) {
    state.filters = filters;
    await loadRows(true);
  }
  say(`${state.total} alert(s) of this rule — ${group.title}`);
}

async function markFinding(group) {
  if (findingState.analysis === null || findingState.analysis === undefined) {
    say("The alert analysis of this detection is not open in the case", true);
    return;
  }
  const { id } = state.openCase;
  try {
    const payload = await apiPost(
      `/api/cases/${id}/analyses/${findingState.analysis}/bookmark-finding`,
      { finding: { RuleTitle: group.title, Computer: group.host } });
    if (state.openCase?.id !== id) return;
    const capped = payload.matched > payload.marked ? ` of ${payload.matched}` : "";
    say(`${payload.marked} alert(s) marked${capped}`);
  } catch (error) {
    if (state.openCase?.id !== id) return;
    say(error.message, true);
  }
}

/* ---------- coverage and diagnostics ---------- */

const coverageState = { report: null };

async function openCoverage() {
  if (!state.openCase) { say("Open a case first", true); return; }
  $("coverage-modal").classList.add("show");
  $("coverage-rows").innerHTML = "";
  $("coverage-note").textContent = "Reading the last check kept with this case…";
  try {
    const payload = await api(`/api/cases/${encodeURIComponent(state.openCase.id)}/coverage?run=false`);
    if (!payload.report) {
      $("coverage-note").textContent = "No check kept yet: press \"Check the coverage\".";
      $("coverage-summary").textContent = "";
      return;
    }
    showCoverage(payload);
  } catch (_) {
    $("coverage-note").textContent = "No check kept yet: press \"Check the coverage\".";
    $("coverage-summary").textContent = "";
  }
}

function showCoverage(payload) {
  coverageState.report = payload.report || null;
  const counts = (payload.report && payload.report.counts) || {};
  $("coverage-summary").textContent = payload.report
    ? `${counts.error || 0} error(s), ${counts.warning || 0} to verify, ${counts.info || 0} information`
    : "";
  $("coverage-note").textContent = payload.report
    ? `Checked on ${payload.report.created} — ${payload.report.expected_profile} profile.`
      + " An absence is a point to verify, never a proof that the machine had nothing."
    : "";
  renderCoverage();
}

function renderCoverage() {
  const findings = (coverageState.report && coverageState.report.findings) || [];
  const level = $("coverage-level").value;
  const needle = $("coverage-search").value.trim().toLowerCase();
  const shown = findings.filter((item) =>
    (!level || item.severity === level)
    && (!needle || `${item.stage} ${item.path} ${item.reason} ${item.code}`
      .toLowerCase().includes(needle)));
  $("coverage-rows").innerHTML = shown.length
    ? shown.slice(0, 800).map((item) => `<tr class="sev-${escapeHtml(item.severity)}">
        <td>${escapeHtml(item.stage || "")}</td>
        <td>${escapeHtml(item.severity || "")}</td>
        <td title="${escapeHtml(item.path || "")}">${escapeHtml(item.label || String(item.path || "").split(/[\\/]/).pop())}</td>
        <td title="${escapeHtml(item.reason || "")}">${escapeHtml(item.reason || "")}</td>
        <td title="${escapeHtml(item.impact || "")}">${escapeHtml(item.impact || "")}</td>
        <td title="${escapeHtml(item.action || "")}">${escapeHtml(item.action || "")}</td></tr>`).join("")
    : '<tr><td colspan="6" class="cellnull">Nothing matches this filter.</td></tr>';
  if (shown.length > 800) {
    $("coverage-note").textContent += ` ${shown.length - 800} more finding(s): narrow the filter or export the report.`;
  }
}

let coverageTools = null;   // the families the analyst expects, when the plan was adjusted

async function openCoveragePlan() {
  if (!state.openCase) { say("Open a case first", true); return; }
  try {
    const plan = await api("/api/coverage-plan");
    const chosen = new Set(coverageTools || plan.profiles[$("coverage-profile").value] || []);
    $("coverage-plan-list").innerHTML = plan.families.map((name) =>
      `<label><input type="checkbox" data-family="${escapeHtml(name)}" ${chosen.has(name) ? "checked" : ""}> ${escapeHtml(name)}</label>`).join("");
    $("coverage-plan-modal").classList.add("show");
  } catch (error) {
    say(error.message, true);
  }
}

function applyCoveragePlan() {
  coverageTools = [...$("coverage-plan-list").querySelectorAll("input[data-family]")]
    .filter((box) => box.checked).map((box) => box.dataset.family);
  $("coverage-plan-modal").classList.remove("show");
  say(`Expected families adjusted: ${coverageTools.length} chosen — a missing one is a point to verify, not a proof of absence`);
}

async function runCoverage() {
  if (!state.openCase) { say("Open a case first", true); return; }
  say("Checking every analysis: this reads them again, it can take a while…");
  $("coverage-note").textContent = "Checking…";
  try {
    const payload = await runTask("coverage", {
      expected: $("coverage-profile").value,
      tools: coverageTools,
      verify_hashes: $("coverage-hashes").checked,
      deep_checks: $("coverage-deep").checked,
    }, "Coverage check");
    $("coverage-modal").classList.add("show"); // the task's progress window had taken the screen
    if (!payload) { $("coverage-note").textContent = "The check was stopped: the previous result stays."; return; }
    showCoverage(payload);
  } catch (error) {
    $("coverage-note").textContent = error.message;
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

async function loadResourcePrefs() {
  try {
    const payload = await api("/api/preferences");
    $("prefs-auto-profile").checked = payload.auto_profiles !== false;
    $("prefs-memory").value = payload.resource_memory_mb;
    $("prefs-query-threads").value = payload.query_threads;
    $("prefs-parsing-threads").value = payload.parsing_threads;
    $("prefs-memory").placeholder = `Automatic · ${payload.automatic_memory_mb} MB`;
    $("prefs-query-threads").placeholder = $("prefs-parsing-threads").placeholder = `Automatic · ${payload.automatic_threads} threads`;
  } catch (error) { say(error.message, true); }
}

async function saveResourcePrefs() {
  try {
    await apiPut("/api/preferences", {
      auto_profiles: $("prefs-auto-profile").checked,
      resource_memory_mb: Number($("prefs-memory").value) || 0,
      query_threads: Number($("prefs-query-threads").value) || 0,
      parsing_threads: Number($("prefs-parsing-threads").value) || 0,
    });
    say("Saved for the next analyses opened: the ones running keep their resources");
  } catch (error) { say(error.message, true); await loadResourcePrefs(); }
}

async function openPreferences() {
  $("prefs-scale").value = localStorage.getItem("fireblade.scale") || "1";
  $("prefs-date-format").value = copyPrefs.dateFormat;
  $("prefs-date-pattern").value = copyPrefs.pattern;
  $("prefs-right-copy").checked = copyPrefs.rightCopy;
  $("prefs-details").value = copyPrefs.details;
  $("prefs-tree").value = copyPrefs.tree;
  $("prefs-pins").value = copyPrefs.pins.join("\n");
  loadResourcePrefs();
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
      view: currentViewFields(),
    });
    say(`View saved: ${name}`);
    $("view-name").value = "";
    await openViewsDialog();
  } catch (error) {
    say(error.message, true);
  }
}

/* The grid state a saved view keeps: the same fields the desktop's view carries. */
function currentViewFields() {
  return {
    search: state.search,
    filters: state.filters,
    expression: state.expression,
    groups: state.groups,
    interval: state.interval,
    sort: state.sort,
    descending: state.descending,
    sort_type: state.sortType,
    sorts: state.multiSort.map((key) => ({ column: key.column, descending: key.descending, kind: key.kind || state.sortType })),
    bookmarks_only: state.bookmarksOnly,
    highlight: state.highlight || "",
    summaries: state.summaries,
    total_summaries: state.totalSummaries,
    footer_mode: state.footerMode,
    show_total: state.showTotal,
    order: state.order,
    order_descending: state.orderDesc !== false,
    order_summary: state.orderSummary || 0,
  };
}

function applyViewFields(view) {
  state.search = view.search || "";
  $("search").value = state.search;
  state.filters = (view.filters || []).map((item) => ({ column: item.column, operator: item.operator, value: item.value }));
  state.expression = view.expression && view.expression.children && view.expression.children.length ? view.expression : null;
  state.groups = view.groups || [];
  state.interval = view.interval || "";
  state.path = [];
  state.sortType = ["text", "number", "timestamp"].includes(view.sort_type) ? view.sort_type : "text";
  state.multiSort = (view.sorts || []).length && (view.sorts || []).length > 1
    ? view.sorts.map((key) => ({ column: key.column, descending: key.descending, kind: key.kind }))
    : [];
  state.sort = view.sort === undefined || view.sort === null ? null : view.sort;
  state.descending = Boolean(view.descending);
  state.bookmarksOnly = Boolean(view.bookmarks_only);
  state.highlight = view.highlight || "";
  state.summaries = (view.summaries || []).map((item) => ({ ...item }));
  state.totalSummaries = (view.total_summaries || []).map((item) => ({ ...item }));
  state.footerMode = view.footer_mode || "hidden";
  state.showTotal = view.show_total !== false;
  state.order = view.order || "";
  state.orderDesc = view.order_descending !== false;
  state.orderSummary = view.order_summary || 0;
  $("bookmarks-only").classList.toggle("active", state.bookmarksOnly);
}

async function applyView(name) {
  try {
    const view = await api(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/views/${encodeURIComponent(name)}`);
    applyViewFields(view);
    closeModals();
    await loadRows(true);
    say(`View applied: ${name}`);
  } catch (error) {
    say(error.message, true);
  }
}

/* ---------- colour rules ---------- */

let rulesCache = [];
let globalRules = null;      // what the shared book says, once, for every analysis
let rulesScope = "analysis";

/* Which rule paints a row is the core's answer, not the page's: the server evaluates every rule
   with the evaluator the desktop's grid uses (`state.styles`, the rows each rule matched, and
   `state.ruleSet`, what each one paints), so an operator means what it means in the desktop. */

/* The values of a column, as the desktop's rules dialog charts them: the shape of
   the data first, the rule second. Clicking a bar fills the value field. */
async function loadRuleValues() {
  if (!state.openCase || !state.columns.length) return;
  const column = Number($("rule-column").value);
  if (!Number.isInteger(column) || column < 0) return;
  const box = $("rule-values");
  box.innerHTML = '<div class="emptygrid">Reading the values…</div>';
  try {
    const params = new URLSearchParams({ offset: "0", limit: "12" });
    params.append("group", String(column));
    const payload = await api(
      `/api/cases/${state.openCase.id}/analyses/${state.analysis}/rows?${params}`);
    const rows = (payload.rows || []).map((row) => ({ value: row[0], count: Number(row[1]) || 0 }));
    const peak = Math.max(1, ...rows.map((row) => row.count));
    box.innerHTML = rows.map((row) => {
      const text = row.value === null || row.value === "" ? "(empty)" : String(row.value);
      return `<div class="value-bar" data-value="${escapeHtml(text)}" title="${escapeHtml(text)}">
        <span class="value-name">${escapeHtml(text)}</span>
        <span class="value-track"><span style="width:${Math.round((row.count / peak) * 100)}%"></span></span>
        <span class="value-count">${row.count}</span></div>`;
    }).join("") || '<div class="emptygrid">No value in this column.</div>';
    box.querySelectorAll(".value-bar").forEach((node) => {
      node.addEventListener("click", () => {
        $("rule-value").value = node.dataset.value;
        $("rule-value").focus();
      });
    });
    $("rule-values-note").textContent =
      `${rows.length} most frequent value(s) of ${state.columns[column + 1] || "this column"}`
      + " — click one to use it";
  } catch (error) {
    box.innerHTML = "";
    $("rule-values-note").textContent = error.message;
  }
}

async function loadRules() {
  if (!state.openCase) return;
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/rules`);
    rulesCache = payload.rules || [];
    renderGrid();
    renderRulesList();  // the list follows the grid at once, not after the shared rules are read
  } catch (_) {
    rulesCache = [];
  }
  await loadGlobalRules();
}

async function loadGlobalRules() {
  if (!state.openCase) return;
  try {
    globalRules = await api(
      `/api/global-rules?identifier=${encodeURIComponent(state.openCase.id)}&index=${state.analysis}`);
  } catch (_) {
    globalRules = null;
  }
}

function analysisColumnOptions() {
  $("rule-column").innerHTML = state.columns.slice(1)
    .map((name, index) => `<option value="${index}">${escapeHtml(name)}</option>`).join("");
}

function openRulesDialog() {
  if (!state.columns.length) { say("Open an analysis first", true); return; }
  setTimeout(loadRuleValues, 0);
  $("rules-modal").classList.add("show");
  showRulesScope("analysis");
  loadGlobalRules().then(() => {
    if (rulesScope === "global") showRulesScope("global");
    else renderRulesList();
  });
}

function showRulesScope(scope) {
  rulesScope = scope;
  document.querySelectorAll(".subtab[data-scope]").forEach((tab) =>
    tab.classList.toggle("active", tab.dataset.scope === scope));
  $("rule-global-row").style.display = scope === "global" ? "flex" : "none";
  if (scope === "global") {
    // The book names its columns: a name travels between analyses, an index does not.
    const names = [...new Set([...((globalRules && globalRules.book_headers) || []),
                               ...state.columns.slice(1)])];
    $("rule-column").innerHTML = names
      .map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
    $("rule-global-enabled").checked = !globalRules || globalRules.enabled !== false;
  } else {
    analysisColumnOptions();
  }
  renderRulesList();
}

function ruleColumnName(rule) {
  if (rulesScope === "global") {
    return rule.column_name
      || (globalRules && (globalRules.book_headers || [])[rule.column]) || "";
  }
  return state.columns[rule.column + 1] || "";
}

function renderRulesList() {
  const list = rulesScope === "global" ? ((globalRules && globalRules.rules) || []) : rulesCache;
  // A rule is read as a sentence: the operator's own name, and a value only when it
  // means something (an empty one printed as "" was noise).
  $("rules-list").innerHTML = list.map((rule, index) => `
    <label><span class="swatch" style="background:${rule.background};width:12px;height:12px;display:inline-block;border:1px solid #999"></span>
      <span>${escapeHtml(ruleSentence(rule))}</span>
      <span class="pin"><button class="btn" data-rule-remove="${index}">Remove</button></span></label>`).join("")
    || `<div class="emptygrid">${rulesScope === "global"
        ? "No shared rule yet: a column absent from an analysis simply skips its rule."
        : "No rule yet."}</div>`;
  if (rulesScope === "global") {
    const skipped = (globalRules && globalRules.skipped) || [];
    $("rules-note").textContent = globalRules
      ? `${globalRules.stored} shared rule(s); ${globalRules.applied} applied to this analysis`
        + (skipped.length ? `; ${skipped.length} skipped — ${skipped.slice(0, 2).join(" · ")}` : "")
        + (globalRules.error ? ` — unreadable: ${globalRules.error}` : "")
      : "Shared rules not loaded yet.";
  } else {
    $("rules-note").textContent = rulesCache.length
      ? `${rulesCache.length} rule(s) for this analysis only` : "No rule for this analysis yet.";
  }
  $("rules-list").querySelectorAll("[data-rule-remove]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (rulesScope === "global") {
        const kept = ((globalRules && globalRules.rules) || []).slice();
        kept.splice(Number(button.dataset.ruleRemove), 1);
        await persistGlobalRules(kept);
      } else {
        rulesCache.splice(Number(button.dataset.ruleRemove), 1);
        await persistRules();
      }
      renderRulesList();
    });
  });
}

async function persistGlobalRules(rules) {
  await apiPut("/api/global-rules", {
    rules, headers: (globalRules && globalRules.case_headers) || state.columns.slice(1) });
  await loadGlobalRules();
  await refreshPaint();
}

/* A rule changed: ask the server again which rule each row of this page answers to. The selection,
   the notes and the page itself stay as they are. */
async function refreshPaint() {
  if (!state.openCase || !state.columns.length || state.grouped) { renderGrid(); return; }
  try {
    const payload = await api(rowsUrl());
    state.styles = payload.styles || {};
    state.ruleSet = payload.rule_set || [];
    renderGrid();
  } catch (error) {
    say(error.message, true);
  }
}

async function persistRules() {
  const response = await fetch(url(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/rules`),
    { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rules: rulesCache }) });
  if (!response.ok) throw new Error((await response.json()).detail || response.statusText);
  // Read the rules back, then the page again: the server resolves a statistic and decides which
  // rule each row answers to, and the grid only paints what it is told.
  await loadRules();
  await refreshPaint();
}

/* The comparisons a rule can make are the core's own list, the one the advanced filter offers:
   written once, and the sentence of a rule reads them lower-cased ("Event equals (exact) 4625"). */
const RULE_OPERATORS = Object.fromEntries(EXPR_OPERATORS
  .filter(([code]) => code !== "expression")
  .map(([code, label]) => [code, label.charAt(0).toLowerCase() + label.slice(1)]));

function populateRuleOperators() {
  $("rule-operator").innerHTML = Object.entries(RULE_OPERATORS).map(([code, label]) =>
    `<option value="${code}">${escapeHtml(label)}</option>`).join("");
}

function conditionSentence(node) {
  if (!node) return "";
  if (Array.isArray(node.children)) {
    const parts = node.children.map((child) => conditionSentence(child)).filter(Boolean);
    if (!parts.length) return "";
    const joiner = node.logic === "or" ? " or " : (node.logic === "not" ? " and not " : " and ");
    return parts.length === 1 ? parts[0] : `(${parts.join(joiner)})`;
  }
  const column = state.columns[node.column + 1] || `column ${node.column + 1}`;
  const operator = RULE_OPERATORS[node.operator] || node.operator;
  const value = String(node.value ?? "").trim();
  if (!value || node.operator === "empty" || node.operator === "not_empty") return `${column} ${operator}`;
  return `${column} ${operator} “${value}”`;
}

function ruleSentence(rule) {
  if (rule.condition) {
    const text = conditionSentence(rule.condition);
    const visual = rule.visual && rule.visual !== "none" ? ` — ${rule.visual}` : "";
    return text ? `${text}${visual}` : "no condition";
  }
  const column = ruleColumnName(rule);
  const operator = RULE_OPERATORS[rule.operator] || rule.operator;
  const value = String(rule.value === null || rule.value === undefined ? "" : rule.value).trim();
  const visual = rule.visual && rule.visual !== "none" ? ` — ${rule.visual}` : "";
  if (!value || rule.operator === "empty" || rule.operator === "not_empty") {
    return `${column} ${operator}${visual}`;
  }
  return `${column} ${operator} “${value}”${visual}`;
}

function showRuleVisual() {
  const visual = $("rule-visual").value;
  $("rule-visual-row").style.display = visual === "none" ? "none" : "";
  $("rule-icon-row").style.display = visual === "icon" ? "" : "none";
  $("rule-middle-label").style.display = visual === "scale3" ? "" : "none";
  $("rule-middle-value").style.display = visual === "scale3" ? "" : "none";
  $("rule-middle-colour").style.display = visual === "scale3" ? "" : "none";
  $("rule-middle-colour-label").style.display = visual === "scale3" ? "" : "none";
  // The middle value and its colour speak only to a three-colour scale; a bar and
  // an icon set read one direction, from the minimum to the maximum.
  const middle = visual === "scale3";
  $("rule-middle-label").style.display = middle ? "" : "none";
  $("rule-middle-value").style.display = middle ? "" : "none";
  // A data bar reads a scale in one direction; three colours need a middle.
}

/* A group is edited as rows: each row is one comparison, and the group's logic says
   how they combine — the desktop's "Add a subgroup" and its AND / OR / NOT. */
function conditionRows() {
  return [...$("rule-conditions").querySelectorAll("[data-condition]")].map((row) => ({
    column: Number(row.querySelector("[data-cond-column]").value),
    operator: row.querySelector("[data-cond-operator]").value,
    value: row.querySelector("[data-cond-value]").value,
  }));
}

function addConditionRow() {
  const row = document.createElement("div");
  row.className = "row";
  row.dataset.condition = "1";
  row.innerHTML = `<select data-cond-column aria-label="Additional rule column">${state.columns.slice(1).map((name, index) =>
      `<option value="${index}">${escapeHtml(name)}</option>`).join("")}</select>
    <select data-cond-operator aria-label="Additional rule operator">${Object.entries(RULE_OPERATORS).map(([value, label]) =>
      `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`).join("")}</select>
    <input data-cond-value placeholder="value">
    <button class="btn" data-condition-remove="1">Remove</button>`;
  row.querySelector("[data-condition-remove]").addEventListener("click", () => {
    row.remove();
    $("rule-logic").value = $("rule-conditions").children.length ? $("rule-logic").value : "single";
  });
  $("rule-conditions").append(row);
}

function ruleConditionPayload(flat) {
  const logic = $("rule-logic").value;
  const extra = conditionRows();
  if (logic === "single" || !extra.length) return null;
  // The core's NOT takes one child: "none of them" is NOT over an OR of the comparisons.
  if (logic === "not") return { logic: "not", children: [{ logic: "or", children: [flat, ...extra] }] };
  return { logic, children: [flat, ...extra] };
}

async function addRule() {
  const columnValue = $("rule-column").value;
  const rule = {
    column: rulesScope === "global" ? columnValue : Number(columnValue),
    operator: $("rule-operator").value,
    value: $("rule-value").value,
    background: $("rule-colour").value,
    foreground: $("rule-ink").value,
    bold: $("rule-bold").checked,
    italic: $("rule-italic").checked,
    underline: $("rule-underline").checked,
    strikeout: $("rule-strikeout").checked,
    font_family: $("rule-font-family").value.trim(),
    font_size: Number($("rule-font-size").value) || 0,
    use_background: $("rule-use-background").checked,
    use_foreground: $("rule-use-foreground").checked,
    use_font: $("rule-use-font").checked,
    stop_if_true: $("rule-stop").checked,
    stat_percent: $("rule-stat-percent").checked,
    stat_include_null: $("rule-stat-null").checked,
    all_source_rows: $("rule-stat-all").checked,
    draw_axis: $("rule-axis").checked,
    axis_color: $("rule-axis-colour").value,
    // "This cell only" is the column of the rule, by name for a shared rule and by index here.
    target: $("rule-target").value !== "cell" ? null
      : (rulesScope === "global" ? columnValue : Number(columnValue)),
    enabled: true,
    condition: null,
    statistic: $("rule-statistic").value || "",
    stat_rank: $("rule-stat-rank").value || "10",
    visual: $("rule-visual").value,
    bound_mode: $("rule-bound").value,
    minimum: $("rule-min").value || "0",
    maximum: $("rule-max").value || "100",
    middle_value: $("rule-middle-value").value || "50",
    middle_color: $("rule-middle-colour").value,
    negative_color: $("rule-negative").value,
    icon_thresholds: $("rule-icon-thresholds").value.split(",").map((item) => item.trim()).filter(Boolean),
    icon_threshold_mode: $("rule-icon-mode").value,
    icon_colors: $("rule-icon-colours").value.split(",").map((item) => item.trim()).filter(Boolean),
  };
  // The whole group travels as one condition tree, and the flat fields stay for the
  // server's own validation and for a client that only reads them.
  // A comparison with nothing to compare would match every row: it is refused, not saved.
  const open = (item) => !["empty", "not_empty"].includes(item.operator) && !String(item.value).trim();
  if (open(rule) || conditionRows().some(open)) {
    say("Give every condition of the rule a value", true);
    return;
  }
  const tree = ruleConditionPayload({ column: Number(columnValue), operator: rule.operator,
                                       value: rule.value });
  if (tree) rule.condition = tree;
  if (rulesScope === "global") {
    try {
      await persistGlobalRules([...((globalRules && globalRules.rules) || []), rule]);
      renderRulesList();
      clearConditionRows();
      say("Shared rule saved: every analysis with that column will use it");
    } catch (error) {
      say(error.message, true);
    }
    return;
  }
  rulesCache.push(rule);
  try {
    await persistRules();
    renderRulesList();
    clearConditionRows();
  } catch (error) {
    rulesCache.pop();
    say(error.message, true);
  }
}

/* The extra comparisons belong to the rule just added: the next rule starts from one. */
function clearConditionRows() {
  $("rule-conditions").innerHTML = "";
  $("rule-logic").value = "single";
}

/* ---------- process pivot ---------- */

let contextRow = null;

async function runPivot() {
  if (!contextRow) return;
  const rowId = contextRow.dataset.row;
  $("row-menu").hidden = true;
  try {
    const response = await fetch(url(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/pivot`),
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
async function checkDerivedColumns() {
  if (!state.columns.length || state.analysis === null || state.analysis === undefined) {
    say("Open an analysis first", true); return;
  }
  const list = $("derived-check-list");
  try {
    const found = await api(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/derived`);
    const rows = found.derived || [];
    list.className = rows.length ? "" : "muted";
    list.innerHTML = rows.length
      ? "<ul>" + rows.map((item) => `<li><b>${escapeHtml(item.name || "")}</b> — `
          + `${escapeHtml(item.operation || "")} `
          + `<span class="muted">${escapeHtml(item.source || item.column || "")}</span></li>`).join("") + "</ul>"
      : "No derived columns.";
  } catch (error) {
    list.className = "muted";
    list.textContent = `The derived columns cannot be read: ${error.message}`;
  }
  $("derived-check-modal").classList.add("show");
}

let derivedOptions = null;

async function openDerivedDialog() {
  if (!state.columns.length) { say("Open an analysis first", true); return; }
  const columns = state.columns.slice(1)
    .map((name, index) => `<option value="${index}">${escapeHtml(name)}</option>`).join("");
  $("derived-source").innerHTML = columns;
  $("derived-time").innerHTML = `<option value="">(date and time in the same column)</option>${columns}`;
  $("derived-name").value = "";
  $("derived-expression").value = "";
  $("derived-operation").value = "timestamp";
  derivedOperationChanged();
  try {
    // The formats and the zones are the core's own tables: written once, there.
    derivedOptions = derivedOptions || await api("/api/derived-options");
    $("derived-format").innerHTML = derivedOptions.formats.map((item) =>
      `<option value="${escapeHtml(item.code)}">${escapeHtml(item.label)}</option>`).join("");
    let browserZone = "";
    try { browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (_) { /* no Intl */ }
    const zones = [...new Set(["UTC", browserZone, ...derivedOptions.zones].filter(Boolean))];
    $("derived-zones").innerHTML = zones.map((zone) => `<option value="${escapeHtml(zone)}">`).join("");
  } catch (error) {
    say(error.message, true);
  }
  $("derived-modal").classList.add("show");
}

function derivedOperationChanged() {
  const timestamp = $("derived-operation").value === "timestamp";
  for (const row of ["source", "time", "format", "zone"]) {
    $(`derived-${row}-row`).style.display = timestamp ? "flex" : "none";
  }
  $("derived-expression-row").style.display = timestamp ? "none" : "flex";
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
    const columns = [state.columns[Number($("derived-source").value) + 1]];
    if ($("derived-time").value !== "") columns.push(state.columns[Number($("derived-time").value) + 1]);
    definition.columns = columns;
    definition.format = $("derived-format").value;
    definition.timezone = $("derived-zone").value.trim() || "UTC";
  }
  closeModals();
  try {
    const response = await fetch(url(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/derived`),
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

const importState = { collections: [], selected: null, collection: "", revision: 0 };

function resetImports() {
  Object.assign(importState, { collections: [], selected: null, collection: "", revision: importState.revision + 1 });
  $("imports-status").value = "";
  $("imports-search").value = "";
  renderImports();
}

async function loadImports() {
  if (!state.openCase) return;
  const { id } = state.openCase;
  const revision = ++importState.revision;
  try {
    const [collections, files] = await Promise.all([
      api(`/api/cases/${id}/imports`),
      api(`/api/cases/${id}/collection-files`),
    ]);
    if (revision !== importState.revision) return;
    const byCollection = new Map();
    for (const file of files.files || []) {
      if (!byCollection.has(file.collection)) byCollection.set(file.collection, []);
      byCollection.get(file.collection).push(file);
    }
    importState.collections = (collections.collections || []).map((collection) => ({
      ...collection,
      files: byCollection.get(collection.name) || collection.files || [],
    }));
    if (!importState.collections.length && (files.files || []).length) {
      importState.collections = [{ name: "", files: files.files }];
    }
    renderImports();
  } catch (error) {
    if (revision === importState.revision) say(error.message, true);
  }
}

/* The imports table is the desktop's: one row per collected file, its status, the
   readers that ran, the reason when it did not, and where its output went. */
function importReadState(file) {
  if (file.ignored) return "parked";
  if (file.status === "companion") return "companion";
  if (["complete", "duplicate"].includes(file.status)) return "read";
  return file.status === "attention" && Number(file.output_count) > 0 ? "partial" : "unread";
}

function renderImports() {
  const wanted = $("imports-status").value;
  const term = ($("imports-search").value || "").trim().toLowerCase();
  // What a file produced, when it produced an analysis: the desktop's "Outputs".
  const outputs = new Map();
  for (const analysis of (state.openCase && state.openCase.analyses) || []) {
    if (analysis.source) outputs.set(analysis.source, analysis.label);
  }
  const rows = [];
  let imported = 0, failed = 0, companions = 0, partial = 0, parked = 0;
  for (const collection of importState.collections) {
    for (const file of collection.files || []) {
      const readState = importReadState(file);
      if (readState === "parked") parked += 1;
      else if (readState === "companion") companions += 1;
      else if (readState === "read") imported += 1;
      else if (readState === "partial") partial += 1;
      else failed += 1;
      if (wanted === "ignored" ? !file.ignored : (wanted && file.status !== wanted)) continue;
      if (!wanted && file.ignored) continue;
      if (term && !`${file.name} ${file.path} ${file.reason} ${(file.tools || []).join(" ")}`
        .toLowerCase().includes(term)) continue;
      rows.push(`<tr data-import="${escapeHtml(file.path)}" data-collection="${escapeHtml(collection.name)}"
          class="${importState.selected === file.path ? "sel" : ""}">
        <td>${escapeHtml(file.status)}${file.ignored ? " · parked" : ""}</td>
        <td title="${escapeHtml(file.path)}">${escapeHtml(file.name)}</td>
        <td>${escapeHtml((file.tools || []).join(", "))}</td>
        <td title="${escapeHtml(file.reason)}">${escapeHtml(file.reason)}</td>
        <td title="${escapeHtml(file.sha256 || "")}">${escapeHtml(outputs.get(file.path) || file.outputs || "")}</td></tr>`);
    }
  }
  $("imports-rows").innerHTML = rows.length ? rows.join("")
    : '<tr><td colspan="5" class="cellnull">No collected file matches this filter.</td></tr>';
  $("imports-rows").querySelectorAll("tr[data-import]").forEach((row) => {
    row.addEventListener("click", () => {
      importState.selected = row.dataset.import;
      importState.collection = row.dataset.collection;
      renderImports();
    });
  });
  $("imports-summary").textContent =
    `${importState.collections.length} import(s) — ${imported} file(s) read, ${failed} not read`
    + (partial ? `, ${partial} partially read` : "")
    + (companions ? `, ${companions} companion file(s) read with their hive` : "")
    + (parked ? `, ${parked} parked` : "");
  if ($("imports-view").style.display !== "none") say($("imports-summary").textContent);
}

/* ---------- global search ---------- */

async function runGlobalSearch() {
  if (!state.openCase) { say("Open a case first", true); return; }
  const text = $("global-text").value.trim();
  if (!text) { say("Type something to search", true); return; }
  const scope = $("global-scope").value;
  const caseId = state.openCase.id;
  const revision = ++reviewSearchRevision;
  $("global-results").replaceChildren();
  $("global-summary").textContent = "Searching…";
  try {
    // A case of hundreds of analyses takes a while: it runs as a job, with progress and a Stop.
    const payload = scope === "library"
      ? await runTask("search-library", { text }, "Search across cases")
      : state.openCase.analyses.length > 40
        ? await runTask("search", { text }, "Search this case")
        : await api(`/api/cases/${caseId}/search?text=${encodeURIComponent(text)}&limit=8`);
    if (revision !== reviewSearchRevision || state.openCase?.id !== caseId) return;
    $("search-modal").classList.add("show");
    if (!payload) { $("global-summary").textContent = "Search stopped"; return; }
    renderReviewSearch(payload, scope);
  } catch (error) {
    if (revision === reviewSearchRevision && state.openCase?.id === caseId) {
      $("global-summary").textContent = error.message;
      $("search-modal").classList.add("show");
    }
  }
}

// Enter in the box searches, as the field's own Search button does.
$("global-text").addEventListener("keydown", (event) => {
  if (event.key === "Enter") { event.preventDefault(); runGlobalSearch(); }
});

/* ---------- actions and tracking ---------- */

const actionState = { items: [], shown: [], selected: null, revision: 0 };

const workspaceState = { entities: [], indicators: [], selected: null };

function resetWorkspace() {
  resetTracking();
  Object.assign(actionState, { items: [], shown: [], selected: null, revision: actionState.revision + 1 });
  Object.assign(workspaceState, { entities: [], indicators: [], selected: null });
  stopEditingEntity();
  renderActions();
  renderEntities();
  renderIndicators();
}

async function loadActions() {
  if (!state.openCase) return;
  const { id, name } = state.openCase;
  const scope = $("action-scope").value;
  const revision = ++actionState.revision;
  try {
    const payload = await api(`/api/cases/${id}/workspace`);
    if (actionState.revision !== revision) return;
    let items = (payload.actions || []).map((item) => ({ ...item, _caseId: id, _caseName: name }));
    // "Every case of the library": the actions of each case, each marked with its own case.
    const clientName = (payload.client?.name || "").trim().toLowerCase();
    if (scope === "all" || (scope === "client" && clientName)) {
      const others = state.cases.filter((item) => item.id !== id && !item.storage_archive);
      const lists = await Promise.all(others.map(async (item) => {
        try {
          const other = await api(`/api/cases/${item.id}/workspace`);
          if (scope === "client" && (other.client?.name || "").trim().toLowerCase() !== clientName) {
            return [];
          }
          return (other.actions || []).map((action) => ({ ...action, _caseId: item.id, _caseName: item.name }));
        } catch (_) {
          return [];
        }
      }));
      if (actionState.revision !== revision) return;
      items = items.concat(...lists);
    }
    actionState.items = items;
    workspaceState.entities = payload.entities || [];
    workspaceState.indicators = payload.iocs || [];
    renderActions();
    renderEntities();
    renderIndicators();
  } catch (error) {
    if (actionState.revision === revision) say(error.message, true);
  }
}

function showWorkspaceSub(name) {
  if (document.querySelector(".subtab.active")?.dataset.sub !== name) rememberReviewPlace();
  document.querySelectorAll(".subtab[data-sub]").forEach((tab) =>
    tab.classList.toggle("active", tab.dataset.sub === name));
  for (const view of ["actions", "indicators", "entities", "tracking"]) {
    const box = $(`sub-${view}`);
    if (box) box.style.display = view === name ? "flex" : "none";
  }
  if (name === "tracking") refreshTracking();
}

function renderEntities() {
  $("entity-rows").innerHTML = workspaceState.entities.length
    ? workspaceState.entities.map((item) => `<tr data-entity="${escapeHtml(item.id)}">
        <td>${escapeHtml(item.kind || "")}</td>
        <td title="${escapeHtml(item.notes || "")}">${escapeHtml(item.label || "")}${(item.tags || []).some(tag => tag.toLowerCase() === "compromised") ? " · Compromised" : ""}</td>
        <td>${escapeHtml(item.hostname || "")}</td>
        <td>${escapeHtml(item.ip || "")}</td>
        <td>${escapeHtml(item.os || "")}</td>
        <td><button class="btn" data-entity-edit="${escapeHtml(item.id)}">Edit</button>
          <button class="btn" data-entity-remove="${escapeHtml(item.id)}">Remove</button></td></tr>`).join("")
    : '<tr><td colspan="6" class="cellnull">No machine or account declared in this case.</td></tr>';
  $("entity-rows").querySelectorAll("[data-entity-edit]").forEach((button) => {
    button.addEventListener("click", () => loadEntityForEdit(button.dataset.entityEdit));
  });
  $("entity-rows").querySelectorAll("[data-entity-remove]").forEach((button) => {
    button.addEventListener("click", () => removeEntity(button.dataset.entityRemove));
  });
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
        <td>${escapeHtml(item.status || "")}</td>
        <td>${(item.observations || []).map(origin =>
          `<div>${escapeHtml([origin.machine, observationSource(origin)].filter(Boolean).join(" · "))}</div>`
        ).join("")}</td></tr>`).join("")
    : '<tr><td colspan="5" class="cellnull">No indicator tracked in this case.</td></tr>';
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

/* The same form adds and changes: `editing` holds the id while a row is being
   corrected, and the button says which of the two it will do. */
let editingEntity = null;

function loadEntityForEdit(entityId) {
  const item = workspaceState.entities.find((entry) => entry.id === entityId);
  if (!item) return;
  editingEntity = entityId;
  $("entity-kind").value = item.kind || "machine";
  $("entity-label").value = item.label || "";
  $("entity-hostname").value = item.hostname || "";
  $("entity-ip").value = item.ip || "";
  $("entity-os").value = item.os || "";
  $("entity-notes").value = item.notes || "";
  $("entity-compromised").checked = (item.tags || []).some(tag => tag.toLowerCase() === "compromised");
  $("entity-add").textContent = "Save";
  $("entity-cancel").style.display = "";
  $("entity-label").focus();
}

function stopEditingEntity() {
  editingEntity = null;
  $("entity-label").value = "";
  $("entity-hostname").value = "";
  $("entity-ip").value = "";
  $("entity-os").value = "";
  $("entity-notes").value = "";
  $("entity-compromised").checked = false;
  $("entity-add").textContent = "Add";
  $("entity-cancel").style.display = "none";
}

async function removeEntity(entityId) {
  const item = workspaceState.entities.find((entry) => entry.id === entityId);
  const name = item ? `${item.kind} ${item.label}` : "this entry";
  if (!window.confirm(`Remove ${name} from the case?`)) return;
  try {
    await fetch(url(`/api/cases/${state.openCase.id}/entities/${encodeURIComponent(entityId)}`),
      { method: "DELETE" }).then(async (response) => {
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.detail || response.statusText);
        return payload;
      });
    await loadActions();
    say(`${name} removed from the case`);
    if (editingEntity === entityId) stopEditingEntity();
  } catch (error) {
    say(error.message, true);
  }
}

async function addEntity() {
  if (!state.openCase) { say("Open a case first", true); return; }
  const label = $("entity-label").value.trim();
  if (!label) { say("Give the machine or the account a name", true); return; }
  const previous = workspaceState.entities.find(entry => entry.id === editingEntity);
  const tags = (previous?.tags || []).filter(tag => tag.toLowerCase() !== "compromised");
  if ($("entity-compromised").checked) tags.push("compromised");
  const fields = {
    kind: $("entity-kind").value, label, tags,
    notes: $("entity-notes").value.trim(),
    hostname: $("entity-hostname").value.trim(),
    ip: $("entity-ip").value.trim(),
    os: $("entity-os").value.trim(),
  };
  try {
    if (editingEntity) {
      const response = await fetch(url(
        `/api/cases/${state.openCase.id}/entities/${encodeURIComponent(editingEntity)}`),
        { method: "PATCH", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(fields) });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || response.statusText);
      stopEditingEntity();
      await loadActions();
      say(`${fields.kind} updated: ${fields.label}`);
      return;
    }
    const payload = await apiPost(`/api/cases/${state.openCase.id}/entities`, fields);
    stopEditingEntity();
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

/* The actions on screen: the scope, the free text and "open only", as the desktop
   filters them — the same three questions, in the same place. */
function shownActions() {
  const term = ($("action-search").value || "").trim().toLowerCase();
  const openOnly = $("action-open-only").checked;
  return actionState.items.filter((item) => {
    if (openOnly && (item.status === "done" || item.status === "cancelled")) return false;
    if (!term) return true;
    return [item.title, item.detail, item.owner, item.machine, item.reference,
            item.intervenant, item.type].join(" ").toLowerCase().includes(term);
  });
}

// What a code stored in the case reads as on screen; an unknown code is shown as it is.
const ACTION_TEXT = {
  owner: { us: "Our team", client: "Client", third_party: "Third party", vendor: "Vendor",
           unassigned: "Unassigned" },
  status: { todo: "To do", in_progress: "In progress", waiting_client: "Waiting for the client",
            waiting_us: "Waiting on our side", blocked: "Blocked", done: "Done", cancelled: "Cancelled" },
  priority: { low: "Low", medium: "Medium", high: "High", critical: "Critical" },
  type: { collect: "Collection", analysis: "Analysis", remediation: "Remediation",
          coordination: "Coordination", meeting: "Meeting", report: "Report",
          destruction: "Destruction", legal: "Legal", other: "Other" },
};

function actionText(kind, code) {
  return (ACTION_TEXT[kind] && ACTION_TEXT[kind][code]) || code || "";
}

function renderActions() {
  const items = shownActions();
  actionState.shown = items;
  const everywhere = $("action-scope").value !== "case";
  const person = (item) => (item.intervenant || actionText("owner", item.owner))
    + (everywhere && item._caseName ? ` · ${item._caseName}` : "");
  $("action-rows").innerHTML = items.length ? items.map((item) => `
    <tr data-action="${escapeHtml(item.id)}" class="${actionState.selected === item.id ? "sel" : ""}">
      <td>${escapeHtml(item.date || "")}</td>
      <td>${escapeHtml(item.due || "")}</td>
      <td>${escapeHtml(actionText("priority", item.priority))}</td>
      <td>${escapeHtml(actionText("status", item.status))}</td>
      <td>${escapeHtml(actionText("type", item.type))}</td>
      <td>${escapeHtml(person(item))}</td>
      <td title="${escapeHtml(item.detail || "")}">${escapeHtml(item.title || "")}</td>
      <td><button class="btn" data-action-close="${escapeHtml(item.id)}">${
        item.status === "done" ? "Reopen" : "Done"}</button></td>
    </tr>`).join("") : '<tr><td colspan="8" class="cellnull">No action recorded in this scope.</td></tr>';
  $("action-rows").querySelectorAll("tr[data-action]").forEach((row) => {
    row.addEventListener("click", (event) => {
      const button = event.target.closest("[data-action-close]");
      if (button) { toggleAction(button.dataset.actionClose); return; }
      actionState.selected = row.dataset.action;
      renderActions();
    });
    row.addEventListener("dblclick", () => openActionEditor(row.dataset.action));
  });
  const open = actionState.items.filter((item) => item.status !== "done" && item.status !== "cancelled").length;
  const overdue = actionState.items.filter((item) => {
    if (!item.due || item.status === "done" || item.status === "cancelled") return false;
    return String(item.due) < new Date().toISOString().slice(0, 10);
  }).length;
  const scope = { all: "every case", client: "the same client", case: "the open case" }[$("action-scope").value];
  $("action-summary").textContent = `${actionState.items.length} action(s) · ${open} open · `
    + `${overdue} overdue · ${scope}`
    + (items.length ? "" : " · No action recorded in this scope.");
}

async function removeActionRow(actionId) {
  const item = actionState.items.find((entry) => entry.id === actionId);
  const title = item ? item.title : "this action";
  if (!window.confirm(`Remove "${title}" from the case?`)) return;
  try {
    const response = await fetch(url(
      `/api/cases/${(item && item._caseId) || state.openCase.id}/actions/${encodeURIComponent(actionId)}`),
      { method: "DELETE" });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || response.statusText);
    await loadActions();
    say(`Action removed: ${title}`);
  } catch (error) {
    say(error.message, true);
  }
}

async function addAction() {
  const title = $("action-title").value.trim();
  if (!title) { say("An action needs a title", true); return; }
  try {
    await apiPost(`/api/cases/${state.openCase.id}/actions`, {
      title, owner: $("action-owner").value, priority: $("action-priority").value,
      type: $("action-type").value,
    });
    $("action-title").value = "";
    await loadActions();
    say("Action added");
  } catch (error) {
    say(error.message, true);
  }
}

/* Every field of an action, as the desktop's action window has them. */
let editingAction = null;

function openActionEditor(actionId) {
  const item = actionState.items.find((entry) => entry.id === (actionId || actionState.selected));
  if (!item) { say("Select an action first", true); return; }
  editingAction = item;
  $("action-modal-title").textContent = `Action — ${item.title || ""}`;
  $("ae-title").value = item.title || "";
  $("ae-status").value = item.status || "todo";
  $("ae-priority").value = item.priority || "medium";
  $("ae-type").value = item.type || "other";
  $("ae-owner").value = item.owner || "unassigned";
  $("ae-person").value = item.intervenant || "";
  $("ae-machine").value = item.machine || "";
  $("ae-date").value = item.date || "";
  $("ae-due").value = item.due || "";
  $("ae-reference").value = item.reference || "";
  $("ae-detail").value = item.detail || "";
  $("action-modal").classList.add("show");
}

async function saveActionEditor() {
  if (!editingAction) return;
  const title = $("ae-title").value.trim();
  if (!title) { say("An action needs a title", true); return; }
  const fields = {
    title, status: $("ae-status").value, priority: $("ae-priority").value, type: $("ae-type").value,
    owner: $("ae-owner").value, intervenant: $("ae-person").value.trim(),
    machine: $("ae-machine").value.trim(), date: $("ae-date").value, due: $("ae-due").value,
    reference: $("ae-reference").value.trim(), detail: $("ae-detail").value,
  };
  const target = editingAction;
  try {
    await apiPatch(`/api/cases/${target._caseId || state.openCase.id}/actions/${target.id}`, fields);
    closeModals();
    await loadActions();
    say(`Action saved: ${title}`);
  } catch (error) {
    say(error.message, true);
  }
}

async function toggleAction(actionId) {
  const item = actionState.items.find((entry) => entry.id === actionId);
  if (!item) return;
  try {
    await apiPatch(`/api/cases/${item._caseId || state.openCase.id}/actions/${actionId}`,
      { status: item.status === "done" ? "todo" : "done" });
    await loadActions();
  } catch (error) {
    say(error.message, true);
  }
}

/* ---------- IOC hunting ---------- */

const iocState = { hits: [], summary: "", rejected: [], hunt: null, list: [], count: 0, offset: 0, pageSize: 250, selected: null, payload: null, revision: 0 };

function resetIoc() {
  resetIocGrouping();
  Object.assign(iocState, { hits: [], summary: "", rejected: [], hunt: null, list: [], count: 0, offset: 0,
    pageSize: 250, selected: null, payload: null, revision: iocState.revision + 1 });
  $("ioc-input").value = "";
  $("ioc-summary").textContent = "Nothing scanned yet.";
  $("ioc-history").innerHTML = '<option value="">Saved hunts…</option>';
  renderIoc();
}

/* What the grid shows, for the commands that "respect the filter": the page keeps the search,
   the column filters and the advanced filter, so it tells the server which they are. */
function liveView() {
  return {
    index: state.analysis, search: state.search, filters: state.filters,
    expression: state.expression && (state.expression.children || []).length ? state.expression : null,
    bookmarks_only: state.bookmarksOnly,
  };
}

function iocOptions() {
  return {
    all: $("ioc-all").checked,
    filters: $("ioc-filters").checked,
    subdomains: $("ioc-subdomains").checked,
    limit: Number($("ioc-limit").value) || 250000,
    index: state.analysis,
    live: liveView(),
  };
}

function iocSummary(payload) {
  const state_ = { complete: "Complete", partial: "Partial", running: "Unfinished — run it again" }[payload.status] || "Unknown state";
  let text = `${state_} · ${Number(payload.scanned).toLocaleString("en-US")} rows read · ${Number(payload.matching_fields).toLocaleString("en-US")} matching fields · ${Number(payload.stored_hits).toLocaleString("en-US")} details kept.`;
  if (payload.truncated) text += " Details limited: the counters cover the whole reading.";
  text += payload.respect_filters ? " Scope: the saved filters." : " Scope: every row of the analyses read.";
  text += ` ${payload.rejected || 0} IOC(s) rejected.`;
  if ((payload.errors || []).length) text += " " + payload.errors.map((item) => `${item.path}: ${item.error}`).join(" ; ");
  return text;
}

/* A hunt, as the desktop shows it: the indicators with their counters, then one page of details. */
function applyHunt(payload) {
  resetIocGrouping();
  iocState.payload = payload;
  iocState.rejected = payload.rejected_lines || [];
  iocState.hunt = payload.hunt;
  iocState.list = payload.list || [];
  iocState.hits = payload.hits || [];
  iocState.count = payload.count || 0;
  iocState.offset = payload.offset || 0;
  iocState.pageSize = payload.page_size || 250;
  iocState.selected = payload.selected || null;
  $("ioc-summary").textContent = iocSummary(payload);
  say($("ioc-summary").textContent);
  renderIoc();
}

async function iocPage(delta, ioc) {
  if (!iocState.hunt || !state.openCase) { say("Hunt first", true); return; }
  const revision = ++iocState.revision;
  const selected = ioc === undefined ? iocState.selected : ioc;
  const offset = ioc === undefined ? Math.max(0, iocState.offset + delta) : 0;
  const params = new URLSearchParams({ offset: String(offset) });
  if (selected) params.set("ioc", String(selected));
  if (ioc !== undefined) iocGrouping.path = [];
  for (const field of iocGrouping.levels) params.append("groups", field);
  if (iocGrouping.path.length) params.set("group_path", JSON.stringify(iocGrouping.path));
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/hunts/${iocState.hunt}?${params}`);
    if (revision !== iocState.revision) return;
    iocState.hits = payload.hits || [];
    iocState.groups = payload.groups;
    iocState.groupSources = payload.group_sources || {};
    iocState.count = payload.count;
    iocState.offset = payload.offset;
    iocState.selected = selected || null;
    renderIoc();
  } catch (error) {
    if (revision === iocState.revision) say(error.message, true);
  }
}

async function stopIocHunt() {
  if (!state.openCase) return;
  try {
    const payload = await apiPost(`/api/cases/${state.openCase.id}/ioc-stop`, {});
    say(payload.stopped ? "Hunt interrupted: incomplete results are discarded; previous saved hunts stay" : "No hunt is running", !payload.stopped && false);
  } catch (error) {
    say(error.message, true);
  }
}

function exportHunt(summary) {
  if (!state.openCase || !iocState.hunt) { say("Nothing to export: hunt first", true); return; }
  downloadFrom(`/api/cases/${state.openCase.id}/hunts/${iocState.hunt}/export?summary=${summary ? "true" : "false"}`);
  say(summary ? "Hunt summary exported" : "Hunt details exported");
}

async function runIocScan() {
  if (!state.openCase) { say("Open a case first", true); return; }
  const text = $("ioc-input").value;
  if (!text.trim()) { say("Paste at least one indicator", true); return; }
  const revision = ++iocState.revision;
  try {
    const payload = await runTask("scan", { text, ...iocOptions() }, "IOC hunting");
    if (!payload || revision !== iocState.revision) return;
    applyHunt(payload);
    loadHuntHistory();
  } catch (error) {
    if (revision !== iocState.revision) return;
    say(error.message, true);
    $("ioc-summary").textContent = error.message;
  }
}

/* "Import TXT / CSV / TSV": the list is read and put in the box, normalised; the hunt is a separate gesture. */
async function runIocFile(file) {
  if (!state.openCase || !file) return;
  const { id } = state.openCase;
  const body = new FormData();
  body.append("file", file);
  say(`Reading ${file.name}…`);
  try {
    const response = await fetch(url(`/api/cases/${id}/ioc-list`), { method: "POST", body });
    const payload = await response.json();
    if (state.openCase?.id !== id) return;
    if (!response.ok) throw new Error(payload.detail || response.statusText);
    $("ioc-input").value = payload.text;
    const refused = (payload.rejected || []).map((item) => `Line ${item.line}: ${item.reason}`).join(" ; ");
    const message = `${payload.valid} valid IOC(s) · ${payload.duplicates} duplicate(s) · ${payload.rejected_total} line(s) rejected. ${refused}`;
    $("ioc-summary").textContent = message;
    say(message);
  } catch (error) {
    if (state.openCase?.id !== id) return;
    say(error.message, true);
    $("ioc-summary").textContent = error.message;
  }
}

async function loadHuntHistory() {
  if (!state.openCase) return;
  const { id } = state.openCase;
  try {
    const payload = await api(`/api/cases/${id}/hunts`);
    if (state.openCase?.id !== id) return;
    $("ioc-history").innerHTML = '<option value="">Saved hunts…</option>' +
      payload.hunts.map((hunt) => `<option value="${escapeHtml(hunt.name)}">${escapeHtml(hunt.started)} · ${hunt.hits} hit(s) · ${escapeHtml(hunt.status)}</option>`).join("");
  } catch (_) { /* an empty list is not an error worth a banner */ }
}

async function openHunt(name) {
  if (!state.openCase || !name) return;
  const revision = ++iocState.revision;
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/hunts/${encodeURIComponent(name)}`);
    if (revision !== iocState.revision) return;
    $("ioc-input").value = payload.text || "";
    applyHunt(payload);
  } catch (error) {
    if (revision === iocState.revision) say(error.message, true);
  }
}

/* Every non-empty line of the box is an indicator: `value`, or `type,value,label` when
   a CSV line names them, which is the shape the desktop accepts too. */
function iocLines() {
  const rows = [];
  for (const raw of ($("ioc-input").value || "").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) continue;
    const parts = line.split(",").map((part) => part.trim());
    if (parts.length >= 3 && /^(ip|domain|url|hash|md5|sha1|sha256)$/i.test(parts[0])) {
      rows.push({ kind: parts[0].toLowerCase(), value: parts[1], label: parts.slice(2).join(",") });
    } else {
      rows.push({ kind: "", value: parts[0], label: parts.slice(1).join(",") });
    }
  }
  return rows;
}

function iocKind(value) {
  const text = String(value || "");
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(text)) return "ip";
  if (/^[0-9a-f]{32}$/i.test(text)) return "md5";
  if (/^[0-9a-f]{40}$/i.test(text)) return "sha1";
  if (/^[0-9a-f]{64}$/i.test(text)) return "sha256";
  if (/^https?:\/\//i.test(text)) return "url";
  if (/^[\w.-]+\.[a-z]{2,}$/i.test(text)) return "domain";
  return "text";
}

function renderIoc() {
  // The list above the matches: what was asked, and what each indicator found.
  $("ioc-list-rows").innerHTML = iocState.list.length ? iocState.list.map((item) =>
    `<tr data-ioc="${item.id}" class="${iocState.selected === item.id ? "sel" : ""}" title="Show the details of this indicator">
      <td>${escapeHtml(item.kind_label || item.kind)}</td>
      <td title="${escapeHtml(item.original)}">${escapeHtml(item.original)}</td>
      <td title="${escapeHtml(item.value)}">${escapeHtml(item.value)}</td>
      <td>${escapeHtml(item.label || "")}</td>
      <td>${item.fields}</td><td>${item.rows}</td><td>${item.details}</td></tr>`).join("")
    : '<tr><td colspan="7" class="cellnull">Paste a list above, then Hunt.</td></tr>';
  // A line the parser refused is told apart from a line with no hit: it was not searched.
  $("ioc-list-rows").innerHTML += iocState.rejected.map((item) =>
    `<tr title="${escapeHtml(item.reason)}"><td>—</td><td>${escapeHtml(item.value)}</td><td></td><td></td>
      <td>0</td><td>0</td><td>not searched: ${escapeHtml(item.reason)}</td></tr>`).join("");

  if (renderIocGrouped()) return;
  $("ioc-rows").innerHTML = iocState.hits.map((hit, position) =>
    `<tr data-hit="${position}" title="Double-click to open the source row">
     <td>${escapeHtml(hit.when || "")}</td>
     <td title="${escapeHtml(hit.original)}">${escapeHtml(hit.original)}</td>
     <td title="${escapeHtml(hit.analysis_label || "")}">${escapeHtml(hit.analysis_label || "this analysis")}</td>
     <td class="rowid">${escapeHtml(String(hit.row_id))}</td>
     <td>${escapeHtml(hit.column_name || String(hit.column))}</td>
     <td title="${escapeHtml(hit.observed)}">${escapeHtml(hit.observed)}</td>
     <td title="${escapeHtml(hit.excerpt || "")}">${escapeHtml((hit.excerpt || "").slice(0, 160))}</td>
     <td>${escapeHtml(hit.rule)}</td></tr>`).join("")
    || '<tr><td colspan="8" class="cellnull">No hit.</td></tr>';
  const first = iocState.count ? iocState.offset + 1 : 0;
  $("ioc-status").textContent = `${first}–${iocState.offset + iocState.hits.length} / ${iocState.count} details`
    + (iocState.selected ? " (one indicator)" : "");
}

/* ---------- timeline ---------- */

const TIMELINE_COLORS = ["#2d9cdb", "#e6a23c", "#27ae82", "#bb6bd9", "#eb6577", "#56bfc4", "#9fa8da", "#b4a34a"];
const timelineState = { offset: 0, text: "", kind: "text", payload: null, dates: {},
                       row: null, source: null,
                       window: null, history: [], hidden: new Set(), start: null, end: null, seq: 0 };
/* The window is a pair of bucket indices, the selection a pair of times: the chart
   can be zoomed without touching the rows, and a duration is the analyst's filter. */

let sourceRowRequest = 0;

function resetTimeline() {
  sourceRowRequest++;
  Object.assign(timelineState, {
    offset: 0, text: "", kind: "text", payload: null, dates: {},
    row: null, source: null, window: null, history: [], start: null, end: null,
  });
  timelineState.seq++;
  timelineState.hidden.clear();
  $("timeline-search").value = "";
  $("timeline-kind").value = "text";
  for (const id of ["timeline-exact", "timeline-bookmarks", "timeline-undated", "timeline-filters"]) {
    $(id).checked = $(id).defaultChecked;
  }
  for (const id of ["timeline-dates", "timeline-rows", "timeline-legend", "timeline-hist",
                    "timeline-window", "timeline-info", "timeline-info-extra", "timeline-selection"]) {
    $(id).textContent = "";
  }
  document.querySelector('[data-act="tl-clear-range"]').disabled = true;
  document.querySelector('[data-act="timeline-open-row"]').disabled = true;
  Object.assign(timelineGrouping, { levels: [], path: [], parents: new Map() });
  $("timeline-group").classList.remove("active");
  $("timeline-group-path").hidden = true;
  $("timeline-key").textContent = "";
  $("timeline-axis").hidden = true;
  renderTimelineLanes([]);
  clearTimelineOverview();
}

function clearTimelineOverview() {
  const canvas = $("timeline-overview-canvas");
  canvas.width = canvas.width; // Reset pixels and the drawing context's transform.
  canvas.onclick = null;
}

/* The desktop chooses, per analysis, how its dates are read. The choice travels
   with every timeline request, so a rebuild reads the case the same way. */
function timelineDatesParam() {
  const chosen = timelineState.dates;
  return Object.keys(chosen).length ? JSON.stringify(chosen) : "";
}

function renderTimelineDates(payload) {
  const box = $("timeline-dates");
  const sources = payload.sources || [];
  const items = sources.map((source) => {
    const chosen = timelineState.dates[String(source.id)] || "auto";
    const options = [
      `<option value="auto" ${chosen === "auto" ? "selected" : ""}>detected${source.column_name ? ": " + escapeHtml(source.column_label || source.column_name) : ""}</option>`,
      `<option value="none" ${chosen === "none" ? "selected" : ""}>no date (correlation only)</option>`,
    ];
    if (source.split) {
      options.push(`<option value="split" ${chosen === "split" ? "selected" : ""}>date + time (separate columns)</option>`);
    }
    (source.headers || []).forEach((name, position) => {
      const label = (source.labels && source.labels[position]) || name;
      options.push(`<option value="${escapeHtml(name)}" ${chosen === name ? "selected" : ""}>${escapeHtml(label)}</option>`);
    });
    const help = source.date_help?.[chosen === "auto" ? source.column_name : chosen];
    const counts = `${source.dated} dated · ${source.undated} undated`;
    return `<div class="tsrc"><span class="tname" title="${escapeHtml(source.original || source.name)}">${escapeHtml(source.name)}</span>
      <select class="select" data-source="${source.id}" aria-label="Date column for ${escapeHtml(source.name)}">${options.join("")}</select>
      <span class="tdates-description" title="${escapeHtml(counts)}">${escapeHtml(help || counts)}</span></div>`;
  }).join("");
  // A collection of hundreds of analyses has hundreds of selectors: folded, they would push the
  // chart and the rows off the screen. The choice stays one click away, and still travels.
  const wasOpen = !!box.querySelector("details[open]");
  box.innerHTML = sources.length > 6
    ? `<details class="tdates-all"${wasOpen ? " open" : ""}><summary>How the dates of ${sources.length} analyses are read
         — detected automatically; open to change one</summary><div class="tdates-grid">${items}</div></details>`
    : items;
}

function applyTimelineDates() {
  const chosen = {};
  document.querySelectorAll('#timeline-dates select[data-source]').forEach((select) => {
    if (select.value && select.value !== "auto") chosen[select.dataset.source] = select.value;
  });
  timelineState.dates = chosen;
  loadTimeline(true);
}

/* One timeline entry, opened in its own analysis: the value the evidence holds. */
async function openSourceRow(index, rowId) {
  if (!state.openCase) return;
  const caseId = state.openCase.id;
  const request = ++sourceRowRequest;
  const current = () => request === sourceRowRequest && state.openCase?.id === caseId
    && $("source-row-modal").classList.contains("show");
  $("source-row-title").textContent = "The source line";
  $("source-row-list").innerHTML = '<div class="emptygrid">Reading the row…</div>';
  $("source-row-modal").classList.add("show");
  try {
    const payload = await api(
      `/api/cases/${caseId}/timeline/row/${index}/${rowId}`);
    if (!current()) return;
    $("source-row-title").textContent = `${payload.label} — row ${payload.row_id}`;
    $("source-row-list").reviewDateContext = payload;
    $("source-row-list").innerHTML = provenanceSummary(payload.provenance)
      + reviewDateRows(payload.columns, payload.values, payload.date_help)
      + payload.columns.map((name, position) => {
      const value = payload.values[position];
      if (payload.columns.length > 128 && (value === null || value === "")) return "";
      const shown = value === null || value === "" ? "(empty)" : String(value).slice(0, 160);
      return `<div class="analysis-line"><span class="analysis-name">${escapeHtml(name)}</span>
        <span class="pin" title="${escapeHtml(value === null ? "" : String(value))}">${escapeHtml(shown)}</span></div>`;
    }).join("");
  } catch (error) {
    if (!current()) return;
    $("source-row-list").innerHTML = "";
    say(error.message, true);
  }
}

function utcLabel(ns) {
  const ms = Number(ns) / 1e6;
  return new Date(ms).toISOString().replace("T", " ").replace(".000Z", "Z");
}

/* The sources still shown: a lane or a legend chip that hides one removes its events from the list
   and the counts too, as the desktop's lanes do, not only from the chart. */
function timelineVisibleSources() {
  const sources = (timelineState.payload && timelineState.payload.sources) || [];
  if (!timelineState.hidden.size || !sources.length) return null;
  return sources.filter((item) => !timelineState.hidden.has(item.id)).map((item) => item.id);
}

async function loadTimeline(reset, force) {
  if (!state.openCase) return;
  if (reset) timelineState.offset = 0;
  // The index is built once per revision: the first read, and a forced rebuild,
  // are the long ones and go through the job with its bar.
  const heavy = Boolean(force) || !timelineState.payload;
  const params = new URLSearchParams({ offset: String(timelineState.offset) });
  if (timelineState.text) { params.set("text", timelineState.text); params.set("kind", timelineState.kind); }
  if ($("timeline-exact").checked) params.set("exact", "true");
  if ($("timeline-bookmarks").checked) params.set("bookmarks", "true");
  const dates = timelineDatesParam();
  if (dates) params.set("dates", dates);
  if (timelineState.start !== null) params.set("start", String(timelineState.start));
  if (timelineState.end !== null) params.set("end", String(timelineState.end));
  if ($("timeline-undated").checked) params.set("include_undated", "true");
  if ($("timeline-filters").checked) {
    params.set("respect_filters", "true");
    params.set("live", JSON.stringify(liveView()));
  }
  const visible = timelineVisibleSources();
  if (visible) params.set("sources", visible.join(","));
  for (const field of timelineGrouping.levels) params.append("groups", field);
  if (timelineGrouping.path.length) params.set("group_path", JSON.stringify(timelineGrouping.path));
  // Reads overlap (a search typed while a window loads): only the latest one may paint, or a slower
  // earlier answer would put an older state back on the screen.
  const mine = ++timelineState.seq;
  try {
    let payload;
    if (heavy) {
      const wanted = { offset: timelineState.offset };
      if (timelineState.text) Object.assign(wanted, { text: timelineState.text, kind: timelineState.kind });
      if (force) wanted.rebuild = true; // Build / refresh reads the analyses again, as the desktop's Refresh does
      wanted.exact = $("timeline-exact").checked;
      wanted.bookmarks = $("timeline-bookmarks").checked;
      if (dates) wanted.dates = JSON.parse(dates);
      if (timelineState.start !== null) wanted.start = timelineState.start;
      if (timelineState.end !== null) wanted.end = timelineState.end;
      wanted.include_undated = $("timeline-undated").checked;
      wanted.respect_filters = $("timeline-filters").checked;
      if (wanted.respect_filters) wanted.live = liveView();
      if (visible) wanted.sources = visible;
      wanted.groups = timelineGrouping.levels;
      wanted.group_path = timelineGrouping.path;
      payload = await runTask("timeline", wanted, "Timeline");
      if (!payload) return;
    } else {
      payload = await api(`/api/cases/${state.openCase.id}/timeline?${params}`);
    }
    if (mine !== timelineState.seq) return;
    timelineState.payload = payload;
    renderTimelineLanes(payload.sources);
    renderTimeline(payload);
    return true;
  } catch (error) {
    if (mine === timelineState.seq) say(error.message, true);
  }
}

function renderTimelineLanes(sources) {
  const lane = $("timeline-lane");
  const previous = lane.value;
  lane.innerHTML = '<option value="">All lanes</option>'
    + sources.map((source) => `<option value="${source.id}">${escapeHtml(source.name)}</option>`).join("");
  if (sources.some((source) => String(source.id) === previous)) lane.value = previous;
}

function renderTimeline(payload) {
  const hasRange = timelineState.start !== null;
  document.querySelector('[data-act="tl-clear-range"]').disabled = !hasRange;
  $("timeline-selection").textContent = hasRange
    ? `${utcLabel(timelineState.start)} → ${utcLabel(timelineState.end)}` : "All dates";
  renderTimelineDates(payload);
  const shown = payload.sources.map((source, index) => ({ source, index }))
    .filter(({ source }) => !timelineState.hidden.has(source.id));
  const legend = $("timeline-legend");
  const focusedSource = document.activeElement?.dataset.tlSourceChip;
  legend.innerHTML = payload.sources.map((source, index) => {
    const off = timelineState.hidden.has(source.id);
    return `<button type="button" class="chip${off ? " off" : ""}" data-tl-source-chip="${source.id}"
      aria-pressed="${!off}" title="${off ? "Show this source again" : "Hide this source"}"
      style="${off ? "opacity:.55" : ""}"><span class="swatch" style="background:${TIMELINE_COLORS[index % TIMELINE_COLORS.length]}"></span>${escapeHtml(source.name)} · ${source.dated} dated / ${source.rows} row(s)</button>`;
  }).join("");
  legend.querySelectorAll("[data-tl-source-chip]").forEach((chip) => {
    if (chip.dataset.tlSourceChip === focusedSource) chip.focus({ preventScroll: true });
    chip.addEventListener("click", () => {
      const id = Number(chip.dataset.tlSourceChip);
      if (timelineState.hidden.has(id)) timelineState.hidden.delete(id);
      else timelineState.hidden.add(id);
      loadTimeline(true);
    });
  });

  const hist = payload.histogram;
  const box = $("timeline-hist");
  if (!hist || !hist.rows.length) {
    box.innerHTML = '<div class="emptygrid">No dated row to chart.</div>';
    $("timeline-window").textContent = "";
    clearTimelineOverview();
  } else {
    box.innerHTML = timelineBars(hist, shown);
    drawOverview(hist);
    timelineWindowLabel(hist);
    timelineDrag(box, hist);
  }
  renderTimelineAxis(hist);

  $("timeline-key").textContent = hist?.rows.length
    ? "Bar height shows the number of events. Colors identify sources. Drag to select a time range." : "";
  if (renderTimelineGrouped(payload)) return;
  const selected = payload.rows.some((row) =>
    row[0] === timelineState.source && row[1] === timelineState.row);
  if (!selected) { timelineState.row = null; timelineState.source = null; }
  $("timeline-info-extra").textContent = selected
    ? `row ${timelineState.row} of ${timelineState.source}` : "";
  document.querySelector('[data-act="timeline-open-row"]').disabled = !selected;
  $("timeline-rows").innerHTML = payload.rows.map((row) => {
    const [source, rowId, timeNs, sourceTime, summary, note, bookmarked, assumedZone] = row;
    const analysis = payload.sources.find(item => item.id === source);
    const color = TIMELINE_COLORS[Math.max(0, payload.sources.indexOf(analysis)) % TIMELINE_COLORS.length];
    const dateTitle = [analysis?.column_label, sourceTime, assumedZone && "No source offset; displayed as UTC"].filter(Boolean).join(" · ");
    return `<tr class="${source === timelineState.source && rowId === timelineState.row ? "sel" : ""}" data-tl-row="${rowId}" data-tl-source="${source}" title="Open the source line">
      <td title="${escapeHtml(dateTitle)}">${timeNs === null ? "(undated)" : escapeHtml(utcLabel(timeNs))}</td>
      <td title="${escapeHtml(analysis?.original || analysis?.name || "")}"><span class="timeline-date-swatch" style="background:${color}"></span>${escapeHtml(analysis?.name || String(source))}</td>
      <td class="rowid">${escapeHtml(String(rowId))}</td>
      <td title="${escapeHtml(summary)}">${bookmarked ? "\u2605 " : ""}${escapeHtml(summary)}</td>
      <td>${escapeHtml(note)}</td></tr>`;
  }).join("");
  $("timeline-rows").querySelectorAll("tr[data-tl-row]").forEach((node) => {
    node.addEventListener("click", () => {
      // One click selects the row, a double click opens it: the desktop's own
      // gesture, and "Open the source row" does the same on the selection.
      $("timeline-rows").querySelectorAll("tr.sel").forEach((row) => row.classList.remove("sel"));
      node.classList.add("sel");
      timelineState.row = Number(node.dataset.tlRow);
      timelineState.source = Number(node.dataset.tlSource);
      document.querySelector('[data-act="timeline-open-row"]').disabled = false;
      $("timeline-info-extra").textContent =
        `row ${node.dataset.tlRow} of ${node.dataset.tlSource}`;
    });
    node.addEventListener("dblclick", () =>
      openSourceRow(Number(node.dataset.tlSource), Number(node.dataset.tlRow)));
  });

  const from = payload.count ? timelineState.offset + 1 : 0;
  const to = Math.min(timelineState.offset + payload.rows.length, payload.count);
  $("timeline-info").textContent = `${from}\u2013${to} / ${payload.count} event(s) — ${payload.extent.dated} dated`;
  say(`Timeline: ${payload.extent.rows} row(s), ${payload.extent.dated} dated`, false, "timeline");
}

/* ---------- the timeline chart, by hand ----------
   The desktop's timeline zooms, pans, fits, goes back, isolates a source and lets the
   analyst select a duration. The chart here is built from the same histogram; the
   window is a pair of buckets, the selection a pair of times, and the rows follow the
   selection because that is the filter the analyst asked for. */

/* The window by two dates, the way the desktop's "Duration…" asks for them. The
   dates are read as the rows are: ISO, and the end of the day when only a day is given. */
async function timelineDuration() {
  const payload = timelineState.payload;
  if (!payload || !payload.extent) { say("Build the timeline first", true); return; }
  if (payload.extent.start === null) { say("No dated event; choose a date column first", true); return; }
  const band = (ns) => utcLabel(ns).slice(0, 16).replace(" ", "T").replace("Z", "");
  const from = await ask({ title: "Time range (UTC)",
                           label: `From (UTC, ISO — empty keeps ${band(payload.extent.start)})`,
                           value: band(payload.extent.start) });
  if (from === null) return;
  const to = await ask({ title: "Time range (UTC)",
                         label: `To (UTC, ISO — empty keeps ${band(payload.extent.end)})`,
                         value: band(payload.extent.end) });
  if (to === null) return;
  const parse = (text, fallback, endOfDay = false) => {
    const iso = text.trim().replace(" ", "T");
    if (!iso) return fallback;
    if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
      return Date.parse(`${iso}T${endOfDay ? "23:59:59.999" : "00:00:00"}Z`) * 1e6;
    }
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(iso)) return NaN;
    return Date.parse(/[zZ]$|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`) * 1e6;
  };
  const start = parse(from, payload.extent.start);
  const end = parse(to, payload.extent.end, true);
  if (Number.isNaN(start) || Number.isNaN(end) || start >= end) {
    say("Those dates do not make a duration", true);
    return;
  }
  timelineState.start = Math.round(start);
  timelineState.end = Math.round(end);
  if (await loadTimeline(true)) {
    say(`Duration: ${band(timelineState.start)} → ${band(timelineState.end)}`);
  }
}

function timelinePage(direction) {
  const payload = timelineState.payload;
  if (!payload) { say("Build the timeline first", true); return; }
  const step = payload.page_size || 250;
  const next = timelineState.offset + direction * step;
  if (next < 0) { say("Already on the first page", true); return; }
  if (next >= payload.count) { say("Already on the last page", true); return; }
  timelineState.offset = next;
  loadTimeline(false);
}

async function openSelectedTimelineRow() {
  if (!timelineState.row) { say("Select a row of the timeline first", true); return; }
  await openSourceRow(timelineState.source, timelineState.row);
}

function timelineRange(hist) {
  const start = timelineState.window ? timelineState.window[0] : 0;
  const end = timelineState.window ? timelineState.window[1] : hist.bins - 1;
  return { start: Math.max(0, start), end: Math.min(hist.bins - 1, end) };
}

function timelineBars(hist, shown) {
  const totals = new Map();
  const visible = new Set(shown.map(({ source }) => source.id));
  for (const [sourceIndex, bucket, count] of hist.rows) {
    // A hidden source keeps its colour slot but stops feeding the bars.
    if (timelineState.hidden.has(sourceIndex)) continue;
    if (!visible.has(sourceIndex)) continue;
    if (!totals.has(bucket)) totals.set(bucket, []);
    totals.get(bucket).push([sourceIndex, count]);
  }
  const { start, end } = timelineRange(hist);
  const peak = Math.max(1, ...[...totals.entries()]
    .filter(([bucket]) => bucket >= start && bucket <= end)
    .map(([, segments]) => segments.reduce((sum, seg) => sum + seg[1], 0)));
  const bars = [];
  const chartHeight = Math.max(24, $("timeline-hist").clientHeight - 6);
  for (let bucket = start; bucket <= end; bucket += 1) {
    const segments = totals.get(bucket) || [];
    const height = segments.reduce((sum, seg) => sum + seg[1], 0);
    const at = Number(hist.start) + Number(hist.width) * bucket;
    const inner = segments.map(([sourceIndex, count]) =>
      `<span class="seg" style="height:${Math.max(1, Math.round(count / peak * chartHeight))}px;`
      + `background:${TIMELINE_COLORS[sourceIndex % TIMELINE_COLORS.length]}"></span>`).join("");
    bars.push(`<span class="bar" data-bucket="${bucket}" title="${utcLabel(at)} · ${height} event(s)" `
      + `style="height:${Math.max(height ? 2 : 0, Math.round(height / peak * chartHeight))}px">${inner}</span>`);
  }
  return bars.join("");
}

function renderTimelineAxis(hist) {
  const axis = $("timeline-axis");
  axis.hidden = !hist?.rows.length;
  if (axis.hidden) return;
  const { start, end } = timelineRange(hist);
  const low = Number(hist.start) + start * Number(hist.width);
  const high = Math.min(Number(hist.end), Number(hist.start) + (end + 1) * Number(hist.width) - 1);
  const short = high - low < 24 * 60 * 60 * 1e9;
  const points = [...new Set([low, Math.round((low + high) / 2), high])];
  axis.replaceChildren(...points.map(value => {
    const label = document.createElement("time");
    const stamp = utcLabel(value);
    label.title = stamp;
    label.textContent = short ? stamp.slice(11, 19) + " UTC" : stamp.slice(0, 10);
    return label;
  }));
}

/* The whole extent, the events as a thin profile, and the window on screen as a band
   the analyst can move by clicking. The desktop calls this its Overview. */
function drawOverview(hist) {
  const canvas = $("timeline-overview-canvas");
  if (!canvas || !hist || !hist.bins) return;
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 800;
  const height = 34;
  canvas.width = Math.round(width * ratio);
  canvas.height = Math.round(height * ratio);
  const context = canvas.getContext("2d");
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, width, height);

  const totals = new Array(hist.bins).fill(0);
  let peak = 1;
  for (const [sourceIndex, bucket, count] of hist.rows) {
    if (timelineState.hidden.has(sourceIndex)) continue;
    totals[bucket] += count;
    peak = Math.max(peak, totals[bucket]);
  }
  const columnWidth = width / hist.bins;
  context.fillStyle = "#9fb3c8";
  totals.forEach((count, bucket) => {
    if (!count) return;
    const bar = Math.max(1, Math.round((count / peak) * (height - 6)));
    context.fillRect(bucket * columnWidth, height - 3 - bar, Math.max(1, columnWidth), bar);
  });

  const { start, end } = timelineRange(hist);
  context.fillStyle = "rgba(23, 75, 115, .18)";
  context.fillRect(start * columnWidth, 0, (end - start + 1) * columnWidth, height);
  context.strokeStyle = "#174b73";
  context.lineWidth = 1;
  context.strokeRect(start * columnWidth + 0.5, 0.5,
                     (end - start + 1) * columnWidth - 1, height - 1);

  canvas.onclick = (event) => {
    const box = canvas.getBoundingClientRect();
    const span = end - start + 1;
    const centre = Math.round(((event.clientX - box.left) / box.width) * hist.bins);
    let low = Math.max(0, Math.min(hist.bins - span, centre - Math.floor(span / 2)));
    timelineState.history.push([start, end]);
    timelineState.window = [low, low + span - 1];
    renderTimeline(timelineState.payload);
  };
}

function timelineWindowLabel(hist) {
  const { start, end } = timelineRange(hist);
  const low = hist.start + start * hist.width;
  const high = hist.start + (end + 1) * hist.width;
  const band = (ns) => utcLabel(ns).slice(0, 16);
  const whole = start === 0 && end === hist.bins - 1;
  const selection = timelineState.start !== null
    ? ` · selection ${band(timelineState.start)} → ${band(timelineState.end)}` : "";
  $("timeline-window").textContent =
    `${whole ? "whole extent" : `window ${band(low)} → ${band(high)}`} (${end - start + 1}/${hist.bins} bins)${selection}`;
}

function timelineZoom(factor, anchor) {
  const hist = timelineState.payload && timelineState.payload.histogram;
  if (!hist) return;
  const { start, end } = timelineRange(hist);
  const span = end - start + 1;
  const next = Math.max(4, Math.round(span * factor));
  if (next === span) return;
  const middle = anchor === undefined ? start + span / 2 : anchor;
  let low = Math.round(middle - next / 2);
  low = Math.max(0, Math.min(hist.bins - next, low));
  timelineState.history.push([start, end]);
  timelineState.window = [low, low + next - 1];
  renderTimeline(timelineState.payload);
}

function timelinePan(factor) {
  const hist = timelineState.payload && timelineState.payload.histogram;
  if (!hist) return;
  const { start, end } = timelineRange(hist);
  const span = end - start + 1;
  const shift = Math.round(span * factor) || (factor > 0 ? 1 : -1);
  const low = Math.max(0, Math.min(hist.bins - span, start + shift));
  if (low === start) return;
  timelineState.history.push([start, end]);
  timelineState.window = [low, low + span - 1];
  renderTimeline(timelineState.payload);
}

/* "15 minutes", "1 hour"…: a duration centred on the selected event, or on the middle of the extent. */
function timelinePreset(seconds) {
  const payload = timelineState.payload;
  if (!seconds || !payload || !payload.extent || payload.extent.start === null) return;
  const selected = payload.rows && timelineState.row
    ? payload.rows.find((row) => row[0] === timelineState.source && row[1] === timelineState.row) : null;
  const centre = selected && selected[2] !== null ? Number(selected[2]) : Math.round((payload.extent.start + payload.extent.end) / 2);
  const half = seconds * 1e9 / 2;
  timelineState.start = Math.round(centre - half);
  timelineState.end = Math.round(centre + half);
  loadTimeline(true);
  say(`Duration: ${utcLabel(timelineState.start).slice(0, 16)} → ${utcLabel(timelineState.end).slice(0, 16)}`);
}

function timelineFit() {
  if (!timelineState.window) return;
  timelineState.history.push(timelineState.window);
  timelineState.window = null;
  renderTimeline(timelineState.payload);
}

function timelineBack() {
  if (!timelineState.history.length) return;
  timelineState.window = timelineState.history.pop();
  renderTimeline(timelineState.payload);
}

function findingShownSources() {
  const sources = (timelineState.payload && timelineState.payload.sources) || [];
  return sources.map((source, index) => ({ source, index }))
    .filter(({ source }) => !timelineState.hidden.has(source.id));
}

/* Drag on the chart: a duration, which filters the rows below. Shift-drag pans. A short drag (a click)
   clears the selection instead of making a window of two buckets. */
function timelineDrag(box, hist) {
  let from = null;
  let panning = null;
  const bucketAt = (event) => {
    const bars = [...box.querySelectorAll(".bar")];
    if (!bars.length) return null;
    const first = bars[0].getBoundingClientRect();
    const last = bars[bars.length - 1].getBoundingClientRect();
    const width = (last.right - first.left) / bars.length;
    const position = Math.floor((event.clientX - first.left) / width);
    return Math.max(0, Math.min(bars.length - 1, position));
  };
  box.onmousedown = (event) => {
    if (event.button !== 0) return;
    if (event.shiftKey) {
      // Shift-drag slides the window: the same gesture as the desktop's pan.
      panning = { bucket: bucketAt(event), window: timelineRange(hist) };
    } else {
      from = bucketAt(event);
    }
    event.preventDefault();
  };
  box.onmousemove = (event) => {
    if (panning) {
      const shift = bucketAt(event) - panning.bucket;
      const span = panning.window.end - panning.window.start + 1;
      let low = Math.max(0, Math.min(hist.bins - span, panning.window.start + shift));
      timelineState.window = [low, low + span - 1];
      box.innerHTML = timelineBars(hist, findingShownSources());
      return;
    }
    if (from === null) return;
    const to = bucketAt(event);
    box.querySelectorAll(".bar.sel").forEach((bar) => bar.classList.remove("sel"));
    const low = Math.min(from, to);
    const high = Math.max(from, to);
    [...box.querySelectorAll(".bar")].forEach((bar) => {
      const bucket = Number(bar.dataset.bucket);
      if (bucket >= low && bucket <= high) bar.classList.add("sel");
    });
  };
  box.onmouseup = (event) => {
    if (panning) {
      panning = null;
      box.onmousemove = null;
      renderTimeline(timelineState.payload);
      return;
    }
    if (from === null) return;
    const to = bucketAt(event);
    const low = Math.min(from, to);
    const high = Math.max(from, to);
    from = null;
    const { start } = timelineRange(hist);
    if (high - low < 1) {
      // One bucket, or none: the selection is cleared, the rows come back whole.
      timelineState.start = null;
      timelineState.end = null;
    } else {
      timelineState.start = hist.start + (start + low) * hist.width;
      timelineState.end = hist.start + (start + high + 1) * hist.width;
    }
    loadTimeline(true);
  };
  box.ondblclick = () => timelineFit();
  box.onwheel = (event) => {
    if (Math.abs(event.deltaY) < 2) return;
    event.preventDefault();
    timelineZoom(event.deltaY < 0 ? 0.6 : 1.8, timelineRange(hist).start + bucketAt(event));
  };
}

/* ---------- artifacts tree ---------- */

/* The Artifacts tree, as the desktop groups it: the collections, then (by family) what each analysis is.
   "families": Collection → artifact family → analyses; "flat": Collection → analyses;
   "folders": Collection → partition → folders, for the evidence that carries its origin. */
const treeState = { mode: "families", collapsed: new Set(), initialized: new Set(), caseId: null };

function loadTreeMode() {
  try {
    const stored = localStorage.getItem("fireblade.treeMode");
    if (["families", "flat", "folders"].includes(stored)) treeState.mode = stored;
  } catch (_) { /* a first visit */ }
}

function treeLeaf(item, depth, label = item.tree_label || item.label) {
  const title = [item.label, ...(item.tree_sources || []), item.source || item.path].filter(Boolean).join("\n");
  return `<div class="node child ${item.index === state.analysis ? "sel" : ""}" data-analysis="${item.index}"
       style="padding-left:${20 + depth * 12}px" title="${escapeHtml(title)}">
      <span class="caret"></span><span class="nlabel">${escapeHtml(label)}</span></div>`
    + treeSourceChildren(item, depth + 1);
}

function treeGroup(key, label, depth, open, active = false) {
  return `<div class="node grp ${active && !open ? "contains-active" : ""}" data-group-key="${escapeHtml(key)}" style="padding-left:${6 + depth * 12}px" title="${escapeHtml(label)}" aria-expanded="${open}">
      <span class="caret">${open ? "▼" : "▷"}</span><span class="nlabel">${escapeHtml(label)}</span></div>`;
}

function treeHtml(analyses) {
  const collections = new Map();
  for (const item of analyses) {
    const owner = item.collection || { key: "", name: "Analyses outside a collection" };
    if (!collections.has(owner.key)) collections.set(owner.key, { name: owner.name, members: [] });
    collections.get(owner.key).members.push(item);
  }
  const html = [];
  const searching = Boolean(($("tree-search").value || "").trim());
  for (const [key, owner] of collections) {
    const rootKey = `c|${key}`;
    const open = searching || !treeState.collapsed.has(rootKey);
    html.push(treeGroup(rootKey, `${owner.name} (${owner.members.length})`, 0, open));
    if (!open) continue;
    if (treeState.mode === "flat" || treeState.mode === "folders") {
      for (const item of owner.members) html.push(treeLeaf(item, 1));
      continue;
    }
    const families = new Map();
    for (const item of owner.members) {
      const family = item.family || "Other artifacts";
      if (!families.has(family)) families.set(family, []);
      families.get(family).push(item);
    }
    const rank = (family) => family === "Supporting files" ? 2 : family === "Files inventory" ? 1 : 0;
    for (const [family, members] of [...families].sort(([a], [b]) => rank(a) - rank(b))) {
      if (members.length === 1) {
        const item = members[0];
        html.push(treeLeaf(item, 1));
        continue;
      }
      const familyKey = `f|${key}|${family}`;
      if (family === "Supporting files" && !treeState.initialized.has(familyKey)) {
        treeState.initialized.add(familyKey);
        treeState.collapsed.add(familyKey);
      }
      const familyOpen = searching || !treeState.collapsed.has(familyKey);
      html.push(treeGroup(familyKey, `${family} (${members.length})`, 1, familyOpen,
        members.some((item) => item.index === state.analysis)));
      if (familyOpen) for (const item of members) html.push(treeLeaf(item, 2));
    }
  }
  return html.join("");
}

function renderTree() {
  const tree = $("tree");
  if (!state.openCase) {
    tree.innerHTML = '<div class="empty">No case open.</div>';
    return;
  }
  if (treeState.caseId !== state.openCase.id) {
    treeState.caseId = state.openCase.id;
    treeState.collapsed.clear();
    treeState.initialized.clear();
  }
  const term = ($("tree-search").value || "").trim().toLowerCase();
  const analyses = state.openCase.analyses.filter((item) =>
    !term || [item.label, item.tree_label, item.family, item.source, ...(item.tree_sources || [])]
      .some((value) => String(value || "").toLowerCase().includes(term)));
  if (!analyses.length) {
    tree.innerHTML = '<div class="empty">' + (state.openCase.analyses.length ? "No analysis matches this filter." : "No analysis in this case.") + "</div>";
    return;
  }
  const closed = (state.openCase && state.openCase.closed) || [];
  tree.innerHTML = treeHtml(analyses) +
    (closed.length ? '<div class="node grp closed-group"><span class="caret">▷</span>Closed (kept in the case)</div>'
      + closed.map((item) => `
      <div class="node child closed" data-reopen="${item.index}"
           title="Open this analysis again — ${escapeHtml(item.source || item.path)}">
        <span class="caret"></span><span class="nlabel">${escapeHtml(item.label)}</span>
      </div>`).join("") : "");
  tree.querySelectorAll("[data-reopen]").forEach((node) => {
    node.addEventListener("click", () => reopenAnalysis(Number(node.dataset.reopen)));
  });
}

/* "Expand the whole tree" / "Collapse the whole tree". */
function treeExpandAll(open) {
  treeState.collapsed.clear();
  if (!open && state.openCase) {
    for (const item of state.openCase.analyses) {
      const owner = item.collection || { key: "" };
      treeState.collapsed.add(`c|${owner.key}`);
      treeState.collapsed.add(`f|${owner.key}|${item.family || "Other artifacts"}`);
    }
  }
  renderTree();
}

async function reopenAnalysis(position) {
  if (!state.openCase) return;
  try {
    const payload = await apiPost(
      `/api/cases/${state.openCase.id}/closed/${position}/reopen`, {});
    await openCase(state.openCase.id);
    state.analysis = payload.index;
    renderTree();
    await loadRows(true);
    say(`Analysis opened again: ${payload.analyses} tab(s), ${payload.closed} still closed`);
  } catch (error) {
    say(error.message, true);
  }
}

function renderPaneTabs() {
  if (!state.openCase) { $("pane-tabs").innerHTML = ""; return; }
  const current = currentAnalysis();
  $("pane-tabs").innerHTML = current
    ? `<div class="ptab active" title="${escapeHtml(current.label)}">${escapeHtml(current.label)}
         <span class="ptab-close" id="close-analysis" title="Close this analysis — the file stays in the case">✕</span></div>`
    : '<div class="ptab active">No analysis</div>';
  if (current) renderGridPreferences(current);
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
  for (const summary of state.summaries) {
    const footer = summary.footer === undefined ? -1 : (summary.footer === null ? "none" : summary.footer);
    params.append("summary", `${summary.column}:${summary.operation}:${summary.kind}:${footer}`);
  }
  for (const summary of state.totalSummaries) {
    params.append("total", `${summary.column}:${summary.operation}:${summary.kind}`);
  }
  if (state.footerMode !== "hidden") params.set("footer_mode", state.footerMode);
  if (copyPrefs.dateFormat !== "source") {
    params.set("date_format", copyPrefs.dateFormat);
    if (copyPrefs.dateFormat === "custom") params.set("date_pattern", copyPrefs.pattern);
  }
  if (!state.showTotal) params.set("show_total", "false");
  if (state.order) {
    params.set("order", state.order);
    params.set("order_descending", state.orderDesc === false ? "false" : "true");
    params.set("order_summary", String(state.orderSummary || 0));
  }
  if (state.path.length) params.set("group_path", JSON.stringify(state.path));
  if (state.multiSort.length) {
    for (const key of state.multiSort) params.append("sortkey", `${key.column}:${key.descending ? "desc" : "asc"}:${key.kind || state.sortType}`);
  } else if (state.sort !== null) {
    params.set("sort", String(state.sort));
    params.set("sort_type", state.sortType);
    params.set("descending", state.descending ? "true" : "false");
  }
  for (const item of state.filters) params.append("filter", `${item.column}:${item.operator}:${item.value}`);
  return params;
}

function rowsUrl(extra) {
  const base = `/api/cases/${state.openCase.id}/analyses/${state.analysis}/rows`;
  const params = query();
  if (state.columns.length > 128 && state.columnContext === `${state.openCase.id}/${state.analysis}`) {
    for (const item of columnWindow(visibleColumns())) {
      if (item.index !== undefined) params.append("column", String(item.index));
    }
  }
  if (state.expandAll && state.groups.length) params.set("expanded", "true");
  if (extra) extra(params);
  return `${base}?${params.toString()}`;
}

/* One request may be in flight on the grid. The menu can stop it: the browser
   abandons the query, the server keeps its own state, and nothing is written. */
let rowsRequest = null;

function stopQuery() {
  if (!rowsRequest) { say("No query is running", true); return; }
  rowsRequest.abort();
  rowsRequest = null;
  say("Query stopped — the page stays as it was");
}

async function loadRows(reset, preserveSelection = false, viewport = false) {
  if (!state.openCase) return;
  if (reset) {
    state.offset = 0;
    $("gridbody").scrollTop = 0;
  }
  // A new page is a new set of rows: a selection of ids that are no longer on
  // screen must not survive into "copy the selected rows".
  if (!preserveSelection) {
    clearTimeout(filterTimer);
    state.selection.clear();
    state.anchor = null;
    state.selected = null;
    showDetails(null);
  }
  rowsRequest?.abort();
  const controller = new AbortController();
  rowsRequest = controller;
  try {
    const payload = await apiAbortable(rowsUrl(), controller.signal);
    if (controller.signal.aborted) return false;
    state.columns = payload.columns;
    state.columnContext = `${state.openCase.id}/${state.analysis}`;
    state.rows = payload.projection ? payload.rows.map((values) => {
      const row = new Array(payload.columns.length);
      payload.projection.forEach((column, position) => { row[column] = values[position]; });
      return row;
    }) : payload.rows;
    state.total = payload.total;
    state.offset = payload.offset;
    state.grouped = Boolean(payload.grouped);
    state.payload = payload;
    state.timestamps = payload.timestamps || [];
    state.styles = payload.styles || {};
    state.ruleSet = payload.rule_set || [];
    if (viewport) {
      await loadCellNotes();
      if (controller.signal.aborted) return false;
      renderGrid();
      return true;
    }
    await loadBookmarks(controller.signal);
    if (controller.signal.aborted) return false;
    await loadCellNotes();
    if (controller.signal.aborted) return false;
    await loadRules();
    if (controller.signal.aborted) return false;
    await loadLayout(controller.signal);
    if (controller.signal.aborted) return false;
    renderPaneTabs();
    return true;
  } catch (error) {
    if (!controller.signal.aborted && error.name !== "AbortError") say(error.message, true);
    return false;
  } finally {
    if (rowsRequest === controller) rowsRequest = null;
  }
}

async function loadBookmarks(signal) {
  const payload = await apiAbortable(`${activeAnalysisPath()}/bookmarks`, signal);
  if (!signal.aborted) {
    state.bookmarks = new Map(payload.bookmarks.map(item => [String(item.row_id), item.note]));
  }
}

async function loadCellNotes() {
  state.cellNotes = new Map();
  if (!state.rows.length) return;
  try {
    const payload = await apiPost(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/cellnotes`,
      { row_ids: state.rows.map((row) => Number(row[0])).filter(Number.isFinite) });
    state.cellNotes = new Map(Object.entries(payload.notes || {}));
  } catch (_) {
    state.cellNotes = new Map();
  }
}

function notesForRow(rowId) {
  return state.cellNotes.get(String(rowId)) || {};
}

async function toggleBookmark(rowId, note) {
  const path = activeAnalysisPath();
  await postBookmark(path, rowId, note);
  if (path === activeAnalysisPath()) await refreshBookmarksView();
}

async function refreshBookmarksView() {
  if (state.bookmarksOnly || state.groups.includes(BOOKMARK_GROUP_COLUMN)) {
    await loadRows(true);
  } else {
    renderGrid();
  }
}

function showCaseStart() {
  if (state.cases.length) {
    clearGrid("Open an investigation", [["Open case library", "cases-list"], ["New case…", "new-case"]],
      "Select a case to review its evidence, findings and investigation history.");
  } else {
    clearGrid("Start an investigation", [["New case…", "new-case"], ["Import portable case…", "import-portable"]],
      "Create a case for your evidence or open a portable Kagarasu case.");
  }
}

function clearGrid(message, actions = [], description = "") {
  $("head").innerHTML = "";
  $("body").innerHTML = "";
  $("cols").innerHTML = "";
  $("grid-empty").hidden = false;
  const empty = $("grid-empty");
  empty.textContent = message;
  if (actions.length) {
    const title = document.createElement("h2");
    title.textContent = message;
    const detail = document.createElement("p");
    detail.textContent = description;
    empty.replaceChildren(title, detail);
    const controls = document.createElement("div");
    controls.className = "empty-grid-actions";
    for (const [label, action] of actions) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn";
      button.textContent = label;
      button.addEventListener("click", () => act(action, button));
      controls.append(button);
    }
    empty.append(controls);
  }
  $("pageinfo").textContent = "";
  updateGridPager();
}

/* Every column in the order the analyst gave them: the row id first, then the order kept with the analysis,
   the columns it does not name following in their own order. */
function orderedColumns() {
  const all = state.columns.map((name, index) => ({ name, index }));
  if (!state.colOrder.length) return all;
  const rank = new Map(state.colOrder.map((header, position) => [header + 1, position]));
  return all.sort((a, b) => {
    if (a.index === 0 || b.index === 0) return a.index === 0 ? -1 : 1;
    return (rank.has(a.index) ? rank.get(a.index) : 1e6 + a.index) - (rank.has(b.index) ? rank.get(b.index) : 1e6 + b.index);
  });
}

/* What a rule paints, as the desktop's rule says it: the colours it applies, the font it sets. */
function ruleCss(rule) {
  const parts = [];
  if (rule.use_background !== false) parts.push(`background:${rule.background}`);
  if (rule.use_foreground !== false) parts.push(`color:${rule.foreground}`);
  if (rule.use_font !== false) {
    if (rule.bold) parts.push("font-weight:600");
    if (rule.italic) parts.push("font-style:italic");
    const lines = [rule.underline ? "underline" : "", rule.strikeout ? "line-through" : ""].filter(Boolean);
    if (lines.length) parts.push(`text-decoration:${lines.join(" ")}`);
    if (rule.font_family) parts.push(`font-family:${String(rule.font_family).replace(/[^\w ,'"-]/g, "")}`);
    if (Number(rule.font_size) > 0) parts.push(`font-size:${Number(rule.font_size)}pt`);
  }
  return parts.join(";");
}

function visibleColumns() {
  return orderedColumns().filter((item) => !state.hidden.has(item.index));
}

/* Keep the real column order and scroll width, but create cells only around the
   viewport. Sparse response arrays distinguish an unloaded value from SQL NULL. */
function columnWindow(columns) {
  if (state.columns.length <= 128) return columns;
  const wrap = $("gridbody");
  const low = Math.max(0, wrap.scrollLeft - 400);
  const high = wrap.scrollLeft + wrap.clientWidth + 400;
  let left = 30;
  const result = [];
  for (const item of columns) {
    const width = state.widths[item.index] || defaultWidth(item.name, item.index);
    const shown = (left + width >= low && left <= high)
      || state.pinned.has(item.index - 1) || state.pinnedRight.has(item.index - 1);
    if (shown) result.push({ ...item, width });
    else if (result.length && result[result.length - 1].index === undefined) result[result.length - 1].width += width;
    else result.push({ width });
    left += width;
  }
  return result;
}

let columnWindowTimer;
let columnWindowFrame = null;
let columnWindowLeft = $("gridbody").scrollLeft;
let columnWindowWidth = $("gridbody").clientWidth;
function refreshColumnViewport() {
  const current = () => state.openCase && state.columns.length > 128 && !state.grouped
    && $("gridbody").clientWidth > 0
    && state.columnContext === `${state.openCase.id}/${state.analysis}`;
  if (!current()) return;
  if (columnWindowFrame === null) columnWindowFrame = requestAnimationFrame(() => {
    columnWindowFrame = null;
    if (current()) renderGrid(true);
  });
  clearTimeout(columnWindowTimer);
  columnWindowTimer = setTimeout(() => {
    if (current() && !rowsRequest) renderGrid();
  }, 100);
}
$("gridbody").addEventListener("scroll", () => {
  const left = $("gridbody").scrollLeft;
  if (left === columnWindowLeft) return;
  columnWindowLeft = left;
  refreshColumnViewport();
}, { passive: true });
new ResizeObserver(() => {
  const width = $("gridbody").clientWidth;
  if (width === columnWindowWidth) return;
  columnWindowWidth = width;
  refreshColumnViewport();
}).observe($("gridbody"));

/* "Highlight matches (empty = disable)", the desktop's own control: the text is cut
   around the term, each piece escaped, and only the pieces are marked. */
function markText(text, terms) {
  const raw = String(text === null || text === undefined ? "" : text);
  const wanted = [...new Set((Array.isArray(terms) ? terms : [terms]).filter(Boolean).map((term) => String(term).toLowerCase()))];
  if (!wanted.length) return escapeHtml(raw);
  const lower = raw.toLowerCase();
  // Every occurrence of every term, case-insensitive; overlapping ones are one mark (the desktop paints the union).
  const spans = [];
  for (const needle of wanted) {
    for (let at = lower.indexOf(needle); at >= 0; at = lower.indexOf(needle, at + needle.length)) {
      spans.push([at, at + needle.length]);
    }
  }
  spans.sort((x, y) => x[0] - y[0] || y[1] - x[1]);
  const merged = [];
  for (const span of spans) {
    const last = merged[merged.length - 1];
    if (last && span[0] <= last[1]) last[1] = Math.max(last[1], span[1]);
    else merged.push([...span]);
  }
  let out = "";
  let from = 0;
  for (const [start, end] of merged) {
    out += escapeHtml(raw.slice(from, start)) + "<mark>" + escapeHtml(raw.slice(start, end)) + "</mark>";
    from = end;
  }
  return out + escapeHtml(raw.slice(from));
}

async function openHighlight() {
  if (!state.columns.length) { say("Open an analysis first", true); return; }
  const answer = await ask({ title: "Highlight text", label: "Text to highlight",
                             note: "Empty turns the highlight off.", value: state.highlight || "" });
  if (answer === null) return;
  state.highlight = answer.trim();
  renderGrid();
  say(state.highlight ? `Highlighting “${state.highlight}”` : "Highlight off");
}

/* ---------- the grouping bar (desktop parity: drag a header, numbered levels, × per level) ---------- */
const GROUP_MIME = "application/x-fireblade-column";
const GROUP_LEVEL_MIME = "application/x-fireblade-group-level";
const BOOKMARK_GROUP_COLUMN = -2;
const BOOKMARK_GROUP_LABEL = "Bookmark status";
const BOOKMARK_GROUP_HEADER = `<th draggable="true" data-bookmark-group
  aria-label="${BOOKMARK_GROUP_LABEL}" title="Drag to group bookmarked rows">
  <button type="button" class="mark-settings" data-row-mark-settings aria-label="Configure row marks"
    title="Configure the row mark cycle. Shift-click a row mark to toggle its bookmark.">☆</button></th>`;

function groupColumnName(column) {
  return column === BOOKMARK_GROUP_COLUMN ? BOOKMARK_GROUP_LABEL : state.columns[column + 1];
}

function renderGroupBar() {
  const chips = $("group-chips");
  const hint = $("group-label");
  const clear = $("group-clear");
  if (!chips) return;
  $("recmd-review").hidden = !Object.keys(currentRecmdColumns()).length;
  renderGroupTrail($("group-path"), state.path, (value, depth) =>
    `${groupColumnName(state.groups[depth])}: ${groupPathValue(value)}`, returnToGridGroup);
  $("grid-group-back").hidden = !state.path.length;
  chips.innerHTML = "";
  if (!state.groups.length) {
    hint.hidden = false;
    hint.textContent = "Drag a header here to group the results";
    clear.hidden = true;
    return;
  }
  hint.hidden = true;
  clear.hidden = false;
  state.groups.forEach((column, level) => {
    if (level) chips.appendChild(groupSeparator(level));
    chips.appendChild(groupChip(level, column));
  });
  chips.appendChild(groupSeparator(state.groups.length));
}

function groupChip(level, column) {
  const chip = document.createElement("span");
  chip.className = "gchip";
  chip.dataset.level = String(level);
  chip.innerHTML = `<span class="gnum">${level + 1}</span><span class="gname">${escapeHtml(groupColumnName(column) || `column ${column + 1}`)}</span>`;
  const close = document.createElement("button");
  close.className = "gx";
  close.title = "Remove this grouping level";
  close.textContent = "×";
  close.addEventListener("click", () => removeGroupLevel(level));
  chip.appendChild(close);
  return chip;
}

function groupSeparator(position) {
  const sep = document.createElement("span");
  sep.className = "gsep";
  sep.dataset.position = String(position);
  sep.textContent = position === state.groups.length ? "+" : "›";
  sep.title = position === state.groups.length
    ? "Drop a header here to add a level at the end"
    : "Drop a header here to insert a level at this position";
  return sep;
}

function addGroupColumn(groupIndex, position) {
  if (groupIndex !== BOOKMARK_GROUP_COLUMN &&
      (!Number.isInteger(groupIndex) || groupIndex < 0 || groupIndex >= state.columns.length - 1)) return;
  if (state.groups.includes(groupIndex)) { say("This column is already grouped", true); return; }
  const at = position === undefined || position === null ? state.groups.length : Math.min(position, state.groups.length);
  state.groups.splice(at, 0, groupIndex);
  state.path = [];
  renderGroupBar();
  loadRows(true);
}

function removeGroupLevel(level) {
  if (level < 0 || level >= state.groups.length) return;
  state.groups.splice(level, 1);
  state.path = [];
  renderGroupBar();
  loadRows(true);
}

function clearGrouping() {
  state.groups = [];
  state.expandAll = false;
  state.path = [];
  state.interval = "";
  renderGroupBar();
  loadRows(true);
}

/* ---------- column auto-fit: double-click the grip to size the column to its content ---------- */
function fitColumnToContent(column) {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  ctx.font = getComputedStyle(document.body).font || "13px sans-serif";
  let max = ctx.measureText(String(state.columns[column] || "")).width + 48;
  for (const row of state.rows) {
    const value = row[column];
    if (value === null || value === undefined || value === "") continue;
    const width = ctx.measureText(String(value)).width;
    if (width > max) max = width;
  }
  state.widths[column] = Math.max(24, Math.min(1200, Math.ceil(max + 16)));
  renderGrid();
  saveLayoutSoon();
}

function renderGrid(deferColumns = false) {
  const empty = $("grid-empty");
  renderGroupBar();
  if (!state.grouped) $("group-chart").hidden = true;
  updateGridPager();
  if (state.grouped) { renderGroupedGrid(); return; }
  const shown = columnWindow(visibleColumns());
  if (!state.columns.length) {
    clearGrid("No analysis open.");
    return;
  }
  const outline = state.payload?.outline;
  empty.hidden = (outline || state.rows).length > 0;
  empty.textContent = state.total
    ? "No row on this page."
    : (state.search || state.filters.length ? "No row matches these filters." : "This analysis is empty.");

  // The header follows `shown`, like the body: a hidden column must not leave its
  // title behind. An absolute index keeps the filters, sorts and widths addressed.
  $("grid").style.width = state.columns.length > 128
    ? `${30 + shown.reduce((total, item) => total + item.width, 0)}px` : "";
  $("cols").innerHTML = '<col style="width:30px">' + shown.map(({ index, width }) =>
    `<col style="width:${width || state.widths[index] || defaultWidth(state.columns[index], index)}px">`).join("");

  const head = ['<tr>', BOOKMARK_GROUP_HEADER];
  shown.forEach(({ index }) => {
    if (index === undefined) { head.push('<th class="column-spacer"></th>'); return; }
    const name = state.columns[index];
    const multi = state.multiSort.findIndex((item) => item.column === index - 1);
    // state.sort names a column by its position without the row-id column, like multiSort does
    const sorted = state.sort === index - 1 || multi >= 0;
    const flag = state.sort === index - 1 ? state.descending : (multi >= 0 ? state.multiSort[multi].descending : false);
    const arrow = sorted ? (flag ? "▼" : "▲") + (multi >= 0 ? String(multi + 1) : "") : "";
    const sortOrder = sorted && multi <= 0 ? ` aria-sort="${flag ? "descending" : "ascending"}"` : "";
    const label = escapeHtml(name);
    head.push(`<th scope="col" class="${sorted ? "sorted" : ""}"${sortOrder} data-column="${index}" draggable="${index === 0 ? "false" : "true"}" title="${label}">
      ${index ? `<button type="button" class="column-sort" aria-label="Sort by ${label}" title="Sort by ${label}"><span class="column-name">${label}</span><span class="sort" aria-hidden="true">${arrow}</span></button>` : '<span class="column-name">Row</span>'}
      ${index ? `<button type="button" class="column-values" data-column-values="${index - 1}" aria-label="Values in ${escapeHtml(name)}" title="View values or hide this column"></button>` : ""}
      <span class="grip" data-grip="${index}"></span></th>`);
  });
  head.push("</tr>");
  // One leading cell for the checkbox column, then one per column.
  head.push('<tr class="colfilter"><th></th>');
  shown.forEach(({ index }) => {
    if (index === undefined) { head.push('<th class="column-spacer"></th>'); return; }
    if (index === 0) { head.push("<th></th>"); return; }
    const current = state.filters.find((item) => item.column === index - 1);
    // The operator is shown as a small icon on the left of the field and chosen from a list; the
    // field holds the value alone. (Typing a prefix such as "=" or "!=" still works.)
    const operator = current ? current.operator : (state.filterOps[index - 1] || "contains");
    const meaning = (FILTER_OPERATORS.find(([code]) => code === operator) || [])[2] || operator;
    const valueFilter = operator === "one_of" ? JSON.parse(current.value).length + " selected" : null;
    head.push(`<th data-filter-column="${index}"><div class="fcell"><button class="fop" data-fop="${index - 1}" aria-label="Filter comparison for ${escapeHtml(state.columns[index])}: ${escapeHtml(meaning)}" title="Comparison: ${escapeHtml(meaning)}">${FILTER_GLYPHS[operator] || "≈"}</button>`
      + `<input data-filter="${index - 1}" aria-label="Filter ${escapeHtml(state.columns[index])}" placeholder="${valueFilter || "Filter…"}" value="${escapeHtml(current && !valueFilter ? current.value : "")}"></div></th>`);
  });
  head.push("</tr>");
  $("head").innerHTML = head.join("");

  const clipped = document.documentElement.classList.contains("rowclip");
  const dataRows = state.rows.map((row) => {
    const id = row[0];
    // Column 0 is the row identifier: it gets its own cell, after the checkbox one.
    const rowNotes = notesForRow(id);
    // The rule is found once, before the cells: a visual needs it per cell.
    const matched = state.styles[String(id)];
    const rule = matched && matched.length ? state.ruleSet[matched[0]] : null;
    const cells = shown.map(({ index }) => {
      if (index === undefined) return '<td class="column-spacer"></td>';
      const value = row[index];
      // The case names its date columns when it has them; a value that reads as a
      // full timestamp is formatted anyway, so the preference is never a no-op.
      const isDate = (Array.isArray(state.timestamps) && state.timestamps.includes(index - 1))
        || DATE_TEXT.test(value === null || value === undefined ? "" : String(value));
      const text = value === undefined ? "…" : value === null || value === ""
        ? "∅"
        : String(value); // the server has already written the date columns the way Preferences asked
      const noted = rowNotes[String(index - 1)];
      const cls = [value === null || value === "" ? "cellnull" : (index === 0 ? "rowid" : ""),
                   noted ? "noted" : ""].filter(Boolean).join(" ");
      const title = noted ? ` title="${escapeHtml(noted)}"` : "";
      const visual = rule ? visualCell(rule, index - 1, row[index]) : null;
      // A rule aimed at one cell colours that cell and leaves the row alone.
      const cellRule = rule && rule.target !== null && rule.target !== undefined
        && (!rule.visual || rule.visual === "none") && Number(rule.target) === index - 1;
      const painted = visual ? ` style="${visual.style}"`
        : (cellRule ? ` style="${ruleCss(rule)}"` : "");
      // Wrapped but not fitted: the text lives in a box as tall as the row.
      const [open, close] = clipped ? ['<div class="clip">', "</div>"] : ["", ""];
      return `<td class="${cls}${visual ? ` ${visual.cls}` : ""}"${title}${painted} data-cell="${index - 1}">${open}`
        + (visual && visual.icon ? `<span class="vicon" style="color:${visual.ink}">${visual.icon}</span>` : "")
        + `${(state.highlight || state.search) ? markText(text, [state.highlight, state.search]) : renderBoolean(index - 1, text)}`
        + `${noted ? '<span class="notemark"></span>' : ""}${close}</td>`;
    }).join("");
    const bookmark = state.bookmarks.get(String(id));
    const quick = state.payload?.row_marks?.[id];
    // "none" is a string, and a string is true: a rule without a visual format must
    // still paint its row. (This cost a silent regression: every plain colour rule
    // stopped painting the day the server started sending visual: "none".)
    const plain = rule && (!rule.visual || rule.visual === "none")
      && (rule.target === null || rule.target === undefined);
    const style = plain
      ? ` style="${ruleCss(rule)}"`
      : "";
    return `<tr data-row="${escapeHtml(String(id))}" class="${rowSelected(id) ? "sel" : ""}"${style}>
      <td class="markcell"><button class="cb${quick ? " quick-mark" : ""}${bookmark ? " marked" : ""}" type="button"
        title="${escapeHtml(bookmark || quick?.label || ROW_MARK_HELP)}"
        aria-label="${escapeHtml(rowMarkLabel(id, quick, bookmark))}" aria-description="${ROW_MARK_HELP}">${quick ? escapeHtml(quick.code) : ""}</button></td>${cells}</tr>`;
  });
  let nextRow = 0;
  const rendered = outline
    ? outline.map((record) => record ? outlineRow(record, shown.length + 1) : dataRows[nextRow++])
    : dataRows;
  $("body").innerHTML = gridVirtualSpacer(shown.length + 1, state.offset) + rendered.join("")
    + gridVirtualSpacer(shown.length + 1, gridPageTotal() - state.offset - rendered.length)
    + footerRowsHtml(shown, 0);

  const total = gridPageTotal();
  const from = total ? state.offset + 1 : 0;
  const to = Math.min(state.offset + rendered.length, total);
  $("pageinfo").textContent = `${from}–${to} / ${total} ${outline ? "entries" : "row(s)"}`;
  if ($("analysis-view").style.display !== "none") {
    say(`${state.total} row(s) in this analysis${state.filters.length ? ` — ${state.filters.length} filter(s)` : ""}`);
  }
  applyPinning();
  if (deferColumns !== true && state.payload?.projection && shown.some((item) => item.index !== undefined
      && !state.payload.projection.includes(item.index))) {
    loadRows(false, true);
  }
}

function outlineRow(record, colspan) {
  const depth = record.path.length;
  const name = groupColumnName(state.groups[depth - 1]);
  const [value, count, ...summaries] = record.values;
  const label = `${name}: ${value === null || value === "" ? "(empty)" : value}`;
  const summary = summaries.length ? ` · ${summaries.map((item, index) =>
    summaryText(state.payload.summaries[index], item)).join(" · ")}` : "";
  const path = record.footer ? "" : ` data-outline-path="${escapeHtml(JSON.stringify(record.path))}"`;
  return `<tr class="${record.footer ? "gfooter" : "outline-group"}"${path}>
    <td colspan="${colspan}" style="padding-left:${8 + (depth - 1) * 14}px">
    ${record.footer ? "Total · " : "▾ "}<b>${escapeHtml(label)}</b> — ${count} row(s)${escapeHtml(summary)}</td></tr>`;
}

/* The desktop charts the grouped counts; this is the same page of groups as the
   grid, so the bars and the table can never disagree. */
const CHART_ROWS = 14;

function renderGroupChart() {
  const box = $("group-chart");
  if (!state.grouped || !state.rows.length) { box.hidden = true; box.innerHTML = ""; return; }
  const name = groupColumnName(state.groups[state.path.length]) || "group";
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
  $("grid").style.width = "";
  const column = state.groups[state.path.length];
  const name = groupColumnName(column) || `column ${column + 1}`;
  const empty = $("grid-empty");
  empty.hidden = state.rows.length > 0;
  empty.textContent = "No group at this level.";

  const summaries = (state.payload && state.payload.summaries) || [];
  $("cols").innerHTML = '<col style="width:30px"><col style="width:34px"><col><col style="width:90px">'
    + summaries.map(() => '<col style="width:130px">').join("");
  $("head").innerHTML = `<tr>${BOOKMARK_GROUP_HEADER}<th>Ro…</th><th>${escapeHtml(name)}</th><th>Rows</th>`
    + summaries.map((item) => `<th title="${escapeHtml(item.name)}">`
      + `${escapeHtml(item.operation)} ${escapeHtml(item.name)}</th>`).join("") + "</tr>";

  const colspan = 4 + summaries.length;
  $("body").innerHTML = gridVirtualSpacer(colspan, state.offset) + state.rows.map((row, position) => {
    const value = row[0];
    const count = row[1];
    const text = value === null || value === "" ? "(empty)" : String(value);
    return `<tr data-group="${escapeHtml(text)}" data-group-depth="${state.path.length}" data-value="${escapeHtml(String(value ?? ""))}"${value === null ? " data-group-null" : ""}>
      <td><span class="cb"></span></td>
      <td class="rowid">${state.offset + position + 1}</td>
      <td title="${escapeHtml(text)}">▸ ${escapeHtml(text)}</td>
      <td>${count}</td>
      ${summaries.map((_item, offset) => {
        const value = row[2 + offset];
        return `<td>${value === null || value === undefined ? "" : escapeHtml(String(value))}</td>`;
      }).join("")}</tr>`;
  }).join("") + gridVirtualSpacer(colspan, gridPageTotal() - state.offset - state.rows.length)
    + footerRowsHtml([], 3 + summaries.length);

  const count = gridPageTotal();
  const from = count ? state.offset + 1 : 0;
  const to = Math.min(state.offset + state.rows.length, count);
  renderGroupChart();
  $("pageinfo").textContent = `${from}–${to} / ${count} group(s) — ${state.total} row(s)`;
  if ($("analysis-view").style.display !== "none") {
    say(`Grouped by ${name} — ${state.rows.length} group(s) on this page, ${state.total} row(s) in the analysis`);
  }
}

/* The summary lines under the rows: a group's own (placed in the column each summary names) and
   the totals of the whole filtered analysis, as the desktop's grid draws its footers. */
function summaryText(item, value) {
  return `${item.operation} ${value === null || value === undefined ? "∅" : value}`;
}

function footerRowsHtml(columns, leading) {
  const payload = state.payload || {};
  let html = "";
  if (payload.footer && (payload.summaries || []).length && payload.footer_mode !== "hidden") {
    const placed = new Map();
    (payload.summaries || []).forEach((item, offset) => {
      const target = (payload.summary_footers || [])[offset];
      const column = target === null || target === undefined ? item.column : target;
      if (column >= 0) placed.set(column, (placed.get(column) ? placed.get(column) + " · " : "") + summaryText(item, payload.footer[offset]));
    });
    if (placed.size) {
      html += `<tr class="gfooter" title="The summaries of this group"><td></td>${columns.map(({ index }) =>
        `<td>${index === 0 ? "Σ" : escapeHtml(placed.get(index - 1) || "")}</td>`).join("")}</tr>`;
    }
  }
  if (payload.totals && (payload.total_summaries || []).length) {
    const text = payload.total_summaries.map((item, offset) =>
      `${escapeHtml(item.name)}: ${escapeHtml(summaryText(item, payload.totals[offset]))}`).join(" · ");
    html += `<tr class="gtotal" title="The totals of the whole filtered analysis"><td></td><td colspan="${Math.max(1, columns.length + leading)}"><b>Total</b> — ${text}</td></tr>`;
  }
  return html;
}

async function completeRow(row, readProvenance = false) {
  const projected = state.payload?.projection;
  if (!row || (!projected && !readProvenance) || row._complete) return row;
  const caseId = state.openCase.id, analysis = state.analysis;
  const payload = await api(`/api/cases/${caseId}/timeline/row/${analysis}/${row[0]}`);
  if (state.openCase?.id !== caseId || state.analysis !== analysis) return null;
  if (projected) payload.values.forEach((value, index) => { row[index + 1] = value; });
  row._complete = true;
  row.provenance = payload.provenance;
  return row;
}

let detailsRequest = 0;
async function showDetails(row) {
  const request = ++detailsRequest;
  const box = $("details");
  if (!row) {
    box.innerHTML = '<div class="ph">Details of the selected row</div>';
    return;
  }
  const recmd = Object.keys(currentRecmdColumns()).length > 0;
  if ((state.payload?.projection || recmd) && !row._complete) {
    box.innerHTML = '<div class="ph">Reading all fields of the selected row…</div>';
    try { row = await completeRow(row, recmd); }
    catch (error) { if (request === detailsRequest) box.textContent = error.message; return; }
    if (request !== detailsRequest || !row) return;
  }
  const rowNotes = notesForRow(row[0]);
  const dates = reviewDateRows(state.columns.slice(1), row.slice(1));
  const source = reviewRowProvenance(row);
  const pairs = visibleColumns().map(({ name, index }) => {
    const value = row[index];
    if (index === 0) return "";
    if (value === null || value === undefined || value === "") return "";
    const note = rowNotes[String(index - 1)];
    return `<tr><td class="k">${escapeHtml(name)}</td>
      <td>${escapeHtml(String(value))}</td>
      <td class="k"><button class="btn" data-cellnote="${index - 1}" aria-label="${note ? "Edit" : "Add"} note for ${escapeHtml(name)}">${note ? "edit note" : "note"}</button>
      ${note ? `<span class="cellnote">${escapeHtml(note)}</span>` : ""}</td></tr>`;
  }).join("");
  const id = String(row[0]);
  const note = state.bookmarks.get(id) || "";
  box.innerHTML = `<div class="detail-fields">${source}${dates}<table>${pairs}</table></div>
    <div class="note-editor">
      <label for="note-input">Bookmark note</label>
      <input id="note-input" value="${escapeHtml(note)}" placeholder="What to remember about this row…">
      <button class="btn" id="note-save">Save</button>
      <button class="btn" id="note-clear">Remove</button>
    </div>`;
  box.querySelectorAll("[data-cellnote]").forEach((button) => {
    button.addEventListener("click", async () => {
      const column = Number(button.dataset.cellnote);
      const current = notesForRow(id)[String(column)] || "";
      const note = await ask({ title: "Cell note",
                               label: `Note for ${state.columns[column + 1] || "this cell"}`,
                               value: current });
      if (note === null) return;
      try {
        await apiPost(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/cellnote`,
          { row_id: Number(id), column, note });
        await loadCellNotes();
        await loadRules();
        // the panel the note was written from shows it now, not after the next selection
        showDetails(state.rows.find((item) => String(item[0]) === id) || null);
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

let tabChosen = false;
let artifactsVisible = null;

function syncArtifacts() {
  const app = document.querySelector(".app");
  const scale = Number(getComputedStyle(app).zoom) || 1;
  const compact = document.documentElement.clientWidth / scale <= 560;
  app.classList.toggle("compact-workspace", compact);
  const available = Boolean(state.openCase);
  const visible = available && (artifactsVisible ?? !compact);
  $("artifacts").hidden = !visible;
  $("artifacts-toggle").disabled = !available;
  $("artifacts-toggle").setAttribute("aria-expanded", String(visible));
  document.querySelector(".work").classList.toggle("artifacts-hidden", !visible);
}

function workspaceTabs() {
  return [...$("doctabs").querySelectorAll(".tab[data-tab]")];
}

function moveWorkspaceTab(event) {
  const tabs = workspaceTabs();
  const index = tabs.indexOf(event.target);
  if (index < 0 || event.altKey || event.ctrlKey || event.metaKey) return;
  let destination;
  if (event.key === "ArrowLeft") destination = (index - 1 + tabs.length) % tabs.length;
  else if (event.key === "ArrowRight") destination = (index + 1) % tabs.length;
  else if (event.key === "Home") destination = 0;
  else if (event.key === "End") destination = tabs.length - 1;
  else return;
  event.preventDefault();
  tabs.forEach((tab, i) => { tab.tabIndex = i === destination ? 0 : -1; });
  tabs[destination].focus();
}

function showTab(name) {
  const tabs = workspaceTabs();
  const selected = tabs.find(tab => tab.dataset.tab === name);
  if (!selected) return;
  if (!selected.classList.contains("active")) rememberReviewPlace();
  const status = $("status");
  if (status.dataset.view && status.dataset.view !== name) {
    status.textContent = status.title = "";
    status.dataset.view = "";
    status.classList.remove("err");
  }
  const focused = document.activeElement;
  $("pane-tabs").hidden = name !== "analyses";
  const previousPanel = focused?.closest('[role="tabpanel"]');
  tabChosen = true;
  for (const tab of tabs) {
    const active = tab === selected;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
    $(tab.getAttribute("aria-controls")).style.display = active ? "flex" : "none";
  }
  if (tabs.includes(focused) || previousPanel?.style.display === "none") {
    selected.focus({ preventScroll: true });
  }
  selected.scrollIntoView({ block: "nearest", inline: "nearest" });
  if (name === "hayabusa" && state.openCase) loadFindings(false);
  if (name === "graph" && state.openCase) buildGraph();
  if (name === "imports" && state.openCase) loadImports();
  if (name === "actions" && state.openCase) {
    loadActions();
    if (document.querySelector('[data-sub="tracking"]').classList.contains("active")) refreshTracking();
  }
  syncArtifacts();
  if (name === "timeline" && state.openCase) loadTimeline(!timelineState.payload);
}

function openGroupPicker() {
  if (!state.columns.length) { say("Open an analysis first", true); return; }
  const list = $("group-levels");
  const columns = [BOOKMARK_GROUP_COLUMN, ...state.columns.slice(1).map((_, column) => column)];
  const order = [...state.groups, ...columns
    .filter((column) => !state.groups.includes(column))];
  list.innerHTML = order.map((column) => `
    <div class="row" draggable="true" data-group-choice>
      <label><input type="checkbox" data-group-level="${column}" ${state.groups.includes(column) ? "checked" : ""}>
        ${escapeHtml(groupColumnName(column))}</label>
      <button type="button" class="btn" data-group-up aria-label="Move ${escapeHtml(groupColumnName(column))} up">↑</button>
      <button type="button" class="btn" data-group-down aria-label="Move ${escapeHtml(groupColumnName(column))} down">↓</button>
    </div>`).join("");
  list.querySelectorAll("[data-group-up], [data-group-down]").forEach((button) => {
    button.addEventListener("click", () => {
      const row = button.parentElement;
      if (button.hasAttribute("data-group-up")) row.previousElementSibling?.before(row);
      else row.nextElementSibling?.after(row);
      button.focus();
    });
  });
  $("group-interval").value = state.interval;
  $("group-modal").classList.add("show");
}

function moveColumn(header, direction) {
  const order = orderedColumns().filter((item) => item.index > 0).map((item) => item.index - 1);
  const at = order.indexOf(header);
  const to = at + direction;
  if (at < 0 || to < 0 || to >= order.length) return;
  [order[at], order[to]] = [order[to], order[at]];
  state.colOrder = order;
  renderGrid();
  saveLayoutSoon();
  openColumnManager();
}

let columnManagerOffset = 0;
function openColumnManager() {
  if (!state.columns.length) { say("Open an analysis first", true); return; }
  if (!$("columns-modal").classList.contains("show")) {
    $("column-search").value = "";
    $("columns-hidden-only").checked = false;
    columnManagerOffset = 0;
  }
  $("family-save").hidden = !reviewFamilyKey();
  const list = $("columns-list");
  const query = $("column-search").value.trim().toLocaleLowerCase();
  const hiddenOnly = $("columns-hidden-only").checked;
  const matches = orderedColumns().filter(({ name, index }) =>
    (!hiddenOnly || state.hidden.has(index)) && (index === 0 ? "Row number" : name).toLocaleLowerCase().includes(query));
  columnManagerOffset = Math.min(columnManagerOffset, Math.max(0, Math.floor((matches.length - 1) / 100) * 100));
  const page = matches.slice(columnManagerOffset, columnManagerOffset + 100);
  const pager = matches.length > 100 ? `<div class="row"><button class="btn" data-column-page="-1" ${columnManagerOffset ? "" : "disabled"}>Previous</button>
    <span>${columnManagerOffset + 1}–${columnManagerOffset + page.length} / ${matches.length} columns</span>
    <button class="btn" data-column-page="1" ${columnManagerOffset + 100 < matches.length ? "" : "disabled"}>Next</button></div>` : "";
  list.innerHTML = pager + page.map(({ name, index }) => `
    <label>
      <input type="checkbox" data-col="${index}" ${state.hidden.has(index) ? "" : "checked"}>
      <span data-column-label>${escapeHtml(index === 0 ? "Row number" : name)}</span>
      ${index ? `<span class="pin"><button class="btn" data-jump-column="${index}" title="Show this column in the grid">Go to</button><button class="btn" data-move="${index - 1}" data-dir="-1" title="Move this column earlier">↑</button>
        <button class="btn" data-move="${index - 1}" data-dir="1" title="Move this column later">↓</button>
        width <input type="number" data-width="${index}" min="30" max="1200" style="width:64px" value="${state.widths[index] || ""}" placeholder="auto">
        <input type="checkbox" data-bool="${index - 1}" ${booleanColumns().has(index - 1) ? "checked" : ""}> boolean
        <input type="checkbox" data-pin="${index - 1}" ${state.pinned.has(index - 1) ? "checked" : ""}> pin left
        <input type="checkbox" data-pinright="${index - 1}" ${state.pinnedRight.has(index - 1) ? "checked" : ""}> pin right</span>` : ""}
    </label>`).join("");
  list.querySelectorAll("[data-column-page]").forEach((button) => button.addEventListener("click", () => {
    columnManagerOffset += Number(button.dataset.columnPage) * 100;
    openColumnManager();
    list.scrollTop = 0;
  }));
  list.querySelectorAll("[data-jump-column]").forEach((button) => button.addEventListener("click", async (event) => {
    event.preventDefault();
    const index = Number(button.dataset.jumpColumn);
    state.hidden.delete(index);
    closeModals();
    if (state.grouped) { state.groups = []; state.path = []; state.expandAll = false; await loadRows(true); }
    renderGrid();
    let left = 30;
    for (const item of visibleColumns()) {
      if (item.index === index) break;
      left += state.widths[item.index] || defaultWidth(item.name, item.index);
    }
    $("gridbody").scrollLeft = Math.max(0, left - 30);
    renderGrid();
    saveLayoutSoon();
  }));
  list.querySelectorAll("button[data-move]").forEach((button) => {
    button.addEventListener("click", (event) => { event.preventDefault(); moveColumn(Number(button.dataset.move), Number(button.dataset.dir)); });
  });
  list.querySelectorAll("input[data-width]").forEach((input) => {
    input.addEventListener("change", () => {
      const index = Number(input.dataset.width);
      const width = Math.round(Number(input.value));
      if (width >= 30) state.widths[index] = width; else delete state.widths[index];
      renderGrid();
      saveLayoutSoon();
    });
  });
  list.querySelectorAll("input[data-col]").forEach((box) => {
    box.addEventListener("change", () => {
      const index = Number(box.dataset.col);
      if (box.checked) state.hidden.delete(index); else state.hidden.add(index);
      updateColumnList();
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
  $("columns-no-match").hidden = matches.length > 0;
  $("column-visibility").textContent = `${state.hidden.size} hidden`;
  $("columns-modal").classList.add("show");
}

function updateColumnList() {
  columnManagerOffset = 0;
  openColumnManager();
}

async function hideEmptyColumns() {
  if (!state.openCase || !currentAnalysis()) return;
  const { id } = state.openCase;
  const analysis = state.analysis;
  const buttons = [$("hide-empty-columns"), $("grid-hide-empty")];
  buttons.forEach(button => { button.disabled = true; });
  say("Checking all rows for empty columns…");
  try {
    const { columns } = await api(`/api/cases/${id}/analyses/${analysis}/empty-columns`);
    if (state.openCase?.id !== id || state.analysis !== analysis) return;
    const before = state.hidden.size;
    columns.forEach((column) => state.hidden.add(column));
    renderGrid();
    if ($("columns-modal").classList.contains("show")) openColumnManager();
    saveLayoutSoon();
    say(`${state.hidden.size - before} empty column(s) hidden`);
  } catch (error) {
    if (state.openCase?.id === id && state.analysis === analysis) say(error.message, true);
  } finally {
    buttons.forEach(button => { button.disabled = false; });
  }
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
  grid.querySelectorAll(".colfilter th[data-filter-column]").forEach((th) => {
    place(th, Number(th.dataset.filterColumn) - 1);
  });
  grid.querySelectorAll("tbody td[data-cell]").forEach((td) => {
    place(td, Number(td.dataset.cell));
  });
}

function applyGrouping() {
  const checked = [...$("group-levels").querySelectorAll("[data-group-level]:checked")];
  state.groups = checked.map((input) => Number(input.dataset.groupLevel));
  state.interval = $("group-interval").value;
  state.path = [];
  closeModals();
  renderGroupBar();
  loadRows(true);
}

/* ---------- one text box ---------- */

/* window.prompt blocks the whole page — the CDP capture stops answering and the
   browser's own box cannot be styled. This is the same question, asked in the
   window, and it resolves null when the analyst cancels. */
const askState = { resolve: null };

function ask(options) {
  const settings = options || {};
  return new Promise((resolve) => {
    $("ask-title").textContent = settings.title || "Value";
    $("ask-label").textContent = settings.label || "Value";
    $("ask-input").value = settings.value === undefined || settings.value === null
      ? "" : String(settings.value);
    $("ask-input").placeholder = settings.placeholder || "";
    const note = $("ask-note");
    note.textContent = settings.note || "";
    note.style.display = settings.note ? "" : "none";
    askState.resolve = resolve;
    $("ask-modal").classList.add("show");
    setTimeout(() => { $("ask-input").focus(); $("ask-input").select(); }, 30);
  });
}

function answerAsk(value) {
  const resolve = askState.resolve;
  askState.resolve = null;
  $("ask-modal").classList.remove("show");
  if (resolve) resolve(value);
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
  // The three heights are one preference now: the dialog writes them together.
  applyStoredRowHeight();
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
  syncArtifacts();
}

/* ---------- events ---------- */

function placePopup(popup, x, y) {
  popup.style.left = "0px";
  popup.style.top = "0px";
  const origin = popup.getBoundingClientRect();
  const scale = origin.width / popup.offsetWidth || 1;
  const width = document.documentElement.clientWidth;
  const height = document.documentElement.clientHeight;
  popup.style.setProperty("--popup-max-width", `${width / scale}px`);
  popup.style.maxHeight = `${height / scale}px`;
  const bounds = popup.getBoundingClientRect();
  popup.style.left = `${(Math.max(0, Math.min(x, width - bounds.width)) - bounds.left) / scale}px`;
  popup.style.top = `${(Math.max(0, Math.min(y, height - bounds.height)) - bounds.top) / scale}px`;
}

function closeMenus() {
  document.querySelectorAll(".menu.show").forEach((menu) => menu.classList.remove("show"));
  document.querySelectorAll(".menubar .m.open").forEach((cell) => {
    cell.classList.remove("open");
    cell.setAttribute("aria-expanded", "false");
  });
}

function openMenu(name) {
  const cell = document.querySelector(`.menubar .m[data-menu="${name}"]`);
  const menu = document.querySelector(`.menu[data-for="${name}"]`);
  if (!cell || !menu) return;
  closeMenus();
  menu.classList.add("show");
  cell.classList.add("open");
  cell.setAttribute("aria-expanded", "true");
  const anchor = cell.getBoundingClientRect();
  placePopup(menu, anchor.left, anchor.bottom);
  return menu;
}

function wireDialogAccessibility() {
  const dialogs = new Map();
  const open = [];
  const visibility = new MutationObserver((records) => {
    const previous = open.at(-1);
    const active = document.activeElement;
    for (const { target } of records) {
      const entry = dialogs.get(target);
      const index = open.indexOf(entry);
      if (target.classList.contains("show")) {
        if (index !== -1) continue;
        entry.opener = previous?.dialog.contains(active) || active === document.body
          ? previous?.opener : active;
        open.push(entry);
      } else if (index !== -1) {
        open.splice(index, 1);
      }
    }
    const current = open.at(-1);
    if (current === previous) return;
    if (current && !current.dialog.contains(document.activeElement)) {
      const first = current.dialog.querySelector("[data-initial-focus]") || current.dialog;
      first.focus({ preventScroll: true });
    } else if (!current && (document.activeElement === document.body ||
        previous?.dialog.contains(document.activeElement))) {
      const opener = previous?.opener;
      if (opener?.isConnected && opener.getClientRects().length) {
        opener.focus({ preventScroll: true });
      }
    }
  });

  document.addEventListener("keydown", (event) => {
    const dialog = open.at(-1)?.dialog;
    if (event.key !== "Tab" || !dialog) return;
    const controls = [...dialog.querySelectorAll("button, input, select, textarea, a[href], [tabindex]")]
      .filter(el => el.tabIndex >= 0 && !el.matches(":disabled") && el.getClientRects().length);
    const first = controls[0] || dialog;
    const last = controls.at(-1) || dialog;
    const active = document.activeElement;
    if (event.shiftKey ? (active === first || active === dialog) : active === last) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus();
    }
  });

  document.querySelectorAll(".modal > .dialog").forEach((dialog) => {
    const modal = dialog.parentElement;
    const title = dialog.querySelector(":scope > h3");
    if (!title) return;
    if (!title.id) title.id = `${modal.id}-title`;
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-labelledby", title.id);
    dialog.setAttribute("aria-modal", "true");
    dialog.tabIndex = -1;
    dialogs.set(modal, { dialog, opener: null });
    visibility.observe(modal, { attributes: true, attributeFilter: ["class"] });
  });
}

function wire() {
  wireDialogAccessibility();
  window.addEventListener("resize", syncArtifacts);
  document.querySelectorAll('.menubar .m').forEach((node) => {
    node.tabIndex = 0;
    node.setAttribute("role", "button");
    node.setAttribute("aria-expanded", "false");
    node.addEventListener("mousedown", (event) => {
      event.stopPropagation();
      if (node.classList.contains("open")) closeMenus();
      else openMenu(node.dataset.menu);
    });
    node.addEventListener("keydown", (event) => {
      if (!["Enter", " ", "ArrowDown"].includes(event.key)) return;
      event.preventDefault();
      openMenu(node.dataset.menu)?.querySelector(".item:not(.disabled)")?.focus();
    });
  });
  // A press inside an open menu must reach its item: closing the menu on mousedown hides
  // the item before the click can land on it, and no menu command would ever run.
  document.addEventListener("mousedown", (event) => {
    if (event.target.closest && event.target.closest(".menu")) return;
    closeMenus();
  });

  document.querySelectorAll("[data-act]").forEach((node) => {
    if (node.matches(".menu .item")) {
      node.tabIndex = 0;
      node.setAttribute("role", "button");
      node.addEventListener("keydown", (event) => {
        if (!["Enter", " "].includes(event.key) || node.classList.contains("disabled")) return;
        event.preventDefault();
        document.querySelector(".menubar .m.open")?.focus();
        node.click();
      });
    }
    node.addEventListener("click", () => {
      // The menu closes first, then the command runs: a command that opens a dialog or
      // reads the page must not find the menu still on screen.
      if (node.closest(".menu")) closeMenus();
      act(node.dataset.act, node);
    });
  });

  document.querySelectorAll(".subtab[data-scope]").forEach((tab) => {
    tab.addEventListener("click", () => showRulesScope(tab.dataset.scope));
  });
  $("disk-start").addEventListener("click", startDiskAnalysis);
  $("disk-source").addEventListener("input", diskSourceEdited);
  $("disk-source").addEventListener("change", () => refreshDiskSpace());
  $("disk-source").addEventListener("keydown", (event) => {
    if (event.key === "Enter") refreshDiskSpace();
  });
  $("disk-kind").addEventListener("change", () => refreshDiskSpace());
  $("import-progress-stop").addEventListener("click", stopImportJob);
  $("retry-open").addEventListener("click", openRetry);
  $("coverage-open").addEventListener("click", openCoverage);
  $("coverage-run").addEventListener("click", runCoverage);
  $("coverage-level").addEventListener("change", renderCoverage);
  $("coverage-search").addEventListener("input", renderCoverage);
  $("coverage-export-json").addEventListener("click", () => {
    if (state.openCase) window.location.href = url(`/api/cases/${encodeURIComponent(state.openCase.id)}/coverage/export`);
  });
  $("coverage-export-csv").addEventListener("click", () => {
    if (state.openCase) window.location.href = url(`/api/cases/${encodeURIComponent(state.openCase.id)}/coverage/export?csv=true`);
  });
  $("rule-global-enabled").addEventListener("change", async (event) => {
    try {
      await apiPost("/api/global-rules/enabled", { enabled: event.target.checked });
      await loadGlobalRules();
      await refreshPaint();
      say(event.target.checked ? "Shared rules applied to this analysis"
                               : "Shared rules left out of this analysis");
    } catch (error) {
      say(error.message, true);
    }
  });
  $("rule-global-export").addEventListener("click", () => {
    window.location.href = url("/api/global-rules/file");
  });
  $("rule-global-import").addEventListener("click", () => $("rule-global-file").click());
  $("rule-global-file").addEventListener("change", async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    try {
      const response = await fetch(url("/api/global-rules/import"), { method: "POST", body });
      if (!response.ok) throw new Error((await response.json()).detail || response.statusText);
      const payload = await response.json();
      await loadGlobalRules();
      await refreshPaint();
      renderRulesList();
      say(`${payload.imported} shared rule(s) imported`);
    } catch (error) {
      say(error.message, true);
    } finally {
      event.target.value = "";
    }
  });

  const tabList = $("doctabs");
  tabList.addEventListener("click", (event) => {
    const tab = event.target.closest(".tab[data-tab]");
    if (tab) showTab(tab.dataset.tab);
  });
  tabList.addEventListener("keydown", moveWorkspaceTab);
  tabList.addEventListener("focusout", (event) => {
    if (tabList.contains(event.relatedTarget)) return;
    workspaceTabs().forEach(tab => {
      tab.tabIndex = tab.getAttribute("aria-selected") === "true" ? 0 : -1;
    });
  });

  $("cases-body").addEventListener("click", (event) => {
    const row = event.target.closest("tr[data-case]");
    if (!row) return;
    state.selectedCase = row.dataset.case;
    renderCaseSelection();
  });
  $("cases-body").addEventListener("keydown", (event) => {
    const row = event.target.closest("tr[data-case]");
    if (!row) return;
    if (event.key === "Enter") {
      event.preventDefault();
      openCase(row.dataset.case);
      return;
    }
    const move = { ArrowDown: row.nextElementSibling, ArrowUp: row.previousElementSibling,
                   Home: row.parentElement.firstElementChild, End: row.parentElement.lastElementChild };
    if (!(event.key in move)) return;
    event.preventDefault();
    const next = move[event.key] || row;
    state.selectedCase = next.dataset.case;
    renderCaseSelection();
    next.focus();
  });
  $("cases-body").addEventListener("dblclick", (event) => {
    const row = event.target.closest("tr[data-case]");
    if (row) openCase(row.dataset.case);
  });
  $("case-search").addEventListener("input", renderCases);
  $("case-archived").addEventListener("change", renderCases);
  $("package-input").addEventListener("change", uploadPortableCase);

  $("tree").addEventListener("click", (event) => {
    const group = event.target.closest("[data-group-key]");
    if (group) {
      const key = group.dataset.groupKey;
      if (treeState.collapsed.has(key)) treeState.collapsed.delete(key); else treeState.collapsed.add(key);
      renderTree();
      return;
    }
    const node = event.target.closest("[data-analysis]");
    if (!node) return;
    selectReviewAnalysis(Number(node.dataset.analysis));
  });
  $("tree-search").addEventListener("input", renderTree);
  $("tree-mode").value = treeState.mode;
  $("tree-mode").addEventListener("change", (event) => {
    treeState.mode = event.target.value;
    try { localStorage.setItem("fireblade.treeMode", treeState.mode); } catch (_) { /* kept for this page */ }
    renderTree();
  });
  $("retry-tick-all").addEventListener("click", () => $("retry-list").querySelectorAll("input[data-retry-tick]").forEach((box) => { box.checked = true; }));
  $("retry-tick-none").addEventListener("click", () => $("retry-list").querySelectorAll("input[data-retry-tick]").forEach((box) => { box.checked = false; }));
  $("retry-bulk-run").addEventListener("click", runRetryTicked);
  $("tree-expand").addEventListener("click", () => treeExpandAll(true));
  $("tree-collapse").addEventListener("click", () => treeExpandAll(false));

  $("search").addEventListener("keydown", (event) => {
    if (event.key === "Enter") { event.preventDefault(); submitReviewSearch(); }
  });
  $("bookmarks-only").addEventListener("click", () => {
    state.bookmarksOnly = !state.bookmarksOnly;
    $("bookmarks-only").classList.toggle("active", state.bookmarksOnly);
    loadRows(true);
  });

  // The toolbar button and the menu command are the same command: one function clears them.
  $("clear").addEventListener("click", clearEveryFilter);

  let resizing = null;
  $("head").addEventListener("mousedown", (event) => {
    const grip = event.target.closest("[data-grip]");
    if (!grip) return;
    event.preventDefault();
    const index = Number(grip.dataset.grip);
    const th = grip.closest("th");
    // The <col> of a header sits at the header's own position (the mark column comes first, and
    // a hidden column leaves a gap in the numbering): not at the column's absolute index.
    const position = [...th.parentNode.children].indexOf(th);
    resizing = { index, position, startX: event.clientX, startWidth: th.getBoundingClientRect().width };
    document.body.style.cursor = "col-resize";
  });
  document.addEventListener("mousemove", (event) => {
    if (!resizing) return;
    const width = Math.max(24, Math.round(resizing.startWidth + event.clientX - resizing.startX));
    state.widths[resizing.index] = width;
    const cols = $("cols").children;
    if (cols[resizing.position]) cols[resizing.position].style.width = width + "px";
  });
  document.addEventListener("mouseup", () => {
    if (!resizing) return;
    resizing = null;
    document.body.style.cursor = "";
    saveLayoutSoon();
  });

  $("head").addEventListener("click", async (event) => {
    const th = event.target.closest("th[data-column]");
    if (!th || event.target.closest("[data-grip], [data-column-values]")) return;
    const index = Number(th.dataset.column);
    if (index === 0) return;
    const column = index - 1;
    if (event.shiftKey) {
      const existing = state.multiSort.find((item) => item.column === column);
      if (existing) existing.descending = !existing.descending;
      else state.multiSort.push({ column, descending: false, kind: state.sortType });
      state.sort = null;
    } else {
      state.multiSort = [];
      if (state.sort === column) state.descending = !state.descending;
      else { state.sort = column; state.descending = false; }
    }
    const keyboardSort = event.detail === 0 && event.target.closest(".column-sort");
    if (await loadRows(true) && keyboardSort && document.activeElement === document.body) {
      $("head").querySelector(`th[data-column="${index}"] .column-sort`)?.focus({ preventScroll: true });
    }
  });

  // Drag a header onto the grouping bar; double-click the grip to fit the column.
  $("head").addEventListener("dragstart", (event) => {
    const th = event.target.closest("th[data-column], th[data-bookmark-group]");
    if (!th) return;
    const column = th.hasAttribute("data-bookmark-group")
      ? BOOKMARK_GROUP_COLUMN : Number(th.dataset.column) - 1;
    if (column === -1) return;
    event.dataTransfer.setData(GROUP_MIME, String(column));
    event.dataTransfer.effectAllowed = "copy";
  });

  $("head").addEventListener("dblclick", (event) => {
    const grip = event.target.closest("[data-grip]");
    if (!grip) return;
    event.preventDefault();
    fitColumnToContent(Number(grip.dataset.grip));
  });

  const groupbar = $("groupbar");
  if (groupbar) {
    const clearDrop = () => {
      groupbar.classList.remove("dropready");
      groupbar.querySelector(".drop-target")?.classList.remove("drop-target");
    };
    const dropTarget = (event) => event.target.closest(".gsep") || groupbar.querySelector(".gsep:last-child");
    groupbar.addEventListener("dragover", (event) => {
      if (![...(event.dataTransfer?.types || [])].includes(GROUP_MIME)) return;
      event.preventDefault();
      event.stopPropagation();
      clearDrop();
      groupbar.classList.add("dropready");
      dropTarget(event)?.classList.add("drop-target");
    });
    groupbar.addEventListener("dragleave", (event) => {
      if (!groupbar.contains(event.relatedTarget)) clearDrop();
    });
    $("head").addEventListener("dragend", clearDrop);
    groupbar.addEventListener("drop", (event) => {
      const value = event.dataTransfer.getData(GROUP_MIME);
      if (value === "") return;
      event.preventDefault();
      event.stopPropagation();
      const sep = dropTarget(event);
      clearDrop();
      const position = sep ? Number(sep.dataset.position) : state.groups.length;
      addGroupColumn(Number(value), position);
    });
  }
  const groupLevels = $("group-levels");
  const clearLevelTarget = () => groupLevels.querySelector(".drop-before, .drop-after")
    ?.classList.remove("drop-before", "drop-after");
  const beforeLevel = (row, y) => {
    const bounds = row.getBoundingClientRect();
    return y < bounds.top + bounds.height / 2;
  };
  groupLevels.addEventListener("dragstart", (event) => {
    const row = event.target.closest("[data-group-choice]");
    if (!row) return;
    row.classList.add("dragging");
    event.dataTransfer.setData(GROUP_LEVEL_MIME, "reorder");
    event.dataTransfer.effectAllowed = "move";
  });
  groupLevels.addEventListener("dragover", (event) => {
    if (!event.dataTransfer.types.includes(GROUP_LEVEL_MIME)) return;
    clearLevelTarget();
    const row = event.target.closest("[data-group-choice]:not(.dragging)");
    if (!row) return;
    event.preventDefault();
    row.classList.add(beforeLevel(row, event.clientY) ? "drop-before" : "drop-after");
  });
  groupLevels.addEventListener("dragleave", (event) => {
    if (!groupLevels.contains(event.relatedTarget)) clearLevelTarget();
  });
  groupLevels.addEventListener("drop", (event) => {
    const source = groupLevels.querySelector(".dragging");
    const target = event.target.closest("[data-group-choice]:not(.dragging)");
    if (!source || !target) return;
    event.preventDefault();
    if (beforeLevel(target, event.clientY)) target.before(source);
    else target.after(source);
    clearLevelTarget();
  });
  groupLevels.addEventListener("dragend", () => {
    groupLevels.querySelector(".dragging")?.classList.remove("dragging");
    clearLevelTarget();
  });
  const clearButton = $("group-clear");
  if (clearButton) clearButton.addEventListener("click", clearGrouping);

  $("head").addEventListener("keydown", (event) => {
    const input = event.target.closest("input[data-filter]");
    if (!input) return;
    if (event.key !== "Enter") return;
    event.preventDefault();
    clearTimeout(filterTimer);
    loadRows(true);
  });

  $("head").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-fop]");
    if (!button) return;
    event.stopPropagation();
    openFilterOperators(button);
  });
  $("head").addEventListener("input", (event) => {
    const input = event.target.closest("input[data-filter]");
    if (!input) return;
    // A sort or page response can replace the header while the analyst types.
    // Cancel that rendering before waiting to submit the new filter.
    rowsRequest?.abort();
    const column = Number(input.dataset.filter);
    // A comparison chosen with the icon is taken as it is ("^abc$" is then a pattern); the typed
    // prefixes (=, !=, ^, $…) only speak while no comparison has been chosen for the column.
    const parsed = state.filterOps[column]
      ? { operator: state.filterOps[column], value: input.value.trim() }
      : parseFilterValue(input.value);
    state.filters = state.filters.filter((item) => item.column !== column);
    if (input.value.trim() || parsed.operator === "empty" || parsed.operator === "not_empty") {
      state.filters.push({ column, ...parsed });
    }
    // The desktop filters while the analyst types; this window used to wait for
    // Enter. Every render rebuilds the filter row, so the caret is put back.
    const caret = input.selectionStart;
    clearTimeout(filterTimer);
    filterTimer = setTimeout(async () => {
      if (!await loadRows(true)) return;
      const again = document.querySelector(`#head input[data-filter="${column}"]`);
      if (!again) return;
      again.focus();
      const at = Math.min(caret === null ? again.value.length : caret, again.value.length);
      again.setSelectionRange(at, at);
    }, 320);
  });

  $("body").addEventListener("contextmenu", (event) => {
    const tr = event.target.closest("tr[data-row]");
    if (!tr) return;
    const cell = event.target.closest("td[data-cell]");
    contextCell = cell ? cell.dataset.cell : null;
    event.preventDefault();
    contextRow = tr;
    if (copyPrefs.rightCopy && !event.shiftKey && cell) {
      // Preferences > copy the cell on right-click: Shift opens the menu instead.
      copyCellValue();
      return;
    }
    const menu = $("row-menu");
    // The two EVTX actions only mean something in an alert analysis.
    for (const action of ["track-ip", "hunt-ip"]) {
      menu.querySelector(`[data-act="${action}"]`).hidden = !cell || !looksLikeIP(cell.textContent);
    }
    const alerts = isAlertAnalysis();
    for (const action of ["alert-context", "alert-source"]) {
      const item = menu.querySelector(`[data-act="${action}"]`);
      if (item) item.hidden = !alerts;
    }
    // As the desktop's menu: a selection that already has a note offers to edit it, else to add one.
    const noted = selectedIds().some((id) => {
      const note = state.bookmarks.get(String(id));
      return note && note !== "bookmarked";
    });
    const add = menu.querySelector('[data-act="note-selection"]');
    const edit = menu.querySelector('[data-act="note-replace"]');
    if (add) add.hidden = noted;
    if (edit) edit.hidden = !noted;
    menu.hidden = false;
    placePopup(menu, event.clientX, event.clientY);
  });
  document.addEventListener("click", () => { $("row-menu").hidden = true; $("filter-operators").hidden = true; });

  $("body").addEventListener("click", (event) => {
    const outline = event.target.closest("tr[data-outline-path]");
    if (outline) {
      state.expandAll = false;
      drillGridGroup(JSON.parse(outline.dataset.outlinePath));
      return;
    }
    const group = event.target.closest("tr[data-group]");
    if (group) {
      if (Number(group.dataset.groupDepth) !== state.path.length) return;
      drillGridGroup([...state.path, group.hasAttribute("data-group-null") ? null : group.dataset.value]);
      return;
    }
    const tr = event.target.closest("tr[data-row]");
    if (!tr) return;
    if (event.target.closest(".markcell")) {
      const id = tr.dataset.row;
      cycleRowMark(id, event.shiftKey).catch((error) => say(error.message, true));
      return;
    }
    // The cell clicked is the active cell, as in the desktop: the commands that act on "the
    // active cell" (filter on it, copy it, highlight it) no longer need a right-click first.
    const cell = event.target.closest("td[data-cell]");
    if (cell) {
      contextCell = cell.dataset.cell;
      contextRow = tr;
      $("body").querySelectorAll("td.activecell").forEach((node) => node.classList.remove("activecell"));
      cell.classList.add("activecell");
    }
    selectRow(tr, event);
  });

  $("first").addEventListener("click", () => {
    if (state.path.length) { returnToGridGroup(0); return; }
    loadRows(true);
  });
  $("prev").addEventListener("click", () => {
    if (!state.offset && state.path.length) { returnToGridGroup(state.path.length - 1); return; }
    state.offset = Math.max(0, state.offset - (state.payload?.limit ?? PAGE));
    loadRows(false);
  });
  $("next").addEventListener("click", () => {
    const total = gridPageTotal();
    const step = state.payload?.limit ?? PAGE;
    if (state.offset + step < total) { state.offset += step; loadRows(false); }
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

  $("details-toggle").addEventListener("click", toggleDetails);
  $("column-search").addEventListener("input", updateColumnList);

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
  // The layout is also a view of what is already in the case: choosing one lays the imports out again.
  $("import-layout").addEventListener("change", async (event) => {
    if (!state.openCase || !(state.openCase.collections || []).length) return;
    const select = event.currentTarget;
    const mode = select.value;
    const { id, layout } = state.openCase;
    select.disabled = true;
    say("Laying the analyses out again…");
    try {
      const done = await apiPost(`/api/cases/${id}/reorganize`, { mode });
      if (state.openCase?.id === id && done.collections) {
        resetTimeline(); resetFindings(); resetGraph(); resetIoc();
      }
      if (state.openCase?.id === id && await openCase(id)) {
        const message = done.collections ? "Layout changed" : "Already laid out that way";
        say([message, ...(done.notices || [])].join(" · "));
      }
    } catch (error) {
      if (state.openCase?.id === id) {
        if (layout) select.value = layout;
        say(error.message, true);
      }
    } finally {
      select.disabled = false;
    }
  });
  $("folder-input").addEventListener("change", (event) => {
    const files = [...(event.target.files || [])];
    event.target.value = "";        // the same folder can be picked again
    if (files.length) importFolder(files);
  });
  for (const id of ["import", "disk"]) {
    $(`${id}-threads`).addEventListener("input", () => showImportThreadCount(id));
  }
  for (const id of ["preview-delimiter", "preview-encoding"]) {
    $(id).addEventListener("change", refreshPreviews);
  }

  document.addEventListener("dragover", (event) => {
    if (!state.openCase) return;
    if (![...(event.dataTransfer?.types || [])].includes("Files")) return;
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

  $("rule-column").addEventListener("change", loadRuleValues);
  $("palette-input").addEventListener("input", renderPalette);
  $("ask-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") { event.preventDefault(); answerAsk($("ask-input").value); }
    if (event.key === "Escape") { event.preventDefault(); answerAsk(null); }
  });
  $("ask-modal").addEventListener("click", (event) => {
    if (event.target.id === "ask-modal") answerAsk(null);
  });

  $("palette-list").addEventListener("click", (event) => {
    const row = event.target.closest("[data-palette]");
    if (row) runPalette(Number(row.dataset.palette));
  });
  $("palette-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      runPalette(commandState.active);
    } else if (["ArrowDown", "ArrowUp"].includes(event.key) && commandState.shown.length) {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      selectPaletteItem(Math.max(0, Math.min(commandState.active + step, commandState.shown.length - 1)));
    }
  });
  $("messages-clear").addEventListener("click", () => {
    messageLog.length = 0;
    openMessages();
    say("Messages cleared");
  });
  $("analyses-save").addEventListener("click", saveAnalysesOrder);
  $("sort-add").addEventListener("click", () => {
    $("sort-rows").appendChild(sortRow({ column: 0, descending: false }));
  });
  $("sort-apply").addEventListener("click", applySortPriority);
  $("summary-add").addEventListener("click", () => {
    $("summary-rows").appendChild(summaryRow());
    refreshSummaryOrderChoices();
  });
  $("total-add").addEventListener("click", () => $("total-rows").appendChild(summaryRow(undefined, false)));
  $("summary-order").addEventListener("change", refreshSummaryOrderChoices);
  $("summary-apply").addEventListener("click", applySummaries);
  $("prefs-copy-headers").addEventListener("change", (event) => {
    copyPrefs.headers = event.target.checked;
    saveCopyPrefs();
    say(event.target.checked ? "Copy includes the headers" : "Copy leaves the headers out");
  });
  $("prefs-date-format").addEventListener("change", (event) => {
    copyPrefs.dateFormat = event.target.value;
    saveCopyPrefs();
    renderGrid();
    say(`Dates shown ${event.target.value}`);
  });
  $("rule-visual").addEventListener("change", showRuleVisual);
  $("session-file").addEventListener("change", (event) => {
    const file = (event.target.files || [])[0];
    if (file) readSessionFile(file);
  });
  $("destroy-photos").addEventListener("change", async (event) => {
    const input = event.currentTarget;
    const draft = destructionDraft;
    if (!draft || !input.files.length) return;
    const submit = $("destroy-modal").querySelector('[data-act="destroy-run"]');
    input.disabled = submit.disabled = true;
    try { await uploadDestroyPhotos([...input.files], draft); }
    catch (error) {
      if (destructionDraft === draft) say(`The photos were not kept: ${error.message}`, true);
    } finally {
      if (destructionDraft === draft) input.disabled = submit.disabled = false;
    }
  });
  $("rule-add-condition").addEventListener("click", () => {
    addConditionRow();
    if ($("rule-logic").value === "single") $("rule-logic").value = "and";
  });
  $("entity-cancel").addEventListener("click", stopEditingEntity);
  $("report-filter").addEventListener("change", renderRetryList);
  $("layout-file").addEventListener("change", async (event) => {
    const file = event.target.files && event.target.files[0];
    if (file) await importLayout(file);
    event.target.value = "";
  });
  $("finding-search").addEventListener("input", renderFindingView);
  $("finding-view").addEventListener("change", renderFindingView);
  $("finding-group").addEventListener("change", renderFindingView);
  $("finding-level").addEventListener("change", renderFindingView);
  $("coverage-plan").addEventListener("click", openCoveragePlan);
  $("coverage-plan-apply").addEventListener("click", applyCoveragePlan);
  $("coverage-profile").addEventListener("change", () => { coverageTools = null; });
  window.addEventListener("resize", () => {
    if ($("finding-view").value !== "table") renderFindingView();
  });
  $("report-type").addEventListener("change", showReportType);
  $("date-mode").addEventListener("change", showDateMode);
  $("date-add").addEventListener("click", addDateCondition);
  $("ioc-scan").addEventListener("click", runIocScan);
  $("ioc-file-open").addEventListener("click", () => $("ioc-file").click());
  $("ioc-file").addEventListener("change", async (event) => {
    const file = event.target.files && event.target.files[0];
    event.target.value = "";
    if (file) await runIocFile(file);
  });
  $("ioc-history").addEventListener("change", (event) => openHunt(event.target.value));
  $("ioc-stop").addEventListener("click", stopIocHunt);
  $("ioc-all-iocs").addEventListener("click", () => iocPage(0, null));
  $("ioc-prev").addEventListener("click", () => iocPage(-iocState.pageSize));
  $("ioc-next").addEventListener("click", () => iocPage(iocState.pageSize));
  $("ioc-list-rows").addEventListener("click", (event) => {
    const row = event.target.closest("tr[data-ioc]");
    if (row) iocPage(0, Number(row.dataset.ioc));
  });
  $("ioc-rows").addEventListener("dblclick", async (event) => {
    const row = event.target.closest("tr[data-hit]");
    if (!row) return;
    const hit = iocState.hits[Number(row.dataset.hit)];
    if (!hit || hit.analysis === null || hit.analysis === undefined) {
      say("This analysis is closed or has changed: reopen the original analysis to read this row", true);
      return;
    }
    await openSourceRow(hit.analysis, hit.row_id);
  });
  $("ioc-history").addEventListener("focus", loadHuntHistory);
  $("derived-operation").addEventListener("change", derivedOperationChanged);
  $("hayabusa-run").addEventListener("click", runHayabusa);
  $("detrules-open").addEventListener("click", openDetectionRules);
  $("detrules-reload").addEventListener("click", loadDetectionRules);
  $("detrules-changed").addEventListener("change", loadDetectionRules);
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
    const group = findingState.shown[Number(button.dataset.finding)];
    if (!group) return;
    if (button.dataset.want === "mark") markFinding(group);
    else showFindingInGrid(group);
  });
  $("hayabusa-summary").addEventListener("click", (event) => {
    const link = event.target.closest("a[data-sources]");
    if (!link || !state.openCase) return;
    event.preventDefault();
    window.location = url(`/api/cases/${state.openCase.id}/detection/${encodeURIComponent(link.dataset.sources)}/sources`);
  });
  $("graph-build").addEventListener("click", buildGraph);
  $("graph-level").addEventListener("change", () => renderGraph(graphPayload));
  $("graph-navigator").addEventListener("click", exportNavigator);
  $("graph-png").addEventListener("click", exportGraphPng);
  $("graph-node").addEventListener("click", openGraphNode);
  // Cards, links and the evidence panel are drawn again at every build: one listener each, on the box.
  $("graph-nodes").addEventListener("click", (event) => {
    const card = event.target.closest(".gnode");
    if (card) { event.stopPropagation(); graphSelect("node", card.dataset.node); }
  });
  $("graph-nodes").addEventListener("keydown", (event) => {
    const card = event.target.closest(".gnode");
    if (card && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); graphSelect("node", card.dataset.node); }
  });
  $("graph-edges").addEventListener("click", (event) => {
    const link = event.target.closest(".gedge, .gpill");
    if (link) { event.stopPropagation(); graphSelect("edge", link.dataset.edge); }
  });
  $("graph-wrap").addEventListener("click", (event) => {
    if (graphSelection && !event.target.closest(".gnode, .gedge, .gpill")) { graphSelection = null; graphHighlight(); renderGraphEvidence(); }
  });
  $("graph-evidence").addEventListener("click", (event) => {
    if (event.target.closest('[data-act="graph-close"]')) { graphSelection = null; graphHighlight(); renderGraphEvidence(); return; }
    const line = event.target.closest('[data-act="graph-line"]');
    if (line) { graphOpenLine(Number(line.dataset.analysis), Number(line.dataset.row), line); return; }
    const show = event.target.closest('[data-act="graph-show"]');
    if (show) graphShowAlerts(show.dataset.title, show.dataset.host);
  });
  $("imports-refresh").addEventListener("click", loadImports);
  $("imports-status").addEventListener("change", renderImports);
  $("imports-search").addEventListener("input", renderImports);
  $("action-add").addEventListener("click", addAction);
  document.querySelectorAll(".subtab[data-sub]").forEach((tab) => {
    tab.addEventListener("click", () => showWorkspaceSub(tab.dataset.sub));
  });
  $("entity-add").addEventListener("click", addEntity);
  $("indicator-add").addEventListener("click", addIndicators);
  $("indicator-remove").addEventListener("click", removeIndicator);
  $("client-open").addEventListener("click", openClientDialog);
  $("client-save").addEventListener("click", saveClientDialog);
  $("action-export").addEventListener("click", () => {
    if (!state.openCase) { say("Open a case first", true); return; }
    window.location.href = url(`/api/cases/${state.openCase.id}/actions/export`);
  });
  $("action-search").addEventListener("input", renderActions);
  $("action-open-only").addEventListener("change", renderActions);
  $("action-scope").addEventListener("change", loadActions);
  $("action-edit").addEventListener("click", () => openActionEditor(actionState.selected));
  $("action-refresh").addEventListener("click", () => loadActions());
  $("action-delete").addEventListener("click", () => {
    if (actionState.selected) removeActionRow(actionState.selected);
  });
  $("timeline-dates").addEventListener("change", applyTimelineDates);
  $("timeline-lane").addEventListener("change", (event) => {
    const selected = event.target.value;
    const sources = timelineState.payload?.sources || [];
    timelineState.hidden.clear();
    if (selected !== "") {
      for (const source of sources) {
        if (String(source.id) !== selected) timelineState.hidden.add(source.id);
      }
    }
    loadTimeline(true);
  });
  $("timeline-build").addEventListener("click", () => loadTimeline(false, true));
  $("timeline-undated").addEventListener("change", () => loadTimeline(true));
  $("timeline-exact").addEventListener("change", () => { if (timelineState.text) loadTimeline(true); });
  $("timeline-bookmarks").addEventListener("change", () => loadTimeline(true));
  $("timeline-preset").addEventListener("change", () => {
    timelinePreset(Number($("timeline-preset").value));
    $("timeline-preset").value = "0";
  });
  $("timeline-correlate").addEventListener("click", () => {
    timelineState.text = $("timeline-search").value.trim();
    timelineState.kind = $("timeline-kind").value;
    loadTimeline(true);
  });
  $("timeline-filters").addEventListener("change", () => loadTimeline(true));
  $("timeline-export").addEventListener("click", () => {
    if (!state.openCase) { say("Open a case first", true); return; }
    const params = new URLSearchParams();
    if (timelineState.start !== null) params.set("start", String(timelineState.start));
    if (timelineState.end !== null) params.set("end", String(timelineState.end));
    if (timelineState.text) { params.set("text", timelineState.text); params.set("kind", timelineState.kind); }
    if ($("timeline-exact").checked) params.set("exact", "true");
    if ($("timeline-bookmarks").checked) params.set("bookmarks", "true");
    const dates = timelineDatesParam();
    if (dates) params.set("dates", dates);
    if ($("timeline-undated").checked) params.set("include_undated", "true");
    if ($("timeline-filters").checked) {
      params.set("respect_filters", "true");
      params.set("live", JSON.stringify(liveView()));
    }
    const visible = timelineVisibleSources();
    if (visible) params.set("sources", visible.join(","));
    for (const field of timelineGrouping.levels) params.append("groups", field);
    if (timelineGrouping.path.length) params.set("group_path", JSON.stringify(timelineGrouping.path));
    // The run is verified server-side; the receipt comes back in the response headers.
    window.location.href = url(`/api/cases/${state.openCase.id}/timeline/export?${params}`);
    say("Timeline exported: the file carries only rows that were written and counted");
  });
  $("timeline-search").addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    timelineState.text = $("timeline-search").value.trim();
    timelineState.kind = $("timeline-kind").value;
    loadTimeline(true);
  });
  $("timeline-prev").addEventListener("click", () => timelinePage(-1));
  $("timeline-next").addEventListener("click", () => timelinePage(1));

  $("prefs-date-pattern").addEventListener("change", (event) => {
    copyPrefs.pattern = event.target.value.slice(0, 120);
    saveCopyPrefs();
    if (state.openCase && state.columns.length) loadRows(false);
  });
  $("prefs-right-copy").addEventListener("change", (event) => { copyPrefs.rightCopy = event.target.checked; saveCopyPrefs(); });
  $("prefs-tree").addEventListener("change", (event) => { copyPrefs.tree = event.target.value; saveCopyPrefs(); applyTreePosition(); });
  $("prefs-details").addEventListener("change", (event) => { copyPrefs.details = event.target.value; saveCopyPrefs(); applyDetailsPosition(); });
  $("prefs-pins").addEventListener("change", (event) => {
    copyPrefs.pins = event.target.value.split(/\r?\n/).map((name) => name.trim()).filter(Boolean).slice(0, 32);
    saveCopyPrefs();
  });
  for (const id of ["prefs-auto-profile", "prefs-memory", "prefs-query-threads", "prefs-parsing-threads"]) {
    $(id).addEventListener("change", saveResourcePrefs);
  }
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

  // The shortcuts announced next to the commands, and no others.
  // Only combinations a page may own are used; the browser keeps Ctrl+R, Ctrl+L, Ctrl+Tab...
  const SHORTCUTS = [
    { key: "o", act: "import-file" },
    { key: "i", shift: true, act: "import-folder" },
    { key: "s", act: "case-save" },
    { key: "e", shift: true, act: "export-csv" },
    { key: "f", act: "global-search" },
    { key: "k", act: "palette" },
    { key: "b", alt: true, act: "mark-selection" },
  ];
  document.addEventListener("keydown", (event) => {
    const command = event.ctrlKey || event.metaKey;
    if (command) {
      const shortcut = SHORTCUTS.find((item) => item.key === event.key.toLowerCase()
        && !!item.shift === event.shiftKey && !!item.alt === event.altKey);
      if (shortcut) {
        event.preventDefault();
        act(shortcut.act).catch((error) => say(error.message, true));
        return;
      }
      // Ctrl+C copies the selected rows, unless the analyst is copying text they selected.
      if (event.key.toLowerCase() === "c" && !event.shiftKey && !event.altKey
          && !(window.getSelection && String(window.getSelection())) && !/^(INPUT|TEXTAREA|SELECT)$/.test(
            (document.activeElement || {}).tagName || "") && state.selection && state.selection.size) {
        event.preventDefault();
        act("copy-row").catch((error) => say(error.message, true));
        return;
      }
    }
    if (event.key === "F1") { event.preventDefault(); act("help-guide").catch(() => {}); return; }
    if (event.key === "F5") { event.preventDefault(); loadCases(); }
    if (event.key === "Escape") {
      const trigger = document.querySelector(".menubar .m.open");
      closeModals();
      $("row-menu").hidden = true;
      $("filter-operators").hidden = true;
      trigger?.focus();
    }
    if (event.key === "/" && !event.ctrlKey && !event.metaKey && !event.altKey &&
        !document.querySelector(".modal.show") && $("search").getClientRects().length &&
        !event.target.closest?.("input, textarea, select, [contenteditable]")) {
      event.preventDefault();
      $("search").focus();
    }
  });
}

function closeModals() {
  if (askState.resolve) answerAsk(null);
  document.querySelectorAll(".modal").forEach((node) => node.classList.remove("show"));
  closeMenus();
}

function showReportType() {
  const client = $("report-type").value === "client";
  $("report-investigation-fields").style.display = client ? "none" : "";
  $("report-client-fields").style.display = client ? "" : "none";
}

function reportResult(message, links = []) {
  // The result stays in the dialog, with a link the analyst clicks: a window opened after a
  // long task is taken for a pop-up by the browser, and the report would be written for nothing.
  const box = $("report-result");
  box.textContent = "";
  box.append(message);
  for (const item of links) {
    const link = document.createElement("a");
    link.href = url(item.url);
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = item.label;
    box.append(" · ", link);
  }
  // The progress window closed every dialog while the report was written: the dialog that
  // asked for it comes back with the answer in it.
  if (box.textContent) $("report-modal").classList.add("show");
}

/* The timeline's current chart as a PNG, with the caption the desktop writes under it: what was
   correlated, exactly or not, which window — and what the picture does not show. */
function timelineChart() {
  const payload = timelineState.payload;
  const hist = payload && payload.histogram;
  if (!hist) return null;
  const sources = payload.sources || [];
  const width = 900;
  const height = 240;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, width, height);
  const { start, end } = timelineRange(hist);
  const totals = new Map();
  for (const [sourceIndex, bucket, count] of hist.rows) {
    if (timelineState.hidden.has(sourceIndex) || bucket < start || bucket > end) continue;
    if (!totals.has(bucket)) totals.set(bucket, []);
    totals.get(bucket).push([sourceIndex, count]);
  }
  const peak = Math.max(1, ...[...totals.values()].map((segments) => segments.reduce((sum, item) => sum + item[1], 0)));
  const span = end - start + 1;
  const bar = (width - 40) / span;
  for (const [bucket, segments] of totals) {
    let y = height - 30;
    for (const [sourceIndex, count] of segments) {
      const part = (count / peak) * (height - 60);
      context.fillStyle = TIMELINE_COLORS[sources.findIndex((item) => item.id === sourceIndex) % TIMELINE_COLORS.length] || "#2d9cdb";
      context.fillRect(20 + (bucket - start) * bar, y - part, Math.max(1, bar - 1), part);
      y -= part;
    }
  }
  context.fillStyle = "#444";
  context.font = "11px sans-serif";
  context.fillText(`${utcLabel(hist.start)} → ${utcLabel(hist.end)}`, 20, height - 10);
  const kinds = { text: "Any text", user: "User", ip: "IP address", path: "Path", hash: "Hash" };
  let caption = "Visible view of the timeline, a snapshot after indexing. Correlation: "
    + (kinds[timelineState.kind] || "Any text") + " · " + (timelineState.text || "none");
  caption += " · " + ($("timeline-exact").checked ? "exact value" : "contains the text");
  if ($("timeline-bookmarks").checked) caption += " · bookmarks only";
  if ($("timeline-filters").checked) caption += " · the analyses' filters applied when the index was built";
  if (timelineState.start !== null && timelineState.end !== null) {
    caption += ` · ${utcLabel(timelineState.start)} — ${utcLabel(timelineState.end)}`;
  }
  caption += " · The tracks outside the visible view are not drawn in this picture.";
  return { png: canvas.toDataURL("image/png").split(",")[1], caption };
}

/* "Client and mission": who the case is for and the engagement; the client report reads them. */
const CLIENT_FIELDS = [["client", "name", "cm-name"], ["client", "reference", "cm-reference"],
  ["client", "sector", "cm-sector"], ["client", "contact", "cm-contact"],
  ["engagement", "contract", "cm-contract"], ["engagement", "lead", "cm-lead"],
  ["engagement", "start", "cm-start"], ["engagement", "end", "cm-end"], ["engagement", "notes", "cm-notes"]];

async function openClientDialog() {
  if (!state.openCase) { say("Open a case first", true); return; }
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/client`);
    for (const [group, field, id] of CLIENT_FIELDS) $(id).value = (payload[group] || {})[field] || "";
    $("cm-result").textContent = "";
    $("client-modal").classList.add("show");
  } catch (error) {
    say(error.message, true);
  }
}

async function saveClientDialog() {
  const body = { client: {}, engagement: {} };
  for (const [group, field, id] of CLIENT_FIELDS) body[group][field] = $(id).value;
  try {
    await apiPut(`/api/cases/${state.openCase.id}/client`, body);
    closeModals();
    say("Client and mission saved");
  } catch (error) {
    $("cm-result").textContent = error.message;
    say(error.message, true);
  }
}

async function buildReport(asPdf) {
  if (!state.openCase) { say("Open a case first", true); return; }
  const client = $("report-type").value === "client";
  const params = client
    ? { client: true, title: $("client-title").value || "",
        analyst: $("client-analyst").value || "",
        findings: $("client-findings").checked, coverage: $("client-coverage").checked,
        pdf: asPdf }
    : { title: $("report-title").value || "Investigation report",
        description: $("report-description").value || "",
        bookmarks_only: $("report-bookmarks").value === "true",
        respect_filters: $("report-filters").checked,
        limit: Math.max(1, Math.min(10000, Number($("report-limit").value) || 2000)),
        live: liveView() };
  try {
    if (!client && $("report-selection").checked) {
      const ids = selectedIds();
      if (!ids.length) { reportResult("Select rows in the grid first."); say("Select rows in the grid first", true); return; }
      params.selected = { index: state.analysis, row_ids: ids };
      params.bookmarks_only = false;
    }
    if (!client && $("report-timeline").checked) {
      const chart = timelineChart();
      if (!chart) { reportResult("Build the timeline first: its chart is what the report would carry."); say("Build the timeline first", true); return; }
      params.timeline = chart;
    }
    if (client) {
      // The client report is one task: it reads the workspace, groups the
      // findings and writes the document, and the bar follows each step.
      const payload = await runTask("report", params, "Client report");
      if (!payload) { reportResult(""); return; }
      const message = `Client report: ${payload.findings} finding(s), ${payload.actions} action(s), `
        + `${payload.indicators} indicator(s)`;
      say(`${message} -> ${payload.name}`);
      reportResult(message, [{ url: payload.url, label: `Open ${payload.name}` }]);
      return;
    }
    const payload = await runTask("report", params, asPdf ? "Report as PDF" : "Report");
    if (!payload) { reportResult(""); return; }
    const empty = !payload.records
      ? " Nothing was selected: bookmark rows, or include every row, to fill the report." : "";
    if (!asPdf) {
      say(`Report: ${payload.records} finding(s) -> ${payload.name}`);
      reportResult(`Report: ${payload.records} finding(s).${empty}`,
                   [{ url: payload.url, label: `Open ${payload.name}` }]);
      return;
    }
    const converted = await runTask("report", { pdf: true, name: payload.name },
                                    "Report as PDF");
    if (!converted) { reportResult(""); return; }
    say(`Report as PDF: ${payload.records} finding(s) -> ${converted.name}`);
    reportResult(`Report as PDF: ${payload.records} finding(s).${empty}`,
                 [{ url: converted.url, label: `Open ${converted.name}` },
                  { url: payload.url, label: "HTML version" }]);
  } catch (error) {
    reportResult(error.message);
    say(error.message, true);
  }
}

async function act(name, node) {
  // A button inside a dialog belongs to that dialog: closing every modal first
  // used to make "Add a condition" dismiss the filter it was editing.
  if (!node || !node.closest(".dialog")) closeModals();
  if (["import-file", "import-folder", "disk-open"].includes(name)) {
    $("import-source-modal").classList.remove("show");
  }
  switch (name) {
    case "refresh-cases":
      await loadCases();
      if (state.openCase && $("tab-analyses").getAttribute("aria-selected") === "true") await loadRows(true);
      break;
    case "close-case": closeCase(); break;
    case "reload-analysis": await loadRows(true); break;
    case "export-csv":
      if (!state.openCase) { say("No case open", true); break; }
      exportRows({});
      break;
    case "export-groups":
      exportRows({ grouped: true });
      break;
    case "export-xlsx":
      if (!state.openCase) { say("No case open", true); break; }
      exportRows({ format: "xlsx" });
      say("Excel export: the same rows, as a workbook");
      break;
    case "import-evidence": openImportSourceChooser(); break;
    case "import-file": openImportDialog(); break;
    case "import-folder": openImportDialog(true); break;
    case "import-view-file": await viewCollectedFile(); break;
    case "import-copy-unread": await copyUnprocessedFiles(); break;
    case "import-export-list": exportCollectedList(); break;
    case "import-park": await parkCollectedFile(); break;
    case "import-delete": await deleteCollectedFile(); break;
    case "open-view-menu": openMenu("view"); break;
    case "preview-choose": $(previewState.folder ? "folder-input" : "preview-input").click(); break;
    case "preview-path": await previewServerPath(); break;
    case "layout-export": exportLayout(); break;
    case "layout-import": $("layout-file").click(); break;
    case "timeline-duration": await timelineDuration(); break;
    case "timeline-open-row": await openSelectedTimelineRow(); break;
    case "tl-zoom-in": timelineZoom(0.6); break;
    case "tl-zoom-out": timelineZoom(1.8); break;
    case "tl-fit": timelineFit(); break;
    case "tl-clear-range":
      timelineState.start = null;
      timelineState.end = null;
      await loadTimeline(true);
      break;
    case "tl-pan-left": timelinePan(-0.5); break;
    case "tl-pan-right": timelinePan(0.5); break;
    case "tl-back": timelineBack(); break;
    case "tl-isolate":
      // Clicking a chip hides one source, the way the desktop isolates one; this
      // brings them all back without rebuilding anything.
      timelineState.hidden.clear();
      $("timeline-lane").value = "";
      if (await loadTimeline(true)) say("Every source is shown again");
      break;
    case "preview-import": await confirmImport(); break;
    case "copy-value": await copyCellValue(); break;
    case "cell-note": await editCellNote(); break;
    case "search-value": await searchValueEverywhere(); break;
    case "correlate-value": await correlateValue(); break;
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
    case "group-column": openCurrentGrouping(); break;
    case "row-height": openRowHeight(); break;
    case "coverage-open": await openCoverage(); break;
    case "detrules-open": await openDetectionRules(); break;
    case "details-toggle": toggleDetails(); break;
    case "reset-widths": resetWidths(); break;
    case "add-filter": await openAddFilter(); break;
    case "clear-filters": clearEveryFilter(); break;
    case "note-selection": await noteSelection("append"); break;
    case "note-replace": await noteSelection("replace"); break;
    case "filter-active-cell": filterFromCell("eq"); break;
    case "expression-andor": openExpressionDialog(); break;
    case "help-hayabusa-source":
      window.open("https://github.com/Yamato-Security/hayabusa/tree/v4.3.1", "_blank", "noopener");
      say("Hayabusa 4.3.1 is the unmodified upstream release: its sources are published at github.com/Yamato-Security/hayabusa");
      break;
    case "reset-view": resetView(); break;
    case "expression-text": await openTextExpression(); break;
    case "show-timeline": showTab("timeline"); break;
    case "highlight-text": await openHighlight(); break;
    case "rowheight-apply": applyRowHeightPrefs(); break;
    case "derived-check": checkDerivedColumns(); break;
    case "session-save": saveSession(); break;
    case "session-open": openSessionFile(); break;
    case "graph-zoom-in": graphZoom(1.2); break;
    case "graph-zoom-out": graphZoom(1 / 1.2); break;
    case "graph-recentre": graphReset(); break;
    case "show-ioc": showTab("ioc"); break;
    case "detect-run": await runHayabusa(); break;
    case "export-annotations": await exportAnnotations(); break;
    case "export-portable": await exportPortable(node?.closest("#cases-view") ? state.selectedCase : state.openCase?.id); break;
    case "import-portable": $("package-input").click(); break;
    case "show-imports": showTab("imports"); break;
    case "stop-query": stopQuery(); break;
    case "ioc-export-matches": exportIocMatches(); break;
    case "ioc-export-summary": exportIocSummary(); break;
    case "case-autosave": showHelp("autosave"); break;
    case "cases-list": showTab("cases"); break;
    case "profiles-plugins": await openCompatibility(); break;
    case "legend": showHelp("legend"); break;
    case "workspace-guide": showHelp("workspace"); break;
    case "help-tutorial": showHelp("tutorial"); break;
    case "bookmark-note": await bookmarkNote(); break;
    case "mark-selection": await markSelection("bookmarked"); break;
    case "integrity": await openIntegrity(); break;
    case "next-tab": stepAnalysis(1); break;
    case "previous-tab": stepAnalysis(-1); break;
    case "expand-groups": expandEveryGroup(); break;
    case "collapse-groups": collapseEveryGroup(); break;
    case "help-guide": showHelp("guide"); break;
    case "help-coverage": showHelp("coverage"); break;
    case "help-ioc": showHelp("ioc"); break;
    case "help-timeline": showHelp("timeline"); break;
    case "help-licenses": showHelp("licenses"); break;
    case "global-search": openReviewSearch("case"); break;
    case "global-run": await runGlobalSearch(); break;
    case "new-case": openCaseDialog("create"); break;
    case "open-selected-case":
      if (state.selectedCase) await openCase(state.selectedCase);
      else say("Select a case first", true);
      break;
    case "rename-case": openCaseDialog("rename"); break;
    case "archive-case": await toggleArchive(); break;
    case "free-space": await freeCaseSpace(); break;
    case "restore-case": await restoreCaseFromArchive(); break;
    case "case-save": await saveCase(); break;
    case "case-confirm": await confirmCaseDialog(); break;
    case "action-save": await saveActionEditor(); break;
    case "destroy-case": openDestroyDialog(); break;
    case "destroy-run": await runDestroy(); break;
    case "report": $("report-modal").classList.add("show"); break;
    case "report-build": await buildReport(false); break;
    case "report-build-pdf": await buildReport(true); break;
    case "columns": openColumnManager(); break;
    case "preferences": await openPreferences(); break;
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
    case "date-filter": await openDateFilter(); break;
    case "summaries": openSummaries(); break;
    case "sort-priority": openSortPriority(); break;
    case "palette": openPalette(); break;
    case "messages": openMessages(); break;
    case "open-analyses": await openAnalysesDialog(); break;
    case "tracking-open": closeModals(); showTab("actions"); showWorkspaceSub("tracking"); break;
    case "track-bookmarks": await importGridBookmarks(); break;
    case "track-row": await openTaggedRow(); break;
    case "track-ip": await useGridIP(true); break;
    case "hunt-ip": await useGridIP(false); break;
    case "disk-open": openDiskDialog(); break;
    case "disk-explorer": await openDiskExplorer(); break;
    case "profile-apply": await applyDetectedProfile(); break;
    case "case-history": await openCaseHistory(node?.closest("#cases-view") ? state.selectedCase : state.openCase?.id); break;
    case "rule-add": await addRule(); break;
    case "pivot": await runPivot(); break;
    case "copy-row": await copySelectedRows(); break;
    case "cell-json": showCellJson(); break;
    case "rule-from-cell": await ruleFromCell(); break;
    case "cell-copy": await navigator.clipboard.writeText($("cell-full").value).then(() => say("Cell copied")); break;
    case "bookmark-row": await markSelection("bookmarked"); break;
    case "derived": openDerivedDialog(); break;
    case "derived-add": await addDerived(); break;
    case "hide-empty-columns": await hideEmptyColumns(); break;
    case "columns-reset": state.hidden.clear(); renderGrid(); openColumnManager(); saveLayoutSoon(); break;
    case "group-apply": applyGrouping(); break;
    case "group-remove":
      clearGrouping();
      say("Grouping removed");
      break;
    case "group-none":
      clearGrouping();
      break;
    case "display-settings": $("settings-modal").classList.add("show"); break;
    case "settings-close": closeModals(); break;
    case "ask-ok": answerAsk($("ask-input").value); break;
    case "ask-cancel": answerAsk(null); break;
    case "compat-open": await openCompatibility(); break;
    case "compat-reload": await loadCompatibility(); break;
    case "plugin-install": $("plugin-input").click(); break;
    case "profile-create": await createProfileFromAnalysis(); break;
    case "about":
      $("about-text").textContent =
        `Kagarasu Host ${$("version").textContent.replace("Kagarasu ", "")} — the same core as the Windows edition, ` +
        "served over HTTP. The palette, the density and the grid behaviour are carried over from the desktop window. " +
        "Everything stays on this machine: nothing is uploaded, and the only outbound request is the " +
        "optional check for a newer release.";
      $("about-modal").classList.add("show");
      break;
    case "about-close": closeModals(); break;
    case "toggle-artifacts":
      artifactsVisible = $("artifacts").hidden;
      syncArtifacts();
      break;
    default: break;
  }
}

/* ---------- boot ---------- */

/* A newer release? The service has already asked the registry (and cached the answer);
   this only decides whether to show the band. It never blocks, never retries in a loop,
   and a dismissed version stays dismissed. */
async function checkForUpdate() {
  try {
    const info = await api("/api/version");
    if (!info || !info.available) return;
    if (localStorage.getItem("fb-update-dismissed") === info.latest) return;
    const commands = info.command || [];
    $("update-text").textContent = `Kagarasu ${info.latest} is available — you run ${info.current}.`;
    $("update-command").textContent = commands[0] || "";
    $("update-command").title = info.note || "";
    $("update-copy").onclick = async () => {
      try { await navigator.clipboard.writeText(commands.join("\n")); say("Update command copied"); }
      catch (_) { say(commands.join(" · ")); }
    };
    $("update-link").onclick = () => { if (info.url) window.open(info.url, "_blank", "noreferrer"); };
    $("update-dismiss").onclick = () => {
      localStorage.setItem("fb-update-dismissed", info.latest);
      $("update-bar").hidden = true;
    };
    $("update-bar").hidden = false;
  } catch (_) { /* a comfort, not a dependency: the page works without the answer */ }
}

async function boot() {
  loadCopyPrefs();
  loadTreeMode();
  applyDetailsPosition();
  applyTreePosition();
  loadPalette();
  applyScale();
  applyRowHeight();
  populateRuleOperators();
  wire();
  fillActionTypes();
  try {
    const health = await api("/health");
    $("version").textContent = `Kagarasu ${health.version} · Host`;
  } catch (_) { /* the version is cosmetic */ }
  await loadCases();
  // A first start can be slow (a case container is starting): do not take the analyst
  // back from the tab they already chose while the list was loading.
  const linkedCase = CASE_PREFIX.slice("/case/".length);
  if (!tabChosen && state.cases.some((item) => item.id === linkedCase)) {
    await openCase(linkedCase);
  }
  if (!tabChosen) showTab(state.cases.length === 1 ? "analyses" : "cases");
  tabChosen = false;
  if (!state.openCase) {
    showCaseStart();
    $("tree").innerHTML = '<div class="empty">No case open.</div>';
  }
  checkForUpdate();
}

document.addEventListener("DOMContentLoaded", boot);
