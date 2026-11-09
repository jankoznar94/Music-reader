
import asyncio, importlib.util, os
_HERE="/home/martin_fabian/noty-app"
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE,"cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(m)
async def main():
    async with m.Harness() as h:
        await h.open()
        await h.open_song(pages=3)
        await asyncio.sleep(0.5)
        await h.ev("document.querySelector('.tb-btn.zoom-btn').click()")
        await asyncio.sleep(0.6)
        print(await h.ev("[...document.querySelectorAll('.zoom-panel button')].map(b=>(b.className||'')+'|'+(b.title||'')+'|'+b.textContent.trim().slice(0,12))"))
asyncio.run(main())
