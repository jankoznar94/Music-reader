#!/usr/bin/env python3
"""Ověření NA ŽIVÉM WEBU: velikost textu před vložením + pojistka lišty úprav.

Navazuje na `probe-live-dynamics.py` — řeší stejné pasti živého prostředí
(starý service worker, stará IndexedDB, minifikovaný build) a měří Z DOM.

Kontroluje to, co se právě nasadilo:
  1. dialog pro text má ovladač velikosti s náhledem „Aa“ (px = hodnota)
  2. tlačítko +/− velikost opravdu mění
  3. zvolená velikost se propíše do ULOŽENÉ anotace a volba se pamatuje
     (`localStorage` po uložení drží zvolené číslo)
  4. „Uložit a ruka“ → nástroj je ruka a prvek je ROVNOU vybraný
  5. ZBLOUDILÉ klepnutí na místo 🗑 v liště úprav prvek NESMAŽE
  6. protidůkaz: stejné klepnutí po položení uvnitř lišty prvek smaže

    python3 scripts/probe-live-text-size.py
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")
LIVE = os.environ.get("NOTY_LIVE", "https://harlequin-music-reader.web.app/")
TRASH = ".edit-bar .eb-btn[title='Smazat']"

_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
_h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_h)
_h.CDP_HTTP = CDP
Harness, Check, make_pdf = _h.Harness, _h.Check, _h.make_pdf


class LiveHarness(Harness):
    async def wipe(self):
        """Odregistruj SW + smaž cache i IndexedDB — jinak sonda vidí starou verzi."""
        try:
            await self.ev("(async () => {"
                          " const rs = await navigator.serviceWorker.getRegistrations();"
                          " for (const r of rs) await r.unregister();"
                          " for (const k of await caches.keys()) await caches.delete(k);"
                          " try { localStorage.removeItem('noty.textSize'); } catch (e) {}"
                          " return true; })()", await_promise=True)
        except Exception as exc:
            print("   (wipe SW selhalo:", exc, ")")
        for db in ("noty-app", "noty"):
            try:
                await self.ev(f"indexedDB.deleteDatabase('{db}')")
            except Exception:
                pass
        await asyncio.sleep(1.2)
        await self.open()
        n = await self.ev("navigator.serviceWorker.getRegistrations().then(r => r.length)",
                          await_promise=True)
        print("   service workerů po vyčištění:", n)


async def item_count(h):
    raw = await h.ev("""(async () => {
      const dbs = await indexedDB.databases();
      const name = (dbs.map(d => d.name) || []).find(n => /noty|music|reader/i.test(n));
      if (!name) return '-1';
      const db = await new Promise(res => { const r = indexedDB.open(name);
        r.onsuccess = () => res(r.result); r.onerror = () => res(null); });
      if (!db) return '-1';
      let n = 0;
      if (db.objectStoreNames.contains('annotations')) {
        const rows = await new Promise(res => {
          const r = db.transaction('annotations', 'readonly').objectStore('annotations').getAll();
          r.onsuccess = () => res(r.result); r.onerror = () => res(null); });
        for (const row of (rows || [])) n += ((row.items || []).length);
      }
      db.close();
      return String(n);
    })()""", await_promise=True)
    return int(raw)


async def dialog_state(h):
    raw = await h.ev("""(() => {
      const on = !!document.querySelector('.text-input-overlay');
      const val = document.querySelector('.ti-size-val');
      const aa = document.querySelector('.ti-size-aa');
      return JSON.stringify({
        open: on,
        sizeRow: !!document.querySelector('.ti-size-row'),
        sizeVal: val ? val.textContent.trim() : null,
        aaPx: aa ? getComputedStyle(aa).fontSize : null,
        hand: !!document.querySelector('.jp-btn.hand'),
        buttons: [...document.querySelectorAll('.text-input-card .jp-btn')]
          .map(b => (b.textContent || '').trim()),
        ls: (() => { try { return localStorage.getItem('noty.textSize'); } catch (e) { return 'ERR'; } })(),
      });
    })()""")
    return json.loads(raw) if raw else {}


def _point_js(sel):
    return """(() => {
      const sel = %s;
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      for (let y = Math.floor(r.top); y <= Math.ceil(r.bottom); y += 2)
        for (let x = Math.floor(r.left); x <= Math.ceil(r.right); x += 2) {
          const hit = document.elementFromPoint(x, y);
          if (hit && (hit === el || (hit.closest && hit.closest(sel) === el))) return [x + 0.5, y + 0.5];
        }
      return null;
    })()""" % json.dumps(sel)


async def tap_el(h, sel, hold_ms=70):
    pt = await h.ev(_point_js(sel))
    if not pt:
        return False
    await h.touch("touchStart", [(pt[0], pt[1], 12)])
    await asyncio.sleep(hold_ms / 1000)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.5)
    return True


async def panel(h, open_wanted):
    """Anotační panel: pro výběr nástroje rozbalený, pro klepání do pásu horní
    lišty sbalený (jinak tam sedí a klepnutí mine vrstvu)."""
    for _ in range(3):
        st = await h.ev("""(() => {
          const b = document.querySelector('.ap-collapse');
          if (!b) return 'none';
          const txt = (b.getAttribute('title') || '');
          return /Rozbalit/.test(txt) ? 'collapsed' : 'open';
        })()""")
        if st == "none":
            return True
        if (st == "open") == open_wanted:
            return True
        await h.ev("document.querySelector('.ap-collapse').click()")
        await asyncio.sleep(0.5)
    return False


async def pick_tool(h, title):
    await panel(h, True)
    r = await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => (x.getAttribute('title') || '').startsWith(%s));"
                   " if (!b) return 'missing'; b.click(); return 'ok'; })()"
                   % json.dumps(title))
    await asyncio.sleep(0.35)
    return r


async def free_xy(h, prefer_low=False):
    ys = [0.62, 0.70, 0.78, 0.50] if prefer_low else [0.34, 0.42, 0.50, 0.58]
    return await h.ev("""(() => {
      const svg = document.querySelector('.annot-layer');
      if (!svg) return null;
      const r = svg.getBoundingClientRect();
      const boxes = [...svg.querySelectorAll('g > text, g > path, g > rect, g > line')]
        .map(e => e.getBoundingClientRect());
      const near = (x, y) => boxes.some(q => q.width > 0 &&
        x > q.left - 28 && x < q.right + 28 && y > q.top - 24 && y < q.bottom + 24);
      for (const fy of %s) for (const fx of [0.58, 0.50, 0.42, 0.66, 0.34]) {
        const x = r.left + r.width * fx, y = r.top + r.height * fy;
        if (document.elementFromPoint(x, y) === svg && !near(x, y)) return {x, y};
      }
      return null;
    })()""" % json.dumps(ys))


async def insert_text(h, x, y, text):
    await pick_tool(h, "Text")
    await panel(h, False)
    await h.pen_tap(x, y)
    await asyncio.sleep(0.9)
    if not await h.ev("!!document.querySelector('.text-input-overlay')"):
        return False
    await h.set_value(".ti-input", text)
    await tap_el(h, ".jp-btn.primary")
    await asyncio.sleep(1.2)
    return True


async def saved_texts(h):
    raw = await h.ev("""(async () => {
      const dbs = await indexedDB.databases();
      const name = (dbs.map(d => d.name) || []).find(n => /noty|music|reader/i.test(n));
      if (!name) return '[]';
      const db = await new Promise(res => { const r = indexedDB.open(name);
        r.onsuccess = () => res(r.result); r.onerror = () => res(null); });
      if (!db) return '[]';
      const out = [];
      if (db.objectStoreNames.contains('annotations')) {
        const rows = await new Promise(res => {
          const r = db.transaction('annotations', 'readonly').objectStore('annotations').getAll();
          r.onsuccess = () => res(r.result); r.onerror = () => res(null); });
        for (const row of (rows || [])) for (const i of (row.items || []))
          if (i.tool === 'text') out.push({text: i.text, size: i.size});
      }
      db.close();
      return JSON.stringify(out);
    })()""", await_promise=True)
    return json.loads(raw) if raw else []


async def trash_point(h):
    return await h.ev("""(() => {
      const b = document.querySelector(%s);
      if (!b) return null;
      const r = b.getBoundingClientRect();
      const x = r.left + r.width / 2, y = r.top + r.height / 2;
      const el = document.elementFromPoint(x, y);
      return {x, y, hitTrash: !!(el && el.closest && el.closest(%s))};
    })()""" % (json.dumps(TRASH), json.dumps(TRASH)))


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
        ok("skladba se na živém webu otevře", bool(await h.ev("!!document.querySelector('.tb-page')")))
        await h.annot_toggle()
        await asyncio.sleep(0.5)
        await panel(h, False)

        # --- 1) dialog pro text má ovladač velikosti s náhledem ---
        p1 = await free_xy(h)
        ok("text se vloží prstem i na živém webu",
           await insert_text(h, p1["x"], p1["y"], "zivy test"),
           f"bod=({p1['x']:.0f},{p1['y']:.0f})")
        n1 = await item_count(h)
        saved = await saved_texts(h)
        ok("1) text se uložil do IndexedDB", any(s.get("text") == "zivy test" for s in saved),
           json.dumps(saved, ensure_ascii=False))

        # otevři dialog znovu (nový text) a prohlédni ovladač
        p2 = await free_xy(h)
        await pick_tool(h, "Text")
        await panel(h, False)
        await h.pen_tap(p2["x"], p2["y"])
        await asyncio.sleep(0.9)
        st = await dialog_state(h)
        ok("2) dialog pro text má ovladač velikosti", st.get("open") and st.get("sizeRow"),
           json.dumps(st, ensure_ascii=False))
        if st.get("open"):
            base = st.get("sizeVal")
            ok("2b) náhled „Aa“ ukazuje skutečnou velikost", st.get("aaPx") == (base + "px"),
               f"val={base} aa={st.get('aaPx')}")
            await tap_el(h, ".ti-size-btn:last-of-type")   # +
            st2 = await dialog_state(h)
            ok("2c) tlačítko + velikost zvětší", st2.get("sizeVal") not in (base, None),
               f"{base} -> {st2.get('sizeVal')}")
            bigger = st2.get("sizeVal")
            ok("2d) „Uložit a ruka“ je v dialogu nabízené", st2.get("hand") is True,
               json.dumps(st2.get("buttons"), ensure_ascii=False))

            # --- 3) Uložit a ruka → ruka + prvek vybraný ---
            await h.set_value(".ti-input", "rukou hned")
            await tap_el(h, ".jp-btn.hand")
            await asyncio.sleep(1.2)
            # POZOR: tlačítka nástrojů jsou v anotačním panelu, a ten je při klepání
            # na noty SBALENÝ — nástroj se dá přečíst jen s rozbaleným panelem.
            await panel(h, True)
            hand = json.loads(await h.ev("""(() => JSON.stringify({
              dialog: !!document.querySelector('.text-input-overlay'),
              toolOn: (() => { const b = [...document.querySelectorAll('.ap-tool')]
                .find(x => (x.getAttribute('title') || '').startsWith('Upravit'));
                return b ? b.classList.contains('on') : null; })(),
              box: !!document.querySelector('.annot-selected'),
              editBar: !!document.querySelector('.edit-bar'),
              editSize: (document.querySelector('.eb-val') || {}).textContent || null,
              ls: (() => { try { return localStorage.getItem('noty.textSize'); } catch (e) { return 'ERR'; } })(),
            }))()"""))
            ok("3) „Uložit a ruka“: dialog zavřen, nástroj ruka, prvek ROVNOU vybraný",
               (not hand["dialog"]) and hand["toolOn"] is True and hand["box"] and hand["editBar"],
               json.dumps(hand, ensure_ascii=False))
            ok("3b) pás úprav hlásí zvolenou velikost", hand["editSize"] == bigger,
               f"{hand['editSize']} vs {bigger}")
            saved = await saved_texts(h)
            ok("3c) ULOŽENÝ text má zvolenou velikost",
               any(s.get("text") == "rukou hned" and str(s.get("size")) == bigger for s in saved),
               json.dumps(saved, ensure_ascii=False))
            # Volba se pamatuje: po uložení drží localStorage zvolené číslo
            ok("3d) volba se pamatuje pro další text (localStorage)",
               hand["ls"] == bigger, f"localStorage={hand['ls']}, zvoleno={bigger}")
            # úklid: zavři pás úprav
            await tap_el(h, ".edit-bar .eb-btn[title='Hotovo']")

        # --- 4) pojistka lišty úprav: zbloudilé klepnutí nesmí smazat ---
        p3 = await free_xy(h)
        await insert_text(h, p3["x"], p3["y"], "pro pojistku")
        n2 = await item_count(h)
        await pick_tool(h, "Upravit")
        await panel(h, False)
        await h.pen_tap(p3["x"], p3["y"])
        await asyncio.sleep(0.9)
        tp = await trash_point(h)
        ok("4) po výběru rukou je lišta úprav a 🗑 k dispozici", bool(tp),
           json.dumps(tp, ensure_ascii=False))
        if tp:
            await h.ev("""(() => {
              const el = document.elementFromPoint(%f, %f);
              if (!el) return false;
              el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true,
                clientX: %f, clientY: %f, view: window}));
              return true;
            })()""" % (tp["x"], tp["y"], tp["x"], tp["y"]))
            await asyncio.sleep(0.9)
            n3 = await item_count(h)
            ok("4b) ZBLOUDILÉ klepnutí na místo 🗑 prvek NESMAŽE (oprava je živá)",
               n3 == n2, f"před={n2} po={n3} (klepnutí mířilo na 🗑: {tp['hitTrash']})")
            ok("4c) test něco dokazuje — klepnutí opravdu dopadlo na 🗑",
               tp["hitTrash"] is True, json.dumps(tp, ensure_ascii=False))
            # --- 5) protidůkaz: po položení uvnitř lišty smazat MUSÍ ---
            await h.ev("""(() => {
              const bar = document.querySelector('.edit-bar');
              if (!bar) return false;
              bar.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, cancelable: true,
                clientX: %f, clientY: %f, pointerId: 7, pointerType: 'touch', isPrimary: true}));
              const el = document.elementFromPoint(%f, %f);
              if (!el) return false;
              el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true,
                clientX: %f, clientY: %f, view: window}));
              return true;
            })()""" % (tp["x"], tp["y"], tp["x"], tp["y"], tp["x"], tp["y"]))
            await asyncio.sleep(0.9)
            n4 = await item_count(h)
            ok("5) ťuknutí na 🗑 (položení uvnitř lišty) prvek smaže — ovládání funguje",
               n4 == n3 - 1, f"{n3} -> {n4}")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
