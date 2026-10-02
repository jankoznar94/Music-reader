#!/usr/bin/env python3
"""Sonda nástroje Značky na ŽIVÉM webu (po nasazení).

Živé prostředí má tři pasti, které v dev režimu nejsou: starý service worker
(drží starý HTML i staré assety) a stará IndexedDB. Sonda proto nejdřív
odregistruje SW, smaže CacheStorage i IndexedDB, teprve pak měří.

Ověřuje totéž co dev sonda, ale jen to podstatné: dlaždice existují, každá
rodina vloží SPRÁVNÝ SMuFL kód, dialog sám nic nevloží.
"""
import asyncio
import importlib.util
import json

_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", "/home/martin_fabian/noty-app/cdp-e2e-harness.py")
_h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_h)
Harness, Check, make_pdf = _h.Harness, _h.Check, _h.make_pdf

LIVE = "https://harlequin-music-reader.web.app/"
KEYS = {
    "béčko": 0xE260, "odrážka": 0xE261, "křížek": 0xE262,
    "trylek": 0xE566, "mordent": 0xE56D,
    "fermata (koruna)": 0xE4C0, "staccato": 0xE4A2,
}


class LiveHarness(Harness):
    async def wipe(self):
        """Odregistruj SW + smaž cache a IndexedDB, ať sonda nevidí starou verzi."""
        try:
            await self.ev("(async () => {"
                          " const rs = await navigator.serviceWorker.getRegistrations();"
                          " for (const r of rs) await r.unregister();"
                          " for (const k of await caches.keys()) await caches.delete(k);"
                          " return true; })()", await_promise=True)
        except Exception as exc:
            print("   (wipe SW selhalo:", exc, ")")
        try:
            await self.ev("indexedDB.deleteDatabase('noty-app')")
        except Exception:
            pass
        await asyncio.sleep(1.2)
        await self.open()
        n = await self.ev("navigator.serviceWorker.getRegistrations().then(r => r.length)",
                          await_promise=True)
        print("   service workerů po vyčištění:", n)


async def glyphs(h):
    return await h.ev("(() => [...document.querySelectorAll('.annot-layer text')]"
                      ".map(t => t.textContent.codePointAt(0)))()")


async def pick_tool(h, prefix):
    await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
               ".find(x => (x.title || '').startsWith(%s)); if (b) b.click(); })()"
               % json.dumps(prefix))
    await asyncio.sleep(0.4)


async def tile_point(h, title):
    return await h.ev("""(() => {
      const want = %s;
      const card = document.querySelector('.text-input-card');
      if (!card) return null;
      const r = card.getBoundingClientRect();
      for (let y = Math.ceil(r.top); y < r.bottom; y++)
        for (let x = Math.ceil(r.left); x < r.right; x++) {
          const el = document.elementFromPoint(x, y);
          const hit = el && el.closest ? el.closest('.mark-sec .dyn-btn') : null;
          if (hit && hit.title === want) return [x, y];
        }
      return null;
    })()""" % json.dumps(title))


async def open_dialog(h):
    for _ in range(8):
        p = await h.free_point()
        if not p:
            continue
        await h.pen_stroke(p["x"], p["y"], p["x"] + 2, p["y"] + 2)
        await asyncio.sleep(0.8)
        if await h.ev("!!document.querySelector('.text-input-overlay')"):
            return p
    return None


async def dismiss(h):
    if not await h.ev("!!document.querySelector('.text-input-overlay')"):
        return True
    pt = await h.ev("""(() => {
      const card = document.querySelector('.text-input-card');
      if (!card) return null;
      const r = card.getBoundingClientRect();
      for (let y = Math.ceil(r.top); y < r.bottom; y++)
        for (let x = Math.ceil(r.left); x < r.right; x++) {
          const el = document.elementFromPoint(x, y);
          const b = el && el.closest ? el.closest('.jp-btn') : null;
          if (b && /Zru/i.test(b.textContent || '')) return [x, y];
        }
      return null; })()""")
    if not pt:
        return False
    await h.pen_tap(pt[0], pt[1])
    await asyncio.sleep(0.6)
    return not await h.ev("!!document.querySelector('.text-input-overlay')")


async def main():
    ok = Check()
    async with LiveHarness(LIVE) as h:
        await h.cdp("Emulation.setDeviceMetricsOverride",
                    {"width": 800, "height": 1280, "deviceScaleFactor": 2, "mobile": True})
        await h.open()
        await asyncio.sleep(1.2)
        print("   URL:", await h.ev("location.href"))
        await h.wipe()

        await h.open_song(pdf=make_pdf(6), reset=False)
        ok("na živém webu se skladba otevře",
           bool(await h.ev("!!document.querySelector('.tb-page')")))

        await h.annot_toggle()
        await pick_tool(h, "Značky")
        ok("nástroj Značky je na živém webu",
           bool(await h.ev("(() => [...document.querySelectorAll('.ap-tool')]"
                           ".some(x => (x.title||'').startsWith('Značky')))()")))

        # dialog: tři sekce, 16 dlaždic
        p = await open_dialog(h)
        ok("dialog značky se otevře", bool(p))
        d = await h.ev("""(() => {
          const card = document.querySelector('.text-input-card');
          if (!card) return null;
          return { sections: [...card.querySelectorAll('.mark-sec-label')].map(e => e.textContent.trim()),
                   n: card.querySelectorAll('.mark-sec .dyn-btn').length }; })()""")
        ok("dialog má tři sekce a 16 dlaždic",
           bool(d) and d["sections"] == ["Posuvky", "Ozdoby", "Drobnosti"] and d["n"] == 16,
           f"{d}")
        await dismiss(h)

        # umístění samo nic nevloží
        auto = []
        for i in range(3):
            before = await glyphs(h)
            p = await open_dialog(h)
            if not p:
                ok(f"umístění #{i+1}: dialog se otevřel", False, "neotevřel se")
                continue
            after = await glyphs(h)
            new = [g for g in after if g not in before]
            auto += new
            ok(f"umístění #{i+1}: sám nic nevložil", not new,
               f"nové={['U+%04X' % g for g in new]}")
            await dismiss(h)
            await pick_tool(h, "Značky")
        ok("žádná samovolná značka (živý web)", auto == [],
           f"samovolně {['U+%04X' % g for g in auto]}")

        # každá rodina vloží správný kód
        for title, cp in KEYS.items():
            await pick_tool(h, "Značky")
            p = await open_dialog(h)
            if not p:
                ok(f"dialog pro '{title}'", False, "neotevřel se")
                continue
            before = await glyphs(h)
            pt = await tile_point(h, title)
            if not pt:
                ok(f"dlaždice '{title}' dosažitelná", False, "bod nenalezen")
                await dismiss(h)
                continue
            await h.pen_tap(pt[0], pt[1])
            await asyncio.sleep(0.7)
            new = [g for g in await glyphs(h) if g not in before]
            ok(f"'{title}' vloží U+{cp:04X}", new == [cp],
               f"vloženo {['U+%04X' % g for g in new]} (bod {pt})")

        # font se opravdu načetl (jinak by dlaždice vypadaly stejně, ale kreslily nic)
        fstat = await h.ev("""(async () => {
          try { await document.fonts.load("26px NotyDyn"); } catch (e) {}
          const st = [];
          document.fonts.forEach(f => { if (/NotyDyn/i.test(f.family)) st.push(f.status); });
          return { faces: st, loaded: document.fonts.check("26px NotyDyn") };
        })()""", await_promise=True)
        ok("font NotyDyn je načtený", bool(fstat) and fstat.get("loaded"), f"{fstat}")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
