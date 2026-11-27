/* Observation log and read-only disk explorer. Shares the Host's case and dialog state. */

let trackingRevision = 0;
let scenarioRevision = 0;
let editedObservation = null;
let displayedEvents = new Map();

function resetTracking() {
  trackingRevision++;
  editedObservation = null;
  $("tracking-tags").replaceChildren();
  $("tracking-rows").replaceChildren();
  $("tracking-network").replaceChildren();
  $("tracking-sequences").replaceChildren();
  displayedEvents.clear();
  resetScenario();
}

function resetScenario() {
  scenarioRevision++;
  $("scenario-panel").open = false;
  $("scenario-edges").replaceChildren();
  $("scenario-status").textContent = "";
}

function trackingParams() {
  const params = new URLSearchParams();
  for (const choice of $("tracking-tags").selectedOptions) params.append("tag", choice.value);
  if ($("tracking-fp").checked) params.set("fp", "true");
  return params;
}

function observationSource(origin) {
  return [origin.file, origin.artifact, origin.line && `row ${origin.line}`, origin.column]
    .filter(Boolean).join(" · ");
}

async function refreshTracking() {
  const id = state.openCase?.id;
  if (!id) return;
  const revision = ++trackingRevision;
  const params = trackingParams();
  params.set("minutes", $("tracking-minutes").value);
  try {
    const { events, tags, connections } = await api(`/api/cases/${id}/tracking?${params}`);
    if (state.openCase?.id !== id || revision !== trackingRevision) return;
    const selected = new Set(params.getAll("tag"));
    $("tracking-tags").replaceChildren(...tags.map(tag => new Option(tag, tag, false, selected.has(tag))));
    displayedEvents = new Map(events.map(event => [event.id, event]));
    $("tracking-rows").innerHTML = events.length ? events.map(event =>
      `<tr><td>${escapeHtml(event.time || "Undated")}</td>
        <td><button class="btn" data-edit-observation="${escapeHtml(event.id)}">${escapeHtml(event.description || event.kind)}</button></td>
        <td>${escapeHtml([event.machine, observationSource(event.origin)].filter(Boolean).join(" · "))}</td>
        <td>${escapeHtml(event.tags.join(", "))}</td>
        <td>${escapeHtml([event.level, event.confidence, event.verdict.replaceAll("_", " ")].join(" · "))}</td></tr>`
    ).join("") : '<tr><td colspan="5">Right-click an analysis row to tag an observation.</td></tr>';
    const hostEvents = new Map();
    for (const event of events) {
      if (!event.machine || !event.time) continue;
      const key = event.machine.toLowerCase();
      if (!hostEvents.has(key)) hostEvents.set(key, []);
      hostEvents.get(key).push(event);
    }
    $("tracking-sequences").innerHTML = hostEvents.size ? [...hostEvents.values()].map(items => {
      const nodes = items.map(event => `<button class="btn" data-edit-observation="${escapeHtml(event.id)}">
        <time>${escapeHtml(event.time)}</time><b>${escapeHtml(event.description || event.kind)}</b>
        <span>${escapeHtml(event.tags.join(", "))}</span></button>`);
      return `<div class="observation-sequence"><b>${escapeHtml(items[0].machine)}</b>
        <div>${nodes.join('<span aria-hidden="true">→</span>')}</div></div>`;
    }).join("") : "<p>No dated observations with a machine in this selection.</p>";
    $("tracking-network").innerHTML = connections.length ? connections.map(connection => {
      const related = connection.followed_by.map(key => displayedEvents.get(key))
        .map(event => `<button class="btn" data-edit-observation="${escapeHtml(event.id)}">${escapeHtml(event.file || event.description || event.kind)}</button>`);
      return `<div class="connection-edge"><button class="btn" data-edit-observation="${escapeHtml(connection.event)}">
        ${escapeHtml(connection.source)} → ${escapeHtml(connection.destination)} (${escapeHtml(connection.direction)})</button>
        ${related.length ? `<span>Later on the same machine → </span>${related.join(" ")}` : ""}</div>`;
    }).join("") : "<p>No tagged network connections in this selection.</p>";
  } catch (error) {
    if (revision === trackingRevision) say(error.message, true);
  }
}

function showObservation(context, record) {
  const event = record.event || {};
  editedObservation = { ...context, id: event.id };
  const fields = $("tracking-form").elements;
  for (const [name, fallback] of Object.entries({
    time: record.time || "", machine: record.origin.machine || "", tags: [],
    description: record.selection || "", level: "medium", confidence: "medium",
    verdict: "open", kind: "observation", direction: "unknown",
    source_ip: "", destination_ip: "", file: "", comment: "",
  })) {
    const value = event[name] ?? record.suggestions?.[name] ?? fallback;
    fields[name].value = Array.isArray(value) ? value.join(", ") : value;
  }
  $("tracking-origin").textContent = observationSource(record.origin);
  $("tracking-delete").hidden = !event.id;
  showObservationFields();
  $("tracking-modal").classList.add("show");
  $("track-rewrite").hidden = true;
  $("track-suggestion-row").hidden = true;
  $("track-suggestion").value = "";
  const current = editedObservation;
  api(`/api/cases/${current.caseId}/tracking/rewrite`).then(settings => {
    if (editedObservation === current) $("track-rewrite").hidden = !settings.enabled;
  }).catch(() => {});
}

function showObservationFields() {
  $("track-network-fields").hidden = $("track-kind").value !== "connection";
  $("track-file-row").hidden = $("track-kind").value !== "file_creation";
}

function gridContext() {
  const id = state.openCase?.id;
  const row = Number(contextRow?.dataset.row);
  if (!id || !Number.isSafeInteger(row) || row < 1) throw new Error("Choose an analysis row.");
  const column = contextColumnIndex();
  return { caseId: id, analysis: state.analysis, row, column: column >= 0 ? column : null };
}

async function openTaggedRow() {
  try {
    const context = gridContext();
    const { caseId, analysis, row, column } = context;
    const query = new URLSearchParams({ analysis, row });
    if (column !== null) query.set("column", column);
    const record = await api(`/api/cases/${caseId}/tracking/row?${query}`);
    if (state.openCase?.id === caseId && state.analysis === analysis) showObservation(context, record);
  } catch (error) { say(error.message, true); }
}

async function importGridBookmarks() {
  try {
    const { caseId, analysis } = gridContext();
    const result = await apiPost(`/api/cases/${caseId}/tracking/bookmarks`, { analysis });
    if (state.openCase?.id !== caseId) return;
    say(`${result.added} bookmark(s) added · ${result.already_tagged} already in the log`);
    showTab("actions");
    showWorkspaceSub("tracking");
  } catch (error) { say(error.message, true); }
}

function looksLikeIP(value) {
  const text = String(value).trim();
  return /^\d{1,3}(?:\.\d{1,3}){3}$/.test(text) || /^[\da-f:]+:[\da-f:.]+$/i.test(text);
}

async function useGridIP(declare) {
  try {
    const { caseId, analysis, row, column } = gridContext();
    const path = `/api/cases/${caseId}/tracking/indicator`;
    const context = { analysis, row, column };
    if (declare) {
      const record = await api(`/api/cases/${caseId}/tracking/row?` + new URLSearchParams(context));
      if (state.openCase?.id !== caseId || state.analysis !== analysis) return;
      const machine = record.origin.machine || window.prompt("Machine where this IP was found (optional)", "");
      if (machine === null) return;
      const result = await apiPost(path, { ...context, machine, declare });
      if (state.openCase?.id === caseId) say(`Tracking ${result.value} with source provenance`);
    } else {
      const result = await apiPost(path, context);
      if (state.openCase?.id !== caseId) return;
      showTab("ioc");
      $("ioc-input").value = result.value;
      const all = $("ioc-all");
      if (all) all.checked = true;
      await runIocScan();
    }
  } catch (error) { say(error.message, true); }
}

let explorer = { revision: 0, images: [], path: "/", offset: 0 };

async function openDiskExplorer() {
  const id = state.openCase?.id;
  if (!id) { say("Open a case first", true); return; }
  try {
    const { images } = await api(`/api/cases/${id}/disk-images`);
    if (state.openCase?.id !== id) return;
    const source = $("disk-source").value;
    closeModals();
    $("image-source").value = /\.(e01|img|dd|raw)$/i.test(source) ? source : "";
    explorer = { revision: explorer.revision + 1, caseId: id, images, path: "/", offset: 0 };
    $("image-status").textContent = "";
    $("disk-explorer-modal").classList.add("show");
    updateImageList();
  } catch (error) { say(error.message, true); }
}

function updateImageList(selected) {
  $("image-list").replaceChildren(...explorer.images.map(image =>
    new Option(image.name, image.id, false, image.id === selected)));
  selectImage();
}

function selectImage() {
  const image = explorer.images.find(item => item.id === $("image-list").value);
  $("image-partition").replaceChildren(...(image?.partitions || []).map(partition =>
    new Option(`${partition.index} · ${partition.type}`, String(partition.index))));
  readImageDirectory();
}

function imageHexDump(content) {
  const bytes = content.split(" ");
  const rows = [];
  for (let offset = 0; offset < bytes.length; offset += 16) {
    const group = bytes.slice(offset, offset + 16);
    const printable = group.map(hex => {
      const value = parseInt(hex, 16);
      return value >= 32 && value < 127 ? String.fromCharCode(value) : ".";
    }).join("");
    rows.push(`${offset.toString(16).padStart(8, "0")}  ${group.join(" ").padEnd(47)}  ${printable}`);
  }
  return rows.join("\n");
}

async function readImageDirectory(path = "/", offset = 0) {
  const image = $("image-list").value;
  const partition = $("image-partition").value;
  const id = explorer.caseId;
  const revision = ++explorer.revision;
  $("image-entries").replaceChildren();
  $("image-preview").hidden = true;
  $("image-up").disabled = true;
  $("image-next").hidden = true;
  $("image-prev").hidden = true;
  $("image-path").textContent = path;
  if (!image || !partition) return;
  $("image-status").textContent = "Reading the directory…";
  try {
    const params = new URLSearchParams({ partition, path, offset });
    const result = await api(`/api/cases/${id}/disk-images/${image}/files?${params}`);
    if (state.openCase?.id !== id || explorer.revision !== revision) return;
    explorer.path = path;
    explorer.offset = offset;
    explorer.next = result.next;
    explorer.entries = result.entries;
    $("image-up").disabled = path === "/";
    $("image-next").hidden = result.next === null;
    $("image-prev").hidden = offset === 0;
    $("image-entries").innerHTML = result.entries.map((entry, index) => {
      const name = escapeHtml(entry.name);
      return `<tr><td>${entry.kind === "directory" ? `<button class="btn" data-image-dir="${index}">${name}/</button>` : name}</td>
        <td>${escapeHtml(entry.kind)}</td><td>${entry.kind === "file" ? entry.size : ""}</td>
        <td>${escapeHtml(entry.created || "")}</td><td>${escapeHtml(entry.modified || "")}</td>
        <td>${entry.kind === "file" ? `<button class="btn" data-image-preview="${index}">Preview</button> <button class="btn" data-image-file="${index}">Collect</button>` : ""}</td></tr>`;
    }).join("");
    $("image-status").textContent = result.entries.length ? "" : "This directory is empty.";
  } catch (error) {
    if (explorer.revision === revision) $("image-status").textContent = error.message;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  for (const id of ["tracking-tags", "tracking-fp", "tracking-minutes"]) $(id).addEventListener("change", refreshTracking);
  for (const format of ["xlsx", "docx"]) {
    $(`tracking-${format}`).addEventListener("click", () => {
      const id = state.openCase?.id;
      if (id) window.location.assign(url(`/api/cases/${id}/tracking/export/${format}?${trackingParams()}`));
    });
  }
  for (const id of ["tracking-rows", "tracking-network", "tracking-sequences"]) $(id).addEventListener("click", (event) => {
    const button = event.target.closest("[data-edit-observation]");
    const entry = displayedEvents.get(button?.dataset.editObservation);
    if (entry && state.openCase) showObservation({ caseId: state.openCase.id }, { event: entry, origin: entry.origin });
  });
  $("track-kind").addEventListener("change", showObservationFields);
  $("track-rewrite").addEventListener("click", async () => {
    const current = editedObservation;
    const input = $("track-description");
    const description = input.value.trim();
    if (!current || !description) return;
    const button = $("track-rewrite");
    button.disabled = true;
    try {
      const suggestion = await apiPost(`/api/cases/${current.caseId}/tracking/rewrite`, { description });
      if (editedObservation !== current || state.openCase?.id !== current.caseId ||
          !$("tracking-modal").classList.contains("show")) return;
      if (input.value.trim() === description) {
        $("track-suggestion").value = suggestion.description;
        $("track-suggestion-row").hidden = false;
      }
    } catch (error) { say(error.message, true); }
    finally { button.disabled = false; }
  });
  $("track-description").addEventListener("input", () => { $("track-suggestion-row").hidden = true; });
  $("track-use-suggestion").addEventListener("click", () => {
    if ($("track-suggestion-row").hidden) return;
    $("track-description").value = $("track-suggestion").value;
    $("track-suggestion-row").hidden = true;
    $("track-description").focus();
  });
  $("tracking-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const context = editedObservation;
    if (!context || state.openCase?.id !== context.caseId) return;
    const fields = Object.fromEntries(new FormData(event.target));
    fields.tags = fields.tags.split(",").map(tag => tag.trim()).filter(Boolean);
    const { caseId, ...record } = context;
    const submit = event.submitter;
    submit.disabled = true;
    try {
      await apiPost(`/api/cases/${caseId}/tracking/events`, { ...record, ...fields });
      if (state.openCase?.id !== caseId || editedObservation !== context) return;
      closeModals();
      say("Observation saved");
      refreshTracking();
    } catch (error) { say(error.message, true); }
    finally { submit.disabled = false; }
  });
  $("tracking-delete").addEventListener("click", async () => {
    const current = editedObservation;
    if (!current?.id || state.openCase?.id !== current.caseId ||
        !window.confirm("Remove this observation from the investigation log?")) return;
    try {
      await apiDelete(`/api/cases/${current.caseId}/tracking/events/${current.id}`);
      if (current !== editedObservation) return;
      closeModals();
      refreshTracking();
    } catch (error) { say(error.message, true); }
  });
  $("disk-browse").addEventListener("click", openDiskExplorer);
  $("image-list").addEventListener("change", selectImage);
  $("image-partition").addEventListener("change", () => readImageDirectory());
  $("image-up").addEventListener("click", () => readImageDirectory(explorer.path.slice(0, explorer.path.lastIndexOf("/")) || "/"));
  $("image-next").addEventListener("click", () => readImageDirectory(explorer.path, explorer.next));
  $("image-prev").addEventListener("click", () => readImageDirectory(explorer.path, Math.max(0, explorer.offset - 200)));
  $("image-open").addEventListener("click", async () => {
    const id = explorer.caseId;
    const instance = explorer;
    const source = $("image-source").value.trim();
    if (!source || !id) return;
    $("image-open").disabled = true;
    $("image-status").textContent = "Opening image read-only…";
    try {
      const image = await apiPost(`/api/cases/${id}/disk-images`, { source });
      if (explorer !== instance || state.openCase?.id !== id) return;
      if (!explorer.images.some(item => item.id === image.id)) explorer.images.push(image);
      updateImageList(image.id);
    } catch (error) { if (explorer === instance) $("image-status").textContent = error.message; }
    finally { $("image-open").disabled = false; }
  });
  $("image-entries").addEventListener("click", async (event) => {
    const dir = event.target.closest("[data-image-dir]");
    const file = event.target.closest("[data-image-file]");
    const preview = event.target.closest("[data-image-preview]");
    if (!dir && !file && !preview) return;
    const entry = explorer.entries[Number(dir?.dataset.imageDir ?? file?.dataset.imageFile ?? preview.dataset.imagePreview)];
    const path = `${explorer.path === "/" ? "" : explorer.path}/${entry.name}`;
    if (dir) { readImageDirectory(path); return; }
    const { caseId, revision } = explorer;
    if (preview) {
      const request = {};
      explorer.previewRequest = request;
      $("image-preview").hidden = true;
      $("image-status").textContent = `Reading ${entry.name}…`;
      try {
        const params = new URLSearchParams({ partition: $("image-partition").value, path });
        const sample = await api(`/api/cases/${caseId}/disk-images/${$("image-list").value}/preview?${params}`);
        if (explorer.revision !== revision || explorer.previewRequest !== request) return;
        const panel = $("image-preview");
        const content = sample.binary ? imageHexDump(sample.content) : sample.content;
        panel.textContent = content + (sample.truncated ? "\n[…]" : "");
        panel.classList.toggle("binary-preview", sample.binary);
        $("image-preview-title").textContent = `${entry.name} · ${sample.binary ? "Hexadecimal preview" : "Text preview"}`;
        panel.hidden = false;
        $("image-status").textContent = "";
      } catch (error) {
        if (explorer.revision === revision && explorer.previewRequest === request) $("image-status").textContent = error.message;
      }
      return;
    }
    file.disabled = true;
    $("image-status").textContent = "Copying and hashing the evidence…";
    try {
      const result = await apiPost(`/api/cases/${caseId}/disk-images/${$("image-list").value}/files`,
        { partition: Number($("image-partition").value), path });
      if (explorer.revision === revision) {
        const link = document.createElement("a");
        link.textContent = "Download case copy";
        link.href = url(`/api/cases/${caseId}/disk-files/${result.id}`);
        $("image-status").replaceChildren(`Collected ${result.name} · SHA-256 ${result.sha256} · `, link);
      }
    } catch (error) { if (explorer.revision === revision) $("image-status").textContent = error.message; }
    finally { file.disabled = false; }
  });
});

async function showScenario() {
  const id = state.openCase?.id;
  if (!id || !$("scenario-panel").open) return;
  const revision = ++scenarioRevision;
  $("scenario-status").textContent = "Reading source records…";
  $("scenario-edges").replaceChildren();
  try {
    const result = await api(`/api/cases/${id}/scenario`);
    if (state.openCase?.id !== id || revision !== scenarioRevision) return;
    const nodes = new Map(result.nodes.map(node => [node.id, node]));
    const card = node => `<div class="gitem"><button class="btn scenario-record" data-analysis="${node.analysis}" data-row="${node.row}">
      <b>${escapeHtml(node.kind)}</b> ${escapeHtml(node.detail)}
      <small>${escapeHtml([node.host, node.time, node.source].filter(Boolean).join(" · "))}</small>
      </button><div class="gslot"></div></div>`;
    $("scenario-edges").innerHTML = result.edges.map(edge => `<div class="scenario-edge">
      ${card(nodes.get(edge.source))}<span>${escapeHtml(edge.reason)} →</span>${card(nodes.get(edge.target))}
    </div>`).join("");
    $("scenario-status").textContent = `${result.edges.length} link(s) across ${result.scanned} compatible analyses` +
      (result.limited ? " · scan limit reached" : "");
  } catch (error) {
    if (state.openCase?.id === id) $("scenario-status").textContent = error.message;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  $("scenario-panel").addEventListener("toggle", showScenario);
  $("scenario-edges").addEventListener("click", event => {
    const button = event.target.closest(".scenario-record");
    if (button) graphOpenLine(Number(button.dataset.analysis), Number(button.dataset.row), button);
  });
  $("incident-open").addEventListener("click", async () => {
    const id = state.openCase?.id;
    if (!id) return;
    try {
      const result = await api(`/api/cases/${id}/incident-context`);
      if (state.openCase?.id !== id) return;
      const form = $("incident-form");
      form.dataset.case = id;
      $("incident-fields").replaceChildren(...Object.entries(result.fields).map(([key, label]) => {
        const row = document.createElement("label");
        row.className = "row";
        const name = document.createElement("span");
        name.textContent = label;
        const input = document.createElement(["discovered", "severity", "incident_type"].includes(key) ? "input" : "textarea");
        input.name = key;
        input.maxLength = key === "discovered" ? 40 : 4000;
        if (input.tagName === "TEXTAREA") input.rows = 2;
        input.value = result.values[key] || "";
        row.append(name, input);
        return row;
      }));
      $("incident-modal").classList.add("show");
    } catch (error) { say(error.message, true); }
  });
  $("incident-form").addEventListener("submit", async event => {
    event.preventDefault();
    const id = event.target.dataset.case;
    if (state.openCase?.id !== id) return;
    try {
      await apiPut(`/api/cases/${id}/incident-context`, Object.fromEntries(new FormData(event.target)));
      if (state.openCase?.id !== id) return;
      closeModals();
      window.location.assign(url(`/api/cases/${id}/incident-context.docx`));
    } catch (error) { say(error.message, true); }
  });
});
