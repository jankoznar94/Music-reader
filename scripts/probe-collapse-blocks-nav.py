#!/usr/bin/env python3
"""Sonda: zasekne listování SBALENÍ anotačního panelu šipkou? (Jan, Oct 2026)

Jan: „Mám trochu pocit, že se to stane po tom, co menu anotace minimalizuji
pomocí šipky."

`.ap-collapse` (šipka v hlavičce panelu) leží v LEVÉ OKRAJOVÉ ZÓNĚ (panel je
left:16px, šířka ≥220px) — tedy přesně tam, kde se listuje. Sonda zopakuje
sbalení/rozbalení prstem i perem a po každé zkusí listovat oběma směry, se
stavovým oknem `window.__navdbg()`.

    scripts/run-probe-fresh.sh scripts/probe-collapse-blocks-nav.py
"""
import asyncio
import importlib.util
import json
import os
import urllib.request

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
ANNOT = "Anotace / listování"
DBG = "JSON.stringify(window.__navdbg ? window.__navdbg() : null)"


def _load_harness():
    for cand in (
        os.path.expanduser("~/noty-app/cdp-e2e-harness.py"),
        "/home/martin_fabian/noty-app/cdp-e2e-harness.py",
    ):
        if os.path.exists(cand):
            spec = importlib.util.spec_from_file_location("cdp_e2e_harness", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise SystemExit("nenalezen cdp-e2e-harness.py")


_m = _load_harness()
_m.CDP_HTTP = CDP
Harness = _m.Harness

GEO = ("(() => { const r = document.querySelector('.stage.backdrop').getBoundingClientRect();"
       " return { left: r.left, top: r.top, width: r.width, height: r.height }; })()")

PANEL = r"""
(() => {
  const p = document.querySelector('.annot-panel');
  if (!p) return { panel: false };
  const r = p.getBoundingClientRect();
  const b = p.querySelector('.ap-collapse');
  const rb = b ? b.getBoundingClientRect() : null;
  const v = document.querySelector('.viewer').getBoundingClientRect();
  return {
    panel: true,
    rect: { top:+r.top.toFixed(0), bottom:+r.bottom.toFixed(0), left:+r.left.toFixed(0), right:+r.right.toFixed(0), h:+r.height.toFixed(0) },
    collapseBtn: rb ? { cx:+(rb.left+rb.width/2).toFixed(0), cy:+(rb.top+rb.height/2).toFixed(0), w:+rb.width.toFixed(0) } : null,
    collapseTitle: b ? b.getAttribute('title') : null,
    inLeftEdge: rb ? (rb.left + rb.width/2) < v.left + 70 : null,
    toolCount: p.querySelectorAll('.ap-tool').length,
  };
})()
"""

TOOLBAR = ("(() => { const p = document.querySelector('.annot-panel');"
           " return p ? p.querySelectorAll('.ap-tool').length : -1; })()")


async def fresh_harness():
    req = urllib.request.Request(f"{CDP}/json/new?about:blank", method="PUT")
    info = json.loads(urllib.request.urlopen(req).read())
    await asyncio.sleep(0.8)
    h = Harness(_m.APP_URL)
    h._fresh_target = info.get("id")
    return h


async def dbg(h):
    raw = await h.ev(DBG)
    return json.loads(raw) if raw else None


async def page(h):
    t = await h.ev("document.querySelector('.tb-page').textContent.trim()")
    l, r = t.split("/")
    return int(l.split(" ")[0].strip()), int(r.strip().split(" ")[0])


async def swipe(h, direction):
    g = await h.ev(GEO)
    y = g["top"] + g["height"] * 0.5
    if direction > 0:
        x0, x1 = g["left"] + g["width"] - 18, g["left"] + g["width"] * 0.55
    else:
        x0, x1 = g["left"] + 18, g["left"] + g["width"] * 0.45
    b = (await page(h))[0]
    await h.finger_swipe(x0, y, x1, y, r=12, steps=10)
    await asyncio.sleep(1.0)
    return b, (await page(h))[0]


async def both_dirs(h):
    """Zkusí otočit tam, kam to jde. Vrátí True/False + popis."""
    cur, tot = await page(h)
    d = 1 if cur < tot else -1
    b, a = await swipe(h, d)
    if b != a:
        return True, "%s->%s (%s)" % (b, a, "vpřed" if d > 0 else "zpět")
    # druhý pokus druhým směrem (kdyby byl první směr na konci dokumentu)
    b2, a2 = await swipe(h, -d)
    return (b2 != a2), "%s->%s (druhý směr %s)" % (b2, a2, "vpřed" if -d > 0 else "zpět")


async def tap_point(h, x, y, kind="finger"):
    if kind == "pen":
        await h.pen_tap(x, y)
    else:
        await h.finger_tap(x, y, r=12)
    await asyncio.sleep(0.8)


async def main():
    h = await fresh_harness()
    async with h:
        await h.open()
        try:
            await h.ev("indexedDB.deleteDatabase('noty-app')")
        except Exception:
            pass
        await asyncio.sleep(0.6)
        await h.open()
        await h.open_song(pages=10, reset=False)

        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
        await h.wait_for("!!document.querySelector('.annot-panel')", 10, "panel")
        await asyncio.sleep(0.6)

        p = await h.ev(PANEL)
        print("panel:", json.dumps(p, ensure_ascii=False))
        ok, det = await both_dirs(h)
        print("BASELINE listování: %s  %s" % ("OK" if ok else "FAIL", det))

        # ---------- 1) SBALENÍ PRSTEM (na šipku) ----------
        print("\n--- 1) sbalení panelu PRSTEM na šipku ---")
        for i in range(3):
            p = await h.ev(PANEL)
            if not p["panel"] or not p["collapseBtn"]:
                print("  panel/šipka zmizely, konec"); break
            print("  stav před %d: tools=%s collapseTitle=%s šipka v levém okraji=%s"
                  % (i + 1, p["toolCount"], p["collapseTitle"], p["inLeftEdge"]))
            await tap_point(h, p["collapseBtn"]["cx"], p["collapseBtn"]["cy"], "finger")
            p2 = await h.ev(PANEL)
            print("  po tapu: tools=%s collapseTitle=%s" % (p2["toolCount"], p2["collapseTitle"]))
            print("  __navdbg:", json.dumps(await dbg(h), ensure_ascii=False))
            ok, det = await both_dirs(h)
            print("  listování: %s  %s" % ("OK" if ok else "**FAIL**", det))
            if not ok:
                for extra in range(3):
                    ok2, det2 = await both_dirs(h)
                    print("    další pokus %d: %s  %s" % (extra + 1, "OK" if ok2 else "FAIL", det2))
                print("    --- vypnutí anotačního režimu ---")
                await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
                await asyncio.sleep(0.8)
                ok3, det3 = await both_dirs(h)
                print("    po vypnutí: %s  %s" % ("OK" if ok3 else "FAIL", det3))
                break

        # ---------- 2) totéž PEREM ----------
        print("\n--- 2) sbalení panelu PEREM na šipku ---")
        # zajisti, že panel existuje a je rozbalený
        if not await h.ev("!!document.querySelector('.annot-panel')"):
            await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
            await asyncio.sleep(0.8)
        for i in range(3):
            p = await h.ev(PANEL)
            if not p["panel"] or not p["collapseBtn"]:
                break
            print("  stav před %d: tools=%s collapseTitle=%s" % (i + 1, p["toolCount"], p["collapseTitle"]))
            await tap_point(h, p["collapseBtn"]["cx"], p["collapseBtn"]["cy"], "pen")
            p2 = await h.ev(PANEL)
            print("  po tapu: tools=%s collapseTitle=%s" % (p2["toolCount"], p2["collapseTitle"]))
            print("  __navdbg:", json.dumps(await dbg(h), ensure_ascii=False))
            await asyncio.sleep(0.5)
            ok, det = await both_dirs(h)
            print("  listování: %s  %s" % ("OK" if ok else "**FAIL**", det))
            if not ok:
                for extra in range(2):
                    ok2, det2 = await both_dirs(h)
                    print("    další pokus %d: %s  %s" % (extra + 1, "OK" if ok2 else "FAIL", det2))
                print("    --- vypnutí anotačního režimu ---")
                await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
                await asyncio.sleep(0.8)
                ok3, det3 = await both_dirs(h)
                print("    po vypnutí: %s  %s" % ("OK" if ok3 else "FAIL", det3))
                break

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
