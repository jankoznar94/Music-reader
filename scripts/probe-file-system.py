#!/usr/bin/env python3
"""Souborový systém v Knihovně: zanořování, drobečková cesta, přesun tažením.

Jan: „Uděláme klasický souborový systém na který jsou uživatelé zvyklí. Složky
se budou zanořovat do sebe.“ + upřesnění: strom, skladba v JEDNÉ složce,
drobečková cesta + podsložky v seznamu, přesun TAŽENÍM, hledání napříč knihovnou.

Model (jako v Průzkumníku): nota s `folderId = null` leží V KOŘENI knihovny.

Sonda prochází celý životní cyklus, protože každé kolečko se dá pokazit jinde:

  1) zakládání složek přes UI (kořenová + PODSLOŽKA tlačítkem ＋ v řádku rodiče)
  2) strom: zanoření (parentId v DB) a odsazení v UI
  3) obsah kořene: složky + noty, které nikam nepatří
  4) vstup do složky: drobečková cesta, prázdný stav, návrat drobečkou
  5) přesun noty TAŽENÍM prstem (toast + zápis do DB)
  6) přesun do ZANOŘENÉ složky (Baroko uvnitř Sborový)
  7) hledání napříč knihovnou + cesta u výsledku
  8) smazání složky s podsložkami: podsložky zmizí, NOTY SE NESMAŽOU
  9) po reloadu strom i noty sedí

⚠️ Dotykové gesto spouštěj VŽDY přes run-probe-fresh.sh — opakovaně použitý
profil Chrome doručování dotyků tiše zabije (viz harness-traps.md bod 1b).

    scripts/run-probe-fresh.sh scripts/probe-file-system.py
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")


def _load_harness():
    cand = os.path.expanduser("~/noty-app/cdp-e2e-harness.py")
    spec = importlib.util.spec_from_file_location("cdp_e2e_harness", cand)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_m = _load_harness()
_m.CDP_HTTP = CDP
Harness, Check = _m.Harness, _m.Check
# Cíl lze přepnout na ŽIVÝ web (NOTY_TARGET=https://…), aby se tatáž sonda dala
# pustit i po nasazení — „v bundlu to je“ ještě neznamená „na webu to funguje“.
TARGET = os.environ.get("NOTY_TARGET") or _m.APP_URL
IS_LIVE = not TARGET.startswith("http://localhost")

LIB = r"""
(() => {
  // ⚠️ Řádek „＋ Nová složka“ NEMÁ počet souborů — `querySelector` na `.folder-meta`
  // vrací null a sonda by spadla na TypeError (přesně se to stalo).
  const rows = [...document.querySelectorAll('.folder-row')].map(r => {
    const nm = r.querySelector('.folder-name');
    const mt = r.querySelector('.folder-meta');
    return {
      name: nm ? nm.textContent.trim() : null,
      meta: mt ? mt.textContent.trim() : null,
      isNew: r.classList.contains('newfolder'),
    };
  });
  // HLEDÁNÍ: do seznamu se dostávají i noty, které v aktuální složce nebydlí —
  // proto se jména sbírají i z rozbalených záložek autorů a při zobrazení
  // výsledků se hlavičky autorů otevírají předem (jinak by se nic neukázalo).
  const groups = [...document.querySelectorAll('.author-group')].map(g => ({
    label: g.querySelector('.author-name') ? g.querySelector('.author-name').textContent.trim() : '',
    open: !!g.querySelector('.songlist'),
    count: g.querySelector('.author-count') ? g.querySelector('.author-count').textContent.trim() : '',
  }));
  const songs = [...document.querySelectorAll('.song .song-name')].map(e => e.textContent.trim());
  const paths = [...document.querySelectorAll('.song .song-folder')].map(e => e.textContent.trim());
  const crumbs = [...document.querySelectorAll('.crumb')].map(c => ({
    name: c.textContent.trim(), on: c.classList.contains('on'), drop: c.dataset.folderDrop,
  }));
  const hint = document.querySelector('.content .center.muted');
  return {
    crumbs, rows, songs, paths, groups,
    folderRows: rows.filter(r => !r.isNew).map(r => r.name + ' (' + r.meta + ')'),
    newFolderRow: rows.some(r => r.isNew),
    empty: hint ? hint.textContent.trim() : null,
    toast: document.querySelector('.toast') ? document.querySelector('.toast').textContent.trim() : null,
  };
})()
"""

TREE = r"""
(() => [...document.querySelectorAll('.grouplist .group')].map(li => {
  const nm = li.querySelector('.group-name');
  const caret = li.querySelector('.caret');
  return {
    name: nm ? nm.textContent.trim().replace(/^📁\s*/, '') : null,
    indent: nm ? parseInt(getComputedStyle(nm).paddingLeft) : 0,
    caret: caret && !caret.classList.contains('empty') ? caret.textContent.trim() : null,
    meta: li.querySelector('.group-meta') ? li.querySelector('.group-meta').textContent.trim() : null,
  };
}))()
"""

DB = r"""
new Promise((resolve) => {
  const req = indexedDB.open('noty-app');
  req.onsuccess = () => {
    const db = req.result;
    const t = db.transaction(['folders', 'songs'], 'readonly');
    const f = t.objectStore('folders').getAll();
    f.onsuccess = () => {
      const s = t.objectStore('songs').getAll();
      s.onsuccess = () => resolve({
        folders: (f.result || []).map(x => ({ id: x.id, name: x.name, parentId: x.parentId || null })),
        songs: (s.result || []).map(x => ({ name: x.name, folderId: x.folderId || null })),
      });
      s.onerror = () => resolve({ err: 'songs' });
    };
    f.onerror = () => resolve({ err: 'folders' });
  };
  req.onerror = () => resolve({ err: 'open' });
})
"""


async def tab(h, name):
    r = await h.ev("(() => { const b=[...document.querySelectorAll('.tab')]"
                   ".find(x=>x.textContent.trim()===%s); if(!b) return 'missing';"
                   " b.click(); return 'ok'; })()" % json.dumps(name))
    await asyncio.sleep(0.6)
    return r


async def upload_one(h, path):
    """Nahraje JEDEN soubor a počká, až se objeví nota.

    ⚠️ Záměrně NEPOUŽÍVÁ `Harness.set_file_input`: ta po CDP volání kontroluje
    `input.files.length`, a protože appka hned po převzetí dělá
    `e.target.value = ''`, přečte nulu a spustí ZÁLOŽNÍ cestu přes DataTransfer →
    soubor se nahraje DVAKRÁT. Přesně to sonda dělala (6 not místo 3) a vypadalo
    to jako chyba appky.

    ⚠️ A nepočítej `li.song`: ty v DOM nejsou, dokud nejsou rozbalené záložky
    autorů. Signálem je appčin vlastní overlay „Nahrávám noty…“ — objeví se
    synchronně v `onFiles` a zmizí po uložení do DB.
    """
    doc = await h.cdp("DOM.getDocument")
    node = await h.cdp("DOM.querySelector",
                       {"nodeId": doc["root"]["nodeId"], "selector": "input[type=file]"})
    await h.cdp("DOM.setFileInputFiles", {"files": [path], "nodeId": node["nodeId"]})
    await h.wait_for("!!document.querySelector('.upload-overlay')", 30,
                     "nahrávání začalo (overlay)")
    await h.wait_for("!document.querySelector('.upload-overlay')", 90,
                     "nahrávání dokončeno")
    await asyncio.sleep(0.4)


async def expand_authors(h):
    """Rozbalí záložky autorů — ale JEN ty ZAVŘENÉ.

    ⚠️ `.author-header` je PŘEPÍNAČ. Když se klikne na všechny, otevřené se
    zavřou a sonda pak měří prázdný DOM jako „rozbítou appku“ (přesně to se
    stalo: noty naskočily jen v krocích, kde byly náhodou otevřené).
    """
    await h.ev("""(() => {
      document.querySelectorAll('.author-group').forEach(g => {
        if (!g.querySelector('.songlist')) {
          const hh = g.querySelector('.author-header');
          if (hh) hh.click();
        }
      });
      return true;
    })()""")
    await asyncio.sleep(0.6)


async def arm_dialogs(h):
    """`prompt()`/`confirm()` v prohlížeči — v headless Chrome dialog zablokuje
    renderer, dokud se neodpoví. Override v JS je pro sondu spolehlivější."""
    return await h.ev(
        "(() => { window.__answer = '';"
        " if (!window.__realPrompt) { window.__realPrompt = window.prompt;"
        "   window.__realConfirm = window.confirm; }"
        " window.prompt = () => window.__answer;"
        " window.confirm = () => true; return 'ok'; })()")


async def set_answer(h, value):
    return await h.ev("(() => { window.__answer = %s; return 'ok'; })()" % json.dumps(value))


async def make_folder_in_list(h, name, as_sub_of=None):
    """Založí složku PŘÍMO V SEZNAMU (Jan: „vytváření složky by mělo být možné
    přímo v rootu") — tlačítkem „＋ Nová složka" pod složkami, nebo v řádku
    rodiče. Záložka „Složky" už neexistuje, takže se nikam nepřepíná.

    ⚠️ Odpověď na dialog nastav PŘED kliknutím. `prompt()` se vyhodnotí
    synchronně v obsluze kliknutí, takže odpověď nastavená po kliknutí dorazí
    pozdě — `createFolder` dostane prázdné jméno a složku vůbec nezaloží
    (sonda to hlásila jako „složky v DB chybí").
    """
    await set_answer(h, name)
    if as_sub_of:
        r = await h.ev(
            "(() => { const li=[...document.querySelectorAll('.folder-row')]"
            ".find(x=>{ const n=x.querySelector('.folder-name');"
            " return n && n.textContent.trim()===%s; });"
            " if(!li) return 'no-row';"
            " const b=[...li.querySelectorAll('button')].find(x=>(x.title||'').startsWith('Nová podsložka'));"
            " if(!b) return 'no-btn'; b.click(); return 'ok'; })()" % json.dumps(as_sub_of))
    else:
        r = await h.ev(
            "(() => { const li=document.querySelector('.folder-row.newfolder');"
            " if(!li) return 'no-new-row'; li.click(); return 'ok'; })()")
    print(f"   zakládám „{name}“:", r)
    await asyncio.sleep(1.1)


async def click_folder_row(h, name):
    return await h.ev(
        "(() => { const r=[...document.querySelectorAll('.folder-row')]"
        ".find(x=>x.textContent.includes(%s)); if(!r) return 'missing'; r.click(); return 'ok'; })()"
        % json.dumps(name))


async def click_crumb(h, name):
    return await h.ev(
        "(() => { const c=[...document.querySelectorAll('.crumb')]"
        ".find(x=>x.textContent.trim()===%s); if(!c) return 'missing'; c.click(); return 'ok'; })()"
        % json.dumps(name))


async def center_of(h, expr):
    return await h.ev("(() => { const el = %s; if (!el) return null;"
                      " const b = el.getBoundingClientRect();"
                      " return { x: Math.round(b.left + b.width/2), y: Math.round(b.top + b.height/2) }; })()"
                      % expr)


async def finger_drag(h, x0, y0, x1, y1, steps=12, r=12):
    await h.touch("touchStart", [(x0, y0, r)])
    await asyncio.sleep(0.12)
    for i in range(1, steps + 1):
        await h.touch("touchMove", [(x0 + (x1 - x0) * i / steps,
                                     y0 + (y1 - y0) * i / steps, r)])
        await asyncio.sleep(0.04)
    await h.touch("touchEnd", [])
    await asyncio.sleep(1.0)


GHOST = r"""
(() => {
  const g = document.querySelector('.drag-ghost');
  if (!g) return null;
  const b = g.getBoundingClientRect();
  return {
    text: g.querySelector('.dg-text') ? g.querySelector('.dg-text').textContent.trim() : null,
    target: g.querySelector('.dg-target') ? g.querySelector('.dg-target').textContent.trim() : null,
    x: Math.round(b.left + b.width / 2), y: Math.round(b.bottom),
    pointerEvents: getComputedStyle(g).pointerEvents,
  };
})()
"""

DRAG_MARKERS = r"""
(() => ({
  dragging: document.querySelectorAll('.song.dragging').length,
  hovered: document.querySelectorAll('.folder-row.drop, .group.drop, .crumb.drop').length,
}))()
"""


async def finger_drag_observed(h, x0, y0, x1, y1, steps=12, r=12, sample_at=1.0):
    """Tažení s ODBĚREM UPROSTŘED — jediný způsob, jak změřit zpětnou vazbu.

    Po `touchEnd` plaketka zmizí, takže kontrola až po tažení by neřekla nic
    o tom, co uživatel vidí BĚHEM něj (přesně to Janovi chybí).

    ⚠️ `sample_at` ber až na KONCI tahu (1.0). V půlce cesty je prst ještě mimo
    cílovou složku, takže zvýraznění cíle logicky chybí — a sonda by hlásila
    falešný FAIL „cíl se nezvýraznil“.
    """
    await h.touch("touchStart", [(x0, y0, r)])
    await asyncio.sleep(0.12)
    mid = None
    for i in range(1, steps + 1):
        f = i / steps
        await h.touch("touchMove", [(x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, r)])
        await asyncio.sleep(0.04)
        if mid is None and f >= sample_at:
            mid = {"ghost": await h.ev(GHOST), "markers": await h.ev(DRAG_MARKERS),
                   "at": {"x": round(x0 + (x1 - x0) * f), "y": round(y0 + (y1 - y0) * f)}}
    await h.touch("touchEnd", [])
    await asyncio.sleep(1.0)
    after = await h.ev(GHOST)
    return mid, after


async def main():
    ok = Check()
    async with Harness(TARGET) as h:
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await asyncio.sleep(0.8)
        if IS_LIVE:
            # ŽIVÝ WEB: PWA drží starý service worker a staré stránky v CacheStorage.
            # Bez odregistrování a smazání cache by sonda měřila PŘEDCHOZÍ verzi
            # a hlásila falešný FAIL („oprava nefunguje“).
            await h.ev("""(async () => {
              for (const r of await navigator.serviceWorker.getRegistrations()) await r.unregister();
              for (const k of await caches.keys()) await caches.delete(k);
              indexedDB.deleteDatabase('noty-app');
              return true;
            })()""", await_promise=True)
            await asyncio.sleep(1.0)
            print("cíl:", TARGET, "(živý web — SW a cache vyčištěny)")

        # --- ČISTÝ START. Dvě pasti naráz:
        #  1) `deleteDatabase` na appce, která drží spojení, zůstane „blocked“ —
        #     smaže se až s reloadem, proto druhý h.open().
        #  2) Předchozí běh mohl skončit v prohlížeči PDF (bez input[type=file]) —
        #     proto jdeme na '/' přes Page.navigate, ne přes h.open() na current URL.
        await h.ev("indexedDB.deleteDatabase('noty-app')")
        await asyncio.sleep(1.0)
        await h.cdp("Page.navigate", {"url": TARGET})
        await h.wait_for("!!document.querySelector('.search')", 40, "knihovna")
        await asyncio.sleep(1.4)
        await arm_dialogs(h)
        print("start:", await h.ev("location.pathname"),
              "| noty po resetu:", await h.ev("document.querySelectorAll('li.song').length"))

        # --- nahrát 3 noty (názvy z fixtury stačí; jde o strukturu, ne o jména) ---
        for i in range(3):
            await upload_one(h, _m.make_pdf(6, f"/tmp/noty-fs-{i}.pdf"))

        await tab(h, 'Noty')
        await expand_authors(h)
        st0 = await h.ev(LIB)
        print("\n--- 0) výchozí stav: noty leží v KOŘENI ---")
        print("   cesta:", [c["name"] for c in st0["crumbs"]], "| noty:", st0["songs"], "| skupiny autorů:", st0["groups"])
        ok("0) nahrané noty leží v kořeni knihovny", len(st0["songs"]) == 3, str(st0["songs"]))

        # ================= 1) zakládání složek PŘÍMO V SEZNAMU =================
        print("\n--- 1) zakládám Sborový, PODSLOŽKU Baroko a Sólový (bez záložky Složky) ---")
        ok("1) záložka „Složky“ už NEEXISTUJE",
           not await h.ev("!![...document.querySelectorAll('.tab')]"
                          ".find(t=>t.textContent.trim()==='Složky')"))
        ok("1) v seznamu je řádek „Nová složka“",
           await h.ev("document.querySelectorAll('.folder-row.newfolder').length") == 1)

        await make_folder_in_list(h, 'Sborový')
        await make_folder_in_list(h, 'Baroko', as_sub_of='Sborový')
        await make_folder_in_list(h, 'Sólový')

        db = await h.ev(DB, await_promise=True)
        f_by_name = {f["name"]: f for f in db["folders"]}
        print("   složky v DB:", json.dumps(db["folders"], ensure_ascii=False))
        sbor, bar, sol = f_by_name.get("Sborový"), f_by_name.get("Baroko"), f_by_name.get("Sólový")
        ok("1) všechny tři složky existují (i podsložka přes ＋)", bool(sbor and bar and sol),
           json.dumps(db["folders"], ensure_ascii=False))
        ok("1) Baroko má parentId na Sborový (zanoření je v datech)",
           bool(sbor and bar and bar["parentId"] == sbor["id"]),
           json.dumps([bar, sbor], ensure_ascii=False))
        ok("1) Baroko se v kořeni jako samostatná složka NEOBJEVÍ (je zanořené)",
           "Baroko" not in await h.ev("JSON.stringify([...document.querySelectorAll('.folder-row .folder-name')]"
                                      ".map(e=>e.textContent.trim()))"),
           await h.ev("JSON.stringify([...document.querySelectorAll('.folder-row .folder-name')]"
                      ".map(e=>e.textContent.trim()))"))
        if not (sbor and bar and sol):
            return ok.report()

        # ================= 2) obsah kořene =================
        print("\n--- 2) kořen: složky NAD notami ---")
        await tab(h, 'Noty')
        await expand_authors(h)
        st1 = await h.ev(LIB)
        print("   cesta:", [c["name"] for c in st1["crumbs"]])
        print("   složky:", st1["folderRows"], "| noty:", st1["songs"])
        ok("2) v kořeni jsou OBĚ kořenové složky (Baroko je zanořené, proto není)",
           sorted(r.split(' ')[0] for r in st1["folderRows"]) == ["Sborový", "Sólový"],
           str(st1["folderRows"]))
        ok("2) v kořeni jsou i noty, které nikam nepatří", len(st1["songs"]) == 3, str(st1["songs"]))
        ok("2) složky jsou v seznamu NAD notami",
           await h.ev("(() => { const f=document.querySelector('.folder-row');"
                      " const s=document.querySelector('li.song');"
                      " if(!f||!s) return false;"
                      " return f.getBoundingClientRect().top < s.getBoundingClientRect().top; })()"))

        # ================= 3) vstup do složky a prázdný stav =================
        print("\n--- 3) vcházím do Sólového (má být prázdný) ---")
        print("   klik na řádek:", await click_folder_row(h, 'Sólový'))
        await asyncio.sleep(0.8)
        st2 = await h.ev(LIB)
        print("   cesta:", [c["name"] for c in st2["crumbs"]], "| noty:", st2["songs"], "| hláška:", st2["empty"])
        ok("3) cesta ukazuje Noty / Sólový",
           [c["name"] for c in st2["crumbs"]] == ["Noty", "Sólový"],
           json.dumps([c["name"] for c in st2["crumbs"]], ensure_ascii=False))
        ok("3) prázdná složka to řekne a poradí, co dělat",
           bool(st2["empty"]) and st2["empty"].startswith("Tato složka je prázdná"), str(st2["empty"]))

        print("\n--- 3b) zpět drobečkovou cestou na kořen ---")
        print("   klik na drobeček:", await click_crumb(h, 'Noty'))
        await asyncio.sleep(0.8)
        await expand_authors(h)
        st3 = await h.ev(LIB)
        print("   cesta:", [c["name"] for c in st3["crumbs"]], "| noty:", st3["songs"])
        ok("3b) drobeček vrátil do kořene", len(st3["crumbs"]) == 1 and len(st3["songs"]) == 3,
           json.dumps(st3["songs"], ensure_ascii=False))

        # ================= 4) přesun TAŽENÍM =================
        print("\n--- 4) tažení noty do Sólového (prstem za úchyt) ---")
        await expand_authors(h)
        handle = await center_of(h, "document.querySelector('li.song .drag-handle')")
        target = await center_of(h, "[...document.querySelectorAll('.folder-row')].find(r=>r.textContent.includes('Sólový'))")
        print("   úchyt:", handle, "| cíl:", target)
        if not (handle and target):
            print("   (nenašla jsem úchyt nebo cíl — tažení přeskočeno)")
        else:
            mid, after = await finger_drag_observed(h, handle["x"], handle["y"], target["x"], target["y"])
            print("   BĚHEM tažení:", json.dumps(mid, ensure_ascii=False))
            print("   PO tažení (plaketka musí zmizet):", after)
            ghost = (mid or {}).get("ghost")
            markers = (mid or {}).get("markers") or {}
            ok("4) během tažení visí plaketka s názvem noty",
               bool(ghost) and bool(ghost.get("text")), json.dumps(ghost, ensure_ascii=False))
            ok("4) tažený řádek je vidět jako tažený (.dragging)",
               markers.get("dragging", 0) >= 1, json.dumps(markers, ensure_ascii=False))
            ok("4) cílová složka je zvýrazněná a plaketka hlásí její jméno",
               bool(ghost) and ghost.get("target") and "Sólový" in ghost["target"]
               and markers.get("hovered", 0) >= 1,
               json.dumps({"ghost": ghost, "markers": markers}, ensure_ascii=False))
            ok("4) plaketka nechytá dotyk (jinak by hledání cíle pod ní selhalo)",
               bool(ghost) and ghost.get("pointerEvents") == "none",
               str(ghost and ghost.get("pointerEvents")))
            ok("4) po puštění plaketka zmizí", after is None, str(after))

            st4 = await h.ev(LIB)
            db = await h.ev(DB, await_promise=True)
            print("   toast:", st4["toast"], "| noty v kořeni:", st4["songs"])
            print("   noty v DB:", json.dumps(db["songs"], ensure_ascii=False))
            ok("4) po tažení je nota v Sólovém (a v kořeni ubyla)",
               len(st4["songs"]) == 2
               and sum(1 for s in db["songs"] if (s["folderId"] or None) == sol["id"]) == 1,
               json.dumps(db["songs"], ensure_ascii=False))
            ok("4) přesun potvrdila hláška",
               bool(st4["toast"]) and "Sólový" in (st4["toast"] or ""), str(st4["toast"]))

        # ================= 5) přesun do ZANOŘENÉ složky =================
        print("\n--- 5) přesun do zanořeného Baroka (uvnitř Sborový) ---")
        # Nejprve je potřeba mít notu VE Sborovém — tažením z kořene.
        await click_crumb(h, 'Noty')
        await asyncio.sleep(0.7)
        await expand_authors(h)
        handle = await center_of(h, "document.querySelector('li.song .drag-handle')")
        target = await center_of(h, "[...document.querySelectorAll('.folder-row')].find(r=>r.textContent.includes('Sborový'))")
        print("   do Sborového: z", handle, "na", target)
        await finger_drag(h, handle["x"], handle["y"], target["x"], target["y"])

        print("   vstup do Sborový:", await click_folder_row(h, 'Sborový'))
        await asyncio.sleep(0.8)
        await expand_authors(h)
        st5 = await h.ev(LIB)
        print("   cesta:", [c["name"] for c in st5["crumbs"]], "| složky:", st5["folderRows"], "| noty:", st5["songs"])
        ok("5) uvnitř Sborového je vidět PODSLOŽKA Baroko",
           any("Baroko" in r for r in st5["folderRows"]), str(st5["folderRows"]))
        ok("5) uvnitř Sborového je i nota k přetažení", bool(st5["songs"]), str(st5["songs"]))
        if st5["songs"] and any("Baroko" in r for r in st5["folderRows"]):
            handle = await center_of(h, "document.querySelector('li.song .drag-handle')")
            target = await center_of(h, "[...document.querySelectorAll('.folder-row')].find(r=>r.textContent.includes('Baroko'))")
            print("   do Baroka: z", handle, "na", target)
            await finger_drag(h, handle["x"], handle["y"], target["x"], target["y"])
            db = await h.ev(DB, await_promise=True)
            print("   noty v DB:", json.dumps(db["songs"], ensure_ascii=False))
            ok("5) nota je v ZANOŘENÉ složce Baroko",
               any((s["folderId"] or None) == bar["id"] for s in db["songs"]),
               json.dumps(db["songs"], ensure_ascii=False))

        # ================= 6) hledání napříč knihovnou =================
        print("\n--- 6) hledání napříč knihovnou (stojím uvnitř Sborového) ---")
        await h.set_value(".search", "noty-fs")
        await asyncio.sleep(0.8)
        await expand_authors(h)
        st6 = await h.ev(LIB)
        print("   nalezeno:", st6["songs"], "| cesty:", st6["paths"], "| skupiny:", st6["groups"])
        ok("6) hledání najde i noty z JINÝCH složek (ne jen z aktuální)",
           len(st6["songs"]) == 3, str(st6["songs"]))
        ok("6) u každé nalezené noty je vidět její CELÁ cesta",
           len(st6["paths"]) == 3 and all(p.replace('·', '').strip() for p in st6["paths"]),
           str(st6["paths"]))
        ok("6) cesta u zanořené noty obsahuje obě úrovně",
           any("Baroko" in p and "Sborový" in p for p in st6["paths"]),
           str(st6["paths"]))
        await h.set_value(".search", "")
        await asyncio.sleep(0.6)

        # ================= 7) smazání složky s podsložkami =================
        print("\n--- 7) mažu Sborový (má uvnitř Baroko i notu) — z řádku v seznamu ---")
        # Do smazané složky se nejdřív vstoupí, aby šlo smazat její řádek
        # (řádek Sborový je v kořeni, takže stačí být v kořeni).
        await click_crumb(h, 'Noty')
        await asyncio.sleep(0.7)
        before = await h.ev(DB, await_promise=True)
        print("   klik 🗑 v řádku Sborový:",
              await h.ev("""(() => { const li=[...document.querySelectorAll('.folder-row')]
                .find(x=>x.querySelector('.folder-name').textContent.includes('Sborový'));
                if(!li) return 'no-row';
                const b=[...li.querySelectorAll('button')].find(x=>(x.title||'').startsWith('Smazat složku'));
                if(!b) return 'no-btn'; b.click(); return 'ok'; })()"""))
        await asyncio.sleep(1.4)
        after = await h.ev(DB, await_promise=True)
        print("   složky po smazání:", json.dumps(after["folders"], ensure_ascii=False))
        print("   noty po smazání:", json.dumps(after["songs"], ensure_ascii=False))
        ok("7) smazaly se i PODSLOŽKY (Baroko)",
           not any(f["name"] == "Baroko" for f in after["folders"]),
           json.dumps(after["folders"], ensure_ascii=False))
        ok("7) žádná NOTA se nesmazala",
           len(after["songs"]) == len(before["songs"]),
           f"před {len(before['songs'])}, po {len(after['songs'])}")
        ok("7) noty z podsložek jsou uvolněné do kořene",
           all(s["folderId"] is None or s["folderId"] not in {sbor["id"], bar["id"]}
               for s in after["songs"]),
           json.dumps(after["songs"], ensure_ascii=False))

        # ================= 8) po reloadu =================
        print("\n--- 8) reload: složky i noty musí sedět ---")
        await h.open()
        await h.wait_for("document.querySelectorAll('.folder-row, li.song').length > 0", 40, "knihovna po reloadu")
        await asyncio.sleep(1.2)
        await tab(h, 'Noty')
        await expand_authors(h)
        st8 = await h.ev(LIB)
        print("   kořen po reloadu – složky:", st8["folderRows"], "| noty:", st8["songs"])
        ok("8) po reloadu zbyl jen Sólový (Baroko i Sborový jsou pryč)",
           sorted(r.split(' ')[0] for r in st8["folderRows"]) == ["Sólový"],
           str(st8["folderRows"]))
        ok("8) noty, které zůstaly, se po reloadu ukazují",
           sorted(st8["songs"]) == ["noty-fs-1", "noty-fs-2"],
           str(st8["songs"]))
        ok("8) nota přesunutá do Sólového tam po reloadu pořád je (v kořeni není)",
           "noty-fs-0" not in st8["songs"], str(st8["songs"]))

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
