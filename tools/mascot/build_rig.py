#!/usr/bin/env python3
"""
Build the LIVING CHARACTER (single-entity warp) and inject it into index.html.

The character is treated as ONE continuous texture — never cut into parts — and animated
by `rig.js` with a smooth warp (a gentle bend toward the cursor from feet to head, plus a
breathing stretch through the chest). Because it is one image, the body is always intact:
no separate head/torso/legs, no seams. The recorded video/clips are kept only as motion
reference, not played.

What it does
  1. Key the white background out of character.png (keep the largest opaque blob).
  2. Crop to a padded box and downscale to a WebP data URI (the single texture).
  3. Measure feet / head / centre in texture pixels.
  4. Fill rig.js and splice the mascot block (CSS + element + script) into index.html.

Requires: numpy, pillow, scipy.
"""
import os, io, base64, json
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
HTML = os.path.join(ROOT, "index.html")
RIGJS = os.path.join(HERE, "rig.js")
SRC = os.path.join(ROOT, "character.png")
OUT = os.path.join(HERE, "rig_parts")          # holds the single texture + meta for inspection

CROP = [80, 360, 890, 2700]                     # padded render box (source px) — full body + lean room
F = 0.52                                        # texture downscale for the web

def key_white(path):
    im = Image.open(path).convert("RGB"); a = np.array(im).astype(int)
    mn, mx = a.min(2), a.max(2)
    nearwhite = (mn > 205) & ((mx - mn) < 30)
    H, W = mn.shape
    seed = np.zeros((H, W), bool); seed[0] = seed[-1] = True; seed[:, 0] = seed[:, -1] = True
    seed &= nearwhite
    bg = ndimage.binary_propagation(seed, mask=nearwhite)
    faint = ((mx - mn) < 55) & (mn > 150)
    bg = ndimage.binary_propagation(bg | seed, mask=(nearwhite | faint))
    fg = ndimage.binary_fill_holes(~bg)
    lbl, n = ndimage.label(fg)
    if n > 1:
        sizes = ndimage.sum(np.ones_like(lbl), lbl, range(1, n + 1)); fg = lbl == (np.argmax(sizes) + 1)
    fg = ndimage.binary_fill_holes(fg)
    return np.dstack([np.array(im), (fg * 255).astype(np.uint8)]).astype(np.uint8)

def main():
    os.makedirs(OUT, exist_ok=True)
    rgba = key_white(SRC)
    im = Image.fromarray(rgba, "RGBA").crop(tuple(CROP))
    im = im.resize((round(im.width * F), round(im.height * F)), Image.LANCZOS)
    TW, TH = im.size
    A = np.array(im)[:, :, 3]
    ys, xs = np.where(A > 40)
    feetY, headY, cx = int(ys.max()), int(ys.min()), float((xs.min() + xs.max()) / 2)
    im.save(os.path.join(OUT, "char.webp"), quality=92, method=6)
    buf = io.BytesIO(); im.save(buf, "WEBP", quality=90, method=6); raw = buf.getvalue()
    RIG = {"tex": "data:image/webp;base64," + base64.b64encode(raw).decode(),
           "TW": TW, "TH": TH, "feetY": feetY, "headY": headY, "cx": round(cx, 1)}
    json.dump({"TW": TW, "TH": TH, "feetY": feetY, "headY": headY, "cx": round(cx, 1),
               "F": F, "crop": CROP, "bytes": len(raw)}, open(os.path.join(OUT, "rig.json"), "w"), indent=2)
    print("single texture %dx%d  feetY=%d headY=%d  %d KB" % (TW, TH, feetY, headY, len(raw) // 1024))

    rig = open(RIGJS).read().replace("__RIG__", json.dumps(RIG))
    css = "\n".join([
        "/* ===== character companion (single-entity living warp) ===== */",
        ".mascot{position:fixed;left:clamp(6px,2vw,30px);bottom:clamp(24px,7vh,90px);z-index:450;width:auto;pointer-events:none;will-change:transform;}",
        ".mascot__cv{display:block;height:clamp(300px,62vh,560px);width:auto;filter:drop-shadow(0 18px 26px rgba(0,0,0,.55));-webkit-user-select:none;user-select:none;}",
        "@media(max-width:640px){.mascot{left:0;}.mascot__cv{height:300px;}}",
    ])
    html_block = ('<!-- ===== character companion ===== -->\n'
                  '<div id="mascot" class="mascot" aria-hidden="true" style="opacity:0;transition:opacity .7s ease">'
                  '<canvas class="mascot__cv"></canvas></div>\n'
                  '<script>\n' + rig + '\n</script>')

    html = open(HTML, encoding="utf-8").read()
    cs = html.index("/* ===== character companion")
    ce = html.index("@media(max-width:640px){.mascot"); ce = html.index("}\n", ce) + 1
    html = html[:cs] + css + html[ce:]
    hs = html.index("<!-- ===== character companion ===== -->")
    he = html.index("})();\n</script>", hs) + len("})();\n</script>")
    html = html[:hs] + html_block + html[he:]
    open(HTML, "w", encoding="utf-8").write(html)
    print("injected single-entity rig into index.html (%d KB)" % (len(html) // 1024))

if __name__ == "__main__":
    main()
