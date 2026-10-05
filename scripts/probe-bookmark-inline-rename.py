#!/usr/bin/env python3
"""Sonda: úprava názvu záložky PŘÍMO NA ŘÁDKU (ne v horním inputu pro novou).

Ověřuje:
  1) horní pole zůstane při editaci PRÁZDNÉ a má placeholder pro NOVOU záložku
  2) tužka na řádku vloží input DO TOHOTO ŘÁDKU (řádek obsahuje input)
  3) napsaný text se uloží (IndexedDB) a horní pole se nezmění
  4) ✕ (Zrušit) zahodí změnu (DB si drží původní název)
  5) Enter na řádku uloží
"""
import asyncio
import importlib.util
import json
import os
import time
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
CDP_BASE = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")


def _load_harness():
    for cand in (
        os.path.join(os.path.expanduser("~"), "noty-app", "cdp-e2e-harness.py"),
        "/home/martin_fabian/noty-app/cdp-e2e-harness.py",
    ):
        if os.path.exists(cand):
            spec = importlib.util.spec_from_file_location("cdp_e2e_harness", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise SystemExit("nenalezen cdp-e2e-harness.py")


_m = _load_harness()
_m.CDP_HTTP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9222")  # harness default 9223; Chrome běží na 9222
Harness, Check = _m.Harness, _m.Check


def fresh_harness():
    req = urllib.request.Request(f"{CDP_BASE}/json/new?about:blank", method="PUT")
    info = json.loads(urllib.request.urlopen(req).read())
    time.sleep(0.8)
    h = Harness(_m.APP_URL)
    h._fresh_target = info.get("id")
    return h


# --- JS helpers -------------------------------------------------------------
ROW_STATE = r"""
(() => {
  const rows = [...document.querySelectorAll('.jp-list .jp-item')];
  return rows.map(r => ({
    text: r.querySelector('.jp-item-label') ? r.querySelector('.jp-item-label').textContent.trim() : null,
    hasTopInput: !!r.querySelector('.jp-input'),
    editVal: r.querySelector('.jp-input') ? r.querySelector('.jp-input').value : null,
    focused: r.querySelector('.jp-input') ? document.activeElement === r.querySelector('.jp-input') : false,
    pencilTitle: r.querySelector('.jp-icon') ? r.querySelector('.jp-icon').getAttribute('title') : null,
  }));
})()
"""

DBS = r"""
(async () => {
  const store = await new Promise((res, rej) => {
    const rq = indexedDB.open('noty-app');
    rq.onsuccess = () => res(rq.result); rq.onerror = () => rej(rq.error);
  });
  const rows = await new Promise((res, rej) => {
    const tx = store.transaction('bookmarks', 'readonly');
    const out = [];
    tx.objectStore('bookmarks').openCursor().onsuccess = (e) => {
      const c = e.target.result;
      if (c) { out.push(c.value); c.continue(); } else res(out);
    };
    tx.onerror = () => rej(tx.error);
  });
  store.close();
  return JSON.stringify(rows);
})()
"""


async def bookmark_state(h):
    return json.loads(await h.ev(DBS, await_promise=True))


async def make_two_bookmarks(h):
    """Záložka na str. 1 a 2 — přes UI (panel 🔖 + horní pole)."""
    await h.click(".tb-btn")  # první tb-btn je Zpět -> ne! použijeme title selektor
    return None


async def main():
    c = Check()
    async with fresh_harness() as h:
        await h.open()  # NEJDŘÍV navigovat — deleteDatabase na about:blank je SecurityError
        try:
            await h.ev("indexedDB.deleteDatabase('noty-app')")
        except Exception:
            pass
        await asyncio.sleep(0.6)
        await h.open()
        await h.open_song(pages=6, reset=False)
        # --- přidej dvě záložky (str. 1 a str. 3) --------------------------
        await h.ev("document.querySelector('.tb-btn[title=\\\"Přidat záložku na tuto stránku\\\"]').click()")
        await h.wait_for("!!document.querySelector('.jump-panel .jp-input')", 10, "panel záložky")
        await h.set_value(".jump-panel .jp-input", "Coda")
        await h.ev("document.querySelector('.jump-panel .jp-btn.primary').click()")
        await h.wait_for("document.querySelectorAll('.bookmark-strip .bookmark-btn').length === 1", 10, "1. záložka")

        await h.goto(3)
        await h.ev("document.querySelector('.tb-btn[title=\\\"Přidat záložku na tuto stránku\\\"]').click()")
        await h.wait_for("!!document.querySelector('.jump-panel .jp-input')", 10, "panel záložky 2")
        await h.set_value(".jump-panel .jp-input", "Solo")
        await h.ev("document.querySelector('.jump-panel .jp-btn.primary').click()")
        await h.wait_for("document.querySelectorAll('.bookmark-strip .bookmark-btn').length === 2", 10, "2. záložka")

        # --- otevři panel záložek a klikni na tužku u PRVNÍHO řádku ------
        await h.ev("document.querySelector('.tb-btn[title=\\\"Přidat záložku na tuto stránku\\\"]').click()")
        await h.wait_for("!!document.querySelector('.jump-panel .jp-list')", 10, "seznam záložek")

        top_title = await h.ev("document.querySelector('.jump-panel .jp-title').textContent.trim()")
        top_placeholder = await h.ev("document.querySelector('.jump-panel .jp-input').placeholder")
        c("horní panel hlásí 'Nová záložka'", top_title == "Nová záložka", repr(top_title))
        c("horní pole je pro NOVOU (placeholder)", "např. Coda" in (top_placeholder or ""), repr(top_placeholder))

        rows = await h.ev(ROW_STATE)
        c("dva řádky záložek", len(rows) == 2, str(rows))

        # tužka = první .jp-icon v řádku
        await h.ev("document.querySelectorAll('.jp-list .jp-item')[0].querySelector('.jp-icon').click()")
        await asyncio.sleep(0.5)

        top_val = await h.ev("document.querySelector('.jump-panel .jp-input').value")
        c("horní pole zůstalo PRÁZDNÉ (editace se tam nepřesunula)", top_val == "", repr(top_val))

        rows = await h.ev(ROW_STATE)
        c("řádek 0 má input NA MÍSTĚ", rows[0]["hasTopInput"], str(rows[0]))
        c("řádek 0 má předplněný název", rows[0]["editVal"] == "Coda", repr(rows[0]["editVal"]))
        c("řádek 0 je fokusovaný", rows[0]["focused"], str(rows[0]))
        c("řádek 1 NEMÁ input", not rows[1]["hasTopInput"], str(rows[1]))
        c("řádek 1 si drží název", "Solo" in (rows[1]["text"] or ""), str(rows[1]))
        c("řádek 0 pořád ukazuje stránku",
          rows[0]["text"] and rows[0]["text"].startswith("str."), str(rows[0]))
        c("v editaci je potvrzovací tlačítko",
          await h.ev("document.querySelectorAll('.jp-list .jp-item')[0].querySelectorAll('.jp-icon').length") == 2)

        # --- napiš nový název a stiskni Enter (uloží) ---------------------
        await h.set_value(".jp-list .jp-item .jp-input", "Coda II")
        await h.ev("(() => { const el = document.querySelector('.jp-list .jp-item .jp-input');"
                   " el.dispatchEvent(new KeyboardEvent('keyup', {key: 'Enter', bubbles: true})); return true; })()")
        await asyncio.sleep(0.8)

        rows = await h.ev(ROW_STATE)
        c("po Enteru input zmizel", not rows[0]["hasTopInput"], str(rows[0]))
        c("po Enteru je na řádku nový název", "Coda II" in (rows[0]["text"] or ""), str(rows[0]))
        db = await bookmark_state(h)
        items = db[0]["items"] if db else []
        c("IndexedDB má nový název", any(i.get("label") == "Coda II" for i in items), str(items))
        c("stránka se nezměnila", any(i.get("label") == "Coda II" and i.get("page") == 0 for i in items), str(items))
        c("řádek zůstal v seznamu i po uložení",
          any("Coda II" in (r["text"] or "") for r in await h.ev(ROW_STATE)), str(await h.ev(ROW_STATE)))

        # --- ✕ (Zrušit) musí změnu zahodit -------------------------------
        await h.ev("document.querySelectorAll('.jp-list .jp-item')[1].querySelector('.jp-icon').click()")
        await asyncio.sleep(0.4)
        await h.set_value(".jp-list .jp-item .jp-input", "NEMÁ SE ULOŽIT")
        # druhé tlačítko v řádku = ✕ Zrušit
        await h.ev("document.querySelectorAll('.jp-list .jp-item')[1].querySelectorAll('.jp-icon')[1].click()")
        await asyncio.sleep(0.8)
        db = await bookmark_state(h)
        items = db[0]["items"] if db else []
        c("Zrušit zahodí změnu (DB)",
          not any(i.get("label") == "NEMÁ SE ULOŽIT" for i in items), str(items))
        rows = await h.ev(ROW_STATE)
        c("Zrušit vrátí řádek bez inputu", not rows[1]["hasTopInput"], str(rows[1]))
        c("Zrušit vrátí původní název", "Solo" in (rows[1]["text"] or ""), str(rows[1]))

    return c.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
