/* Kagarasu Host — the window manager.

   The desktop's windows can be moved, resized, and its panes can be dragged apart. A browser
   page has none of that by itself, so this file gives the client the same three gestures:

     - every dialog is moved by its title bar and resized from its corner;
     - the artifact tree is resized from the splitter that separates it from the grid;
     - the row details are resized from the splitter that separates them from the grid.

   Geometry is remembered for the session of the page and, when the browser allows it, across
   reloads. A browser that refuses storage still gets a working layout. */
(function () {
  "use strict";

  var KEY = "fireblade.layout";
  var layout = {};
  try { layout = JSON.parse(window.localStorage.getItem(KEY) || "{}") || {}; } catch (e) { layout = {}; }

  function save() {
    try { window.localStorage.setItem(KEY, JSON.stringify(layout)); } catch (e) { /* storage refused */ }
  }

  function clamp(value, low, high) { return Math.max(low, Math.min(high, value)); }

  /* ---- dialogs ------------------------------------------------------------------------- */

  function freeze(dialog) {
    /* Leave flex centring: from here on the dialog owns its own coordinates. */
    var box = dialog.getBoundingClientRect();
    dialog.style.position = "absolute";
    dialog.style.margin = "0";
    dialog.style.left = box.left + "px";
    dialog.style.top = box.top + "px";
    dialog.dataset.free = "1";
  }

  function keepInside(dialog) {
    var left = parseFloat(dialog.style.left) || 0;
    var top = parseFloat(dialog.style.top) || 0;
    var width = dialog.offsetWidth;
    var height = dialog.offsetHeight;
    /* The title bar must stay reachable, and so must the buttons at the foot: a dialog that
       fills in after it opened (the preferences read the server first) grows downward, and
       would otherwise leave its Close button below the visible page. */
    dialog.style.left = clamp(left, 40 - width, window.innerWidth - 40) + "px";
    dialog.style.top = clamp(top, 0, Math.max(0, window.innerHeight - height - 4)) + "px";
  }

  function arrange(modal) {
    var dialog = modal.querySelector(".dialog");
    if (!dialog) { return; }
    var saved = layout["dialog:" + modal.id];
    dialog.style.position = "";
    dialog.style.margin = "";
    dialog.style.left = "";
    dialog.style.top = "";
    dialog.style.width = dialog.dataset.width || "";
    dialog.style.height = dialog.dataset.height || "";
    delete dialog.dataset.free;
    if (saved) {
      if (saved.width) { dialog.style.width = clamp(saved.width, 260, window.innerWidth - 8) + "px"; }
      if (saved.height) { dialog.style.height = clamp(saved.height, 120, window.innerHeight - 8) + "px"; }
    }
    freeze(dialog);
    if (saved && typeof saved.left === "number") {
      dialog.style.left = saved.left + "px";
      dialog.style.top = saved.top + "px";
    }
    keepInside(dialog);
  }

  function remember(modal) {
    var dialog = modal.querySelector(".dialog");
    if (!dialog || !dialog.dataset.free) { return; }
    layout["dialog:" + modal.id] = {
      left: parseFloat(dialog.style.left) || 0, top: parseFloat(dialog.style.top) || 0,
      width: dialog.offsetWidth, height: dialog.offsetHeight
    };
    save();
  }

  function wireDialog(modal) {
    var dialog = modal.querySelector(".dialog");
    var title = dialog && dialog.querySelector("h3");
    if (!dialog || !title || modal.dataset.windowed) { return; }
    modal.dataset.windowed = "1";
    /* What the page asked for (an inline width) is the size a reset returns to. */
    dialog.dataset.width = dialog.style.width;
    dialog.dataset.height = dialog.style.height;
    dialog.classList.add("window");
    title.classList.add("grab");

    var dragging = false;
    title.addEventListener("pointerdown", function (event) {
      if (event.button !== 0 || event.target.closest("button, input, select, a")) { return; }
      if (!dialog.dataset.free) { freeze(dialog); }
      dragging = true;
      var startX = event.clientX, startY = event.clientY;
      var originX = parseFloat(dialog.style.left) || 0, originY = parseFloat(dialog.style.top) || 0;
      title.setPointerCapture(event.pointerId);
      function move(e) {
        dialog.style.left = originX + e.clientX - startX + "px";
        dialog.style.top = originY + e.clientY - startY + "px";
        keepInside(dialog);
      }
      function stop() {
        dragging = false;
        title.removeEventListener("pointermove", move);
        title.removeEventListener("pointerup", stop);
        title.removeEventListener("pointercancel", stop);
        remember(modal);
      }
      title.addEventListener("pointermove", move);
      title.addEventListener("pointerup", stop);
      title.addEventListener("pointercancel", stop);
      event.preventDefault();
    });

    /* Resize comes from the browser's own corner handle (CSS `resize`); its end is noticed here. */
    dialog.addEventListener("pointerup", function () { remember(modal); });

    /* Content that arrives after the dialog opened changes its height: keep it in view. */
    if (window.ResizeObserver) {
      new ResizeObserver(function () {
        if (modal.classList.contains("show") && dialog.dataset.free && !dragging) { keepInside(dialog); }
      }).observe(dialog);
    }

    new MutationObserver(function () {
      if (modal.classList.contains("show")) {
        window.requestAnimationFrame(function () { arrange(modal); });
      }
    }).observe(modal, { attributes: true, attributeFilter: ["class"] });
  }

  /* ---- splitters ----------------------------------------------------------------------- */

  function splitter(kind, before, after, apply, read, limits) {
    var bar = document.createElement("div");
    bar.className = "splitter " + kind;
    bar.setAttribute("role", "separator");
    bar.setAttribute("aria-orientation", kind === "vsplit" ? "vertical" : "horizontal");
    bar.title = "Drag to resize · double-click to reset";
    after.parentNode.insertBefore(bar, after);

    bar.addEventListener("pointerdown", function (event) {
      if (event.button !== 0) { return; }
      var start = kind === "vsplit" ? event.clientX : event.clientY;
      var origin = read();
      var zoom = parseFloat(window.getComputedStyle(document.querySelector(".app") || document.body).zoom) || 1;
      bar.setPointerCapture(event.pointerId);
      bar.classList.add("drag");
      function move(e) {
        var delta = ((kind === "vsplit" ? e.clientX : e.clientY) - start) / zoom;
        apply(clamp(origin + (kind === "vsplit" ? -delta : -delta), limits[0], limits[1]()));
      }
      function stop() {
        bar.removeEventListener("pointermove", move);
        bar.removeEventListener("pointerup", stop);
        bar.removeEventListener("pointercancel", stop);
        bar.classList.remove("drag");
      }
      bar.addEventListener("pointermove", move);
      bar.addEventListener("pointerup", stop);
      bar.addEventListener("pointercancel", stop);
      event.preventDefault();
    });
    bar.addEventListener("dblclick", function () { apply(null); });
    return bar;
  }

  function wireSplitters() {
    var tree = document.getElementById("artifacts");
    var pane = document.querySelector(".work > .pane");
    if (tree && pane && !document.querySelector(".splitter.vsplit")) {
      var applyTree = function (width) {
        if (width === null) { delete layout.tree; tree.style.flex = ""; tree.style.width = ""; }
        else { layout.tree = width; tree.style.flex = "0 0 " + width + "px"; tree.style.width = width + "px"; }
        save();
      };
      if (layout.tree) { applyTree(layout.tree); }
      splitter("vsplit", pane, tree, applyTree, function () { return tree.offsetWidth; },
               [120, function () { return Math.max(160, document.body.clientWidth * 0.6); }]);
    }
    var details = document.getElementById("details");
    var grid = document.querySelector(".gridwrap");
    if (details && grid && !document.querySelector(".splitter.hsplit")) {
      var applyDetails = function (height) {
        if (height === null) { delete layout.details; details.style.flex = ""; details.style.height = ""; }
        else { layout.details = height; details.style.flex = "0 0 " + height + "px"; details.style.height = height + "px"; }
        save();
      };
      if (layout.details) { applyDetails(layout.details); }
      splitter("hsplit", grid, details, applyDetails, function () { return details.offsetHeight; },
               [40, function () { return Math.max(80, document.body.clientHeight * 0.7); }]);
    }
  }

  function start() {
    Array.prototype.forEach.call(document.querySelectorAll(".modal"), wireDialog);
    wireSplitters();
  }

  if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", start); }
  else { start(); }
  window.FirebladeWindows = { arrange: arrange, reset: function () { layout = {}; save(); } };
})();
