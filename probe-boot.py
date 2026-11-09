
import asyncio, importlib.util, os
_HERE="/home/martin_fabian/noty-app"
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE,"cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(m)
async def main():
    async with m.Harness() as h:
        await h.open()
        print("url:", await h.ev("location.href"))
        print("body len:", await h.ev("document.body.innerText.length"))
        print("body:", (await h.ev("document.body.innerText"))[:400])
        print("inputs:", await h.ev("[...document.querySelectorAll('input')].map(i=>i.type+':'+(i.className||''))"))
asyncio.run(main())
