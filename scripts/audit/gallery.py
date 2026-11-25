"""A tour of the Host: every menu entry, tab and window, photographed and linted.

The tour opens a case in a real browser, presses every command of every menu, every tab, every
toolbar button and the cell menu, and for each state it

* saves a screenshot (``<out>/NN-<name>.png``),
* lints the page: text cut off by its box, controls outside the window, controls on top of one
  another, controls with no name, duplicate ids, French words in the chrome, low contrast,
* records the console errors, the page errors and the requests the server refused.

The result is ``<out>/report.md`` and ``<out>/findings.json``. It is a tool for a person with
eyes: the lints find what a program can see, the screenshots are for the rest.

    python -m scripts.audit.gallery --url http://127.0.0.1:8080 --case "My case" --out shots/
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

LINT = r"""
() => {
  const out = [];
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none" &&
      parseFloat(s.opacity || "1") > 0.05;
  };
  const name = (el) => {
    const t = (el.innerText || el.value || el.getAttribute("title") || el.getAttribute("aria-label") || "").trim().replace(/\s+/g, " ");
    return (el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") + (t ? " “" + t.slice(0, 40) + "”" : ""));
  };
  // The part of the page a person is looking at: the open window, else the whole page.
  const modal = document.querySelector(".modal.show .dialog");
  const root = modal || document.body;
  const inside = (el) => root.contains(el);
  const controls = [...document.querySelectorAll("button, a[href], input:not([type=hidden]), select, textarea, [data-act]")]
    .filter((el) => visible(el) && inside(el));
  // 1. controls outside the window
  for (const el of controls) {
    const r = el.getBoundingClientRect();
    if (r.right > innerWidth + 1 || r.bottom > innerHeight + 1 || r.left < -1 || r.top < -1) {
      // a control inside a scrolling box is reached by scrolling: only flag the unscrollable
      let scroller = el.parentElement, scrolls = false;
      while (scroller && scroller !== document.body) {
        const s = getComputedStyle(scroller);
        if (/(auto|scroll)/.test(s.overflowY + s.overflowX) && scroller.scrollHeight > scroller.clientHeight) { scrolls = true; break; }
        scroller = scroller.parentElement;
      }
      if (!scrolls) out.push({kind: "outside the window", what: name(el)});
    }
  }
  // 2. text cut off by its own box (a clipped label, not a scrolling table)
  for (const el of root.querySelectorAll("button, label, h3, h2, .tb, .item, .tab, .node, th, option, .btn, .info, .note")) {
    if (!visible(el)) continue;
    const s = getComputedStyle(el);
    if ((s.overflow === "hidden" || s.textOverflow === "ellipsis") && el.scrollWidth > el.clientWidth + 2 && (el.innerText || "").trim().length > 3) {
      out.push({kind: "text cut off", what: name(el)});
    }
  }
  // 3. controls on top of one another
  const boxes = controls.map((el) => [el, el.getBoundingClientRect()]);
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const [a, ra] = boxes[i], [b, rb] = boxes[j];
    if (a.contains(b) || b.contains(a)) continue;
    const w = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left);
    const h = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
    if (w > 4 && h > 4 && w * h > 0.3 * Math.min(ra.width * ra.height, rb.width * rb.height)) {
      out.push({kind: "controls overlap", what: name(a) + "  ×  " + name(b)});
    }
  }
  // 4. controls with no name at all
  for (const el of controls) {
    if (el.matches("input[type=checkbox], input[type=radio]")) {
      const labelled = el.closest("label") || (el.id && document.querySelector('label[for="' + el.id + '"]')) || el.title || el.getAttribute("aria-label");
      if (!labelled) out.push({kind: "checkbox without a label", what: name(el)});
    } else if (el.matches("button, a")) {
      if (!(el.innerText || "").trim() && !el.title && !el.getAttribute("aria-label") && !el.querySelector("img, svg")) out.push({kind: "button without a name", what: name(el)});
    } else if (el.matches("input:not([type=file]), select, textarea")) {
      const labelled = el.closest("label") || (el.id && document.querySelector('label[for="' + el.id + '"]')) || el.placeholder || el.title || el.getAttribute("aria-label");
      if (!labelled) out.push({kind: "field without a label", what: name(el)});
    }
  }
  // 5. French in the chrome (the grid holds evidence and is left alone)
  const french = /[àâäçéèêëîïôöùûüÿœæ]|\b(le|la|les|des|une|un|pour|avec|sans|dans|vous|votre|aucun|aucune|fichier|dossier|ouvrir|enregistrer|annuler|fermer|chercher|rechercher|affichage|préférences)\b/i;
  const chrome = modal ? [modal] : [...document.querySelectorAll(".menubar, .toolbar, .tabs, .menu.show, .filterbar, .panel-title, .statusbar, #tree, #row-menu")];
  for (const box of chrome) {
    const walker = document.createTreeWalker(box, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const text = n.nodeValue.trim();
      const el = n.parentElement;
      if (!text || !visible(el) || el.closest("#body, #head, #hayabusa-rows, #timeline-rows, #ioc-rows, #imports-rows, textarea, pre, code, #tree .node.child, #pane-tabs")) continue;
      if (french.test(text)) out.push({kind: "French text", what: name(el) + " — " + text.slice(0, 60)});
    }
  }
  // 6. duplicate ids and labels pointing nowhere
  const ids = {};
  for (const el of document.querySelectorAll("[id]")) ids[el.id] = (ids[el.id] || 0) + 1;
  for (const [id, count] of Object.entries(ids)) if (count > 1) out.push({kind: "duplicate id", what: "#" + id + " ×" + count});
  for (const l of document.querySelectorAll("label[for]")) if (!document.getElementById(l.getAttribute("for"))) out.push({kind: "label for a missing id", what: l.getAttribute("for")});
  // 7. low contrast text (WCAG ratio under 3: unreadable for many)
  const lum = (c) => { const [r, g, b] = c.map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const parse = (s) => { const m = s.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(",").map(Number); return {c: p.slice(0, 3), a: p.length > 3 ? p[3] : 1}; };
  const backdrop = (el) => { for (let n = el; n; n = n.parentElement) { const b = parse(getComputedStyle(n).backgroundColor); if (b && b.a > 0.5) return b.c; } return [255, 255, 255]; };
  const seen = new Set();
  for (const el of root.querySelectorAll("button, label, h3, .tb, .item, .tab, .info, .note, th, td, span, div")) {
    if (!visible(el) || !inside(el)) continue;
    const own = [...el.childNodes].filter((n) => n.nodeType === 3 && n.nodeValue.trim().length > 2);
    if (!own.length) continue;
    const fg = parse(getComputedStyle(el).color); if (!fg) continue;
    const l1 = lum(fg.c) + 0.05, l2 = lum(backdrop(el)) + 0.05;
    const ratio = Math.max(l1, l2) / Math.min(l1, l2);
    const key = name(el);
    if (ratio < 3 && !seen.has(key) && !el.closest("#body, #head")) { seen.add(key); out.push({kind: "low contrast", what: key + " (" + ratio.toFixed(1) + ":1)"}); }
  }
  return out;
}
"""


class Tour:
    def __init__(self, page, out: Path):
        self.page = page
        self.out = out
        self.count = 0
        self.findings: list[dict] = []
        self.console: list[str] = []
        self.failed: list[str] = []
        self.page_errors: list[str] = []
        page.on("console", self._console)
        page.on("pageerror", lambda e: self.page_errors.append(str(e)))
        page.on("response", self._response)
        page.on("dialog", lambda d: d.accept())

    def _console(self, message):
        if message.type in ("error", "warning"):
            self.console.append(
                f"{message.type}: {message.text} @ {message.location.get('url', '')}"
            )

    def _response(self, response):
        if response.status >= 400 and "/api/" in response.url:
            self.failed.append(f"{response.status} {response.request.method} {response.url}")

    def shot(self, name: str, lint: bool = True) -> str:
        self.count += 1
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]
        file = f"{self.count:03d}-{slug}.png"
        self.page.wait_for_timeout(250)
        self.page.screenshot(path=str(self.out / file))
        if lint:
            try:
                for item in self.page.evaluate(LINT):
                    self.findings.append({"shot": file, "state": name, **item})
            except Exception as exc:  # noqa: BLE001 - a page mid-navigation
                self.findings.append(
                    {"shot": file, "state": name, "kind": "lint failed", "what": str(exc)[:100]}
                )
        return file

    def close_windows(self):
        self.page.keyboard.press("Escape")
        self.page.evaluate(
            "document.querySelectorAll('.modal.show').forEach(m => m.classList.remove('show'))"
        )
        self.page.evaluate(
            "document.querySelectorAll('.menu.show').forEach(m => m.classList.remove('show'))"
        )
        self.page.evaluate(
            "(() => { const r = document.getElementById('row-menu'); if (r) r.hidden = true; })()"
        )


SKIP = ("destroy-case", "close-case", "disk-open", "import-folder")


def run(url: str, case: str, out: Path, width: int, height: int, tabs_only: bool) -> Tour:
    from playwright.sync_api import sync_playwright

    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        import os

        browser = playwright.chromium.launch(
            executable_path=os.environ.get("FIREBLADE_CHROMIUM") or None
        )
        page = browser.new_page(viewport={"width": width, "height": height}, accept_downloads=True)
        tour = Tour(page, out)
        page.goto(url.rstrip("/") + "/")
        page.wait_for_selector("#menubar")
        page.wait_for_timeout(1200)
        tour.shot("start")
        page.click('.tabs .tab:text-is("Cases")')
        tour.shot("cases tab")
        page.dblclick(f'tr:has(td:text-is("{case}")) td >> nth=0')
        page.wait_for_selector("#body tr[data-row]", timeout=120000)
        page.wait_for_timeout(1500)
        tour.shot("case open")
        page.locator("#body tr[data-row]").first.locator("td[data-cell]").first.click()
        tour.shot("row selected")
        # the tabs
        for tab in page.eval_on_selector_all(
            ".tabs .tab", "els => els.map(e => e.innerText.trim())"
        ):
            page.click(f'.tabs .tab:text-is("{tab}")')
            page.wait_for_timeout(900)
            tour.shot(f"tab {tab}")
        page.click('.tabs .tab:text-is("Analyses")')
        # the cell menu and a header
        page.locator("#body tr[data-row]").first.locator("td[data-cell]").nth(1).click(
            button="right"
        )
        tour.shot("cell menu")
        tour.close_windows()
        if tabs_only:
            browser.close()
            return tour
        # every menu, every command
        menus = page.eval_on_selector_all(".menubar .m", "els => els.map(e => e.dataset.menu)")
        for menu in menus:
            page.click(f'.menubar .m[data-menu="{menu}"]')
            tour.shot(f"menu {menu}")
            acts = page.eval_on_selector_all(
                f'.menu[data-for="{menu}"] [data-act]',
                "els => els.map(e => [e.dataset.act, e.innerText.trim().split('\\n')[0]])",
            )
            tour.close_windows()
            for act, _label in acts:
                if act in SKIP:
                    continue
                page.click('.tabs .tab:text-is("Analyses")')
                page.click(f'.menubar .m[data-menu="{menu}"]')
                try:
                    page.click(f'.menu.show [data-act="{act}"]', timeout=3000)
                except Exception as exc:  # noqa: BLE001
                    tour.findings.append(
                        {
                            "shot": "",
                            "state": f"{menu}/{act}",
                            "kind": "command not pressable",
                            "what": str(exc)[:100],
                        }
                    )
                    tour.close_windows()
                    continue
                page.wait_for_timeout(900)
                tour.shot(f"{menu} {act}")
                tour.close_windows()
        browser.close()
    return tour


def write_report(tour: Tour, out: Path) -> None:
    (out / "findings.json").write_text(
        json.dumps(
            {
                "findings": tour.findings,
                "console": tour.console,
                "failed_requests": tour.failed,
                "page_errors": tour.page_errors,
            },
            indent=1,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    by_kind: dict[str, list[dict]] = {}
    for item in tour.findings:
        by_kind.setdefault(item["kind"], []).append(item)
    lines = [f"# Gallery report\n\n{tour.count} screenshots, {len(tour.findings)} lint findings.\n"]
    for kind, items in sorted(by_kind.items()):
        lines.append(f"\n## {kind} ({len(items)})\n")
        seen = set()
        for item in items:
            key = (item["what"], item["state"])
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"- `{item['shot']}` {item['state']}: {item['what']}")
    lines.append(f"\n## Console ({len(tour.console)})\n")
    lines += [f"- {text}" for text in sorted(set(tour.console))[:40]]
    lines.append(f"\n## Refused requests ({len(tour.failed)})\n")
    lines += [f"- {text}" for text in sorted(set(tour.failed))[:40]]
    lines.append(f"\n## Page errors ({len(tour.page_errors)})\n")
    lines += [f"- {text}" for text in tour.page_errors[:20]]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--url", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--width", type=int, default=1500)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--tabs-only", action="store_true", help="the tabs and the cell menu only")
    args = parser.parse_args(argv)
    out = Path(args.out)
    tour = run(args.url, args.case, out, args.width, args.height, args.tabs_only)
    write_report(tour, out)
    print(f"{tour.count} screenshots, {len(tour.findings)} findings -> {out / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
