#!/usr/bin/env python3
"""ŽIVÝ WEB: vykreslují se glyfy Značek na PRODUKCI?

Rozhodující je INKOUST a ADVANCE, ne přítomnost prvku v DOM — chybějící glyf
se vykreslí jako `.notdef` (tofu obdélníček) s NENULOVOU šířkou i inkoustem,
takže „element existuje" projde, i když uživatel vidí prázdné obdélníčky.

Přesně tahle chyba na produkci byla: font se změnil (42 → 62 glyfů), ale URL
zůstala stejná a Workbox ji (revision: null) nikdy znovu nestáhl → tablet držel
starý font. Sonda proto měří advance proti metrikám aktuálního fontu.

⚠️ Živá sonda se smí spustit JEN JEDNOU na čerstvý Chrome — druhý běh v řadě
uvízne na „Nahrávám noty… 0 / 1" (zacpaná IndexedDB). Restart:
    pkill -f "user-data-dir=/tmp/chrome-noty"; sleep 3; rm -rf /tmp/chrome-noty
"""
import asyncio
import importlib.util
import json
import os
import time
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
CDP_BASE = "http://127.0.0.1:9222"
LIVE = "https://harlequin-music-reader.web.app/"


def _load_harness():
    for cand in (
        os.path.join(_HERE, "cdp-e2e-harness.py"),
        os.path.expanduser(
            "~/.hermes/profiles/cfsb-agent/skills/software-development/"
            "pwa-pdf-viewer/scripts/cdp-e2e-harness.py"),
    ):
        if os.path.exists(cand):
            spec = importlib.util.spec_from_file_location("cdp_e2e_harness", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise SystemExit("nenalezen cdp-e2e-harness.py")


_mod = _load_harness()
Harness, Check = _mod.Harness, _mod.Check


def fresh_harness(url=LIVE):
    req = urllib.request.Request(f"{CDP_BASE}/json/new?about:blank", method="PUT")
    info = json.loads(urllib.request.urlopen(req).read())
    time.sleep(0.8)
    h = Harness(url)
    h._fresh_target = info.get("id")
    return h


# Stejná čísla jako MARK_ADV v appce = advance z metrik aktuálního fontu.
MARKS = {
    "bb": (0xE264, 0.413), "b": (0xE260, 0.226), "odr": (0xE261, 0.168),
    "k": (0xE262, 0.249), "kk": (0xE263, 0.250),
    "trylek": (0xE566, 0.521), "obal": (0xE567, 0.460),
    "obalo": (0xE568, 0.457), "trylks": (0xE56C, 0.730),
    "mord": (0xE56D, 0.729),
    "ferm": (0xE4C0, 0.605), "cez": (0xE4D1, 0.385),
    "dech": (0xE4CE, 0.153), "akc": (0xE4A0, 0.339),
    "stacc": (0xE4A2, 0.084), "ten": (0xE4A4, 0.338),
}
NOTDEF_CP = 0xEFFF
NOTDEF_ADV = 0.375

MEASURE = """(async (cp) => {
  try { await document.fonts.load('40px NotyDyn'); } catch (e) {}
  const S = 64, PX = 40;
  const cv = document.createElement('canvas');
  cv.width = S; cv.height = S;
  const ctx = cv.getContext('2d');
  ctx.font = PX + 'px NotyDyn';
  ctx.textBaseline = 'alphabetic'; ctx.textAlign = 'left';
  const adv = ctx.measureText(String.fromCodePoint(cp)).width / PX;
  ctx.clearRect(0, 0, S, S);
  ctx.fillStyle = '#000';
  ctx.fillText(String.fromCodePoint(cp), 2, S - 10);
  const d = ctx.getImageData(0, 0, S, S).data;
  let ink = 0;
  for (let i = 3; i < d.length; i += 4) if (d[i] > 40) ink++;
  return { ink: ink, advanceEm: +adv.toFixed(4) };
})"""

CLEAN = r"""
(async () => {
  const rs = await navigator.serviceWorker.getRegistrations();
  for (const r of rs) await r.unregister();
  for (const k of await caches.keys()) await caches.delete(k);
  return { unregistered: rs.length };
})()
"""


async def main():
    ok = Check()
    async with fresh_harness() as h:
        await h.open()
        print("   úklid SW:", await h.ev(CLEAN, await_promise=True))
        await h.cdp("Page.navigate", {"url": LIVE + "?cb=" + str(int(time.time()))})
        await h.wait_for("document.readyState === 'complete'", timeout=30, label="reload")
        await asyncio.sleep(3.0)
        await h.set_tablet(800, 1280, 2)
        await asyncio.sleep(1.5)

        # Která URL fontu se na produkci opravdu použila?
        font_src = await h.ev(r"""
        (() => {
          for (const ss of document.styleSheets) {
            try {
              for (const r of ss.cssRules) {
                if (r.constructor.name === 'CSSFontFaceRule' &&
                    /NotyDyn/.test(r.style.fontFamily)) {
                  return r.style.src || r.cssText;
                }
              }
            } catch (e) {}
          }
          return null;
        })()
        """)
        print("   @font-face src na produkci:", font_src)
        ok("produkce odkazuje na HASHOVANÝ font (ne /assets/noty-dyn.woff2)",
           bool(font_src) and "noty-dyn-" in str(font_src)
           and "noty-dyn.woff2" not in str(font_src),
           str(font_src))

        await h.ev("(async()=>{try{await document.fonts.load('40px NotyDyn')}catch(e){};return 1})()",
                   await_promise=True)
        await asyncio.sleep(0.6)
        ready = await h.ev("document.fonts.check('40px NotyDyn')")
        ok("font NotyDyn je na produkci načtený", ready, f"check={ready}")

        tofu = await h.ev(f"({MEASURE})({NOTDEF_CP})", await_promise=True)
        ok("kontrola slepoty: neznámý kód dá notdef",
           abs(tofu["advanceEm"] - NOTDEF_ADV) < 0.01, str(tofu))

        bad = []
        for key, (cp, exp) in MARKS.items():
            m = await h.ev(f"({MEASURE})({cp})", await_promise=True)
            good = abs(m["advanceEm"] - exp) < 0.02 and m["ink"] > 0 and m["ink"] != tofu["ink"]
            if not good:
                bad.append(key)
            ok(f"LIVE glyf {key} ({hex(cp)}) se vykresluje", good,
               f"inkoust={m['ink']} (notdef {tofu['ink']}), advance={m['advanceEm']} (čekáno {exp})")

        if bad:
            print(f"\n   CHYBÍ NA PRODUKCI: {bad}")
        return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
