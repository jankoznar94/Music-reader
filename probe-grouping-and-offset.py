#!/usr/bin/env python3
"""Ověření dvou nových funkcí na ŽIVÉM dev serveru (stav, ne kód).

A) Přepínač seskupení podle skladatelů v přehledu souborů.
B) Posun číslování stránek (jiné vydání / noty začínající vyšší stránkou):
   - zadání „první stránka má číslo N" v dialogu Přejít na stránku
   - tlačítka − / + v panelu Odebrat stránky
   - počítadlo, mini atury i skok na zadanou stránku musí sedět
   - posun se ukládá na skladbu (přežije reload)

Vkládání PDF jde přes DataTransfer — CDP `DOM.setFileInputFiles` v této
Chrome soubor nevloží (input.files zůstane prázdný). Každý dotaz má timeout.
"""
import asyncio
import base64
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
Harness, Check = m.Harness, m.Check

SONG_ID = r"""
new Promise((resolve) => {
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const r = q.result.transaction('songs', 'readonly').objectStore('songs').getAll();
    r.onsuccess = () => resolve(r.result.length ? r.result[0].id : null);
    r.onerror = () => resolve(null);
  };
  q.onerror = () => resolve(null);
})
"""

SONG_ROW = r"""
new Promise((resolve) => {
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const r = q.result.transaction('songs', 'readonly').objectStore('songs').getAll();
    r.onsuccess = () => resolve(r.result.length
      ? {id: r.result[0].id, offset: r.result[0].pagesOffset} : null);
  };
})
"""


async def safe(h, expr, label, timeout=20, promise=False):
    try:
        return await asyncio.wait_for(h.ev(expr, await_promise=promise), timeout)
    except asyncio.TimeoutError:
        print("TIMEOUT", label)
        return None


async def attach_pdf(h, path):
    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode()
    js = (
        "(() => { const bin = atob(%s); const u = new Uint8Array(bin.length);"
        " for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);"
        " const dt = new DataTransfer();"
        " dt.items.add(new File([u], %s, {type: 'application/pdf'}));"
        " const el = document.querySelector('input[type=file]');"
        " el.files = dt.files;"
        " el.dispatchEvent(new Event('change', {bubbles: true}));"
        " return el.files.length; })()"
        % (json.dumps(b64), json.dumps(os.path.basename(path))))
    return await h.ev(js)


async def wait_for(h, expr, timeout=60, label="", promise=False):
    t0 = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - t0 < timeout:
        v = await safe(h, expr, label, 15, promise)
        if v:
            return v
        await asyncio.sleep(1.0)
    return None


async def main():
    ok = Check()
    pdf = m.make_pdf(6)
    async with Harness() as h:
        await h.reset_db()
        await h.set_tablet()

        # ---------- A) PŘEHLED: přepínač seskupení -----------------------
        await attach_pdf(h, pdf)
        got = await wait_for(h, "document.querySelectorAll('.author-group').length > 0",
                             90, "upload")
        ok("PDF se nahrálo (skupiny autorů existují)", bool(got))
        if not got:
            return ok.report()

        exists = await safe(h, "!!document.querySelector('.group-toggle')", "toggle exists")
        ok("tlačítko seskupení je v toolbaru", bool(exists))
        ok("tlačítko je ve výchozím stavu ZAPNUTÉ",
           bool(await safe(h, "document.querySelector('.group-toggle').classList.contains('on')",
                           "toggle on")))

        await safe(h, "document.querySelectorAll('.author-header').length", "headers")
        n_before = await safe(h, "document.querySelectorAll('.author-header').length", "h0")
        await safe(h, "document.querySelector('.group-toggle').click()", "click toggle")
        await asyncio.sleep(0.5)
        n_headers = await safe(h, "document.querySelectorAll('.author-header').length", "h1")
        o = await safe(h, "document.querySelector('.group-toggle').classList.contains('on')",
                       "toggle state")
        ok("vypnutím zmizí hlavičky autorů (plochý seznam)", n_headers == 0,
           f"hlaviček {n_before} -> {n_headers}, on={o}")

        await safe(h, "document.querySelector('.group-toggle').click()", "click back")
        await asyncio.sleep(0.5)
        n_after = await safe(h, "document.querySelectorAll('.author-header').length", "h2")
        ok("zapnutím se záložky vrátí", n_after == n_before,
           f"hlaviček {n_before} -> {n_after}")

        # ---------- B) PROHLÍŽEČ: posun číslování -----------------------
        row = await safe(h, SONG_ROW, "song row", 20, True)
        sid = row["id"] if row else None
        if not sid:
            ok("našla se nahraná skladba", False)
            return ok.report()
        await h.cdp("Page.navigate", {"url": "http://localhost:5173/prohlizec/" + sid})
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="viewer")
        await h.wait_for("!document.querySelector('.viewer-loading')", timeout=40, label="page")
        await asyncio.sleep(1.5)

        counter = await safe(h, "document.querySelector('.tb-page').textContent.trim()", "c0")
        ok("počítadlo začíná na 1 / 6", counter.startswith("1 / 6"), counter)

        # zadání první stránky = 7  (offset +6)
        await safe(h, "document.querySelector('.tb-page').click()", "open dialog")
        await asyncio.sleep(0.4)
        has_input = await safe(h, "!!document.querySelector('.pg-offset-input')", "offset input")
        ok("dialog nabízí pole pro první stránku", bool(has_input))
        await h.set_value(".pg-offset-input", "7")
        await safe(h, "document.querySelector('.pg-offset .pg-btn').click()", "apply")
        await asyncio.sleep(0.6)
        counter = await safe(h, "document.querySelector('.tb-page').textContent.trim()", "c1")
        ok("po zadání první stránky 7 počítadlo hlásí 7 / 12", counter.startswith("7 / 12"),
           counter)

        # zavřít dialog, zkusit skok na zadanou stránku 8 (= 2. stránka PDF, slot 1)
        await safe(h, "document.querySelector('.pg-btn') && "
                      "[...document.querySelectorAll('.pg-btn')].find(b => b.textContent.trim() === 'Zavřít').click()",
                   "close dialog")
        await asyncio.sleep(0.3)
        await safe(h, "document.querySelector('.tb-page').click()", "open dialog 2")
        await asyncio.sleep(0.4)
        await h.set_value(".pg-input", "8")
        await safe(h, "[...document.querySelectorAll('.pg-btn')]"
                      ".find(b => b.textContent.trim() === 'Přejít').click()", "go")
        await asyncio.sleep(1.2)
        counter = await safe(h, "document.querySelector('.tb-page').textContent.trim()", "c2")
        ok("zadání čísla 8 sedí na stránku s číslem 8 (ne 8. list)", counter.startswith("8 / 12"),
           counter)

        # mini atury musí nést čísla 7..12
        await safe(h, "[...document.querySelectorAll('.tb-btn')]"
                      ".find(b => (b.title || '').includes('Slider')).click()", "open slider")
        await asyncio.sleep(1.2)
        nums = await safe(h, "[...document.querySelectorAll('.thumb-num')]"
                             ".map(e => e.textContent.trim()).join(',')", "thumbs")
        ok("mini atury číslují 7,8,9,10,11,12", nums == "7,8,9,10,11,12", str(nums))

        # tlačítka − / + posunou počítadlo
        await safe(h, "[...document.querySelectorAll('.tb-btn')]"
                      ".find(b => (b.title || '').includes('Odebrat stránky')).click()", "open pages")
        await asyncio.sleep(0.4)
        b = await safe(h, "!![...document.querySelectorAll('.zp-btn')]"
                          ".find(x => (x.title || '').includes('Posunout číslování o 1 výš'))", "plus")
        ok("v panelu je tlačítko pro posun číslování", bool(b))
        await safe(h, "[...document.querySelectorAll('.zp-btn')]"
                      ".find(x => (x.title || '').includes('Posunout číslování o 1 výš')).click()",
                   "click plus")
        await asyncio.sleep(0.6)
        counter = await safe(h, "document.querySelector('.tb-page').textContent.trim()", "c3")
        ok("tlačítko + posune číslování na 9 / 13", counter.startswith("9 / 13"), counter)

        # uložení na skladbu: přežije reload
        await asyncio.sleep(0.6)
        saved = await safe(h, SONG_ROW, "song row 2", 20, True)
        ok("posun se uložil na skladbu (pagesOffset = 7)",
           bool(saved) and saved.get("offset") == 7, json.dumps(saved))

    return ok.report()


asyncio.run(main())
