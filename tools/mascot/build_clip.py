#!/usr/bin/env python3
"""
Build the mascot's gesture library and inject it into index.html.

The character is a *full-body gesture player*: every gesture is a horizontal
sprite-atlas of full-body frames (head-to-shoes), normalized to a common canvas
with the feet on a fixed baseline, so the character is the SAME size in every
gesture and clips are drop-in interchangeable.

Sources
  - "video":      frames cut from the reference clip in the repo root
                  (real, natural human motion; black background is keyed out).
  - "walk-atlas": the side-on walk in tools/mascot/sources/walk_atlas.webp
                  (the reference video has no walking, so the walk comes from here).

Add a gesture
  1. Pick a frame range in the reference video (2fps contact sheet: `ffmpeg -i <video>
     -vf fps=2 sheet_%03d.png`) where the FULL body + shoes are visible.
  2. Add one entry to CLIPS below.
  3. Run:  python3 tools/mascot/build_clip.py
  See tools/mascot/README.md for the full guide.

Requires: ffmpeg, numpy, pillow, scipy.
"""
import subprocess, os, glob, json, base64, io, sys
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
HTML = os.path.join(ROOT, "index.html")
ENGINE = os.path.join(HERE, "engine.js")
WALK_ATLAS = os.path.join(HERE, "sources", "walk_atlas.webp")
CLIPS_DIR = os.path.join(HERE, "clips")

def find_video():
    vids = sorted(glob.glob(os.path.join(ROOT, "*.mp4")))
    if not vids:
        sys.exit("No reference .mp4 found in repo root.")
    return vids[0]

# ---- common full-body canvas (keep constant so every gesture matches) ----
CW, CH = 320, 460          # frame size on the page's canvas
BODY_H = 392               # head-top -> feet-bottom maps to this many px
BASE_Y = CH - 34           # feet baseline

# ---- the gesture library (the single source of truth) ----
# POLICY: front-and-centre, full-body only. No side/left/right posing, no zoom.
#         Back-facing clips are allowed only when explicitly requested.
# fps  : playback speed; loop: keep looping; mirror: flip horizontally;
# video sources take a list of frame numbers; pingpong makes a seamless loop.
CLIPS = {
    "idle": {"source": "video", "frames": list(range(180, 217, 4)),
             "pingpong": True, "mirror": False, "fps": 9, "loop": True},
    # --- add more FRONT-FACING, full-body gestures here, e.g. ---
    # "talk":   {"source":"video", "frames":list(range(150,186,3)), "fps":11, "loop":False},
    # "wave":   {"source":"video", "frames":[...], "fps":12, "loop":False},
    # "back":   {"source":"video", "frames":[...], "fps":9,  "loop":True},   # only when you ask for it
}

# ---------------------------------------------------------------- helpers ----
def key(img_rgb, T=18, soft=22):
    """Remove the near-black background, keep the largest connected blob."""
    a = np.asarray(img_rgb.convert("RGB")).astype(np.float32)
    lum = a.max(2)
    fg = ndimage.binary_fill_holes(lum > T)
    lbl, n = ndimage.label(fg)
    if n > 1:
        sizes = ndimage.sum(np.ones_like(lbl), lbl, range(1, n + 1))
        fg = lbl == (np.argmax(sizes) + 1)
    fg = ndimage.binary_fill_holes(fg)
    alpha = np.clip((lum - T) / soft, 0, 1) * fg
    return Image.fromarray(np.dstack([a, alpha * 255]).astype(np.uint8), "RGBA"), alpha

def metrics(alpha):
    rows = (alpha > 0.4).sum(1)
    cols = np.where(rows >= 8)[0]
    head_y, feet_y = int(cols.min()), int(cols.max())
    bh = feet_y - head_y
    band = np.zeros_like(alpha, bool)
    band[int(feet_y - 0.08 * bh):feet_y + 1] = True
    _, fx = np.where((alpha > 0.4) & band)
    feet_cx = float(np.median(fx)) if len(fx) else float(np.median(np.where(alpha[feet_y] > 0.4)[0]))
    return head_y, feet_y, feet_cx, bh

def normalize(im, alpha, mirror=False):
    """Scale by body height and anchor the feet to a fixed baseline + centre."""
    if mirror:
        im = im.transpose(Image.FLIP_LEFT_RIGHT); alpha = alpha[:, ::-1]
    _, feet_y, feet_cx, bh = metrics(alpha)
    sc = BODY_H / bh
    ims = im.resize((max(1, round(im.width * sc)), max(1, round(im.height * sc))), Image.LANCZOS)
    canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    canvas.alpha_composite(ims, (round(CW / 2 - feet_cx * sc), round(BASE_Y - feet_y * sc)))
    return canvas

def dump_video_frames(video, frames, outdir):
    os.makedirs(outdir, exist_ok=True)
    for f in glob.glob(f"{outdir}/*.png"):
        os.remove(f)
    sel = "+".join(f"eq(n\\,{f})" for f in frames)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", video,
                    "-vf", f"select='{sel}'", "-vsync", "0", f"{outdir}/f_%03d.png"], check=True)
    return sorted(glob.glob(f"{outdir}/f_*.png"))

def build_frames(name, spec, video):
    if spec["source"] == "video":
        fs = dump_video_frames(video, spec["frames"], os.path.join(CLIPS_DIR, "_" + name))
        norm = [normalize(*key(Image.open(p)), mirror=spec.get("mirror", False)) for p in fs]
        if spec.get("pingpong") and len(norm) > 2:
            norm = norm + norm[-2:0:-1]
        return norm
    elif spec["source"] == "walk-atlas":
        wa = Image.open(WALK_ATLAS).convert("RGBA")
        fw0 = wa.width // 13                       # 13-frame atlas (0=idle, 1..12=stride)
        norm = []
        for i in spec["frames"]:
            fr = wa.crop((i * fw0, 0, i * fw0 + fw0, wa.height))
            al = np.asarray(fr)[:, :, 3].astype(np.float32) / 255.0
            norm.append(normalize(fr, al, mirror=spec.get("mirror", False)))
        return norm
    raise ValueError("unknown source " + spec["source"])

def atlas_b64(norm, quality):
    n = len(norm)
    atlas = Image.new("RGBA", (CW * n, CH), (0, 0, 0, 0))
    for i, f in enumerate(norm):
        atlas.alpha_composite(f, (i * CW, 0))
    buf = io.BytesIO(); atlas.save(buf, "WEBP", quality=quality, method=6)
    return atlas, buf.getvalue(), n

# ------------------------------------------------------------------- main ----
def main():
    os.makedirs(CLIPS_DIR, exist_ok=True)
    video = find_video()
    print("reference video:", os.path.basename(video))
    registry, manifest = [], {}
    for name, spec in CLIPS.items():
        norm = build_frames(name, spec, video)
        q = 82 if spec["source"] == "walk-atlas" else 78
        atlas, raw, n = atlas_b64(norm, q)
        atlas.save(os.path.join(CLIPS_DIR, name + ".webp"), quality=q, method=6)  # inspect artefact
        src = "data:image/webp;base64," + base64.b64encode(raw).decode()
        registry.append('%s:{src:"%s",n:%d,fps:%d,loop:%s}'
                        % (name, src, n, spec.get("fps", 12), "true" if spec.get("loop") else "false"))
        manifest[name] = {"frames": n, "fps": spec.get("fps", 12), "loop": bool(spec.get("loop")), "bytes": len(raw)}
        print(f"  {name:8s} frames={n:3d}  {len(raw)//1024:4d} KB")
    json.dump(manifest, open(os.path.join(CLIPS_DIR, "clips.json"), "w"), indent=2)

    clips_literal = "{" + ",".join(registry) + "}"
    engine = (open(ENGINE).read()
              .replace("__FW__", str(CW)).replace("__FH__", str(CH)).replace("__CLIPS__", clips_literal))

    bubble = ('.mascot__bubble{position:absolute;left:50%;bottom:calc(100% - 12px);'
              'transform:translate(-50%,8px) scale(.92);transform-origin:50% 100%;max-width:240px;'
              'background:linear-gradient(180deg,rgba(20,24,33,.97),rgba(12,15,20,.97));color:var(--ink);'
              "border:1px solid rgba(94,234,212,.4);border-radius:14px;padding:9px 14px;"
              "font:600 13px/1.4 'Inter',system-ui,sans-serif;box-shadow:0 14px 34px rgba(0,0,0,.5);"
              "opacity:0;pointer-events:none;transition:opacity .3s ease,transform .3s var(--ease);}")
    css = "\n".join([
        "/* ===== character companion (full-body gesture player) ===== */",
        ".mascot{position:fixed;left:clamp(6px,2vw,30px);bottom:clamp(36px,11vh,130px);z-index:450;width:auto;pointer-events:none;transform-origin:left bottom;will-change:transform;transform:translateZ(0);}",
        ".mascot__cv{display:block;height:clamp(210px,34vh,320px);width:auto;filter:drop-shadow(0 16px 22px rgba(0,0,0,.5));-webkit-user-select:none;user-select:none;}",
        ".mascot__shadow{position:absolute;left:50%;bottom:8px;width:38%;height:12px;transform:translateX(-50%);background:radial-gradient(ellipse at center,rgba(0,0,0,.5),rgba(0,0,0,0) 70%);filter:blur(3px);z-index:-1;opacity:0;transition:opacity .7s ease;}",
        ".mascot.arrived .mascot__shadow{opacity:1;}",
        bubble,
        '.mascot__bubble::after{content:"";position:absolute;left:50%;top:100%;transform:translateX(-50%);border:7px solid transparent;border-top-color:rgba(12,15,20,.97);}',
        ".mascot__bubble.show{opacity:1;transform:translate(-50%,0) scale(1);}",
        "@media(max-width:640px){.mascot{left:4px;}.mascot__cv{height:175px;}}",
    ])
    html_block = ('<!-- ===== character companion ===== -->\n'
                  '<div id="mascot" class="mascot" aria-hidden="true">'
                  '<span class="mascot__shadow"></span><div class="mascot__bubble"></div>'
                  '<canvas class="mascot__cv"></canvas></div>\n'
                  '<script>\n' + engine + '\n</script>')

    html = open(HTML, encoding="utf-8").read()
    cs = html.index("/* ===== character companion")
    ce = html.index("@media(max-width:640px){.mascot")
    ce = html.index("}\n", ce) + 1
    html = html[:cs] + css + html[ce:]
    hs = html.index("<!-- ===== character companion ===== -->")
    marker = "})();\n</script>"
    he = html.index(marker, hs) + len(marker)
    html = html[:hs] + html_block + html[he:]
    open(HTML, "w", encoding="utf-8").write(html)
    print("injected into index.html  (%d KB)" % (len(html) // 1024))

if __name__ == "__main__":
    main()
