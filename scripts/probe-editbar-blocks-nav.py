#!/usr/bin/env python3
"""Sonda: zablokuje VYBRANÝ prvek (lišta .edit-bar) okrajové listování?

Jan (Oct 2026): „Opravdu se občas stane, že při anotačním režimu přestane
fungovat listování stránek. Funguje to, ale prostě po určité době, nebo akci, se
to sekne a pak už listovat nejde. Jen po vypnutí anotačního režimu."

HYPOTÉZA:
  Režim „Ruka" (✋ Upravit) vybere klepnutím prvek → zobrazí se `.edit-bar`
  (lišta s akcemi pro vybraný prvek). `isControlTarget()` ji považuje za
  ovládací prvek, takže klepnutí na okraj, které na lištu spadne, NElístuje.
  Uživatel to vidí jako „listování přestalo fungovat".
  Vypnutí anotačního režimu → watch(annotMode) → endEdit() → editingId = null
  → `.edit-bar` zmizí → listování zase jde. Přesně Janovo „jen po vypnutí
  anotačního režimu se to rozjede".

Sonda změří:
  1) geometrii .edit-bar (překrývá okrajové zóny?)
  2) listování PŘED výběrem prvku vs. PO výběru (s i bez lišty)
  3) co se stane po vypnutí/zapnutí anotačního režimu

    scripts/run-probe-fresh.sh scripts/probe-editbar-blocks-nav.py
"""
import asyncio
import importlib.util
import json
import os
import urllib.request

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
ANNOT = "Anotace / listování"


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
Harness, Check = _m.Harness, _m.Check

GEO = ("(() => { const r = document.querySelector('.stage.backdrop').getBoundingClientRect();"
       " return { left: r.left, top: r.top, width: r.width, height: r.height }; })()")

EDITBAR = r"""
(() => {
  const bars = [...document.querySelectorAll('.edit-bar')];
  const v = document.querySelector('.viewer').getBoundingClientRect();
  return {
    count: bars.length,
    bars: bars.map(b => {
      const r = b.getBoundingClientRect();
      return {
        top: +r.top.toFixed(0), bottom: +r.bottom.toFixed(0),
        left: +r.left.toFixed(0), right: +r.right.toFixed(0),
        w: +r.width.toFixed(0), h: +r.height.toFixed(0),
        // překryv s okrajovým pruhem 70 px vlevo/vpravo?
        coversLeftEdge: r.left <= v.left + 70 && r.right > v.left,
        coversRightEdge: r.right >= v.right - 70 && r.left < v.right,
        pe: getComputedStyle(b).pointerEvents,
      };
    }),
    viewer: { left: +v.left.toFixed(0), right: +v.right.toFixed(0), w: +v.width.toFixed(0) },
  };
})()
"""


async def fresh_harness():
    req = urllib.request.Request(f"{CDP}/json/new?about:blank", method="PUT")
    info = json.loads(urllib.request.urlopen(req).read())
    await asyncio.sleep(0.8)
    h = Harness(_m.APP_URL)
    h._fresh_target = info.get("id")
    return h


async def page_info(h):
    t = await h.ev("document.querySelector('.tb-page').textContent.trim()")
    left, rest = t.split("/")
    return int(left.split(" ")[0].strip()), int(rest.strip().split(" ")[0])


async def swipe_dir(h, direction):
    g = await h.ev(GEO)
    y = g["top"] + g["height"] * 0.5
    if direction > 0:
        x0, x1 = g["left"] + g["width"] - 18, g["left"] + g["width"] * 0.55
    else:
        x0, x1 = g["left"] + 18, g["left"] + g["width"] * 0.45
    before = (await page_info(h))[0]
    await h.finger_swipe(x0, y, x1, y, r=12, steps=10)
    await asyncio.sleep(1.0)
    return before, (await page_info(h))[0]


async def try_swipe(h):
    for _ in range(2):
        cur, tot = await page_info(h)
        d = 1 if cur < tot else -1
        b, a = await swipe_dir(h, d)
        if b != a:
            return True, "%s->%s" % (b, a)
        await asyncio.sleep(0.8)
    return False, "stuck na %s" % b


async def tool(h, title):
    return await h.ev(
        "(() => { const b = [...document.querySelectorAll('.ap-tool')]"
        ".find(x => x.getAttribute('title') === %s); if (!b) return 'missing';"
        " b.click(); return 'ok'; })()" % json.dumps(title))


async def centre(h, fx=0.5, fy=0.4):
    g = await h.ev(GEO)
    return (g["left"] + g["width"] * fx, g["top"] + g["height"] * fy)


async def main():
    c = Check()
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

        ok, det = await try_swipe(h)
        c("1) BASELINE listování", ok, det)
        c("1) žádná .edit-bar", (await h.ev(EDITBAR))["count"] == 0, str(await h.ev(EDITBAR)))

        # --- nakresli anotaci perem ---------------------------------------
        await tool(h, "Tužka")
        x, y = await centre(h, 0.5, 0.35)
        await h.pen_stroke(x - 40, y, x + 40, y, steps=8)
        await asyncio.sleep(1.2)

        # --- vyber ji nástrojem Ruka --------------------------------------
        await tool(h, "Upravit / přesunout text či dynamiku")
        await asyncio.sleep(0.4)
        # klepni pero na místo tahu (mírně nad ním, aby to trefilo pero ne prst)
        await h.pen_tap(x - 40, y)
        await asyncio.sleep(0.9)

        eb = await h.ev(EDITBAR)
        print("  .edit-bar po výběru:", json.dumps(eb, ensure_ascii=False))
        c("2) vybraný prvek → .edit-bar se zobrazila", eb["count"] > 0, str(eb["count"]))
        if eb["count"]:
            covers = eb["bars"][0]["coversLeftEdge"] or eb["bars"][0]["coversRightEdge"]
            print("  lišta zasahuje do okrajové zóny:", covers,
                  "| levá hrana lišty:", eb["bars"][0]["left"], "| pravá:", eb["bars"][0]["right"],
                  "| okraj zóny L:", eb["viewer"]["left"], "R:", eb["viewer"]["right"])

        ok, det = await try_swipe(h)
        c("3) listování s VYBRANÝM prvkem (lišta na obrazovce)", ok, det)

        # --- co na to vypnutí režimu --------------------------------------
        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
        await asyncio.sleep(0.8)
        eb2 = await h.ev(EDITBAR)
        c("4) vypnutí režimu schovalo .edit-bar", eb2["count"] == 0, str(eb2["count"]))
        ok, det = await try_swipe(h)
        c("4) listování po vypnutí režimu", ok, det)

    return c.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
