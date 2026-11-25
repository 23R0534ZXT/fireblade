/* Fireblade Host — grid client. Palette and density live in app.css. */
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
  interval: "",        // date interval applied to the grouped column
  expression: null,    // FilterGroup sent to the core
  path: [],            // drill-down values
  multiSort: [],       // [{column, descending}] in application order
  hidden: new Set(),    // column indexes hidden by the analyst
  pinned: new Set(),    // column indexes frozen on the left
  pinnedRight: new Set(), // column indexes frozen on the right
  selection: new Set(), // row ids selected on this page (Shift extends, Ctrl toggles)
  anchor: null,         // the row a Shift-click extends from
  summaries: [],        // [{column, operation, kind}] shown beside each group
  order: "",            // how the groups are ordered: count, value or a summary
  orderDesc: true,
  orderSummary: 0,
  payload: null,        // the last rows answer, kept for its summary labels
  timestamps: [],       // columns the case marks as dates
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

function openDiskDialog() {
  if (!state.openCase) { say("Open a case first", true); return; }
  $("disk-source").value = "";
  $("disk-kind").value = "mounted";
  $("disk-modal").classList.add("show");
}

async function startDiskAnalysis() {
  const source = $("disk-source").value.trim();
  if (!source) { say("Give the volume or image to analyse", true); return; }
  const kind = $("disk-kind").value;
  closeModals();
  say("Preparing the disk walk…");
  try {
    const started = await apiPost(`/api/cases/${state.openCase.id}/disk-jobs`,
      { source, kind });
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
    return item.status !== "complete" && item.status !== "companion" && !item.ignored;
  });
  const aside = retryState.files.filter((item) => item.ignored).length;
  $("report-summary").textContent = `${retryState.files.length} file(s) in the reports`
    + (aside ? `, ${aside} set aside` : "");
  $("retry-list").innerHTML = files.length
    ? files.map((item) => `<div class="retry-line${item.ignored ? " aside" : ""}">
        <span class="retry-path" title="${escapeHtml(item.path)}">${escapeHtml(item.path.split(/[\\/]/).pop())}
          <em>${escapeHtml(item.status)}${item.ignored ? " · set aside" : ""}${item.reason ? " — " + escapeHtml(item.reason) : ""}</em></span>
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

async function runRetry(path, reader) {
  const item = retryState.files.find((entry) => entry.path === path);
  if (!item) return;
  say(`Reading ${item.path.split(/[\\/]/).pop()} with ${reader}…`);
  try {
    const payload = await apiPost(
      `/api/cases/${state.openCase.id}/collections/${encodeURIComponent(item.collection)}/retry`,
      { path: item.path, reader });
    closeModals();
    await openCase(state.openCase.id);
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
const copyPrefs = { headers: true, dateFormat: "source" };

function loadCopyPrefs() {
  try {
    const stored = JSON.parse(localStorage.getItem("fireblade.display") || "{}");
    if (typeof stored.headers === "boolean") copyPrefs.headers = stored.headers;
    if (["source", "iso", "iso7"].includes(stored.dateFormat)) copyPrefs.dateFormat = stored.dateFormat;
  } catch (_) { /* a first visit, or storage disabled */ }
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

/* Every command the window carries: menus, the toolbar and the grid's buttons.
   The palette runs the same element the mouse would click, so the two cannot drift. */
function paletteEntries() {
  const entries = [];
  const seen = new Set();
  const add = (label, node) => {
    const text = String(label || "").replace(/\s+/g, " ").trim();
    if (!text || seen.has(text)) return;
    seen.add(text);
    entries.push({ label: text, node });
  };
  // Everything the window offers without opening a dialog first: menu items, the
  // toolbars, the grid's own bar, the tabs. A button inside a closed dialog is not
  // reachable from here, so it is left out rather than run blind.
  document.querySelectorAll("[data-act]").forEach((node) => {
    if (node.closest(".modal")) return;
    add(node.textContent || node.getAttribute("title"), node);
  });
  document.querySelectorAll(".app button, .app .tab").forEach((node) => {
    if (node.closest(".modal") || node.disabled) return;
    add(node.textContent, node);
  });
  document.querySelectorAll(".tab[data-tab]").forEach((node) => add(`Show ${node.textContent}`, node));
  return entries;
}

function renderPalette() {
  const needle = $("palette-input").value.trim().toLowerCase();
  const entries = paletteEntries();
  const shown = needle
    ? entries.filter((item) => item.label.toLowerCase().includes(needle))
    : entries;
  commandState.shown = shown;
  $("palette-list").innerHTML = shown.length
    ? shown.slice(0, 40).map((item, position) => `<div class="palette-item" data-palette="${position}">
        ${escapeHtml(item.label)}</div>`).join("")
    : '<div class="emptygrid">No command matches.</div>';
  $("palette-list").querySelectorAll("[data-palette]").forEach((node) => {
    node.addEventListener("click", () => runPalette(Number(node.dataset.palette)));
  });
}

async function runPalette(position) {
  const entry = commandState.shown[position];
  if (!entry) return;
  closeModals();
  const node = entry.node;
  if (node.classList && node.classList.contains("item")) node.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  else node.click();
  say(`Command: ${entry.label}`);
}

function openPalette() {
  $("palette-input").value = "";
  renderPalette();
  $("palette-modal").classList.add("show");
  setTimeout(() => $("palette-input").focus(), 30);
}

const commandState = { shown: [] };

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
      state.analysis = Number(node.dataset.analysisOpen);
      state.path = [];
      closeModals();
      await loadRows(true);
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

async function openCaseHistory() {
  if (!state.openCase) { say("Open a case first", true); return; }
  $("history-list").innerHTML = '<div class="emptygrid">Reading the history…</div>';
  $("history-modal").classList.add("show");
  try {
    const payload = await api(`/api/cases/${encodeURIComponent(state.openCase.id)}/history`);
    $("history-list").innerHTML = (payload.entries || []).length
      ? payload.entries.map((item) => `<div class="analysis-line">
          <span class="analysis-name" title="${escapeHtml(payload.folder)}">${escapeHtml(item.when)} — ${escapeHtml(item.name)}</span>
          <span class="pin"><button class="btn" data-history-restore="${escapeHtml(item.name)}">Restore</button></span>
        </div>`).join("")
      : '<div class="emptygrid">No recorded state for this case yet.</div>';
    $("history-list").querySelectorAll("[data-history-restore]").forEach((node) => {
      node.addEventListener("click", () => restoreHistory(node.dataset.historyRestore));
    });
  } catch (error) {
    $("history-list").innerHTML = "";
    say(error.message, true);
  }
}

async function restoreHistory(name) {
  if (!state.openCase) return;
  if (!window.confirm(`Restore the state ${name}? The present state is kept in the same folder first.`)) return;
  try {
    const payload = await apiPost(
      `/api/cases/${state.openCase.id}/history/${encodeURIComponent(name)}/restore`, {});
    closeModals();
    await openCase(state.openCase.id);
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

function say(message, error) {
  const node = $("status");
  node.textContent = message;
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

async function runTask(kind, params, title) {
  if (!state.openCase) { say("Open a case first", true); return null; }
  const token = ++taskState.seq;
  progressOpen(title);
  let started;
  try {
    started = await apiPost(`/api/cases/${state.openCase.id}/tasks`, { kind, params: params || {} });
  } catch (error) {
    $("import-progress-modal").classList.remove("show");
    say(error.message, true);
    throw error;
  }
  taskState.job = started.job;
  for (;;) {
    await new Promise((resolve) => setTimeout(resolve, 500));
    if (token !== taskState.seq) return null;      // another command took the window
    let payload;
    try { payload = await api(`/api/tasks/${taskState.job}`); }
    catch (error) {
      // A job the service no longer knows cannot finish: stop asking.
      $("import-progress-message").textContent = error.message;
      $("import-progress-modal").classList.remove("show");
      taskState.job = null;
      say(error.message, true);
      return null;
    }
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
async function offerSheets(payload) {
  const row = $("preview-sheet-row");
  if (!payload || !EXCEL_SUFFIX.test(String(payload.name || ""))) {
    row.style.display = "none";
    $("preview-sheet").innerHTML = "";
    return;
  }
  try {
    const sheets = await apiPost(`/api/cases/${state.openCase.id}/sheets`, { path: payload.path });
    $("preview-sheet").innerHTML = (sheets.sheets || []).map((name) =>
      `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
    row.style.display = "";
    if (sheets.sheets && sheets.sheets.length > 1) {
      $("preview-note").textContent = `${sheets.sheets.length} sheet(s) in this workbook: the first is chosen.`;
    }
  } catch (error) {
    row.style.display = "none";
    say(error.message, true);
  }
}

function chosenSheet(payload) {
  if (!payload || !EXCEL_SUFFIX.test(String(payload.name || ""))) return "";
  return $("preview-sheet").value || "";
}

function openImportDialog() {
  if (!state.openCase) { say("Open a case before importing", true); return; }
  previewState.items = [];
  $("import-title").textContent = "Import a file";
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

/* A collection is a tree. The browser hands a directory over one file at a time, each
   with its relative path; the case rebuilds that tree under evidence/, then the folder is
   previewed and imported exactly as a folder on the server. */
function openFolderPicker() {
  if (!state.openCase) { say("Open a case before importing", true); return; }
  $("folder-input").click();
}

async function importFolder(files) {
  if (!state.openCase) { say("Open a case before importing", true); return; }
  const identifier = state.openCase.id;
  $("import-modal").classList.add("show");
  $("import-title").textContent = "Import a folder";
  previewState.items = [];
  renderPreview();
  const note = $("preview-note");
  note.classList.remove("err");
  let root = "";
  let index = 0;
  for (const file of files) {
    index += 1;
    note.textContent = `Sending ${index}/${files.length} — ${file.webkitRelativePath || file.name}`;
    const body = new FormData();
    body.append("file", file);
    body.append("relative", file.webkitRelativePath || file.name);
    try {
      const response = await fetch(url(`/api/cases/${identifier}/upload-folder`), { method: "POST", body });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || response.statusText);
      root = payload.root || root;
    } catch (error) {
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
    previewState.items = [{ name: payload.name || root, payload }];
    note.textContent = `${files.length} file(s) ready. Nothing has been read into the case yet.`;
  } catch (error) {
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
      const response = await fetch(url(`/api/cases/${state.openCase.id}/preview-upload`), { method: "POST", body });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || payload.error || response.statusText);
      previewState.items.push({ name: file.name, payload });
    } catch (error) {
      previewState.items.push({ name: file.name, error: error.message });
    }
  }
  $("preview-note").textContent = `${previewState.items.length} file(s) ready. Nothing has been read into the case yet.`;
  $("preview-note").classList.remove("err");
  await offerSheets(previewState.items[previewState.items.length - 1].payload);
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
    await offerSheets(payload);
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

const importJobState = { job: null, stopped: false };

/* An import runs on the server, in the background: the window stays usable, the
   progress is visible, and the run can be stopped without losing what was read. */
async function startImportJob(source, layout, options, sheet) {
  const body = new FormData();
  body.append("organization", layout);
  if (Array.isArray(source)) source.forEach((item) => body.append("sources", item));
  else body.append("source", source);
  if (options.delimiter) body.append("delimiter", options.delimiter);
  if (options.encoding) body.append("encoding", options.encoding);
  if (sheet) body.append("sheet", sheet);
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

async function confirmImport() {
  if (!previewState.items.length) return;
  const layout = $("import-layout").value;
  const options = csvOptions();
  let imported = 0;
  const ready = previewState.items.filter((item) => !item.error && item.payload && item.payload.path);
  // Files chosen together are one collection: the layout (per file, per artifact family, or one
  // grid for everything) is how that collection is laid out, so it is imported in one go. A
  // workbook is read sheet by sheet and keeps its own import.
  const together = layout !== "files" && ready.length > 1 &&
    ready.every((item) => !/\.(xlsx|xlsm|xls)$/i.test(item.payload.path));
  if (together) {
    say(`Importing ${ready.length} files…`);
    try {
      const job = await startImportJob(ready.map((item) => item.payload.path), layout, options, "");
      const outcome = await followImportJob(job);
      if (outcome.status === "complete" && outcome.result && outcome.result.analyses) imported = ready.length;
      else say(`${(outcome.result && outcome.result.message) || outcome.error || outcome.status}`, true);
    } catch (error) {
      say(error.message, true);
      return;
    }
    closeModals();
    await openCase(state.openCase.id);
    say(`${imported} file(s) imported`);
    return;
  }
  for (const item of previewState.items) {
    if (item.error) continue;
    const source = item.payload && item.payload.path;
    if (!source) continue;
    say(`Importing ${item.name}…`);
    try {
      const job = await startImportJob(source, layout, options, chosenSheet(item.payload));
      const outcome = await followImportJob(job);
      if (outcome.status === "complete" && outcome.result && outcome.result.analyses) imported += 1;
      else if (outcome.status === "cancelled") {
        say(`${item.name}: import stopped — what was written stays in the case`, true);
        break;
      } else {
        say(`${item.name}: ${(outcome.result && outcome.result.message) || outcome.error || outcome.status}`, true);
      }
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
  await saveDisplayNow();
  try {
    const saved = await apiPost(`/api/cases/${state.openCase.id}/save`, {});
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
      say(`Case created: ${created.name}`);
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

async function openDestroyDialog() {
  const chosen = targetCaseId();
  if (chosen && (!state.openCase || state.openCase.id !== chosen)) await openCase(chosen);
  if (!state.openCase) { say("Open the case you want to erase", true); return; }
  const caseId = state.openCase.id;
  const name = state.openCase.name;
  $("destroy-confirm").value = "";
  $("destroy-target").textContent = `Case: ${name} — type that name to confirm.`;
  $("destroy-modal").classList.add("show");
  /* Where the certificate goes: the analyst decides, because a document nobody can find
     was not written. The service gives its own default; the driver's folder cannot move. */
  try {
    const settings = await api("/api/settings");
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
    if (!state.openCase || state.openCase.id !== caseId) return;
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
async function uploadDestroyPhotos(files) {
  const sources = [];
  for (const file of files) {
    const data = new FormData();
    data.append("file", file);
    const response = await fetch(url(`/api/cases/${state.openCase.id}/preview-upload`),
                                 { method: "POST", body: data });
    if (!response.ok) throw new Error(await response.text());
    const saved = await response.json();
    sources.push(saved.path || saved.source);
  }
  const response = await fetch(url(`/api/cases/${state.openCase.id}/destruction/attachments`), {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sources }),
  });
  if (!response.ok) throw new Error(await response.text());
  const kept = await response.json();
  state.destroyAttachments = kept.attachments || [];
  $("destroy-photo-count").textContent = `${kept.count} photo(s)`;
  say(`${kept.count} photo(s) for the certificate`);
}

async function runDestroy() {
  const confirmation = $("destroy-confirm").value.trim();
  const body = {
    method: $("destroy-method").value,
    operator: $("destroy-operator").value,
    witness: $("destroy-witness").value,
    reason: $("destroy-reason").value,
    confirmation,
    attachments: state.destroyAttachments || [],
    certificate_folder: $("destroy-certificate").value.trim(),
  };
  if (confirmation !== state.openCase.name) { say("The typed name does not match", true); return; }
  closeModals();
  say("Erasing the case — this takes a moment…");
  try {
    const response = await fetch(url(`/api/cases/${state.openCase.id}/destroy`),
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || response.statusText);
    state.openCase = null;
    await loadCases();
    showTab("cases");
    const outside = payload.outside ? `, ${payload.outside} outside the folder` : "";
    say(`Case erased: ${payload.files} file(s)${outside}, certificate ${payload.certificate}`);
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

async function apiPost(path, body) {
  const response = await fetch(url(path), { method: "POST", headers: { "Content-Type": "application/json" },
                                       body: JSON.stringify(body) });
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

/* The case the Cases tab's buttons act on: the one selected in the table, else the one open. */
function targetCaseId() {
  if (state.selectedCase && state.cases.some((item) => item.id === state.selectedCase)) return state.selectedCase;
  return state.openCase ? state.openCase.id : null;
}

function targetCase() {
  const id = targetCaseId();
  return id ? state.cases.find((item) => item.id === id) || null : null;
}

function renderCases() {
  const term = ($("case-search").value || "").toLowerCase();
  const archived = $("case-archived").checked;
  const matches = state.cases.filter((item) => {
    if (!archived && item.status === "archived") return false;
    return !term || [item.name, item.description, item.environment, item.id, item.status]
      .join(" ").toLowerCase().includes(term);
  });
  const body = $("cases-body");
  const when = (value) => (value ? String(value).replace("T", " ").slice(0, 19) : "—");
  body.innerHTML = matches.map((item) => `
    <tr data-case="${escapeHtml(item.id)}" class="${
      [state.openCase && state.openCase.id === item.id ? "sel" : "",
       state.selectedCase === item.id ? "selected" : ""].filter(Boolean).join(" ")}">
      <td title="${escapeHtml(item.description || "")}">${escapeHtml(item.name || "(unnamed)")}</td>
      <td>${escapeHtml(String(item.collection_count ?? (item.collections || []).length ?? 0))}</td>
      <td>${escapeHtml(CASE_STATUS[item.status] || item.status || "—")}${item.storage_archive ? " · kept in an archive" : ""}</td>
      <td>${escapeHtml(String(item.analysis_count ?? 0))}</td>
      <td>${escapeHtml(when(item.created))}</td>
      <td>${escapeHtml(when(item.updated))}</td>
      <td>${escapeHtml(when(item.opened || item.updated))}</td>
    </tr>`).join("");
  $("case-count").textContent = `${matches.length} case(s) displayed`;
  renderCaseSelection();
  $("cases-empty").hidden = matches.length > 0;
  $("cases-empty").textContent = state.cases.length
    ? "No case matches this filter."
    : "The library is empty. A case written by the Windows edition opens here as soon as its folder is in the library.";
}

/* What depends on the selected case, without rebuilding the table: a click must not replace the
   rows, or the second click of a double click lands on a row that is no longer there. */
function renderCaseSelection() {
  const target = targetCase();
  $("cases-body").querySelectorAll("tr[data-case]").forEach((row) => {
    row.classList.toggle("selected", row.dataset.case === state.selectedCase);
    row.classList.toggle("sel", Boolean(state.openCase) && row.dataset.case === state.openCase.id);
  });
  $("case-footer-description").textContent = target
    ? (target.description || "No description for this case.")
    : "Select a case to read its description.";
  $("archive-case").textContent = target && target.status === "archived" ? "Reactivate" : "Archive";
  $("restore-case").hidden = !(target && target.storage_archive);
}

async function openCase(identifier) {
  try {
    const kept = state.cases.find((item) => item.id === identifier);
    if (kept && kept.storage_archive) {
      state.selectedCase = identifier;
      renderCaseSelection();
      say("This case is kept in an archive: press Restore… to bring it back", true);
      return;
    }
    const detail = await api(`/api/cases/${identifier}`);
    state.openCase = detail;
    // The analyses closed and kept: the tree lists them, and they open again.
    try {
      const closed = await api(`/api/cases/${identifier}/closed`);
      state.openCase.closed = closed.closed || [];
    } catch (_) {
      state.openCase.closed = [];
    }
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
    say("This file is not a Fireblade layout", true);
    return;
  }
  state.widths = document_.widths || {};
  state.hidden = new Set(document_.hidden || []);
  state.pinned = new Set(document_.pinned || []);
  state.pinnedRight = new Set(document_.pinned_right || []);
  if (Number.isInteger(document_.sort)) state.sort = document_.sort;
  state.descending = Boolean(document_.descending);
  state.multiSort = Array.isArray(document_.multiSort) ? document_.multiSort : [];
  if (Array.isArray(document_.groups)) state.groups = document_.groups;
  state.path = [];
  await saveDisplayNow();
  await loadRows(true);
  say(`Layout imported: ${Object.keys(state.widths).length} column width(s), `
    + `${state.hidden.size} hidden, ${state.pinned.size + state.pinnedRight.size} pinned`);
}

async function saveDisplayNow() {
  try {
    await apiPost(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/display`,
      { widths: state.widths, hidden: [...state.hidden], pinned: [...state.pinned],
        pinned_right: [...state.pinnedRight] });
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
  row.innerHTML = `<select data-expr-col>${state.columns.slice(1).map((name, index) =>
      `<option value="${index}" ${index === (condition.column ?? 0) ? "selected" : ""}>${escapeHtml(name)}</option>`).join("")}</select>
    <select data-expr-op>${EXPR_OPERATORS.map(([code, label]) =>
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

/* ---------- EVTX detection ---------- */

/* The event logs of the case, what the engine read of each, and the run that turns
   them into alerts. The desktop asks for a minimum severity and one button; so here. */
function renderEvtx() {
  const analyses = (state.openCase && state.openCase.analyses) || [];
  const logs = analyses.filter((item) => /\.evtx$/i.test(String(item.source || ""))
    || /\.evtx/i.test(String(item.label || "")));
  const box = $("evtx-rows");
  if (!logs.length) {
    box.innerHTML = '<tr><td colspan="5" class="cellnull">Import a collection to enable detection.</td></tr>';
    $("evtx-summary").textContent = "Import a collection to enable detection.";
    return;
  }
  box.innerHTML = logs.map((item) =>
    `<tr><td title="${escapeHtml(item.source || "")}">${escapeHtml(item.label || "")}</td>
      <td>${escapeHtml(String((item.source_info && item.source_info.rows) ?? item.rows ?? ""))}</td>
      <td>${escapeHtml(String((item.source_info && (item.source_info.dated
        ?? item.source_info.timestamps)) ?? ""))}</td>
      <td>${escapeHtml(((item.source_info && item.source_info.readers) || []).join(", ")
        || "the engine")}</td>
      <td class="cellnull"></td></tr>`).join("");
  const alerts = analyses.filter((item) => /alertes hayabusa/i.test(String(item.label || ""))).length;
  $("evtx-summary").textContent = `${logs.length} event log(s) read`
    + (alerts ? ` — ${alerts} alert analysis(es) in the case` : "");
}

async function runEvtxDetection() {
  if (!state.openCase) { say("Open a case first", true); return; }
  const level = $("evtx-level").value;
  $("evtx-summary").textContent = `Analyzing the event logs at level ${level}…`;
  say(`Hayabusa: running at level ${level}…`);
  try {
    const payload = await runTask("detect", { min_level: level }, "Hayabusa");
    if (!payload) return;
    state.openCase = await api(`/api/cases/${state.openCase.id}`);
    renderTree();
    renderEvtx();
    say(`Hayabusa: ${payload.total} finding(s) at level ${level}+`);
  } catch (error) {
    $("evtx-summary").textContent = error.message;
    say(error.message, true);
  }
}

/* ---------- the window's own commands, the ones a menu carries ---------- */

/* A row height is a reading comfort, not case data: it lives in the browser. */
function toggleDetails() {
  const box = $("details");
  box.style.display = box.style.display === "none" ? "block" : "none";
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

function clearEveryFilter() {
  state.filters = [];
  state.search = "";
  state.offset = 0;
  $("search").value = "";
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

function exportIocMatches() {
  if (!iocState.hits.length) { say("Nothing to export: hunt first", true); return; }
  const lines = [["indicator", "analysis", "row", "column", "observed", "rule"]];
  for (const hit of iocState.hits) {
    lines.push([hit.indicator, hit.analysis_label || "", hit.row_id, hit.column,
                hit.observed, hit.rule]);
  }
  downloadCsv("ioc-matches.csv", lines);
  say(`${iocState.hits.length} match(es) exported`);
}

function exportIocSummary() {
  const counts = new Map();
  for (const hit of iocState.hits) counts.set(hit.indicator, (counts.get(hit.indicator) || 0) + 1);
  const lines = [["type", "indicator", "label", "rows"]];
  for (const line of iocLines()) {
    lines.push([line.kind || iocKind(line.value), line.value, line.label || "",
                counts.get(line.value) || 0]);
  }
  downloadCsv("ioc-summary.csv", lines);
  say(`${lines.length - 1} indicator(s) summarised`);
}

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
      if (!["complete", "attention", "duplicate"].includes(file.status)) paths.push(file.path);
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
  const lines = [["row_id", "note", "values"]];
  const rows = new Map(state.rows.map((row) => [String(row[0]), row]));
  for (const [rowId, note] of state.bookmarks.entries()) {
    const row = rows.get(String(rowId));
    const values = row ? row.slice(1).join(" | ") : "";
    lines.push([rowId, String(note || ""), values]);
  }
  const csv = lines.map((line) => line.map((cell) =>
    '"' + String(cell).replace(/"/g, '""') + '"').join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `bookmarks-${(state.openCase.name || "case").replace(/[^\w.-]+/g, "-")}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
  say(`${state.bookmarks.size} bookmark(s) exported`);
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
    const saved = await api(`/api/cases/${state.openCase.id}/session`);
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
  const buffer = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (const byte of buffer) binary += String.fromCharCode(byte);
  try {
    const result = await api(`/api/cases/${state.openCase.id}/session/open`,
      { method: "POST", body: JSON.stringify({ content: btoa(binary) }) });
    const missing = (result.missing || []).length
      ? ` — ${result.missing.length} not in this case` : "";
    say(`Session opened: ${result.added} analysis(es)${missing}`);
    await loadAnalyses();
  } catch (error) { say(`The session was not opened: ${error.message}`, true); }
}

async function exportPortable() {
  if (!state.openCase) { say("Open a case first", true); return; }
  try {
    const payload = await runTask("package", { include_sources: true }, "Portable case");
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
  try {
    for (const id of limited) {
      const before = plain(state.bookmarks.get(String(id)));
      const note = mode === "append" && before ? `${before}\n${text.trim()}` : text.trim();
      await postBookmark(id, note);
    }
    renderGrid();
    say(`${limited.length} row(s) noted`);
  } catch (error) {
    say(error.message, true);
  }
}

async function bookmarkNote() {
  const ids = selectedIds();
  if (!ids.length) { say("Select a row first", true); return; }
  const text = await ask({ title: "Bookmark / note",
                           label: "Note for this bookmark",
                           note: "Empty keeps a plain mark." });
  if (text === null) return;
  await markSelection(text.trim());
}

/* Next and previous analysis, the way the desktop walks its tabs. */
function stepAnalysis(direction) {
  const analyses = (state.openCase && state.openCase.analyses) || [];
  if (analyses.length < 2) { say("This case holds a single analysis", true); return; }
  const here = analyses.findIndex((item) => item.index === state.analysis);
  const next = analyses[(here + direction + analyses.length) % analyses.length];
  state.analysis = next.index;
  state.filters = [];
  state.offset = 0;
  state.selected = null;
  state.path = [];
  renderTree();
  loadRows(true);
  say(`Analysis: ${next.label}`);
}

/* The grouped grid drills down one level at a time: collapsing is the root, and
   expanding walks into the first group of the level on screen. */
function collapseEveryGroup() {
  if (!state.grouped) { say("This analysis is not grouped", true); return; }
  state.path = [];
  state.offset = 0;
  loadRows(true);
  say("Every group collapsed: back to the first level");
}

async function expandEveryGroup() {
  if (!state.grouped) { say("This analysis is not grouped", true); return; }
  const first = state.rows[0];
  if (!first) { say("No group on this page", true); return; }
  state.path = [...state.path, String(first[0] ?? "")];
  state.offset = 0;
  await loadRows(true);
  say("Opened the first group of this level");
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
    const lines = [
      ["Analysis", entry ? entry.label : ""],
      ["Source", source || "(nothing recorded)"],
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
    guide: ["Fireblade Host — user guide", [
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
    tutorial: ["Fireblade Host — full tutorial", [
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
      "Fireblade Host — internal edition. Python, FastAPI, DuckDB, openpyxl and PySide6",
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
const findingState = { groups: [], incidents: [], source: "", loaded: false };

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
  try {
    const payload = await api(`/api/cases/${encodeURIComponent(state.openCase.id)}/findings`);
    findingState.groups = payload.groups || [];
    findingState.incidents = payload.incidents || [];
    findingState.source = payload.source || "";
    findingState.loaded = true;
    if (payload.error) say(payload.error, true);
    renderFindingView();
  } catch (error) {
    findingState.groups = [];
    say(error.message, true);
    renderFindingView();
  }
}

function renderFindingView() {
  const view = $("finding-view").value;
  $("finding-table").style.display = view === "table" ? "" : "none";
  $("finding-map-box").style.display = view === "table" ? "none" : "";
  const hits = findingState.groups.reduce((sum, group) => sum + (group.count || 0), 0);
  $("finding-summary").textContent = findingState.groups.length
    ? `${findingState.groups.length} finding(s), ${hits} alert(s)`
      + (findingState.source ? ` — ${findingState.source}` : "")
    : "No finding yet: run the detection, or open the alert analysis.";
  if (view === "table") { renderFindingSeverity(shownFindings()); renderFindingTable(); return; }
  drawFindingMap(view);
}

/* The findings on screen: the filter reads the rule, the host and the event ids,
   the way the desktop's own field does. */
function shownFindings() {
  const term = ($("finding-search").value || "").trim().toLowerCase();
  if (!term) return findingState.groups;
  return findingState.groups.filter((group) =>
    [group.title, group.host, (group.event_ids || []).join(" "), group.tactics,
     group.techniques, group.level].join(" ").toLowerCase().includes(term));
}

function renderFindingTable() {
  const groups = shownFindings();
  $("hayabusa-rows").innerHTML = groups.length
    ? groups.map((group) => `<tr>
        <td>${escapeHtml(group.start || "(undated)")}</td>
        <td>${escapeHtml(group.level || "")}</td>
        <td title="${escapeHtml(group.details || "")}">${escapeHtml(group.title || "")}</td>
        <td>${escapeHtml(group.host || "")}</td>
        <td>${group.count || 0}</td>
        <td>${escapeHtml((group.event_ids || []).join(", "))}</td>
        <td title="${escapeHtml(group.tactics || "")}">${escapeHtml(group.techniques || "")}</td>
      </tr>`).join("")
    : '<tr><td colspan="7" class="cellnull">No finding matches this filter.</td></tr>';
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

function sortRow(key = { column: 0, descending: false }) {
  const row = document.createElement("tr");
  row.innerHTML = `<td><select data-sort-column>${state.columns.slice(1).map((name, index) =>
      `<option value="${index}" ${index === key.column ? "selected" : ""}>${escapeHtml(name)}</option>`).join("")}</select></td>
    <td><select data-sort-direction>
      <option value="asc" ${key.descending ? "" : "selected"}>A → Z</option>
      <option value="desc" ${key.descending ? "selected" : ""}>Z → A</option></select></td>
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
    : (state.sort !== null ? [{ column: state.sort, descending: state.descending }] : []);
  for (const key of keys) $("sort-rows").appendChild(sortRow(key));
  $("sort-modal").classList.add("show");
}

async function applySortPriority() {
  const keys = [];
  $("sort-rows").querySelectorAll("tr").forEach((row) => {
    keys.push({ column: Number(row.querySelector("[data-sort-column]").value),
                descending: row.querySelector("[data-sort-direction]").value === "desc" });
  });
  state.multiSort = keys;
  if (keys.length) { state.sort = keys[0].column; state.descending = keys[0].descending; }
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

function summaryRow(summary = { column: 0, operation: "count", kind: "number" }) {
  const row = document.createElement("tr");
  row.innerHTML = `<td><select data-summary-column>${state.columns.slice(1).map((name, index) =>
      `<option value="${index}" ${index === summary.column ? "selected" : ""}>${escapeHtml(name)}</option>`).join("")}</select></td>
    <td><select data-summary-operation>${SUMMARY_OPERATIONS.map(([code, label]) =>
      `<option value="${code}" ${code === summary.operation ? "selected" : ""}>${escapeHtml(label)}</option>`).join("")}</select></td>
    <td><select data-summary-kind>${SUMMARY_KINDS.map(([code, label]) =>
      `<option value="${code}" ${code === summary.kind ? "selected" : ""}>${escapeHtml(label)}</option>`).join("")}</select></td>
    <td><button class="btn" data-summary-remove title="Remove this summary">✕</button></td>`;
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
    });
  });
  state.summaries = summaries;
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

async function loadDateRanges() {
  if (dateState.ranges.length) return;
  try {
    const payload = await api("/api/date-ranges");
    dateState.ranges = payload.ranges || [];
    $("date-range").innerHTML = dateState.ranges
      .map((item) => `<option value="${escapeHtml(item.name)}">${escapeHtml(item.name)}</option>`).join("");
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
    const row = state.rows.find((item) => String(item[0]) === id);
    if (!row) continue;
    lines.push(shown.map((item) => cell(row[item.index])).join("\t"));
  }
  try {
    await navigator.clipboard.writeText(lines.join("\n"));
    say(`${ids.length} row(s) copied as a table`);
  } catch (_) {
    say("The browser refused clipboard access", true);
  }
}

async function postBookmark(rowId, note) {
  const body = JSON.stringify({ row_id: Number(rowId), note: note ?? "" });
  const response = await fetch(url(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/bookmark`),
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
  $("graph-summary").textContent = "Building…";
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/graph`);
    if (payload.empty) {
      // Nothing to draw yet: say what to do, as a hint rather than an error.
      renderGraph({ nodes: [], edges: [] });
      $("graph-summary").textContent = payload.message;
      return;
    }
    renderGraph(payload);
  } catch (error) {
    $("graph-summary").textContent = error.message;
    say(error.message, true);
  }
}

/* The graph is drawn by the server; the window only scales it. A zoom keeps the
   centre of the drawing where it is, and Recentre puts it back to 1. */
let graphScale = 1;

function graphZoom(factor) {
  const nodes = $("graph-nodes");
  if (!nodes || !nodes.children.length) { say("Build the graph first", true); return; }
  graphScale = Math.max(0.4, Math.min(3, graphScale * factor));
  nodes.style.transform = `scale(${graphScale})`;
  nodes.style.transformOrigin = "top left";
  $("graph-summary").textContent = `Zoom ${Math.round(graphScale * 100)} %`;
}

function graphReset() {
  graphScale = 1;
  const nodes = $("graph-nodes");
  if (nodes) nodes.style.transform = "";
  const wrap = $("graph-wrap");
  if (wrap) wrap.scrollTo({ left: 0, top: 0 });
  say("Graph recentred");
}

async function exportGraphPng() {
  if (!state.openCase) { say("Open a case first", true); return; }
  try {
    const payload = graphVisible(await api(`/api/cases/${state.openCase.id}/graph`));
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

/* "Which levels of the chain to show": hosts, techniques or indicators; free nodes always stay. */
function graphVisible(payload) {
  const level = $("graph-level").value;
  if (!level) return payload;
  const nodes = payload.nodes.filter((node) => node.kind === level || !["host", "technique", "ioc"].includes(node.kind));
  const kept = new Set(nodes.map((node) => node.id));
  return { ...payload, nodes, edges: payload.edges.filter((edge) => kept.has(edge.source) && kept.has(edge.target)) };
}

function renderGraph(whole) {
  graphPayload = whole;
  const payload = graphVisible(whole);
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
    const payload = await runTask("detect", { min_level: level }, "Hayabusa");
    if (!payload) return;
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
    await loadFindings(true);
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
  state.summaries = []; state.order = "";
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

/* ---------- coverage and diagnostics ---------- */

const coverageState = { report: null };

async function openCoverage() {
  if (!state.openCase) { say("Open a case first", true); return; }
  $("coverage-modal").classList.add("show");
  $("coverage-rows").innerHTML = "";
  $("coverage-note").textContent = "Reading the last check kept with this case…";
  try {
    const payload = await api(`/api/cases/${encodeURIComponent(state.openCase.id)}/coverage?run=false`);
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
        <td title="${escapeHtml(item.path || "")}">${escapeHtml(String(item.path || "").split(/[\\/]/).pop())}</td>
        <td title="${escapeHtml(item.reason || "")}">${escapeHtml(item.reason || "")}</td>
        <td title="${escapeHtml(item.impact || "")}">${escapeHtml(item.impact || "")}</td>
        <td title="${escapeHtml(item.action || "")}">${escapeHtml(item.action || "")}</td></tr>`).join("")
    : '<tr><td colspan="6" class="cellnull">Nothing matches this filter.</td></tr>';
  if (shown.length > 800) {
    $("coverage-note").textContent += ` ${shown.length - 800} more finding(s): narrow the filter or export the report.`;
  }
}

async function runCoverage() {
  if (!state.openCase) { say("Open a case first", true); return; }
  const query = new URLSearchParams({
    expected: $("coverage-profile").value,
    verify_hashes: $("coverage-hashes").checked ? "true" : "false",
    deep_checks: $("coverage-deep").checked ? "true" : "false",
    run: "true" });
  say("Checking every analysis: this reads them again, it can take a while…");
  $("coverage-note").textContent = "Checking…";
  try {
    const payload = await api(`/api/cases/${encodeURIComponent(state.openCase.id)}/coverage?${query}`);
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
let globalRules = null;      // what the shared book says, once, for every analysis
let rulesScope = "analysis";

/* The book's rules reach the grid already mapped onto this analysis' columns;
   a rule the grid cannot evaluate (two conditions, an expression) is skipped
   rather than approximated. */
function globalRuleList() {
  if (!globalRules || !globalRules.enabled) return [];
  return (globalRules.effective || []).filter((rule) => rule.simple !== false);
}

/* One comparison, against the row's values (index 0 is the row id). */
function matchesCondition(condition, values) {
  if (!condition || !Number.isInteger(condition.column) || condition.column < 0) return false;
  const raw = values[condition.column + 1];
  const text = raw === null || raw === undefined ? "" : String(raw);
  const value = condition.value ?? "";
  switch (condition.operator) {
    case "eq": return text.toLowerCase() === String(value).toLowerCase();
    case "ne": return text.toLowerCase() !== String(value).toLowerCase();
    case "starts": return text.toLowerCase().startsWith(String(value).toLowerCase());
    case "ends": return text.toLowerCase().endsWith(String(value).toLowerCase());
    case "gt": case "ge": case "lt": case "le": {
      const a = Number(text), b = Number(value);
      if (Number.isNaN(a) || Number.isNaN(b)) return false;
      if (condition.operator === "gt") return a > b;
      if (condition.operator === "ge") return a >= b;
      if (condition.operator === "lt") return a < b;
      return a <= b;
    }
    case "empty": return text === "";
    case "not_empty": return text !== "";
    default: return text.toLowerCase().includes(String(value).toLowerCase());
  }
}

/* A rule's condition is a tree: a comparison, or a group of them combined with AND,
   OR or NOT — the desktop's subgroups. */
function matchesConditionTree(node, values, depth = 0) {
  if (!node || depth > 24) return false;
  if (!Array.isArray(node.children)) return matchesCondition(node, values);
  const children = node.children;
  const logic = node.logic || "and";
  if (!children.length) return logic === "not";
  if (logic === "or") return children.some((child) => matchesConditionTree(child, values, depth + 1));
  if (logic === "not") {
    return !children.some((child) => matchesConditionTree(child, values, depth + 1));
  }
  return children.every((child) => matchesConditionTree(child, values, depth + 1));
}

function matchesRule(rule, values) {
  if (!rule.enabled) return false;
  if (rule.condition) return matchesConditionTree(rule.condition, values);
  if (rule.simple === false) return false;
  if (!Number.isInteger(rule.column) || rule.column < 0) return false;
  // A statistic names the rows it selects; the server resolved it once.
  if (rule.statistic) {
    const column = Number.isInteger(rule.value_column) ? rule.value_column : rule.column;
    const raw = values[column + 1];
    const text = raw === null || raw === undefined ? "" : String(raw);
    const resolved = rule.resolved;
    if (!resolved) return false;
    if (Array.isArray(resolved.values)) {
      const needle = rule.stat_ignore_case ? text.toLowerCase() : text;
      return resolved.values.some((value) =>
        (rule.stat_ignore_case ? String(value).toLowerCase() : String(value)) === needle);
    }
    const number = Number(text);
    if (Number.isNaN(number) || resolved.threshold === undefined) return false;
    if (resolved.compare === "ge") {
      return resolved.strict ? number > resolved.threshold : number >= resolved.threshold;
    }
    return resolved.strict ? number < resolved.threshold : number <= resolved.threshold;
  }
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
    renderGrid();
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
}

async function persistRules() {
  const response = await fetch(url(`/api/cases/${state.openCase.id}/analyses/${state.analysis}/rules`),
    { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rules: rulesCache }) });
  if (!response.ok) throw new Error((await response.json()).detail || response.statusText);
  // Read the rules back: a statistic is resolved on the server, and the grid can
  // only apply what the server says it selects.
  await loadRules();
}

const RULE_OPERATORS = { contains: "contains", ne: "does not contain", eq: "equals",
                         starts: "starts with", ends: "ends with", gt: ">", ge: ">=",
                         lt: "<", le: "<=", empty: "is empty", not_empty: "is not empty" };

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
  row.innerHTML = `<select data-cond-column>${state.columns.slice(1).map((name, index) =>
      `<option value="${index}">${escapeHtml(name)}</option>`).join("")}</select>
    <select data-cond-operator>${Object.entries(RULE_OPERATORS).map(([value, label]) =>
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

const importState = { collections: [], selected: null, collection: "" };

async function loadImports() {
  if (!state.openCase) return;
  try {
    const [collections, files] = await Promise.all([
      api(`/api/cases/${state.openCase.id}/imports`),
      api(`/api/cases/${state.openCase.id}/collection-files`),
    ]);
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
    say(error.message, true);
  }
}

/* The imports table is the desktop's: one row per collected file, its status, the
   readers that ran, the reason when it did not, and where its output went. */
function renderImports() {
  const wanted = $("imports-status").value;
  const term = ($("imports-search").value || "").trim().toLowerCase();
  // What a file produced, when it produced an analysis: the desktop's "Outputs".
  const outputs = new Map();
  for (const analysis of (state.openCase && state.openCase.analyses) || []) {
    if (analysis.source) outputs.set(analysis.source, analysis.label);
  }
  const rows = [];
  let imported = 0, failed = 0;
  for (const collection of importState.collections) {
    for (const file of collection.files || []) {
      const ok = ["complete", "attention", "duplicate"].includes(file.status);
      if (ok) imported += 1; else failed += 1;
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

const actionState = { items: [], shown: [], selected: null };

const workspaceState = { entities: [], indicators: [], selected: null };

async function loadActions() {
  if (!state.openCase) return;
  try {
    const payload = await api(`/api/cases/${state.openCase.id}/workspace`);
    actionState.items = (payload.actions || []).map((item) => ({ ...item, _caseId: state.openCase.id,
                                                                  _caseName: state.openCase.name }));
    // "Every case of the library": the actions of each case, each marked with its own case.
    if ($("action-scope").value === "all") {
      const others = state.cases.filter((item) => item.id !== state.openCase.id && !item.storage_archive);
      const lists = await Promise.all(others.map(async (item) => {
        try {
          const other = await api(`/api/cases/${item.id}/workspace`);
          return (other.actions || []).map((action) => ({ ...action, _caseId: item.id, _caseName: item.name }));
        } catch (_) {
          return [];
        }
      }));
      actionState.items = actionState.items.concat(...lists);
    }
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
    ? workspaceState.entities.map((item) => `<tr data-entity="${escapeHtml(item.id)}">
        <td>${escapeHtml(item.kind || "")}</td>
        <td>${escapeHtml(item.label || "")}</td>
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
  const fields = {
    kind: $("entity-kind").value, label,
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
  const everywhere = $("action-scope").value === "all";
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
  const scope = $("action-scope").value === "all" ? "every case" : "the open case";
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

const iocState = { hits: [], summary: "" };

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
    index: state.analysis,
    live: liveView(),
  };
}

function iocSummary(payload) {
  const kinds = Object.entries(payload.by_kind || {}).map(([k, v]) => `${v} ${k}`).join(", ");
  const scope = payload.all_analyses ? "every analysis" : "this analysis";
  return `${payload.indicators} indicator(s) over ${scope}, ${payload.scanned} row(s) scanned — `
    + `${payload.hits.length} hit(s)${kinds ? " : " + kinds : ""}`
    + (payload.respect_filters ? " (filters respected)" : "")
    + (payload.rejected ? ` · ${payload.rejected} line(s) rejected` : "")
    + (payload.duplicates ? ` · ${payload.duplicates} duplicate(s)` : "")
    + (payload.truncated ? " (list truncated)" : "");
}

async function runIocScan() {
  if (!state.openCase) { say("Open a case first", true); return; }
  const text = $("ioc-input").value;
  if (!text.trim()) { say("Paste at least one indicator", true); return; }
  try {
    const payload = await runTask("scan", { text, ...iocOptions() }, "IOC hunting");
    if (!payload) return;
    iocState.hits = payload.hits;
    loadHuntHistory();
    const summary = iocSummary(payload);
    $("ioc-summary").textContent = summary;
    say(summary);
    renderIoc();
  } catch (error) {
    say(error.message, true);
    $("ioc-summary").textContent = error.message;
  }
}

async function runIocFile(file) {
  if (!state.openCase || !file) return;
  const body = new FormData();
  body.append("file", file);
  const options = iocOptions();
  body.append("all_analyses", options.all ? "true" : "false");
  body.append("respect_filters", options.filters ? "true" : "false");
  body.append("live", JSON.stringify(options.live));
  body.append("subdomains", options.subdomains ? "true" : "false");
  body.append("index", String(options.index));
  say(`Reading ${file.name}…`);
  try {
    const response = await fetch(url(`/api/cases/${state.openCase.id}/ioc-file`), { method: "POST", body });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || response.statusText);
    iocState.hits = payload.hits;
    $("ioc-input").value = "";
    loadHuntHistory();
    const summary = iocSummary(payload);
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
  // The list above the matches: what was asked, and what it found.
  const counts = new Map();
  for (const hit of iocState.hits) {
    counts.set(hit.indicator, (counts.get(hit.indicator) || 0) + 1);
  }
  const lines = iocLines();
  $("ioc-list-rows").innerHTML = lines.length ? lines.map((line) => {
    const found = counts.get(line.value) || 0;
    return `<tr><td>${escapeHtml(line.kind || iocKind(line.value))}</td>
      <td title="${escapeHtml(line.value)}">${escapeHtml(line.value)}</td>
      <td title="${escapeHtml(line.value)}">${escapeHtml(line.value)}</td>
      <td>${escapeHtml(line.label || "")}</td>
      <td>${found}</td>
      <td>${found ? "matched" : "no hit"}</td></tr>`;
  }).join("") : '<tr><td colspan="6" class="cellnull">Paste a list above, then Hunt.</td></tr>';

  $("ioc-rows").innerHTML = iocState.hits.map((hit) =>
    `<tr><td>${escapeHtml(hit.when || hit.date || "")}</td>
     <td title="${escapeHtml(hit.indicator)}">${escapeHtml(hit.indicator)}</td>
     <td title="${escapeHtml(hit.analysis_label || "")}">${escapeHtml(hit.analysis_label || "this analysis")}</td>
     <td class="rowid">${escapeHtml(String(hit.row_id))}</td>
     <td>${escapeHtml(hit.analysis === state.analysis
        ? (state.columns[hit.column + 1] || String(hit.column))
        : `column ${hit.column + 1}`)}</td>
     <td title="${escapeHtml(hit.observed)}">${escapeHtml(hit.observed)}</td>
     <td>${escapeHtml(hit.rule)}</td></tr>`).join("")
    || '<tr><td colspan="7" class="cellnull">No hit.</td></tr>';
  $("ioc-status").textContent = `${iocState.hits.length} match(es) for ${lines.length} indicator(s)`;
}

/* ---------- timeline ---------- */

const TIMELINE_COLORS = ["#2d9cdb", "#e6a23c", "#27ae82", "#bb6bd9", "#eb6577", "#56bfc4", "#9fa8da", "#b4a34a"];
const timelineState = { offset: 0, text: "", kind: "text", payload: null, dates: {},
                       row: null, source: null,
                       window: null, history: [], hidden: new Set(), start: null, end: null };
/* The window is a pair of bucket indices, the selection a pair of times: the chart
   can be zoomed without touching the rows, and a duration is the analyst's filter. */

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

/* One timeline entry, opened in its own analysis: the value the evidence holds. */
async function openSourceRow(index, rowId) {
  if (!state.openCase) return;
  $("source-row-title").textContent = "The source line";
  $("source-row-list").innerHTML = '<div class="emptygrid">Reading the row…</div>';
  $("source-row-modal").classList.add("show");
  try {
    const payload = await api(
      `/api/cases/${state.openCase.id}/timeline/row/${index}/${rowId}`);
    $("source-row-title").textContent = `${payload.label} — row ${payload.row_id}`;
    $("source-row-list").innerHTML = payload.columns.map((name, position) => {
      const value = payload.values[position];
      const shown = value === null || value === "" ? "(empty)" : String(value).slice(0, 160);
      return `<div class="analysis-line"><span class="analysis-name">${escapeHtml(name)}</span>
        <span class="pin" title="${escapeHtml(value === null ? "" : String(value))}">${escapeHtml(shown)}</span></div>`;
    }).join("");
  } catch (error) {
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
  try {
    let payload;
    if (heavy) {
      const wanted = { offset: timelineState.offset };
      if (timelineState.text) Object.assign(wanted, { text: timelineState.text, kind: timelineState.kind });
      if (dates) wanted.dates = JSON.parse(dates);
      if (timelineState.start !== null) wanted.start = timelineState.start;
      if (timelineState.end !== null) wanted.end = timelineState.end;
      wanted.include_undated = $("timeline-undated").checked;
      wanted.respect_filters = $("timeline-filters").checked;
      if (wanted.respect_filters) wanted.live = liveView();
      if (visible) wanted.sources = visible;
      payload = await runTask("timeline", wanted, "Timeline");
      if (!payload) return;
    } else {
      payload = await api(`/api/cases/${state.openCase.id}/timeline?${params}`);
    }
    timelineState.payload = payload;
    renderTimeline(payload);
  } catch (error) {
    say(error.message, true);
  }
}

function renderTimeline(payload) {
  renderTimelineDates(payload);
  const shown = payload.sources.map((source, index) => ({ source, index }))
    .filter(({ source }) => !timelineState.hidden.has(source.id));
  $("timeline-legend").innerHTML = payload.sources.map((source, index) => {
    const off = timelineState.hidden.has(source.id);
    return `<span class="chip${off ? " off" : ""}" data-tl-source-chip="${source.id}"
      title="${off ? "Show this source again" : "Hide this source"}"
      style="${off ? "opacity:.45" : ""}"><span class="swatch" style="background:${TIMELINE_COLORS[index % 8]}"></span>${escapeHtml(source.name)} — ${source.dated} dated / ${source.rows} row(s)</span>`;
  }).join("");
  const lane = $("timeline-lane");
  if (lane && !lane.dataset.filled) {
    lane.innerHTML = '<option value="">All lanes</option>'
      + payload.sources.map((source) => `<option value="${source.id}">${escapeHtml(source.name)}</option>`).join("");
    lane.dataset.filled = "1";
    lane.addEventListener("change", () => {
      timelineState.hidden.clear();
      if (lane.value !== "") {
        for (const source of payload.sources) {
          if (String(source.id) !== lane.value) timelineState.hidden.add(source.id);
        }
      }
      loadTimeline(true);
    });
  }
  $("timeline-legend").querySelectorAll("[data-tl-source-chip]").forEach((chip) => {
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
  } else {
    box.innerHTML = timelineBars(hist, shown);
    drawOverview(hist);
    timelineWindowLabel(hist);
    timelineDrag(box, hist);
  }

  $("timeline-rows").innerHTML = payload.rows.map((row) => {
    const [source, rowId, timeNs, sourceTime, summary, note, bookmarked] = row;
    return `<tr data-tl-row="${rowId}" data-tl-source="${source}" title="Open the source line">
      <td>${timeNs === null ? "(undated)" : escapeHtml(utcLabel(timeNs))}</td>
      <td>${payload.sources[source] ? escapeHtml(payload.sources[source].name) : source}</td>
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
      $("timeline-info-extra").textContent =
        `row ${node.dataset.tlRow} of ${node.dataset.tlSource}`;
    });
    node.addEventListener("dblclick", () =>
      openSourceRow(Number(node.dataset.tlSource), Number(node.dataset.tlRow)));
  });

  const from = payload.count ? timelineState.offset + 1 : 0;
  const to = Math.min(timelineState.offset + payload.rows.length, payload.count);
  $("timeline-info").textContent = `${from}\u2013${to} / ${payload.count} event(s) — ${payload.extent.dated} dated`;
  say(`Timeline: ${payload.extent.rows} row(s), ${payload.extent.dated} dated`);
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
  const band = (ns) => utcLabel(ns).slice(0, 16).replace(" ", "T").replace("Z", "");
  const from = await ask({ title: "Show a duration",
                           label: `From (UTC, ISO — empty keeps ${band(payload.extent.start)})`,
                           value: band(payload.extent.start) });
  if (from === null) return;
  const to = await ask({ title: "Show a duration",
                         label: `To (UTC, ISO — empty keeps ${band(payload.extent.end)})`,
                         value: band(payload.extent.end) });
  if (to === null) return;
  const parse = (text, fallback) => {
    if (!text.trim()) return fallback;
    const stamp = Date.parse(text.trim().length <= 10 ? `${text.trim()}T00:00:00Z` : text.trim());
    if (Number.isNaN(stamp)) return NaN;
    return stamp * 1e6;
  };
  const start = parse(from, payload.extent.start);
  const end = parse(to, payload.extent.end);
  if (Number.isNaN(start) || Number.isNaN(end) || start >= end) {
    say("Those dates do not make a duration", true);
    return;
  }
  timelineState.start = Math.round(start);
  timelineState.end = Math.round(end);
  loadTimeline(true);
  say(`Duration: ${band(timelineState.start)} → ${band(timelineState.end)}`);
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
  for (let bucket = start; bucket <= end; bucket += 1) {
    const segments = totals.get(bucket) || [];
    const height = segments.reduce((sum, seg) => sum + seg[1], 0);
    const inner = segments.map(([sourceIndex, count]) =>
      `<span class="seg" style="height:${Math.max(1, Math.round(count / peak * 56))}px;`
      + `background:${TIMELINE_COLORS[sourceIndex % 8]}"></span>`).join("");
    bars.push(`<span class="bar" data-bucket="${bucket}" title="${height} event(s)" `
      + `style="height:${Math.max(height ? 2 : 0, Math.round(height / peak * 56))}px">${inner}</span>`);
  }
  return bars.join("");
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
  box.addEventListener("wheel", (event) => {
    if (Math.abs(event.deltaY) < 2) return;
    event.preventDefault();
    timelineZoom(event.deltaY < 0 ? 0.6 : 1.8, bucketAt(event));
  }, { passive: false });
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
  const closed = (state.openCase && state.openCase.closed) || [];
  tree.innerHTML = '<div class="node grp"><span class="caret">▼</span>Analyses</div>' +
    analyses.map((item) => `
      <div class="node child ${item.index === state.analysis ? "sel" : ""}" data-analysis="${item.index}"
           title="${escapeHtml(item.source || item.path)}">
        <span class="caret"></span>${escapeHtml(item.label)}
      </div>`).join("") +
    (closed.length ? '<div class="node grp closed-group"><span class="caret">▷</span>Closed (kept in the case)</div>'
      + closed.map((item) => `
      <div class="node child closed" data-reopen="${item.index}"
           title="Open this analysis again — ${escapeHtml(item.source || item.path)}">
        <span class="caret"></span>${escapeHtml(item.label)}
      </div>`).join("") : "");
  tree.querySelectorAll("[data-reopen]").forEach((node) => {
    node.addEventListener("click", () => reopenAnalysis(Number(node.dataset.reopen)));
  });
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
  for (const summary of state.summaries) {
    params.append("summary", `${summary.column}:${summary.operation}:${summary.kind}`);
  }
  if (state.order) {
    params.set("order", state.order);
    params.set("order_descending", state.orderDesc === false ? "false" : "true");
    params.set("order_summary", String(state.orderSummary || 0));
  }
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

/* One request may be in flight on the grid. The menu can stop it: the browser
   abandons the query, the server keeps its own state, and nothing is written. */
let rowsRequest = null;

function stopQuery() {
  if (!rowsRequest) { say("No query is running", true); return; }
  rowsRequest.abort();
  rowsRequest = null;
  say("Query stopped — the page stays as it was");
}

async function loadRows(reset) {
  if (!state.openCase) return;
  if (reset) state.offset = 0;
  // A new page is a new set of rows: a selection of ids that are no longer on
  // screen must not survive into "copy the selected rows".
  state.selection.clear();
  state.anchor = null;
  const controller = new AbortController();
  rowsRequest = controller;
  try {
    const payload = await apiAbortable(rowsUrl(), controller.signal);
    state.columns = payload.columns;
    state.rows = payload.rows;
    state.total = payload.total;
    state.offset = payload.offset;
    state.grouped = Boolean(payload.grouped);
    state.payload = payload;
    state.timestamps = payload.timestamps || [];
    await loadBookmarks();
    await loadCellNotes();
    await loadRules();
    await loadLayout();
    renderPaneTabs();
  } catch (error) {
    if (error.name === "AbortError") return;   // the analyst stopped it: not a failure
    say(error.message, true);
  } finally {
    if (rowsRequest === controller) rowsRequest = null;
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

/* "Highlight matches (empty = disable)", the desktop's own control: the text is cut
   around the term, each piece escaped, and only the pieces are marked. */
function markText(text, term) {
  const raw = String(text === null || text === undefined ? "" : text);
  if (!term) return escapeHtml(raw);
  const lower = raw.toLowerCase();
  const needle = term.toLowerCase();
  let from = 0;
  let out = "";
  for (;;) {
    const at = lower.indexOf(needle, from);
    if (at < 0) { out += escapeHtml(raw.slice(from)); return out; }
    out += escapeHtml(raw.slice(from, at)) + "<mark>" + escapeHtml(raw.slice(at, at + needle.length)) + "</mark>";
    from = at + needle.length;
  }
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

  // The header follows `shown`, like the body: a hidden column must not leave its
  // title behind. An absolute index keeps the filters, sorts and widths addressed.
  $("cols").innerHTML = '<col style="width:30px">' + shown.map(({ index }) =>
    `<col style="width:${state.widths[index] || defaultWidth(state.columns[index], index)}px">`).join("");

  const head = ['<tr><th></th>'];
  shown.forEach(({ index }) => {
    const name = state.columns[index];
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
    // The rule is found once, before the cells: a visual needs it per cell.
    const rule = rulesCache.concat(globalRuleList()).find((item) => matchesRule(item, row));
    const cells = shown.map(({ index }) => {
      const value = row[index];
      // The case names its date columns when it has them; a value that reads as a
      // full timestamp is formatted anyway, so the preference is never a no-op.
      const isDate = (Array.isArray(state.timestamps) && state.timestamps.includes(index - 1))
        || DATE_TEXT.test(value === null || value === undefined ? "" : String(value));
      const text = value === null || value === ""
        ? "∅"
        : String(isDate ? formatTimestamp(value, copyPrefs.dateFormat) : value);
      const noted = rowNotes[String(index - 1)];
      const cls = [value === null || value === "" ? "cellnull" : (index === 0 ? "rowid" : ""),
                   noted ? "noted" : ""].filter(Boolean).join(" ");
      const title = noted ? ` title="${escapeHtml(noted)}"` : "";
      const visual = rule ? visualCell(rule, index - 1, row[index]) : null;
      // A rule aimed at one cell colours that cell and leaves the row alone.
      const cellRule = rule && rule.target !== null && rule.target !== undefined
        && (!rule.visual || rule.visual === "none") && Number(rule.target) === index - 1;
      const painted = visual ? ` style="${visual.style}"`
        : (cellRule ? ` style="background:${rule.background};color:${rule.foreground}${rule.bold ? ";font-weight:600" : ""}"` : "");
      return `<td class="${cls}${visual ? ` ${visual.cls}` : ""}"${title}${painted} data-cell="${index - 1}">`
        + (visual && visual.icon ? `<span class="vicon" style="color:${visual.ink}">${visual.icon}</span>` : "")
        + `${state.highlight ? markText(text, state.highlight) : renderBoolean(index - 1, text)}`
        + `${noted ? '<span class="notemark"></span>' : ""}</td>`;
    }).join("");
    const marked = state.bookmarks.has(String(id)) ? "marked" : "";
    // "none" is a string, and a string is true: a rule without a visual format must
    // still paint its row. (This cost a silent regression: every plain colour rule
    // stopped painting the day the server started sending visual: "none".)
    const plain = rule && (!rule.visual || rule.visual === "none")
      && (rule.target === null || rule.target === undefined);
    const style = plain
      ? ` style="background:${rule.background};color:${rule.foreground}${rule.bold ? ";font-weight:600" : ""}"`
      : "";
    return `<tr data-row="${escapeHtml(String(id))}" class="${rowSelected(id) ? "sel" : ""}"${style}>
      <td class="markcell"><span class="cb ${marked}" title="${marked ? escapeHtml(String(state.bookmarks.get(String(id)) || "Bookmarked")) : "Bookmark this row"}"></span></td>${cells}</tr>`;
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

  const summaries = (state.payload && state.payload.summaries) || [];
  $("cols").innerHTML = '<col style="width:30px"><col style="width:34px"><col><col style="width:90px">'
    + summaries.map(() => '<col style="width:130px">').join("");
  $("head").innerHTML = `<tr><th></th><th>Ro…</th><th>${escapeHtml(name)}</th><th>Rows</th>`
    + summaries.map((item) => `<th title="${escapeHtml(item.name)}">`
      + `${escapeHtml(item.operation)} ${escapeHtml(item.name)}</th>`).join("") + "</tr>";

  $("body").innerHTML = state.rows.map((row, position) => {
    const value = row[0];
    const count = row[1];
    const text = value === null || value === "" ? "(empty)" : String(value);
    return `<tr data-group="${escapeHtml(text)}" data-value="${escapeHtml(String(value ?? ""))}">
      <td><span class="cb"></span></td>
      <td class="rowid">${state.offset + position + 1}</td>
      <td title="${escapeHtml(text)}">▸ ${escapeHtml(text)}</td>
      <td>${count}</td>
      ${summaries.map((_item, offset) => {
        const value = row[2 + offset];
        return `<td>${value === null || value === undefined ? "" : escapeHtml(String(value))}</td>`;
      }).join("")}</tr>`;
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

function showTab(name) {
  tabChosen = true;
  document.querySelectorAll(".tab[data-tab]").forEach((tab) =>
    tab.classList.toggle("active", tab.dataset.tab === name));
  $("analysis-view").style.display = name === "analyses" ? "flex" : "none";
  $("cases-view").style.display = name === "cases" ? "flex" : "none";
  $("timeline-view").style.display = name === "timeline" ? "flex" : "none";
  $("ioc-view").style.display = name === "ioc" ? "flex" : "none";
  $("actions-view").style.display = name === "actions" ? "flex" : "none";
  $("imports-view").style.display = name === "imports" ? "flex" : "none";
  $("hayabusa-view").style.display = name === "hayabusa" ? "flex" : "none";
  $("evtx-view").style.display = name === "evtx" ? "flex" : "none";
  if (name === "hayabusa" && state.openCase) loadFindings(false);
  if (name === "evtx" && state.openCase) renderEvtx();
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
}

/* ---------- events ---------- */

function openMenu(name) {
  const cell = document.querySelector(`.menubar .m[data-menu="${name}"]`);
  const menu = document.querySelector(`.menu[data-for="${name}"]`);
  if (!cell || !menu) return;
  document.querySelectorAll(".menu").forEach((node) => node.classList.remove("show"));
  menu.style.left = `${cell.getBoundingClientRect().left}px`;
  menu.classList.add("show");
  cell.classList.add("open");
}

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
  function closeMenus() {
    document.querySelectorAll(".menu").forEach((m) => m.classList.remove("show"));
    document.querySelectorAll(".menubar .m").forEach((m) => m.classList.remove("open"));
  }
  // A press inside an open menu must reach its item: closing the menu on mousedown hides
  // the item before the click can land on it, and no menu command would ever run.
  document.addEventListener("mousedown", (event) => {
    if (event.target.closest && event.target.closest(".menu")) return;
    closeMenus();
  });

  document.querySelectorAll("[data-act]").forEach((node) => {
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
      renderRulesList();
      say(`${payload.imported} shared rule(s) imported`);
    } catch (error) {
      say(error.message, true);
    } finally {
      event.target.value = "";
    }
  });

  document.querySelectorAll(".tab[data-tab]").forEach((tab) => {
    tab.addEventListener("click", () => showTab(tab.dataset.tab));
  });

  $("cases-body").addEventListener("click", (event) => {
    const row = event.target.closest("tr[data-case]");
    if (!row) return;
    state.selectedCase = row.dataset.case;
    renderCaseSelection();
  });
  $("cases-body").addEventListener("dblclick", (event) => {
    const row = event.target.closest("tr[data-case]");
    if (row) openCase(row.dataset.case);
  });
  $("case-search").addEventListener("input", renderCases);
  $("case-archived").addEventListener("change", renderCases);
  $("package-input").addEventListener("change", uploadPortableCase);

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
    // Search and every filter go — the advanced one and its date windows too; the
    // groups, the sort keys and the colours stay, as the desktop's own command says.
    state.search = "";
    state.filters = [];
    state.expression = null;
    state.sort = null;
    state.descending = false;
    state.bookmarksOnly = false;
    $("bookmarks-only").classList.remove("active");
    $("search").value = "";
    const root = $("expr-root");
    if (root) {
      root.innerHTML = "";
      root.appendChild(exprGroupNode({ logic: "and", children: [] }, 0));
    }
    loadRows(true);
  });

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
    // The desktop filters while the analyst types; this window used to wait for
    // Enter. Every render rebuilds the filter row, so the caret is put back.
    const caret = input.selectionStart;
    clearTimeout(filterTimer);
    filterTimer = setTimeout(async () => {
      await loadRows(true);
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

  $("details-toggle").addEventListener("click", toggleDetails);

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
  $("folder-input").addEventListener("change", (event) => {
    const files = [...(event.target.files || [])];
    event.target.value = "";        // the same folder can be picked again
    if (files.length) importFolder(files);
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

  $("rule-column").addEventListener("change", loadRuleValues);
  $("palette-input").addEventListener("input", renderPalette);
  $("ask-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") { event.preventDefault(); answerAsk($("ask-input").value); }
    if (event.key === "Escape") { event.preventDefault(); answerAsk(null); }
  });
  $("ask-modal").addEventListener("click", (event) => {
    if (event.target.id === "ask-modal") answerAsk(null);
  });

  $("palette-input").addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    runPalette(0);
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
    if (!state.openCase) return;
    try { await uploadDestroyPhotos([...event.target.files]); }
    catch (error) { say(`The photos were not kept: ${error.message}`, true); }
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
    const item = hayabusaState.findings[Number(button.dataset.finding)];
    if (!item) return;
    if (button.dataset.want === "mark") markFinding(item);
    else showFindingInGrid(item);
  });
  $("hayabusa-summary").addEventListener("click", (event) => {
    const link = event.target.closest("a[data-sources]");
    if (!link || !state.openCase) return;
    event.preventDefault();
    window.location = url(`/api/cases/${state.openCase.id}/detection/${encodeURIComponent(link.dataset.sources)}/sources`);
  });
  $("graph-build").addEventListener("click", buildGraph);
  $("graph-level").addEventListener("change", () => renderGraph(graphPayload));
  $("evtx-run").addEventListener("click", runEvtxDetection);
  $("evtx-refresh").addEventListener("click", renderEvtx);
  $("graph-navigator").addEventListener("click", exportNavigator);
  $("graph-png").addEventListener("click", exportGraphPng);
  $("graph-node").addEventListener("click", openGraphNode);
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
  $("timeline-build").addEventListener("click", () => loadTimeline(false, true));
  $("timeline-undated").addEventListener("change", () => loadTimeline(true));
  $("timeline-filters").addEventListener("change", () => loadTimeline(true));
  $("timeline-export").addEventListener("click", () => {
    if (!state.openCase) { say("Open a case first", true); return; }
    const params = new URLSearchParams();
    if (timelineState.text) { params.set("text", timelineState.text); params.set("kind", timelineState.kind); }
    const dates = timelineDatesParam();
    if (dates) params.set("dates", dates);
    if ($("timeline-undated").checked) params.set("include_undated", "true");
    if ($("timeline-filters").checked) {
      params.set("respect_filters", "true");
      params.set("live", JSON.stringify(liveView()));
    }
    const visible = timelineVisibleSources();
    if (visible) params.set("sources", visible.join(","));
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

  // The shortcuts the menus announce, and no others: a hint that does nothing is a lie.
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
    if (event.key === "Escape") closeModals();
    if (event.key === "/" && document.activeElement.tagName !== "INPUT") {
      event.preventDefault();
      $("search").focus();
    }
  });
}

function closeModals() {
  if (askState.resolve) answerAsk(null);
  document.querySelectorAll(".modal").forEach((node) => node.classList.remove("show"));
  document.querySelectorAll(".menu").forEach((node) => node.classList.remove("show"));
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
        bookmarks_only: $("report-bookmarks").value === "true" };
  try {
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
  switch (name) {
    case "refresh-cases": await loadCases(); if (state.openCase) await loadRows(true); break;
    case "close-case": closeCase(); break;
    case "reload-analysis": await loadRows(true); break;
    case "export-csv":
      if (!state.openCase) { say("No case open", true); break; }
      window.location.href = url(rowsUrl().replace("/rows?", "/export?"));
      break;
    case "export-xlsx":
      if (!state.openCase) { say("No case open", true); break; }
      window.location.href = url(rowsUrl().replace("/rows?", "/export?") + "&format=xlsx");
      say("Excel export: the same rows, as a workbook");
      break;
    case "import-file": openImportDialog(); break;
    case "import-folder": openFolderPicker(); break;
    case "import-view-file": await viewCollectedFile(); break;
    case "import-copy-unread": await copyUnprocessedFiles(); break;
    case "import-export-list": exportCollectedList(); break;
    case "import-park": await parkCollectedFile(); break;
    case "import-delete": await deleteCollectedFile(); break;
    case "open-view-menu": openMenu("view"); break;
    case "preview-choose": $("preview-input").click(); break;
    case "preview-path": await previewServerPath(); break;
    case "layout-export": exportLayout(); break;
    case "layout-import": $("layout-file").click(); break;
    case "timeline-duration": await timelineDuration(); break;
    case "timeline-open-row": await openSelectedTimelineRow(); break;
    case "tl-zoom-in": timelineZoom(0.6); break;
    case "tl-zoom-out": timelineZoom(1.8); break;
    case "tl-fit": timelineFit(); break;
    case "tl-back": timelineBack(); break;
    case "tl-isolate":
      // Clicking a chip hides one source, the way the desktop isolates one; this
      // brings them all back without rebuilding anything.
      timelineState.hidden.clear();
      $("timeline-lane").value = "";
      loadTimeline(true);
      say("Every source is shown again");
      break;
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
    case "show-timeline": showTab("timeline"); break;
    case "show-evtx": showTab("evtx"); break;
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
    case "export-portable": await exportPortable(); break;
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
    case "global-search": $("search-modal").classList.add("show"); break;
    case "global-run": await runGlobalSearch(); $("search-modal").classList.add("show"); break;
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
    case "disk-open": openDiskDialog(); break;
    case "profile-apply": await applyDetectedProfile(); break;
    case "case-history": await openCaseHistory(); break;
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
    case "ask-ok": answerAsk($("ask-input").value); break;
    case "ask-cancel": answerAsk(null); break;
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

/* A newer release? The service has already asked the registry (and cached the answer);
   this only decides whether to show the band. It never blocks, never retries in a loop,
   and a dismissed version stays dismissed. */
async function checkForUpdate() {
  try {
    const info = await api("/api/version");
    if (!info || !info.available) return;
    if (localStorage.getItem("fb-update-dismissed") === info.latest) return;
    const commands = info.command || [];
    $("update-text").textContent = `Fireblade ${info.latest} is available — you run ${info.current}.`;
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
  loadPalette();
  applyScale();
  applyRowHeight();
  wire();
  fillActionTypes();
  try {
    const health = await api("/health");
    $("version").textContent = `Fireblade ${health.version} · Host`;
  } catch (_) { /* the version is cosmetic */ }
  await loadCases();
  // A first start can be slow (a case container is starting): do not take the analyst
  // back from the tab they already chose while the list was loading.
  if (!tabChosen) showTab(state.cases.length === 1 ? "analyses" : "cases");
  tabChosen = false;
  clearGrid(state.cases.length
    ? "Open a case from the Cases tab."
    : "The library is empty. A case written by the Windows edition opens here as soon as its folder is in the library.");
  $("tree").innerHTML = '<div class="empty">No case open.</div>';
  checkForUpdate();
}

document.addEventListener("DOMContentLoaded", boot);
