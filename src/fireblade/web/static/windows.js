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
    var box = dialog.getBoundingClientRect();
    /* offsetHeight rounds fractional text metrics and can put the footer outside the viewport. */
    dialog.style.left = clamp(left, 0, window.innerWidth - Math.ceil(box.width)) + "px";
    dialog.style.top = clamp(top, 0, window.innerHeight - Math.ceil(box.height)) + "px";
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

  function remember(modal, resized) {
    var dialog = modal.querySelector(".dialog");
    if (!dialog || !dialog.dataset.free) { return; }
    var saved = layout["dialog:" + modal.id] || {};
    saved.left = parseFloat(dialog.style.left) || 0;
    saved.top = parseFloat(dialog.style.top) || 0;
    if (resized) {
      saved.width = dialog.offsetWidth;
      saved.height = dialog.offsetHeight;
    }
    layout["dialog:" + modal.id] = saved;
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
        if (originX !== dialog.offsetLeft || originY !== dialog.offsetTop) { remember(modal, false); }
      }
      title.addEventListener("pointermove", move);
      title.addEventListener("pointerup", stop);
      title.addEventListener("pointercancel", stop);
      event.preventDefault();
    });

    /* Resize comes from the browser's own corner handle (CSS `resize`); its end is noticed here. */
    var initialSize = null;
    dialog.addEventListener("pointerdown", function (event) {
      initialSize = event.target === dialog ? [dialog.offsetWidth, dialog.offsetHeight] : null;
    });
    dialog.addEventListener("pointerup", function () {
      if (initialSize && (dialog.offsetWidth !== initialSize[0] || dialog.offsetHeight !== initialSize[1])) {
        remember(modal, true);
      }
      initialSize = null;
    });

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

  function splitter(kind, panel, apply, read, limits) {
    var bar = document.createElement("div");
    bar.className = "splitter " + kind;
    bar.setAttribute("role", "separator");
    bar.setAttribute("aria-orientation", kind === "vsplit" ? "vertical" : "horizontal");
    bar.title = "Drag to resize · double-click to reset";
    panel.parentNode.insertBefore(bar, panel);

    bar.addEventListener("pointerdown", function (event) {
      if (event.button !== 0) { return; }
      var vertical = kind === "vsplit";
      var axis = vertical ? "left" : "top";
      var start = vertical ? event.clientX : event.clientY;
      var origin = read();
      var direction = panel.getBoundingClientRect()[axis] < bar.getBoundingClientRect()[axis] ? 1 : -1;
      var zoom = parseFloat(window.getComputedStyle(document.querySelector(".app") || document.body).zoom) || 1;
      bar.setPointerCapture(event.pointerId);
      bar.classList.add("drag");
      function move(e) {
        var delta = ((vertical ? e.clientX : e.clientY) - start) / zoom;
        apply(clamp(origin + direction * delta, limits[0], limits[1]()));
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
      splitter("vsplit", tree, applyTree, function () { return tree.offsetWidth; },
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
      splitter("hsplit", details, applyDetails, function () { return details.offsetHeight; },
               [40, function () { return Math.max(80, document.body.clientHeight * 0.7); }]);
    }
  }

  function start() {
    Array.prototype.forEach.call(document.querySelectorAll(".modal"), wireDialog);
    window.addEventListener("resize", function () {
      document.querySelectorAll(".modal.show .dialog[data-free]").forEach(keepInside);
    });
    wireSplitters();
  }

  if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", start); }
  else { start(); }
  window.FirebladeWindows = { arrange: arrange, reset: function () { layout = {}; save(); } };
})();
