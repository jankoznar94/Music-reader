import asyncio, importlib.util, json, base64, os
_HERE = "/home/martin_fabian/noty-app"
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(m)

async def main():
    async with m.Harness() as h:
        info = await h.ev("""(() => {
          const layer = document.querySelector('.annot-layer');
          const lr = layer.getBoundingClientRect();
          const texts = [...layer.querySelectorAll('text')].map(t => {
            const r = t.getBoundingClientRect();
            return {x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height)};
          });
          const circles = [...layer.querySelectorAll('circle')].map(c => {
            const r = c.getBoundingClientRect();
            return {x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height)};
          });
          return {layer: {l: Math.round(lr.left), t: Math.round(lr.top), w: Math.round(lr.width), h: Math.round(lr.height)},
                  texts, circles};
        })()""")
        print(json.dumps(info, indent=1))
        shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
        open("/tmp/dotted-shot2.png", "wb").write(base64.b64decode(shot["data"]))

asyncio.run(main())
