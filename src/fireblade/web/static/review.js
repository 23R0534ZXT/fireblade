/* Analyst navigation, grid preferences and evidence review. */
"use strict";

function currentAnalysis() {
  return state.openCase?.analyses.find(item => item.index === state.analysis);
}

function reviewSetting(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; }
  catch (_) { return fallback; }
}

function storeReviewSetting(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); return true; }
  catch (error) { say(error.message, true); return false; }
}

function reviewFamilyKey() {
  const item = currentAnalysis();
  return item?.family && ["artifacts", "schemas"].includes(item.collection?.layout)
    ? "fireblade.familyColumns." + item.family : "";
}

function columnKeysForReview() {
  const counts = new Map();
  return state.columns.map((name, index) => {
    if (!index) return "row-number";
    const count = (counts.get(name) || 0) + 1;
    counts.set(name, count);
    return JSON.stringify([name, count]);
  });
}

function familyDisplay(stored) {
  const key = reviewFamilyKey();
  const family = key && reviewSetting(key, null);
  if (!family || stored.configured || Object.keys(stored.widths || {}).length
    || ["hidden", "pinned", "pinned_right", "order"].some(field => stored[field]?.length)) return stored;
  const indexByKey = new Map(columnKeysForReview().map((key, index) => [key, index]));
  const positions = keys => keys.map(key => indexByKey.get(key)).filter(index => index !== undefined);
  return {
    widths: Object.fromEntries(Object.entries(family.widths)
      .filter(([key]) => indexByKey.has(key)).map(([key, width]) => [indexByKey.get(key), width])),
    hidden: positions(family.hidden), pinned: positions(family.pinned).map(index => index - 1),
    pinned_right: positions(family.pinned_right).map(index => index - 1),
    order: positions(family.order).map(index => index - 1),
  };
}

function saveFamilyDisplay() {
  const key = reviewFamilyKey();
  if (!key) return;
  const keys = columnKeysForReview(), display = currentDisplay();
  const names = (indexes, offset = 0) => indexes.map(index => keys[index + offset]).filter(Boolean);
  const remembered = {
    widths: Object.fromEntries(Object.entries(display.widths).filter(([index]) => keys[index])
      .map(([index, width]) => [keys[index], width])),
    hidden: names(display.hidden), pinned: names(display.pinned, 1),
    pinned_right: names(display.pinned_right, 1), order: names(display.order, 1),
  };
  if (!storeReviewSetting(key, remembered)) return;
  saveLayoutSoon();
  renderPaneTabs();
  say(`Column preferences saved for ${currentAnalysis().family}`);
}

function renderGridPreferences(item) {
  const key = reviewFamilyKey();
  const firstVisit = key && !reviewSetting(key, null);
  const input = item.source_info || {};
  const isFamily = input.parser === "organized" || /\/results\/organisation-/.test(item.source.replaceAll("\\", "/"));
  const source = isFamily ? "Merged source files" : item.source || "Source unavailable";
  $("pane-tabs").insertAdjacentHTML("beforeend", `
    <button class="ptab grid-preferences${firstVisit ? " first-visit" : ""}" type="button" data-grid-preferences
      title="${firstVisit ? "Set and save the column layout for this artifact family" : "Arrange, hide or restore columns"}">Grid preferences</button>
    <button class="btn grid-source" type="button" data-grid-provenance title="${escapeHtml(source)}">${escapeHtml(isFamily ? source : "Source details")}</button>`);
}

function resetGridReview() {
  gridGroupPositions.clear();
  $("gridbody").scrollTop = 0;
  $("grid-hidden-columns").hidden = true;
}

function groupPathValue(value) {
  return value == null || value === "" ? "(empty)" : String(value);
}

function renderGroupTrail(element, path, label, back) {
  element.hidden = path.length === 0;
  element.replaceChildren();
  path.forEach((value, depth) => {
    if (depth) element.append(" › ");
    const text = label(value, depth);
    if (depth + 1 === path.length) { element.append(text); return; }
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    button.title = "Return to this parent";
    button.onclick = () => back(depth + 1);
    element.append(button);
  });
}

const gridGroupPositions = new Map();

function drillGridGroup(path) {
  gridGroupPositions.set(JSON.stringify(state.path), {
    offset: state.offset, scrollTop: $("gridbody").scrollTop,
  });
  state.path = path.map(value => value == null ? null : String(value));
  loadRows(true);
}

async function returnToGridGroup(depth) {
  state.path = state.path.slice(0, depth);
  const previous = gridGroupPositions.get(JSON.stringify(state.path));
  state.offset = previous?.offset || 0;
  if (await loadRows(false)) $("gridbody").scrollTop = previous?.scrollTop || 0;
}

let gridContinuous = reviewSetting("fireblade.continuousGrid", false);
let gridScrollFrame = 0;

function gridIsContinuous() {
  return gridContinuous && Boolean(state.openCase && state.columns.length);
}

function gridPageTotal() {
  return state.payload?.page_total ?? state.total;
}

function gridVirtualHeight() {
  const prefs = rowHeightPrefs();
  const natural = state.grouped ? prefs.groups : prefs.rows;
  return Math.min(natural, 12000000 / Math.max(1, gridPageTotal()));
}

function updateGridPager() {
  const continuous = gridIsContinuous();
  $("gridbody").classList.toggle("continuous", continuous);
  $("grid-scroll-mode").setAttribute("aria-pressed", String(continuous));
  $("grid-scroll-mode").textContent = continuous ? "Pages" : "Continuous scroll";
  $("grid-scroll-mode").disabled = !state.openCase;
  $("prev").hidden = continuous;
  $("next").hidden = continuous;
  $("first").hidden = continuous && state.path.length === 0;
  const parent = $("grid-group-back");
  parent.hidden = !state.path.length;
  $("grid-hidden-columns").hidden = !state.hidden.size;
  $("grid-hidden-columns").textContent = `Hidden columns (${state.hidden.size})`;
}

function gridVirtualSpacer(colspan, count) {
  if (!gridIsContinuous() || count <= 0) return "";
  return `<tr class="grid-spacer" aria-hidden="true"><td colspan="${colspan}" style="height:${Math.floor(count * gridVirtualHeight())}px"></td></tr>`;
}

function scrollReviewRows() {
  if (!gridIsContinuous() || gridScrollFrame) return;
  gridScrollFrame = requestAnimationFrame(async () => {
    gridScrollFrame = 0;
    if (!gridIsContinuous() || rowsRequest || gridPageTotal() <= PAGE) return;
    const box = $("gridbody"), prefs = rowHeightPrefs();
    const rowHeight = state.grouped ? prefs.groups : prefs.rows;
    const virtualHeight = gridVirtualHeight();
    const position = box.scrollTop / virtualHeight;
    const outline = state.payload?.outline;
    const currentCount = outline?.length ?? state.rows.length;
    const top = state.offset * virtualHeight;
    const bottom = top + currentCount * rowHeight;
    if ((state.offset === 0 || box.scrollTop >= top + 16 * rowHeight)
      && (state.offset + currentCount >= gridPageTotal() || box.scrollTop + box.clientHeight < bottom - 16 * rowHeight)) return;
    const offset = Math.min(Math.max(0, gridPageTotal() - PAGE), Math.max(0, Math.floor(position) - 60));
    if (offset === state.offset) return;
    const previous = state.offset;
    state.offset = offset;
    if (!await loadRows(false, false, true) && state.offset === offset && !rowsRequest) state.offset = previous;
  });
}

const reviewHistory = [];
let restoringReviewPlace = false;

function rememberReviewPlace() {
  if (restoringReviewPlace) return;
  const tab = $("doctabs").querySelector(".active")?.dataset.tab;
  if (!tab) return;
  const place = {
    tab, caseId: state.openCase?.id, analysis: state.analysis, offset: state.offset,
    analysisPath: currentAnalysis()?.path,
    scrollTop: $("gridbody").scrollTop, scrollLeft: $("gridbody").scrollLeft,
    path: [...state.path], expandAll: state.expandAll,
    parents: structuredClone(gridGroupPositions),
    view: structuredClone(currentViewFields()),
    sub: $("actions-view").querySelector(".subtab.active")?.dataset.sub,
  };
  const previous = reviewHistory.at(-1);
  if (previous && ["tab", "caseId", "analysis", "offset", "sub"].every(key => previous[key] === place[key])
    && JSON.stringify(place.path) === JSON.stringify(previous.path)
    && JSON.stringify(place.view) === JSON.stringify(previous.view)) return;
  reviewHistory.push(place);
  if (reviewHistory.length > 50) reviewHistory.shift();
  $("workspace-back").disabled = false;
}

async function reviewBack() {
  if (restoringReviewPlace || !reviewHistory.length) return;
  const place = reviewHistory.pop();
  restoringReviewPlace = true;
  try {
    closeModals();
    if (place.caseId && place.caseId !== state.openCase?.id) {
      if (!await openCase(place.caseId, place.analysis)) return;
    } else if (!place.caseId && state.openCase) {
      closeCase();
    }
    if (place.caseId && place.tab === "analyses") {
      const target = state.openCase.analyses.find(item => item.path === place.analysisPath);
      if (!target) { showTab("analyses"); say("The previous grid is outside the current layout.", true); return; }
      state.analysis = target.index;
      resetAnalysisQuery();
      applyViewFields(place.view);
      state.expandAll = place.expandAll;
      state.path = place.path;
      for (const [key, offset] of place.parents) gridGroupPositions.set(key, offset);
      state.offset = place.offset;
      renderTree();
      showTab("analyses");
      if (await loadRows(false)) {
        $("gridbody").scrollTop = place.scrollTop;
        $("gridbody").scrollLeft = place.scrollLeft;
      }
    } else {
      showTab(place.tab);
      if (place.tab === "actions" && place.sub) showWorkspaceSub(place.sub);
    }
  } finally {
    restoringReviewPlace = false;
    $("workspace-back").disabled = reviewHistory.length === 0;
  }
}

async function selectReviewAnalysis(index, filter = null) {
  if (!state.openCase) return false;
  if (index !== state.analysis || filter) rememberReviewPlace();
  state.analysis = index;
  resetAnalysisQuery();
  const restored = currentAnalysis()?.session_view;
  if (!filter && restored) applyViewFields(restored);
  if (filter) state.filters = [filter];
  renderTree();
  return loadRows(true);
}

let reviewSearchRevision = 0;

function openReviewSearch(scope, text = $("search").value) {
  $("global-scope").value = scope;
  $("global-text").value = text;
  $("search-modal").classList.add("show");
  $("global-text").focus();
}

function submitReviewSearch() {
  const text = $("search").value.trim(), scope = $("search-scope").value;
  if (scope === "analysis") { state.search = text; return loadRows(true); }
  openReviewSearch(scope, text);
  return runGlobalSearch();
}

function renderReviewSearch(payload, scope) {
  const cases = payload.cases || [payload];
  const count = cases.reduce((sum, item) => sum + item.analyses.filter(analysis => analysis.count).length, 0);
  const skipped = payload.skipped || [];
  $("global-summary").textContent = `${payload.total} hit(s) in ${count} analysis(es)`
    + (scope === "library" ? ` · ${cases.length} matching case(s) of ${payload.searched}` : "")
    + (skipped.length ? ` · ${skipped.length} unreadable case(s)` : "");
  const term = payload.text;
  $("global-results").innerHTML = cases.map(item => {
    const analyses = item.analyses.filter(analysis => analysis.count);
    if (!analyses.length) return "";
    const contents = analyses.map(analysis => {
      const path = `data-review-case="${escapeHtml(item.case)}" data-review-index="${analysis.index}"`;
      return `<div class="analysis-hit"><header><b>${escapeHtml(analysis.label)}</b>
        <span>${analysis.count} hit(s)</span><button class="btn" ${path} data-review-grid>Open filtered grid</button></header>
        ${analysis.rows.slice(0, 8).map(row => `<button type="button" class="hit" ${path} data-review-row="${row.row_id}"
          title="${escapeHtml(row.file || "")}"><strong>Row ${row.row_id}</strong>
          ${(row.matches || []).map(match => `<span>${escapeHtml(match.column)} · ${markText(match.value, [term])}</span>`).join("")}
          ${row.file ? `<small>${escapeHtml(row.file)}</small>` : ""}</button>`).join("")}</div>`;
    }).join("");
    return scope === "library" ? `<section><h4>${escapeHtml(item.case_name)}</h4>${contents}</section>` : contents;
  }).join("") + skipped.map(item => `<p class="note">${escapeHtml(item.case)} · ${escapeHtml(item.error)}</p>`).join("");
  if (!payload.total && !skipped.length) $("global-results").textContent = "No matching row.";
  $("global-results").dataset.term = term;
}

let facet = null;

const RECMD_FIELD_LABELS = {
  category: "Category", rule: "Rule", hive: "Source hive", key: "Registry key", value: "Value name",
  file: "Collected file",
};

function currentRecmdColumns() {
  if (!state.openCase || state.columnContext !== `${state.openCase.id}/${state.analysis}`) return {};
  return state.payload?.recmd_columns || {};
}

function openRecmdReview() {
  const fields = currentRecmdColumns();
  if (!Object.keys(fields).length) return;
  const source = fields.hive === undefined ? "file" : "hive";
  const order = fields.category === undefined ? ["key", "value", source] : ["category", "rule", source];
  const columns = roles => roles.map(role => fields[role]).filter(index => index !== undefined);
  const button = (label, action) => {
    const element = document.createElement("button");
    element.type = "button";
    element.className = "btn";
    element.textContent = label;
    element.onclick = action;
    return element;
  };
  const group = roles => {
    rememberReviewPlace();
    state.groups = columns(roles);
    state.interval = "";
    state.order = "value";
    state.orderDesc = false;
    reloadRecmdView();
  };
  const presets = [
    button(`Group by ${order.filter(role => fields[role] !== undefined)
      .map(role => RECMD_FIELD_LABELS[role].toLowerCase()).join(" → ")}`, () => group(order)),
    button(`Sort by ${RECMD_FIELD_LABELS[order[0]].toLowerCase()}`, () => {
      rememberReviewPlace();
      state.groups = [];
      state.multiSort = columns(order).map(column => ({ column, descending: false, kind: "text" }));
      state.sort = state.multiSort[0].column;
      state.sortType = "text";
      state.descending = false;
      reloadRecmdView();
    }),
  ];
  if (fields[source] !== undefined) {
    presets.splice(1, 0, button(`Group by ${RECMD_FIELD_LABELS[source].toLowerCase()} first`, () =>
      group([source, ...order.filter(role => role !== source)])));
  }
  if (fields.file !== undefined && source !== "file") {
    presets.splice(-1, 0, button("Group by collected file first", () =>
      group(["file", ...order])));
  }
  $("recmd-presets").replaceChildren(...presets);
  $("recmd-filters").replaceChildren(...Object.entries(fields).map(([role, index]) =>
    button(`Filter by ${RECMD_FIELD_LABELS[role].toLowerCase()}`, () => {
      closeModals();
      openColumnValues(index);
    })));
  $("recmd-modal").classList.add("show");
  presets[0].focus();
}

function reloadRecmdView() {
  state.expandAll = false;
  state.path = [];
  gridGroupPositions.clear();
  closeModals();
  loadRows(true);
}

function readColumnValues(column) {
  const item = state.filters.find(filter => filter.column === column && filter.operator === "one_of");
  if (!item) return [];
  try { return JSON.parse(item.value); } catch (_) { return []; }
}

function openColumnValues(column) {
  if (!state.openCase) return;
  facet = {
    column, analysis: state.analysis, caseId: state.openCase.id, offset: 0, seq: 0,
    checked: new Set(readColumnValues(column)),
  };
  $("column-values-title").textContent = `Values in ${state.columns[column + 1]}`;
  $("column-values-search").value = "";
  $("column-values-modal").classList.add("show");
  $("column-values-search").focus();
  loadColumnValues(facet, 0);
}

async function loadColumnValues(current, offset) {
  if (!current || state.openCase?.id !== current.caseId || state.analysis !== current.analysis) return;
  const seq = ++current.seq;
  $("column-values-status").textContent = "Counting matching values…";
  try {
    const result = await apiPost(`/api/cases/${current.caseId}/analyses/${current.analysis}/column-values`, {
      column: current.column, offset, text: $("column-values-search").value,
      context: { ...liveView(), filters: state.filters.map(item => [item.column, item.operator, item.value]),
        groups: [...state.groups], interval: state.interval, path: [...state.path] },
    });
    if (facet !== current || current.seq !== seq || state.openCase?.id !== current.caseId
      || state.analysis !== current.analysis) return;
    current.offset = offset;
    current.next = result.next;
    const list = $("column-values-list");
    list.replaceChildren(...result.values.map(([value, count]) => {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = current.checked.has(value);
      const name = document.createElement("span"), total = document.createElement("span");
      name.textContent = groupPathValue(value);
      name.title = value;
      total.textContent = count.toLocaleString();
      total.className = "pin";
      input.onchange = () => {
        if (input.checked) current.checked.add(value); else current.checked.delete(value);
        updateFacetStatus(current, result.values.length);
      };
      label.append(input, name, total);
      return label;
    }));
    $("column-values-prev").disabled = !offset;
    $("column-values-more").disabled = result.next == null;
    updateFacetStatus(current, result.values.length);
  } catch (error) {
    if (facet === current && current.seq === seq) $("column-values-status").textContent = error.message;
  }
}

function updateFacetStatus(current, shown) {
  $("column-values-status").textContent = `${current.checked.size} selected · ${shown} values shown`;
}

function applyColumnValues() {
  if (!facet || state.openCase?.id !== facet.caseId || state.analysis !== facet.analysis) return;
  const value = JSON.stringify([...facet.checked]);
  if (facet.checked.size > 100) { say("Select up to 100 values.", true); return; }
  state.filters = state.filters.filter(item => item.column !== facet.column);
  if (facet.checked.size) state.filters.push({ column: facet.column, operator: "one_of", value });
  closeModals();
  loadRows(true);
}

const sourceTree = new Map();
let treeMenuTarget = null;

function treeSourceKey(index) {
  const item = state.openCase?.analyses.find(analysis => analysis.index === Number(index));
  return item ? `${state.openCase.id}/${item.path || item.recorded_path}` : "";
}

function treeSourceChildren(item, depth) {
  const key = treeSourceKey(item.index);
  const entry = sourceTree.get(key);
  if (!entry?.open) return "";
  const files = entry.values.map(([file, count], index) =>
    `<button type="button" class="node tree-source" style="padding-left:${20 + depth * 12}px" data-source-index="${item.index}"
      data-source-file="${index}" title="${escapeHtml(file)}"><span class="nlabel">${escapeHtml(file.split(/[\\/]/).at(-1) || "(source unavailable)")}</span>
      <small>${count.toLocaleString()}</small></button>`).join("");
  return files + (entry.loading ? '<div class="node">Reading source files…</div>' : "")
    + (entry.next != null ? `<button class="node tree-source" style="padding-left:${20 + depth * 12}px"
      data-source-index="${item.index}" data-source-more>More files…</button>` : "");
}

async function expandTreeSources(index, offset = 0) {
  const id = state.openCase?.id;
  if (!id) return;
  const key = treeSourceKey(index);
  if (!key) return;
  let entry = sourceTree.get(key);
  if (!offset && entry?.open) { entry.open = false; renderTree(); return; }
  if (!offset) {
    entry = { open: true, loading: true, values: [], next: null };
    sourceTree.set(key, entry);
  } else if (!entry || entry.loading) return;
  entry.loading = true;
  entry.next = null;
  renderTree();
  try {
    const result = await apiPost(`/api/cases/${id}/analyses/${index}/column-values`, { offset });
    if (sourceTree.get(key) !== entry) return;
    entry.values.push(...result.values);
    entry.column = result.column;
    entry.next = result.next;
  } catch (error) {
    if (state.openCase?.id === id) say(error.message, true);
  } finally {
    entry.loading = false;
    if (state.openCase?.id === id) renderTree();
  }
}

function provenanceSummary(origin) {
  if (!origin || ![origin.file, origin.recorded_file, origin.reader].some(Boolean)) return "";
  const hive = origin.recmd?.hive;
  const rows = [
    [hive && hive === origin.file ? "Source hive" : "Source file", origin.file],
    ["Source hive", hive === origin.file ? "" : hive],
    ["File recorded by the reader", origin.recorded_file],
    ["Reader", origin.reader], ["Parser output", origin.working_file],
    ["Registry batch", origin.batch],
    ["RECmd category", origin.recmd?.category], ["RECmd rule", origin.recmd?.rule],
  ].filter(([, value]) => value);
  return `<dl class="evidence-origin">${rows.map(([name, value]) =>
    `<dt>${escapeHtml(name)}</dt><dd>${escapeHtml(String(value))}</dd>`).join("")}</dl>`;
}

function reviewRowProvenance(row) {
  if (row.provenance) return provenanceSummary(row.provenance);
  const item = currentAnalysis();
  const info = item?.source_info || {};
  const merged = info.parser === "organized" || /\/results\/organisation-/.test((item?.source || "").replaceAll("\\", "/"));
  const normalize = name => name.toLowerCase().replace(/[^a-z0-9]/g, "");
  const fields = new Map(state.columns.map((name, index) => [normalize(name), row[index]]));
  const file = (merged ? row[2] : item?.source) || "";
  const reader = merged ? row[3] : info.parser;
  const recorded = ["hivepath", "sourcefile", "sourcefilename", "firebladeevtxsource"].map(key => fields.get(key)).find(Boolean);
  return provenanceSummary({ file, recorded_file: recorded === file ? "" : recorded, reader,
    batch: reader === "RECmd" ? "Kroll_Batch.reb" : "", working_file: merged ? "" : info.working_path });
}

const LNK_DATES = {
  sourcecreated: "Creation of the shortcut file read by the parser",
  sourcemodified: "Modification of the shortcut file read by the parser",
  sourceaccessed: "Last access recorded for the shortcut file read by the parser",
  targetcreated: "Target creation recorded inside the shortcut",
  targetmodified: "Target modification recorded inside the shortcut",
  targetaccessed: "Target access recorded inside the shortcut",
  trackercreatedon: "Timestamp from the shortcut tracking block",
};

function reviewDateRows(columns, values, provided) {
  const keys = columns.map(name => name.toLowerCase().replace(/[^a-z0-9]/g, ""));
  if (!provided && !(keys.includes("sourcecreated") && keys.includes("targetcreated"))) return "";
  const rows = columns.map((column, index) => {
    const label = provided ? provided[column] : LNK_DATES[keys[index]];
    if (!label) return "";
    return `<tr><th title="${escapeHtml(column)}">${escapeHtml(label)}</th>
      <td>${escapeHtml(String(values[index] ?? "(empty)"))}</td>
      <td><button class="btn" data-lnk-clock="${index}">Use in timeline</button></td></tr>`;
  }).filter(Boolean).join("");
  return rows ? `<div class="lnk-dates"><b>Shortcut timestamps</b>
    <div class="note">Use a shortcut date to study the .lnk file. If it was copied or extracted, check the original filesystem metadata. Target dates describe metadata saved inside the shortcut. Corroborate execution with another artifact.</div>
    <table>${rows}</table></div>` : "";
}

const defaultQuickMarks = [
  { code: "H", label: "High" }, { code: "M", label: "Medium" },
  { code: "L", label: "Low" }, { code: "FP", label: "False positive" },
];
const markRequests = new Set();
const ROW_MARK_HELP = "Click to cycle row marks. Shift-click to toggle a bookmark.";

function rowMarkLabel(id, quick, bookmark) {
  return [`Mark row ${id}`, quick?.label, bookmark && "bookmarked"].filter(Boolean).join(", ");
}

function quickMarks() {
  return reviewSetting("fireblade.quickMarks", defaultQuickMarks);
}

function openQuickMarks() {
  $("quick-marks-text").value = quickMarks().map(mark => `${mark.code} = ${mark.label}`).join("\n");
  $("quick-marks-error").textContent = "";
  $("quick-marks-modal").classList.add("show");
}

async function cycleRowMark(id, bookmark) {
  const marks = quickMarks(), quick = state.payload?.row_marks?.[id];
  if (bookmark || (!quick && (!marks.length || state.bookmarks.has(String(id))))) {
    const current = state.bookmarks.get(String(id)) || "";
    await toggleBookmark(id, current ? "" : "bookmarked");
    return;
  }
  const caseId = state.openCase?.id, analysis = state.analysis;
  const key = `${caseId}/${analysis}/${id}`;
  if (!caseId || markRequests.has(key)) return;
  markRequests.add(key);
  const current = quick?.code || "";
  const next = marks[marks.findIndex(item => item.code === current) + 1] || {};
  try {
    const result = await apiPost(`/api/cases/${caseId}/analyses/${analysis}/row-mark`, {
      row: Number(id), code: next.code || "", label: next.label || "", expected: current,
    });
    if (state.openCase?.id !== caseId || state.analysis !== analysis) return;
    const stored = state.payload.row_marks ||= {};
    if (result.code) stored[id] = result; else delete stored[id];
    const mark = $("body").querySelector(`tr[data-row="${id}"] .markcell button`);
    if (mark) {
      mark.textContent = result.code || "";
      const bookmark = state.bookmarks.get(String(id));
      mark.title = bookmark || result.label || ROW_MARK_HELP;
      mark.setAttribute("aria-label", rowMarkLabel(id, result, bookmark));
      mark.classList.toggle("quick-mark", Boolean(result.code));
      mark.classList.toggle("marked", Boolean(bookmark));
    }
  } finally { markRequests.delete(key); }
}

const TIMELINE_GROUP_LABELS = {
  analysis: "Analysis", day: "UTC day", date_status: "Date availability", bookmark: "Bookmark status",
};
let tableGroupEditor = null;

function chooseTableGrouping(options, selected, onApply) {
  tableGroupEditor = onApply;
  const list = $("table-group-levels");
  const keys = [...selected, ...Object.keys(options).filter(key => !selected.includes(key))];
  list.replaceChildren(...keys.map(key => {
    const row = document.createElement("div");
    row.className = "row";
    const label = document.createElement("label"), input = document.createElement("input");
    input.type = "checkbox";
    input.value = key;
    input.checked = selected.includes(key);
    label.append(input, options[key]);
    row.append(label);
    for (const [text, direction] of [["↑", -1], ["↓", 1]]) {
      const move = document.createElement("button");
      move.className = "btn";
      move.type = "button";
      move.textContent = text;
      move.setAttribute("aria-label", `Move ${options[key]} ${direction < 0 ? "up" : "down"}`);
      move.onclick = () => direction < 0 ? row.previousElementSibling?.before(row) : row.nextElementSibling?.after(row);
      row.append(move);
    }
    return row;
  }));
  $("table-group-modal").classList.add("show");
}

const timelineGrouping = { levels: [], path: [], parents: new Map() };

function timelineGroupLabel(field, value, payload) {
  if (field === "analysis") return payload.sources.find(source => String(source.id) === value)?.name || groupPathValue(value);
  return groupPathValue(value);
}

function renderTimelineGrouped(payload) {
  const trail = $("timeline-group-path");
  renderGroupTrail(trail, timelineGrouping.path, (value, depth) =>
    timelineGroupLabel(timelineGrouping.levels[depth], value, payload), depth => {
    timelineGrouping.path = timelineGrouping.path.slice(0, depth);
    timelineState.offset = timelineGrouping.parents.get(JSON.stringify(timelineGrouping.path)) || 0;
    loadTimeline(false);
  });
  if (timelineGrouping.path.length) {
    const root = document.createElement("button");
    root.type = "button";
    root.textContent = "All groups";
    root.onclick = () => {
      timelineGrouping.path = [];
      timelineState.offset = timelineGrouping.parents.get("[]") || 0;
      loadTimeline(false);
    };
    trail.prepend(root, " › ");
  }
  const hasGroups = Array.isArray(payload.groups);
  $("timeline-table-cols").hidden = hasGroups;
  $("timeline-table-head").innerHTML = hasGroups
    ? `<tr><th>${TIMELINE_GROUP_LABELS[timelineGrouping.levels[timelineGrouping.path.length]]}</th><th>Events</th></tr>`
    : "<tr><th>Date UTC</th><th>Analysis</th><th>Source row</th><th>Summary</th><th>Note</th></tr>";
  if (!hasGroups) return false;
  const field = timelineGrouping.levels[timelineGrouping.path.length];
  $("timeline-rows").innerHTML = payload.groups.map(([value, count], index) =>
    `<tr><td><button class="btn" data-timeline-group="${index}" data-group-depth="${timelineGrouping.path.length}">▸ ${escapeHtml(timelineGroupLabel(field, value, payload))}</button></td><td>${count.toLocaleString()}</td></tr>`).join("");
  $("timeline-info").textContent = `${payload.count} group(s) · ${payload.extent.rows} event(s)`;
  $("timeline-info-extra").textContent = "";
  document.querySelector('[data-act="timeline-open-row"]').disabled = true;
  return true;
}

const tableGroups = new Map();

function openCurrentGrouping() {
  const tab = $("doctabs").querySelector(".active")?.dataset.tab;
  const view = { timeline: "timeline-group", hayabusa: "finding-table-group", ioc: "ioc-group" }[tab];
  if (view) { $(view).click(); return; }
  const sub = $("actions-view").querySelector(".subtab.active")?.dataset.sub;
  const body = tab === "actions" ? {
    actions: "action-rows", indicators: "indicator-rows", entities: "entity-rows", tracking: "tracking-rows",
  }[sub] : { imports: "imports-rows", cases: "cases-body" }[tab];
  if (body) { tableGroups.get($(body))?.button.click(); return; }
  if (tab === "analyses") openGroupPicker();
}

function installTableGrouping(id, button, options) {
  const body = $(id), wrap = body.closest(".gridwrap, .caseswrap");
  const controls = document.createElement("div");
  controls.className = "table-group-controls";
  if (!button) {
    button = document.createElement("button");
    button.type = "button";
    button.className = "btn";
    button.textContent = "Group…";
    controls.append(button);
  }
  const trail = document.createElement("nav");
  trail.setAttribute("aria-label", "Grouping path");
  trail.className = "group-trail";
  controls.append(trail);
  wrap.before(controls);
  const group = { levels: [], path: [], options, button, trail };
  tableGroups.set(body, group);
  button.onclick = () => chooseTableGrouping(options, group.levels, levels => {
    group.levels = levels;
    group.path = [];
    paintTableGroups(body, group);
  });
  new MutationObserver(records => {
    if (records.some(record => [...record.addedNodes, ...record.removedNodes].some(node =>
      node.nodeType === Node.ELEMENT_NODE && !node.classList.contains("table-review-group")))) paintTableGroups(body, group);
  }).observe(body, { childList: true });
  paintTableGroups(body, group);
}

function paintTableGroups(body, group) {
  body.querySelectorAll(".table-review-group").forEach(row => row.remove());
  const columns = body.closest("table").tHead.rows[0].cells.length;
  const rows = [...body.rows].filter(row => row.cells.length === columns);
  const value = (row, level) => row.cells[Number(group.levels[level])]?.textContent.trim() || "";
  const matches = rows.filter(row => group.path.every((key, level) => value(row, level) === key));
  const shown = new Set(matches);
  const field = group.levels[group.path.length];
  for (const row of rows) row.hidden = Boolean(group.levels.length && (field !== undefined || !shown.has(row)));
  renderGroupTrail(group.trail, group.path, (key, depth) =>
    `${group.options[group.levels[depth]]} · ${groupPathValue(key)}`, depth => {
    group.path = group.path.slice(0, depth);
    paintTableGroups(body, group);
  });
  if (group.path.length) {
    const root = document.createElement("button");
    root.textContent = "All groups";
    root.type = "button";
    root.onclick = () => { group.path = []; paintTableGroups(body, group); };
    const back = document.createElement("button");
    back.type = "button";
    back.textContent = "← Parent";
    back.onclick = () => { group.path.pop(); paintTableGroups(body, group); };
    group.trail.prepend(root, back, " › ");
  }
  group.button.classList.toggle("active", group.levels.length > 0);
  if (field === undefined) return;
  const groups = new Map();
  for (const row of matches) {
    const key = value(row, group.path.length);
    groups.set(key, (groups.get(key) || 0) + 1);
  }
  const fragment = document.createDocumentFragment();
  for (const [key, count] of groups) {
    const row = document.createElement("tr");
    row.className = "table-review-group";
    const cell = row.insertCell();
    cell.colSpan = columns;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn";
    button.textContent = `▸ ${group.options[field]} · ${groupPathValue(key)} (${count})`;
    button.onclick = () => { group.path.push(key); paintTableGroups(body, group); };
    cell.append(button);
    fragment.append(row);
  }
  body.prepend(fragment);
}

document.addEventListener("DOMContentLoaded", () => {
  $("workspace-back").onclick = reviewBack;
  document.addEventListener("keydown", event => {
    if (event.altKey && event.key === "ArrowLeft" && reviewHistory.length) {
      event.preventDefault();
      reviewBack();
    }
  });
  $("search-submit").onclick = submitReviewSearch;
  $("recmd-review").onclick = openRecmdReview;
  if (CASE_PREFIX) {
    for (const id of ["search-scope", "global-scope"]) {
      const option = $(id).querySelector('option[value="library"]');
      option.disabled = true;
      option.textContent = "Across cases (single-container Host)";
    }
  }
  $("global-results").addEventListener("click", async event => {
    const button = event.target.closest("[data-review-case]");
    if (!button) return;
    const index = Number(button.dataset.reviewIndex), id = button.dataset.reviewCase;
    const term = $("global-results").dataset.term;
    closeModals();
    if (state.openCase?.id !== id && !await openCase(id, index)) return;
    if (button.hasAttribute("data-review-row")) {
      openSourceRow(index, Number(button.dataset.reviewRow));
      return;
    }
    await selectReviewAnalysis(index);
    showTab("analyses");
    state.search = term;
    $("search").value = term;
    $("search-scope").value = "analysis";
    loadRows(true);
  });
  $("columns-hidden-only").onchange = updateColumnList;
  $("family-save").onclick = saveFamilyDisplay;
  $("pane-tabs").addEventListener("click", event => {
    if (event.target.closest("[data-grid-preferences]")) openColumnManager();
    if (event.target.closest("[data-grid-provenance]")) openIntegrity();
  });
  $("grid-hidden-columns").onclick = () => {
    openColumnManager();
    $("columns-hidden-only").checked = true;
    updateColumnList();
  };
  $("grid-group-back").onclick = () => returnToGridGroup(state.path.length - 1);
  $("grid-scroll-mode").onclick = async () => {
    gridContinuous = !gridContinuous;
    storeReviewSetting("fireblade.continuousGrid", gridContinuous);
    if (gridContinuous) {
      renderGrid();
      $("gridbody").scrollTop = state.offset * gridVirtualHeight();
    } else {
      state.offset = Math.floor(state.offset / PAGE) * PAGE;
      $("gridbody").scrollTop = 0;
      updateGridPager();
      await loadRows(false);
    }
  };
  $("gridbody").addEventListener("scroll", scrollReviewRows, { passive: true });
  $("head").addEventListener("click", event => {
    const values = event.target.closest("[data-column-values]");
    if (values) openColumnValues(Number(values.dataset.columnValues));
    if (event.target.closest("[data-row-mark-settings]")) openQuickMarks();
  });
  $("column-values-apply").onclick = applyColumnValues;
  $("column-values-hide").onclick = () => {
    if (!facet || state.analysis !== facet.analysis || state.openCase?.id !== facet.caseId) return;
    state.hidden.add(facet.column + 1);
    closeModals();
    renderGrid();
    saveLayoutSoon();
  };
  let facetTimer;
  $("column-values-search").oninput = () => {
    clearTimeout(facetTimer);
    const current = facet;
    if (current) current.seq++;
    facetTimer = setTimeout(() => loadColumnValues(current, 0), 200);
  };
  $("column-values-prev").onclick = () => loadColumnValues(facet, Math.max(0, facet.offset - 100));
  $("column-values-more").onclick = () => { if (facet?.next != null) loadColumnValues(facet, facet.next); };
  $("quick-marks-save").onclick = () => {
    const marks = $("quick-marks-text").value.split(/\r?\n/).map(line => line.trim()).filter(Boolean).map(line => {
      const at = line.indexOf("=");
      const code = (at < 0 ? line : line.slice(0, at)).trim().toUpperCase();
      return { code, label: (at < 0 ? code : line.slice(at + 1)).trim() || code };
    });
    if (marks.length > 20 || new Set(marks.map(mark => mark.code)).size !== marks.length
      || marks.some(mark => !/^[\p{L}\d_-]{1,8}$/u.test(mark.code) || mark.label.length > 80)) {
      $("quick-marks-error").textContent = "Enter up to 20 unique codes with 1–8 letters, numbers, hyphens or underscores, and labels up to 80 characters.";
      return;
    }
    if (storeReviewSetting("fireblade.quickMarks", marks)) closeModals();
  };
  $("tree").addEventListener("contextmenu", event => {
    const node = event.target.closest("[data-analysis], [data-group-key]");
    if (!node) return;
    event.preventDefault();
    treeMenuTarget = node;
    const button = $("tree-expose-sources");
    const key = treeSourceKey(node.dataset.analysis);
    button.textContent = sourceTree.get(key)?.open ? "Hide source files" : "Show source files";
    $("tree-menu").hidden = false;
    placePopup($("tree-menu"), event.clientX, event.clientY);
  });
  $("tree-expose-sources").onclick = () => {
    $("tree-menu").hidden = true;
    if (!treeMenuTarget?.isConnected) return;
    if (treeMenuTarget.hasAttribute("data-analysis")) {
      expandTreeSources(Number(treeMenuTarget.dataset.analysis));
    } else {
      treeState.collapsed.delete(treeMenuTarget.dataset.groupKey);
      renderTree();
    }
    treeMenuTarget = null;
  };
  document.addEventListener("click", event => {
    if (!event.target.closest("#tree-menu")) $("tree-menu").hidden = true;
  });
  $("tree").addEventListener("click", event => {
    const file = event.target.closest("[data-source-index]");
    if (!file) return;
    const index = Number(file.dataset.sourceIndex);
    const entry = sourceTree.get(treeSourceKey(index));
    if (!entry) return;
    if (file.hasAttribute("data-source-more")) { expandTreeSources(index, entry.next); return; }
    const [value] = entry.values[Number(file.dataset.sourceFile)];
    selectReviewAnalysis(index, entry.column == null ? null : { column: entry.column, operator: "one_of", value: JSON.stringify([value]) });
  });
  for (const node of [$("details"), $("source-row-list")]) {
    node.addEventListener("click", event => {
      const button = event.target.closest("[data-lnk-clock]");
      if (!button || !state.openCase) return;
      const column = Number(button.dataset.lnkClock);
      const context = node === $("details")
        ? { index: state.analysis, header: state.columns[column + 1] }
        : node.reviewDateContext && { index: node.reviewDateContext.analysis, header: node.reviewDateContext.columns[column] };
      if (!context?.header) return;
      selectTimelineClock(context.index, context.header);
    });
  }
  $("table-group-apply").onclick = () => {
    const callback = tableGroupEditor;
    const levels = [...$("table-group-levels").querySelectorAll("input:checked")].map(input => input.value);
    closeModals();
    callback?.(levels);
  };
  $("timeline-group").onclick = () => chooseTableGrouping(TIMELINE_GROUP_LABELS, timelineGrouping.levels, levels => {
    Object.assign(timelineGrouping, { levels, path: [], parents: new Map() });
    $("timeline-group").classList.toggle("active", levels.length > 0);
    loadTimeline(true);
  });
  $("timeline-rows").addEventListener("click", event => {
    const group = event.target.closest("[data-timeline-group]");
    if (!group || Number(group.dataset.groupDepth) !== timelineGrouping.path.length) return;
    timelineGrouping.parents.set(JSON.stringify(timelineGrouping.path), timelineState.offset);
    timelineGrouping.path.push(timelineState.payload.groups[Number(group.dataset.timelineGroup)][0]);
    loadTimeline(true);
  });
  $("ioc-group").onclick = () => chooseTableGrouping(IOC_GROUP_LABELS, iocGrouping.levels, levels => {
    if (!iocState.hunt) { say("Run or open a hunt to group its matches.", true); return; }
    Object.assign(iocGrouping, { levels, path: [], parents: new Map() });
    $("ioc-group").classList.toggle("active", levels.length > 0);
    iocPage(-iocState.offset);
  });
  $("ioc-rows").addEventListener("click", event => {
    const group = event.target.closest("[data-ioc-group]");
    if (!group || Number(group.dataset.groupDepth) !== iocGrouping.path.length) return;
    iocGrouping.parents.set(JSON.stringify(iocGrouping.path), iocState.offset);
    iocGrouping.path.push(iocState.groups[Number(group.dataset.iocGroup)][0]);
    iocPage(-iocState.offset);
  });
  const tables = {
    "hayabusa-rows": [ "finding-table-group", { 1: "Severity", 2: "Rule", 3: "Computer", 5: "Event ID", 6: "Technique" }],
    "imports-rows": [null, { 0: "Status", 1: "File", 2: "Reader", 3: "Reason" }],
    "tracking-rows": [null, { 2: "Machine and source", 3: "Tags", 4: "Level, confidence and verdict" }],
    "action-rows": [null, { 1: "Status", 2: "Priority", 3: "Owner" }],
    "indicator-rows": [null, { 0: "Type", 3: "Status" }],
    "entity-rows": [null, { 0: "Kind", 2: "Hostname" }],
    "ioc-list-rows": [null, { 0: "Type", 3: "Label" }],
    "cases-body": [null, { 2: "Status" }],
  };
  Object.entries(tables).forEach(([id, [button, options]]) => installTableGrouping(id, button && $(button), options));
  $("graph-tag-filter").onchange = () => renderGraph(graphPayload);
  $("graph-evidence").addEventListener("click", async event => {
    const button = event.target.closest("[data-graph-observation], [data-graph-record]");
    const caseId = state.openCase?.id;
    if (!button || !caseId) return;
    try {
      if (button.hasAttribute("data-graph-record")) {
        const params = new URLSearchParams({ record: button.dataset.graphRecord, line: button.dataset.graphRecordLine });
        const { analysis, row } = await api(`/api/cases/${caseId}/marked-row?${params}`);
        if (state.openCase?.id === caseId) openSourceRow(analysis, row);
        return;
      }
      const entry = await api(`/api/cases/${caseId}/tracking/events/${button.dataset.graphObservation}`);
      if (state.openCase?.id !== caseId) return;
      showObservation({ caseId }, { event: entry, origin: entry.origin });
    } catch (error) { say(error.message, true); }
  });
});

function selectTimelineClock(index, header) {
  const selected = { ...timelineState.dates, [index]: header };
  closeModals();
  rememberReviewPlace();
  timelineState.dates = selected;
  const selector = $("timeline-dates").querySelector(`select[data-source="${index}"]`);
  if (selector && ![...selector.options].some(option => option.value === header)) {
    selector.add(new Option(header, header));
  }
  if (selector) selector.value = header;
  if ($("tab-timeline").classList.contains("active")) loadTimeline(true);
  else showTab("timeline");
}

const IOC_GROUP_LABELS = { indicator: "IOC", source: "Analysis", column: "Column", rule: "Match rule" };
const iocGrouping = { levels: [], path: [], parents: new Map() };

function resetIocGrouping() {
  Object.assign(iocGrouping, { levels: [], path: [], parents: new Map() });
  Object.assign(iocState, { groups: null, groupSources: {} });
  $("ioc-group").classList.remove("active");
  $("ioc-group-path").hidden = true;
}

function renderIocGrouped() {
  const label = (field, value) => field === "source" ? iocState.groupSources[value] || groupPathValue(value) : groupPathValue(value);
  const trail = $("ioc-group-path");
  const back = depth => {
    iocGrouping.path = iocGrouping.path.slice(0, depth);
    iocPage((iocGrouping.parents.get(JSON.stringify(iocGrouping.path)) || 0) - iocState.offset);
  };
  renderGroupTrail(trail, iocGrouping.path, (key, depth) => label(iocGrouping.levels[depth], key), back);
  if (iocGrouping.path.length) {
    const root = document.createElement("button");
    root.type = "button";
    root.textContent = "All groups";
    root.onclick = () => back(0);
    trail.prepend(root, " › ");
  }
  const hasGroups = Array.isArray(iocState.groups);
  $("ioc-match-cols").hidden = hasGroups;
  const field = iocGrouping.levels[iocGrouping.path.length];
  $("ioc-match-head").innerHTML = hasGroups
    ? `<tr><th>${IOC_GROUP_LABELS[field]}</th><th>Matches</th></tr>`
    : "<tr><th>Source date</th><th>IOC</th><th>Analysis</th><th>Source row</th><th>Column</th><th>Observed value</th><th>Excerpt</th><th>Rule</th></tr>";
  if (!hasGroups) return false;
  $("ioc-rows").innerHTML = iocState.groups.map(([value, count], index) =>
    `<tr><td><button class="btn" data-ioc-group="${index}" data-group-depth="${iocGrouping.path.length}">▸ ${escapeHtml(label(field, value))}</button></td><td>${count.toLocaleString()}</td></tr>`).join("");
  $("ioc-status").textContent = `${iocState.count} group(s) of stored matches`;
  return true;
}
