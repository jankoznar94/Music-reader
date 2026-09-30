#!/usr/bin/env python3
"""Sonda CHOVÁNÍ dialogu dynamiky na ŽIVÉM webu.

Řeší tři pasti živého prostředí (starý SW, stará IndexedDB, minifikovaný build):
  - odregistruje service workery a smaže CacheStorage + IndexedDB
  - měří z DOM (nic z devtoolsRawSetupState)
  - klepe na body dlaždic nalezené přes document.elementFromPoint

Scénáře: umístění perem nesmí samo vložit dynamiku (5x), volba dlaždic
mp/fff/pp perem → U+E52C/U+E530/U+E52B, volba prstem, Zrušit.
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
KEY = {"mp": 0xE52C, "fff": 0xE530, "pp": 0xE52B, "sf": 0xE524, "f": 0xE522}


class LiveHarness(Harness):
    async def wipe(self):
        """Odregistruj SW + smaž cache, ať sonda nevidí starou verzi appky."""
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
        # po reloadu musí být SW přesně 1 (nově nainstalovaný) — jinak měření lže
        n = await self.ev("navigator.serviceWorker.getRegistrations().then(r => r.length)",
                          await_promise=True)
        print("   service workerů po vyčištění:", n)


async def state(h):
    return await h.ev(
        "(() => ({ open: !!document.querySelector('.text-input-overlay'),"
        " glyphs: [...document.querySelectorAll('.annot-layer text')]"
        "   .map(t => t.textContent.codePointAt(0)) }))()")


async def point_of(h, key, sel=".dyn-btn"):
    return await h.ev("""(() => {
      const want = %s, sel = %s;
      const card = document.querySelector('.text-input-card');
      if (!card) return null;
      const r = card.getBoundingClientRect();
      for (let y = Math.ceil(r.top); y < r.bottom; y += 3) {
        for (let x = Math.ceil(r.left); x < r.right; x += 3) {
          const el = document.elementFromPoint(x, y);
          if (!el) continue;
          const hit = el.closest ? el.closest(sel) : null;
          if (sel === '.dyn-btn') { if (hit && hit.title === want) return [x + 0.5, y + 0.5]; }
          else if (hit) return [x + 0.5, y + 0.5];
        }
      }
      return null;
    })()""" % (json.dumps(key), json.dumps(sel)))


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
    pt = await point_of(h, "", ".jp-btn")
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
        await asyncio.sleep(1.0)
        print("   URL:", await h.ev("location.href"))
        await h.wipe()

        await h.open_song(pdf=make_pdf(6), reset=False)
        ok("na živém webu se skladba otevře", bool(await h.ev("!!document.querySelector('.tb-page')")))

        await h.annot_toggle()
        ok("anotační režim se zapne",
           bool(await h.ev("!!document.querySelector('.annot-panel')")))
        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => (x.title || '').startsWith('Dynamika')); if (b) b.click(); })()")
        await asyncio.sleep(0.5)

        # 1) umístění perem samo nic nevloží
        auto = []
        for i in range(5):
            before = await state(h)
            p = await open_dialog(h)
            if not p:
                ok(f"umístění #{i+1}: dialog se otevřel", False, "neotevřel se")
                continue
            after = await state(h)
            new = [g for g in after["glyphs"] if g not in before["glyphs"]]
            auto += new
            ok(f"umístění #{i+1}: dialog zůstal a sám nic nevložil",
               after["open"] and not new,
               f"open={after['open']} nové={['U+%04X' % g for g in new]}")
            closed = await dismiss(h)
            if not closed:
                ok(f"umístění #{i+1}: jde zavřít dotykem na Zrušit", False, "zůstal otevřený")
            await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                       ".find(x => (x.title || '').startsWith('Dynamika')); if (b) b.click(); })()")
            await asyncio.sleep(0.4)
        ok("žádné samovolné vložení dynamiky (živý web)", auto == [],
           f"samovolně {['U+%04X' % g for g in auto]}")

        # 2) volby dlaždic perem
        for key in ("mp", "fff", "pp"):
            p = await open_dialog(h)
            if not p:
                ok(f"dialog pro volbu {key}", False, "neotevřel se")
                continue
            st = await state(h)
            pt = await point_of(h, key)
            if not pt:
                ok(f"dlaždice {key} dosažitelná", False, "bod nenalezen")
                continue
            await h.pen_tap(pt[0], pt[1])
            await asyncio.sleep(0.7)
            st2 = await state(h)
            new = [g for g in st2["glyphs"] if g not in st["glyphs"]]
            ok(f"volba '{key}' vloží U+{KEY[key]:04X}", new == [KEY[key]],
               f"vloženo {['U+%04X' % g for g in new]}")

        # 3) volba prstem
        p = await open_dialog(h)
        if p:
            st = await state(h)
            pt = await point_of(h, "sf")
            if pt:
                await h.finger_tap(pt[0], pt[1])
                await asyncio.sleep(0.7)
                st2 = await state(h)
                new = [g for g in st2["glyphs"] if g not in st["glyphs"]]
                ok("volba prstem 'sf' vloží U+E524", new == [0xE524],
                   f"vloženo {['U+%04X' % g for g in new]}")

        # 4) Zrušit
        p = await open_dialog(h)
        if p:
            st = await state(h)
            closed = await dismiss(h)
            st2 = await state(h)
            ok("Zrušit dotykem nic nevloží a dialog zmizí",
               closed and (not st2["open"]) and st2["glyphs"] == st["glyphs"],
               f"open={st2['open']}")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
