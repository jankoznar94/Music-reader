#!/usr/bin/env python3
"""Headless CDP harness for the noty-app PDF viewer (no Playwright / jsdom needed).

WHY: a change that is "in the bundle" is not a change that works. Drive the real dev
server once and assert on real DOM state before reporting the work as done.

SETUP (one-time, WSL)
    # Chrome installed by `agent-browser install` lives under ~/.agent-browser/browsers
    # and needs the bundled NSS libs on the loader path:
    export LD_LIBRARY_PATH="$HOME/.agent-browser/lib:$LD_LIBRARY_PATH"
    export CHROME_BIN=$(ls -d "$HOME"/.agent-browser/browsers/chrome-*/chrome | head -1)
    "$CHROME_BIN" --version          # must print a version before going further

RUN IT (both in the background)
    "$CHROME_BIN" --headless=new --disable-gpu --no-sandbox \
        --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-noty about:blank
    (cd ~/noty-app && npx vite --port 5173 --strictPort)

THEN
    python3 scripts/cdp-e2e-harness.py    # smoke (page entry) + nav_gestures()

Traps this file encodes:
  * SET THE VIEWPORT FIRST. The default headless window is ~780x437, shorter than the page
    area needs, so the annotation panel ends up over the canvas CENTRE and every mid-canvas
    tap silently hits the panel instead of the score (a phantom "pen doesn't draw" FAIL).
  * Find interaction points with document.elementFromPoint over a small grid - never from
    the element's own getBoundingClientRect().
  * The annotation layer is pointer-events:none while annotation mode is OFF, so probing for
    .annot-layer returns null. Toggle annotation mode ON before looking for a drawing point.
  * A pen stroke needs press + mouseMoved + release, all pointerType="pen".
  * The library opens with every author group COLLAPSED - no `li.song` node exists until an
    `.author-header` is clicked. Expand first (expand_authors_js).
  * Upload through `DOM.setFileInputFiles`, then WAIT for the app's own DOM change (a
    `.author-group` appearing). The call returns an empty `{}` either way.
  * Open the piece by clicking `.song-name`; the row's action buttons are separate controls.
  * Chrome DOES deliver synthetic touch radiusX/radiusY faithfully (verified: 70 and 12 both
    arrived). If a radius-based feature fails here it is a real bug, not a harness artifact -
    log e.touches[0].radiusX in the page before doubting the test.

Input API choice (the difference between a real test and a fake failure):
  finger  -> Input.dispatchTouchEvent     (emits genuine touch AND pointer events)
  stylus  -> Input.dispatchMouseEvent with pointerType="pen"  (a stylus emits no touch events)
  mouse   -> blocked by the default-on pen-only filter; reports `mouse` and draws nothing
"""

import asyncio
import json
import time
import urllib.request

import websockets

CDP_HTTP = "http://127.0.0.1:9222"
APP_URL = "http://localhost:5173/"
FIXTURE = "/tmp/noty-fixture.pdf"


class Check:
    """Collects pass/fail lines so one run reports every assertion, not just the first."""

    def __init__(self):
        self.failures = []

    def __call__(self, label, ok, detail=""):
        print(f"{'OK  ' if ok else 'FAIL'} {label} {detail}")
        if not ok:
            self.failures.append(f"{label} {detail}")

    def report(self):
        print()
        if self.failures:
            print("FAILURES:")
            for f in self.failures:
                print(" -", f)
            return 1
        print("ALL CHECKS PASSED")
        return 0


def make_pdf(pages=6, path=FIXTURE):
    """Minimal valid multi-page PDF with one line of text per page (stdlib only).

    A generated fixture beats asking Jan for a file: reproducible, tiny, and it lets the
    smoke test assert an exact page count ("1 / 6").
    """
    objs = ["<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + i} 0 R" for i in range(pages))
    objs.append(f"<< /Type /Pages /Count {pages} /Kids [{kids}] >>")
    for i in range(pages):
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Contents {3 + pages + i} 0 R "
            f"/Resources << /Font << /F1 {3 + 2 * pages} 0 R >> >> >>"
        )
    for i in range(pages):
        stream = f"BT /F1 36 Tf 60 750 Td (Stranka {i + 1} z {pages}) Tj ET"
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out, offsets = "%PDF-1.4\n", []
    for i, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n"
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n")
    with open(path, "w", encoding="latin-1") as fh:
        fh.write(out)
    return path


class Harness:
    """Minimal CDP client + viewer helpers (context manager).

    Selectors reflect the CURRENT app: `.song-name` opens the piece, `.tb-page` is the
    top-bar page counter, the page dialog uses `.pg-input` / `.pg-btn.primary`.
    """

    def __init__(self, url=APP_URL):
        self.url = url
        self._id = 0
        self.ws = None

    async def __aenter__(self):
        pages = json.loads(urllib.request.urlopen(f"{CDP_HTTP}/json/list").read())
        page = next(p for p in pages if p["type"] == "page")
        self.ws = await websockets.connect(page["webSocketDebuggerUrl"], max_size=64 * 1024 * 1024)
        for domain in ("Runtime.enable", "DOM.enable", "Page.enable"):
            await self.cdp(domain)
        return self

    async def __aexit__(self, *exc):
        await self.ws.close()

    async def cdp(self, method, params=None):
        self._id += 1
        await self.ws.send(json.dumps({"id": self._id, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    async def ev(self, expr, await_promise=False):
        res = await self.cdp("Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": await_promise})
        if "exceptionDetails" in res:
            raise RuntimeError("JS: " + json.dumps(res["exceptionDetails"])[:300])
        return res.get("result", {}).get("value")

    async def wait_for(self, expr, timeout=30, label=""):
        start = time.time()
        while time.time() - start < timeout:
            try:
                if await self.ev(expr):
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.4)
        raise TimeoutError(f"timeout: {label or expr}")

    async def open(self):
        await self.cdp("Page.navigate", {"url": self.url})
        await self.wait_for("document.readyState === 'complete'", label="app load")
        await asyncio.sleep(1.0)

    async def set_tablet(self, w=800, h=1280, dsf=2):
        """Tablet-ish portrait viewport. MUST be called before asserting anything:
        at the default headless size the annotation panel covers the canvas centre."""
        await self.cdp("Emulation.setDeviceMetricsOverride",
                       {"width": w, "height": h, "deviceScaleFactor": dsf, "mobile": True})
        await asyncio.sleep(0.8)

    async def reset_db(self):
        """Fresh IndexedDB so a run is repeatable (otherwise old songs skew the asserts)."""
        await self.ev("indexedDB.deleteDatabase('noty-app')")
        await asyncio.sleep(0.8)
        await self.open()

    async def set_file_input(self, selector, path):
        doc = await self.cdp("DOM.getDocument")
        node = await self.cdp("DOM.querySelector",
                              {"nodeId": doc["root"]["nodeId"], "selector": selector})
        await self.cdp("DOM.setFileInputFiles", {"files": [path], "nodeId": node["nodeId"]})

    async def set_value(self, selector, value):
        """Set an input and fire a bubbling `input` event (what v-model listens for)."""
        return await self.ev(
            "(() => { const el = document.querySelector(%s); if (!el) return 'missing';"
            " el.value = %s; el.dispatchEvent(new Event('input', { bubbles: true }));"
            " return el.value; })()" % (json.dumps(selector), json.dumps(value)))

    async def click(self, selector):
        return await self.ev(
            "(() => { const el = document.querySelector(%s); if (!el) return 'missing';"
            " el.click(); return 'ok'; })()" % json.dumps(selector))

    async def canvas_len(self, selector="canvas.pdf-canvas"):
        return await self.ev(f"document.querySelector({json.dumps(selector)}).toDataURL().length")

    @staticmethod
    def expand_authors_js():
        """Author groups start collapsed - song rows only exist after a header click."""
        return ("(() => { document.querySelectorAll('.author-header')"
                ".forEach(h => h.click()); return true; })()")

    # --- navigation through the app's own UI ---------------------------------
    async def open_song(self, pdf=None, pages=6, reset=True):
        pdf = pdf or make_pdf(pages)
        if reset:
            await self.reset_db()
        await self.set_tablet()
        await self.set_file_input("input[type=file]", pdf)
        await self.wait_for("document.querySelectorAll('.author-group').length > 0",
                            timeout=60, label="PDF upload")
        await self.ev(self.expand_authors_js())
        await self.wait_for("document.querySelectorAll('li.song').length > 0",
                            timeout=10, label="expand authors")
        await self.click(".song-name")   # NOT the row and NOT its action buttons
        await self.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="open viewer")
        await self.wait_for("!document.querySelector('.viewer-loading')", timeout=40, label="first page")
        await asyncio.sleep(1.0)

    async def page_text(self):
        return await self.ev("document.querySelector('.tb-page').textContent.trim()")

    async def goto(self, n):
        await self.click(".tb-page")
        await self.wait_for("!!document.querySelector('.pg-input')", timeout=5, label="page dialog")
        await self.set_value(".pg-input", str(n))
        await self.click(".pg-btn.primary")
        await asyncio.sleep(1.0)

    async def annot_toggle(self):
        await self.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                      ".find(x => (x.title || '').startsWith('Anotace')); if (b) b.click(); })()")
        await asyncio.sleep(0.5)

    # --- geometry probes -----------------------------------------------------
    async def geo(self):
        return await self.ev(
            "(() => { const v = document.querySelector('.viewer').getBoundingClientRect();"
            " const bar = document.querySelector('.top-bar').getBoundingClientRect();"
            " return {w: v.width, h: v.height, left: v.left, top: v.top, barBottom: bar.bottom}; })()")

    async def free_point(self, x_lo=0.3, x_hi=0.7):
        """A point that provably hits the annotation layer (not a panel).
        Require annotation mode ON first - the layer is pointer-events:none otherwise."""
        xs = [x_lo + (x_hi - x_lo) * i / 6 for i in range(7)]
        ys = [0.4 + 0.5 * i / 6 for i in range(7)]
        return await self.ev(
            "(() => { const v = document.querySelector('.viewer').getBoundingClientRect();"
            " const xs = %s, ys = %s;"
            " for (const fy of ys) { const y = v.top + v.height * fy;"
            "   for (const fx of xs) { const x = v.left + v.width * fx;"
            "     const el = document.elementFromPoint(x, y);"
            "     if (el && el.classList && el.classList.contains('annot-layer'))"
            "       return {x, y}; } }"
            " return null; })()" % (json.dumps(xs), json.dumps(ys)))

    # --- real input events ---------------------------------------------------
    async def touch(self, kind, points):
        """points: [(x, y, radius)] - radius is delivered faithfully by Chrome."""
        tp = [{"x": x, "y": y, "id": i, "radiusX": r, "radiusY": r, "force": 1.0}
              for i, (x, y, r) in enumerate(points)]
        await self.cdp("Input.dispatchTouchEvent", {"type": kind, "touchPoints": tp})

    async def finger_tap(self, x, y, r=12):
        await self.touch("touchStart", [(x, y, r)])
        await asyncio.sleep(0.06)
        await self.touch("touchEnd", [])
        await asyncio.sleep(0.7)

    async def palm_tap(self, x, y, r=70):
        await self.touch("touchStart", [(x, y, r)])
        await asyncio.sleep(0.1)
        await self.touch("touchEnd", [])
        await asyncio.sleep(0.7)

    async def finger_swipe(self, x0, y0, x1, y1, r=12, steps=8):
        await self.touch("touchStart", [(x0, y0, r)])
        for i in range(1, steps + 1):
            await self.touch("touchMove", [(x0 + (x1 - x0) * i / steps,
                                            y0 + (y1 - y0) * i / steps, r)])
            await asyncio.sleep(0.015)
        await self.touch("touchEnd", [])
        await asyncio.sleep(0.9)

    async def pen_down(self, x, y):
        await self.cdp("Input.dispatchMouseEvent",
                       {"type": "mousePressed", "x": x, "y": y, "button": "left",
                        "clickCount": 1, "pointerType": "pen"})

    async def pen_move(self, x, y):
        await self.cdp("Input.dispatchMouseEvent",
                       {"type": "mouseMoved", "x": x, "y": y, "button": "left",
                        "buttons": 1, "pointerType": "pen"})

    async def pen_up(self, x, y):
        await self.cdp("Input.dispatchMouseEvent",
                       {"type": "mouseReleased", "x": x, "y": y, "button": "left",
                        "clickCount": 1, "pointerType": "pen"})

    async def pen_tap(self, x, y):
        await self.pen_down(x, y)
        await self.pen_up(x, y)
        await asyncio.sleep(0.5)

    async def pen_stroke(self, x0, y0, x1, y1, steps=10):
        """press + moves + release: a press/release pair alone emits no pointermove
        and nothing draws."""
        await self.pen_down(x0, y0)
        for i in range(1, steps + 1):
            await self.pen_move(x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps)
            await asyncio.sleep(0.02)
        await self.pen_up(x1, y1)
        await asyncio.sleep(0.7)


async def open_first_song(h, pdf=FIXTURE, pages=6, expand=True):
    """Back-compat wrapper: upload a fixture, expand the author group, open the piece."""
    await h.open_song(pdf=pdf, pages=pages)


async def smoke():
    """Upload a 6-page fixture, open it, then exercise the manual page-number entry."""
    pdf = make_pdf(6)
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf)

        ind = await h.page_text()
        ok("page indicator starts at 1 / 6", ind == "1 / 6", ind)

        await h.goto(5)
        ok("typed page 5 jumps", (await h.page_text()) == "5 / 6", await h.page_text())

        await h.click(".tb-page")
        await asyncio.sleep(0.3)
        await h.set_value(".pg-input", "99")
        await h.click(".pg-btn.primary")
        await asyncio.sleep(0.9)
        clamped = await h.page_text()
        ok("99 clamps to the last page", clamped == "6 / 6", clamped)

        await h.click(".tb-page")
        await asyncio.sleep(0.3)
        await h.set_value(".pg-input", "abc")
        await h.click(".pg-btn.primary")
        await asyncio.sleep(0.9)
        ok("junk input leaves the page alone", (await h.page_text()) == clamped, await h.page_text())

    return ok.report()


async def nav_gestures():
    """The page-turn contract: pen annotates, finger pages, and only at the edges.

    Run after ANY change to the viewer's touch/pointer handlers.
    """
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pages=6)

        g = await h.geo()
        left_x = g["left"] + 25
        right_x = g["left"] + g["w"] - 25
        y = g["barBottom"] + 200
        mid_x = g["left"] + g["w"] / 2

        # annotation mode: the layer only takes hits when it is active
        await h.annot_toggle()
        ok("annotation mode opens", bool(await h.ev("!!document.querySelector('.annot-panel')")))
        free = await h.free_point()
        ok("found a canvas point to draw on", bool(free), str(free))
        if not free:
            return ok.report()

        p0 = await h.ev("document.querySelectorAll('.annot-layer path').length")
        page0 = await h.page_text()
        await h.pen_stroke(free["x"] - 40, free["y"] - 20, free["x"] + 40, free["y"] + 20)
        p1 = await h.ev("document.querySelectorAll('.annot-layer path').length")
        ok("pen draws a stroke", p1 > p0, f"paths {p0}->{p1}")
        ok("pen stroke does not turn the page", page0 == await h.page_text(), page0)

        await h.pen_tap(left_x, free["y"])
        ok("pen tap in the edge band does not turn the page",
           page0 == await h.page_text(), await h.page_text())

        await h.finger_tap(free["x"], free["y"])
        ok("finger tap on the score does not turn the page (annotation on)",
           page0 == await h.page_text(), await h.page_text())

        await h.palm_tap(left_x + 10, free["y"])
        ok("palm tap in the edge band does not turn the page (annotation on)",
           page0 == await h.page_text(), await h.page_text())

        # reading mode
        await h.annot_toggle()
        await h.goto(3)
        ok("starts at 3 / 6 for the edge tests", (await h.page_text()) == "3 / 6",
           await h.page_text())

        await h.finger_tap(left_x, y)
        ok("finger tap on the LEFT edge -> previous page", (await h.page_text()) == "2 / 6",
           await h.page_text())

        await h.finger_tap(right_x, y)
        ok("finger tap on the RIGHT edge -> next page", (await h.page_text()) == "3 / 6",
           await h.page_text())

        before = await h.page_text()
        await h.finger_tap(mid_x, y)
        ok("finger tap mid-canvas does not turn the page", before == await h.page_text())

        before = await h.page_text()
        await h.finger_swipe(right_x - 5, y, right_x - 150, y)
        ok("finger swipe started on the edge turns the page", before != await h.page_text(),
           f"{before} -> {await h.page_text()}")

        before = await h.page_text()
        await h.finger_swipe(mid_x, y, mid_x - 150, y)
        ok("finger swipe started at the centre does NOT turn the page",
           before == await h.page_text(), before)

        before = await h.page_text()
        await h.palm_tap(left_x + 10, y)
        ok("palm tap in the edge band does not turn the page (reading)",
           before == await h.page_text(), before)

        ok("edge hint strips show while reading",
           (await h.ev("document.querySelectorAll('.edge-hint').length")) == 2)
        await h.annot_toggle()
        ok("edge hint strips hide in annotation mode",
           (await h.ev("document.querySelectorAll('.edge-hint').length")) == 0)

    return ok.report()


if __name__ == "__main__":
    async def main():
        rc = await smoke()
        rc |= await nav_gestures()
        return rc

    try:
        raise SystemExit(asyncio.run(main()))
    except (ConnectionRefusedError, OSError) as exc:
        raise SystemExit(
            f"Could not reach Chrome on {CDP_HTTP} ({exc}).\n"
            "Start it with --remote-debugging-port=9222 (see this file's docstring), "
            "set LD_LIBRARY_PATH to ~/.agent-browser/lib, and run the vite dev server on 5173."
        )
