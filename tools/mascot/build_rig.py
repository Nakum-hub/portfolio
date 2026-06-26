#!/usr/bin/env python3
"""
Build the LIVING CHARACTER RIG and inject it into index.html.

This is NOT clip playback. The character design (character.png) is segmented into a
small skeleton — head / torso+arms / legs — and `rig.js` animates it procedurally
every frame (breathing, weight-shift sway, head look-at-cursor). The recorded video
and the clips under clips/ are kept only as *motion reference*, not played.

What it does
  1. Key the white background out of character.png.
  2. Cut head / upper(torso+arms) / lower(legs) with feathered, overlapping seams
     (the lower part stays opaque under the shirt hem so motion shows no gap).
  3. Compute joint pivots (neck, waist) and a crop box.
  4. Downscale the parts to WebP data URIs, fill rig.js, and splice the mascot block
     (CSS + element + script) into index.html.

Limitation: in this single front illustration the arms hang flush against the body,
so they can't be detached for big arm gestures. The rig animates head + torso + legs
(breathing, sway, look-at), which is what makes a 2-D character read as alive. Studio
arm/finger gestures would need either extra reference art (arm raised) or a Live2D/Spine
rig authored in their editor.

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
PARTS_DIR = os.path.join(HERE, "rig_parts")

# cut lines / pivots in source-image pixels (character.png is 1536x2730)
NECK_Y, WAIST_Y = 825, 1490
F = 0.5                              # part downscale for the web
CROP = [120, 370, 850, 2695]        # render crop (with motion padding)

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
    return np.dstack([np.array(im), (fg * 255).astype(np.uint8)]), fg

def cut(rgba, fg):
    H, W, _ = rgba.shape
    yy = np.arange(H)[:, None].astype(float)
    ramp = lambda y0, y1: np.clip((yy - y0) / (y1 - y0), 0, 1)
    def apply(col):
        out = rgba.astype(float); out[:, :, 3] *= col[:, 0][:, None].repeat(W, 1)
        return Image.fromarray(out.clip(0, 255).astype(np.uint8), "RGBA")
    head  = apply(1 - ramp(NECK_Y - 10, NECK_Y + 60))                       # opaque to neck, feather out
    upper = apply(ramp(NECK_Y - 35, NECK_Y + 3) * (1 - ramp(WAIST_Y, WAIST_Y + 65)))
    lower = apply(ramp(WAIST_Y - 41, WAIST_Y - 40))                         # opaque from under the hem
    def cx(y):
        xx = np.where(fg[y])[0]; return float((xx.min() + xx.max()) / 2) if len(xx) else W / 2
    feet_y = int(np.where(fg.any(1))[0].max())
    return ({"head": head, "upper": upper, "lower": lower},
            {"neck": [cx(NECK_Y), NECK_Y], "waist": [cx(WAIST_Y), WAIST_Y], "feet": [cx(feet_y - 25), feet_y]})

def datauri(im):
    im = im.resize((round(im.width * F), round(im.height * F)), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "WEBP", quality=90, method=6)
    return "data:image/webp;base64," + base64.b64encode(b.getvalue()).decode(), len(b.getvalue())

def main():
    os.makedirs(PARTS_DIR, exist_ok=True)
    rgba, fg = key_white(SRC)
    parts, piv = cut(rgba, fg)
    uris = {}; total = 0
    for k, im in parts.items():
        im.save(os.path.join(PARTS_DIR, k + ".webp"), quality=92, method=6)   # stored for inspection
        uris[k], n = datauri(im); total += n
    sc = lambda p: [round(p[0] * F, 1), round(p[1] * F, 1)]
    RIG = {"parts": uris, "neck": sc(piv["neck"]), "waist": sc(piv["waist"]), "feet": sc(piv["feet"]),
           "crop": [round(c * F, 1) for c in CROP]}
    json.dump({"neck": piv["neck"], "waist": piv["waist"], "feet": piv["feet"], "F": F, "crop": CROP, "bytes": total},
              open(os.path.join(PARTS_DIR, "rig.json"), "w"), indent=2)
    print("rig parts %d KB" % (total // 1024))

    rig = open(RIGJS).read().replace("__RIG__", json.dumps(RIG))
    css = "\n".join([
        "/* ===== character companion (living procedural rig) ===== */",
        ".mascot{position:fixed;left:clamp(6px,2vw,30px);bottom:clamp(30px,9vh,110px);z-index:450;width:auto;pointer-events:none;will-change:transform;}",
        ".mascot__cv{display:block;height:clamp(230px,40vh,360px);width:auto;filter:drop-shadow(0 18px 26px rgba(0,0,0,.55));-webkit-user-select:none;user-select:none;}",
        ".mascot__shadow{position:absolute;left:50%;bottom:10px;width:34%;height:12px;transform:translateX(-50%);background:radial-gradient(ellipse at center,rgba(0,0,0,.5),rgba(0,0,0,0) 70%);filter:blur(3px);z-index:-1;opacity:0;transition:opacity .8s ease;}",
        ".mascot.arrived .mascot__shadow{opacity:1;}",
        "@media(max-width:640px){.mascot{left:2px;}.mascot__cv{height:185px;}}",
    ])
    html_block = ('<!-- ===== character companion ===== -->\n'
                  '<div id="mascot" class="mascot" aria-hidden="true" style="opacity:0;transition:opacity .7s ease">'
                  '<span class="mascot__shadow"></span><canvas class="mascot__cv"></canvas></div>\n'
                  '<script>\n' + rig + '\n</script>')

    html = open(HTML, encoding="utf-8").read()
    cs = html.index("/* ===== character companion")
    ce = html.index("@media(max-width:640px){.mascot"); ce = html.index("}\n", ce) + 1
    html = html[:cs] + css + html[ce:]
    hs = html.index("<!-- ===== character companion ===== -->")
    he = html.index("})();\n</script>", hs) + len("})();\n</script>")
    html = html[:hs] + html_block + html[he:]
    open(HTML, "w", encoding="utf-8").write(html)
    print("injected rig into index.html (%d KB)" % (len(html) // 1024))

if __name__ == "__main__":
    main()
