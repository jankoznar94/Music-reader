#!/usr/bin/env python3
"""Sonda: vyskočí čtečka při listování do seznamu skladeb? (Jan, Oct 2026)

Jan: „Při pokusu o listování na další nebo předchozí stránku se teď stává, že
appka vyskočí do seznamu skladeb. To se Dříve nikdy nedělo."

Appka umí do knihovny jen dvěma cestami:
  * `goBack()` (tlačítko Zpět v liště) → `router.push('/')`
  * `onMounted`: `if (!s) router.push('/')` (skladba v IndexedDB není)
plus prohlížeč sám (gesto zpět / tlačítko zpět) → historie.

Sonda proto:
  1) Instrumentuje `history.pushState/replaceState` a `popstate` — každý zápis
     do historie se zaloguje i s krátkým stackem, takže je vidět, KDO navigaci
     vyvolal.
  2) Listuje krajem displeje (tapy i swipy, vlevo i vpravo, v režimu čtení,
     v anotaci, s odebranou stránkou a se skokem v číslování) a po každém kroku
     kontroluje `location.pathname` + jestli je na obrazovce `.viewer`, nebo
     knihovna (`.library`).
  3) Totéž se sestavou (skupina) o dvou skladbách — listování na poslední
     stránce přepíná skladbu.

Použití:  scripts/run-probe-fresh.sh scripts/probe-nav-jump-to-library.py
"""
import asyncio
import importlib.util
import json
import os
import urllib.request

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")


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
_m.APP_URL = os.environ.get("NOTY_APP", _m.APP_URL)
if os.environ.get("NOTY_CDP"):
    _m.CDP_HTTP = CDP
Harness = _m.Harness
Check = _m.Check
make_pdf = _m.make_pdf


async def fresh_harness():
    req = urllib.request.Request(f"{CDP}/json/new?about:blank", method="PUT")
    info = json.loads(urllib.request.urlopen(req).read())
    await asyncio.sleep(0.8)
    h = Harness(_m.APP_URL)
    h._fresh_target = info.get("id")
    return h


INSTRUMENT = r"""
(() => {
  if (window.__navlog) return 'already';
  window.__navlog = [];
  const stamp = (kind, url) => window.__navlog.push({
    kind, url: String(url), href: location.href,
    stack: String((new Error().stack) || '').split('\n').slice(1, 5).join(' || ')
  });
  const p = history.pushState.bind(history), r = history.replaceState.bind(history);
  history.pushState = (s, t, u) => { stamp('pushState', u); return p(s, t, u); };
  history.replaceState = (s, t, u) => { stamp('replaceState', u); return r(s, t, u); };
  window.addEventListener('popstate', () => stamp('popstate', location.href));
  return 'installed';
})()
"""

SNAP = r"""
(() => ({
  href: location.pathname + location.search,
  viewer: !!document.querySelector('.viewer'),
  library: !!document.querySelector('.library'),
  page: (document.querySelector('.tb-page') || {}).textContent || null,
  nav: (window.__navlog || []).length
}))()
"""


async def snap(h):
    return await h.ev(SNAP)


async def navlog(h):
    return json.loads(await h.ev("JSON.stringify(window.__navlog || [])"))


def _report(ok, label, before, after, logbefore):
    same = before["href"] == after["href"] and after["viewer"] and not after["library"]
    ok(f"{label} (zůstává v notách)",
       same, f"{before['href']} p{before['page']} -> {after['href']} p{after['page']}"
            f" viewer={after['viewer']} library={after['library']}"
            f" navlog+{after['nav'] - logbefore}")
    return after["page"]


async def exercise(h, ok, label, steps=6, annot=False):
    """Střídavě listuje krajem vlevo/vpravo. Vrací True, když appka zůstala."""
    g = await h.geo()
    left_x = g["left"] + 22
    right_x = g["left"] + g["w"] - 22
    y = g["barBottom"] + 200
    keep = True
    for i in range(steps):
        b = await snap(h)
        if i % 2 == 0:
            await h.finger_tap(right_x, y)
        else:
            await h.finger_tap(left_x, y)
        a = await snap(h)
        if not (a["viewer"] and not a["library"] and a["href"] == b["href"]):
            keep = False
            await _report_async(ok, f"{label}: tap kraj #{i + 1}", b, a, b["nav"])
    # swipy
    for i in range(2):
        b = await snap(h)
        if i == 0:
            await h.finger_swipe(right_x - 4, y, right_x - 160, y)
        else:
            await h.finger_swipe(left_x + 4, y, left_x + 160, y)
        a = await snap(h)
        if not (a["viewer"] and not a["library"] and a["href"] == b["href"]):
            keep = False
            await _report_async(ok, f"{label}: swipe kraj #{i + 1}", b, a, b["nav"])
    if keep:
        a = await snap(h)
        ok(f"{label}: 8 listovacích gest zůstává v notách", True,
           f"{a['href']} p{a['page']} navlog+{a['nav']}")
    return keep


async def _report_async(ok, label, b, a, logbefore):
    ok(label + " (zůstává v notách)", False,
       f"{b['href']} p{b['page']} -> {a['href']} p{a['page']} viewer={a['viewer']}"
       f" library={a['library']} navlog+{a['nav'] - logbefore}")


async def main():
    ok = Check()
    async with await fresh_harness() as h:
        await h.open()
        await h.open_song(pages=8)
        await h.ev(INSTRUMENT)
        song_id = (await snap(h))["href"].split("/prohlizec/")[1].split("?")[0]
        print("otevřená skladba:", song_id)

        # --- A) režim čtení, čistá skladba -----------------------------------
        await exercise(h, ok, "čtení")

        # --- B) anotační režim ----------------------------------------------
        await h.annot_toggle()
        await exercise(h, ok, "anotace")
        await h.annot_toggle()

        # --- C) odebraná stránka (nová funkce) ------------------------------
        await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                   ".find(x => (x.title || '').startsWith('Odebrat stránky')); b && b.click(); return true; })()")
        await asyncio.sleep(0.4)
        await h.click(".zoom-panel .zp-btn")
        await asyncio.sleep(0.8)
        print("odebrané stránky:", await h.ev("document.querySelector('.pages-list') ? 'panel' : '?'"))
        await exercise(h, ok, "odebraná stránka")

        # --- D) skok v číslování (nová funkce) ------------------------------
        await h.click(".tb-page")
        await asyncio.sleep(0.4)
        await h.set_value(".pg-offset-input", "9")
        await h.ev("(() => { const b = [...document.querySelectorAll('.pg-btn')]"
                   ".find(x => x.textContent.includes('Nastavit odsud')); b && b.click(); return true; })()")
        await asyncio.sleep(0.8)
        await h.ev("(() => { const b = [...document.querySelectorAll('.pg-btn')]"
                   ".find(x => x.textContent.trim() === 'Zavřít'); b && b.click(); return true; })()")
        await asyncio.sleep(0.4)
        await exercise(h, ok, "skok v číslování")

        # --- E) sestava o dvou skladbách ------------------------------------
        # Nahrát druhý PDF umí jen knihovna → přejít na '/', nahrát a vrátit se
        # do čtečky přes ?group= (přesně tak, jak to dělá uživatel ze sestavy).
        pdf2 = make_pdf(3, "/tmp/noty-fixture-b.pdf")
        await h.cdp("Page.navigate", {"url": _m.APP_URL})
        await h.wait_for("!!document.querySelector('.library')", timeout=30, label="knihovna")
        await asyncio.sleep(1.0)
        await h.set_file_input("input[type=file]", pdf2)
        await h.wait_for("document.querySelectorAll('.author-group').length > 0", timeout=60,
                         label="PDF 2")
        await asyncio.sleep(2.5)
        ids = json.loads(await h.ev(
            "JSON.stringify([...document.querySelectorAll('li.song')].map(x => x.dataset.id || ''))"))
        print("skladby v DB:", ids)
        gid = await h.ev(
            "(() => { return new Promise(res => { const r = indexedDB.open('noty-app');"
            " r.onsuccess = () => { const db = r.result;"
            "   const tx = db.transaction('songs', 'readonly');"
            "   const q = tx.objectStore('songs').getAll();"
            "   q.onsuccess = () => { const all = q.result.map(s => s.id);"
            "     const g = { id: 'probe-group-1', name: 'Sonda', songIds: all, createdAt: Date.now() };"
            "     const tx2 = db.transaction('groups', 'readwrite');"
            "     tx2.objectStore('groups').put(g);"
            "     tx2.oncomplete = () => res(JSON.stringify(all)); }; }; }) })()",
            await_promise=True)
        print("sestava:", gid)
        await h.ev(f"window.__navlog = []")
        await h.ev(f"location.hash = ''")
        await h.cdp("Page.navigate", {"url": f"{_m.APP_URL}prohlizec/{song_id}?group=probe-group-1"})
        await h.wait_for("!!document.querySelector('.tb-grp')", timeout=30, label="skupina")
        await asyncio.sleep(1.0)
        await h.ev(INSTRUMENT)
        grp_before = await h.ev("document.querySelector('.tb-grp').textContent.trim()")
        print("sestava v liště:", grp_before)
        await exercise(h, ok, "sestava")

        log = await navlog(h)
        print("\n--- historie (co kdo zapsal) ---")
        for e in log:
            print(" ", e["kind"], e["url"], "|", e["stack"][:180])
        if not log:
            print("  (žádný zápis do historie)")

    return ok.report()


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except (ConnectionRefusedError, OSError) as exc:
        raise SystemExit(f"Chrome na {CDP} neodpovídá ({exc})")
