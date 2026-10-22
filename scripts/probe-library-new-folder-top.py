#!/usr/bin/env python3
"""Řádek „Nová složka" je v přehledu souborů NAD všemi složkami a pořád funguje.

1. otevře knihovnu, založí dvě složky (prompt přes override)
2. první řádek seznamu složek musí být „Nová složka" a musí být výš než složky
3. klepnutí na něj založí další složku (nezůstalo jen jako dekorace)
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")


def _load():
    spec = importlib.util.spec_from_file_location(
        "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.CDP_HTTP = CDP
    return m


m = _load()
Harness, Check = m.Harness, m.Check

ROWS = """(() => {
  const rows = [...document.querySelectorAll('.folderlist .folder-row')];
  return JSON.stringify(rows.map(r => ({
    name: (r.querySelector('.folder-name') || {}).textContent,
    newfolder: r.classList.contains('newfolder'),
    top: Math.round(r.getBoundingClientRect().top),
  })));
})()"""

NEW_FOLDER = """(name => {
  window.prompt = () => name;
  const r = document.querySelector('.folderlist .folder-row.newfolder');
  if (!r) return 'missing';
  r.click();
  return 'ok';
})"""


async def add_folder(h, name):
    return await h.ev(NEW_FOLDER + "(" + json.dumps(name) + ")")


async def rows(h):
    return json.loads(await h.ev(ROWS))


async def main():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await asyncio.sleep(1.0)
        # knihovna je výchozí obrazovka; ujistit se, že jsme na záložce Noty
        await h.ev("(() => { const t=[...document.querySelectorAll('.tab')]"
                   ".find(x=>x.textContent.trim()==='Noty'); if (t) t.click(); return 1; })()")
        await asyncio.sleep(0.4)

        print("zakládám A:", await add_folder(h, "Test A"))
        await h.wait_for("!!document.querySelector('.folder-row[data-folder-drop]')", 10, "složka A")
        await asyncio.sleep(0.4)
        await add_folder(h, "Test B")
        await h.wait_for("document.querySelectorAll('.folder-row[data-folder-drop]').length >= 2",
                         10, "složka B")
        await asyncio.sleep(0.4)

        r = await rows(h)
        print("řádky:", r)
        ok("první řádek je Nová složka", bool(r) and r[0]["newfolder"] is True, str(r[:1]))
        ok("Nová složka je NAD ostatními složkami",
           bool(r) and r[0]["newfolder"] and all(x["top"] > r[0]["top"] for x in r[1:] if not x["newfolder"]),
           f"tops={[x['top'] for x in r]}")
        ok("složky jsou pod ní (2)", len([x for x in r if not x["newfolder"]]) == 2, str(len(r)))

        # a řádek pořád zakládá složku
        await h.ev("window.prompt = () => 'Test C'")
        await h.ev("document.querySelector('.folderlist .folder-row.newfolder').click()")
        await h.wait_for("document.querySelectorAll('.folder-row[data-folder-drop]').length >= 3",
                         10, "složka C")
        r2 = await rows(h)
        ok("klepnutí na řádek založí další složku",
           len([x for x in r2 if not x["newfolder"]]) == 3, str(r2))
        ok("řádek zůstal nahoře i po přidání", r2[0]["newfolder"] is True, str(r2[:1]))
    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
