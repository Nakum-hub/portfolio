#!/usr/bin/env python3
"""
build_rig.py — turn the single front-facing illustration `character.png` into a
humanoid 2-D cut-out rig: a set of body-part PNG layers + a rig.json describing
each layer's placement, joint pivot and parent.

Why it works on a flat illustration:
  * the shirt is one flat charcoal colour and the trousers one flat beige, so we
    can cut a limb at its joint and *inpaint* the flat colour behind it. Lifting a
    forearm then reveals clean shirt / trouser underneath instead of a hole.
  * the torso and leg layers are kept fully opaque across the whole silhouette
    (generous overlap at the joints), so a moving part never exposes the canvas.

Output (to OUT_DIR):
  parts/<name>.png    cropped RGBA layer
  rig.json            {canvas, joints, parts:[{name,x,y,w,h,pivot,parent,z,src}]}
  live2d/<name>.png   full-canvas-sized layers for Live2D / Cubism import
  live2d/layers.json  ordered layer manifest for the Live2D pipeline
  debug/*.png         reassembly + pose checks
"""
import json, os
import numpy as np
from PIL import Image
from scipy import ndimage

SRC      = os.path.join(os.path.dirname(__file__), "..", "..", "character.png")
OUT_DIR  = os.path.join(os.path.dirname(__file__))
EXPORT   = 0.5          # export scale (character ~1135px tall -> crisp + small)
FEATHER  = 26           # internal seam feather, px (full-res)

# ---- joint fractions (of the character bounding box), tuned on the overlay ----
J = dict(neck_y=0.158, shoulder_y=0.20, elbow_y=0.375, hand_b=0.60,
         waist_y=0.50, hip_y=0.575, knee_y=0.73, ankle_y=0.92,
         shoulderL=0.30, shoulderR=0.70, elbowL=0.21, elbowR=0.82,
         hipL=0.40, hipR=0.60, kneeL=0.37, kneeR=0.62, inseam=0.50)


def char_mask(rgb):
    """Largest non-white connected component = the person (drops bg + smudge)."""
    mn = rgb.min(axis=2)
    fg = mn < 232
    lbl, n = ndimage.label(fg)
    sizes = ndimage.sum(np.ones_like(lbl), lbl, range(1, n + 1))
    return lbl == (np.argmax(sizes) + 1)


def ramp_up(yy, a, b):    # 0 for y<a, ->1 at y>=b
    return np.clip((yy - a) / max(1e-6, (b - a)), 0, 1)


def ramp_dn(yy, a, b):    # 1 for y<a, ->0 at y>=b
    return 1.0 - ramp_up(yy, a, b)


def nearest_fill(rgb, valid, where):
    """Fill `where` pixels with the colour of the nearest `valid` pixel."""
    idx = ndimage.distance_transform_edt(~valid, return_distances=False,
                                         return_indices=True)
    out = rgb.copy()
    sel = where
    out[sel] = rgb[idx[0][sel], idx[1][sel]]
    return out


def main():
    im = Image.open(SRC).convert("RGB")
    W, H = im.size
    rgb = np.array(im).astype(np.uint8)
    char = char_mask(rgb)
    ys, xs = np.where(char)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    Wb, Hb = x1 - x0, y1 - y0

    def AX(fx): return x0 + fx * Wb
    def AY(fy): return y0 + fy * Hb
    def cx(y):
        xr = np.where(char[int(y)])[0]
        return float((xr.min() + xr.max()) / 2) if len(xr) else (x0 + x1) / 2

    yy = np.repeat(np.arange(H)[:, None], W, axis=1).astype(np.float32)
    xx = np.repeat(np.arange(W)[None, :], H, axis=0).astype(np.float32)
    # erode 1px for the alpha base -> drops the light anti-aliased silhouette halo
    # (so edges stay clean on a dark background) without touching internal seams.
    charf = ndimage.binary_erosion(char, iterations=1).astype(np.float32)

    neck_y, shoulder_y = AY(J["neck_y"]), AY(J["shoulder_y"])
    elbow_y, hand_b = AY(J["elbow_y"]), AY(J["hand_b"])
    waist_y, hip_y = AY(J["waist_y"]), AY(J["hip_y"])
    knee_y, ankle_y = AY(J["knee_y"]), AY(J["ankle_y"])
    inseam_x = AX(J["inseam"])
    hem = hip_y + 0.045 * Hb       # shirt hem covers a little below the hip joint

    # ---- colour classes (flat clothing colours let us separate + inpaint) ------
    R, G, B = rgb[:, :, 0].astype(int), rgb[:, :, 1].astype(int), rgb[:, :, 2].astype(int)
    bright = rgb.mean(axis=2)
    beige = char & (bright > 158) & (np.abs(R - G) < 26) & ((R - B) < 48)   # trousers + shoes

    def largest(m):
        lbl, n = ndimage.label(m)
        if n == 0:
            return m
        sizes = ndimage.sum(np.ones_like(lbl), lbl, range(1, n + 1))
        return lbl == (np.argmax(sizes) + 1)

    def softmask(m):
        # soft-edged float mask; arm layers and the torso-removal share it so their
        # alphas sum to ~1 at the seam (both garment-dark -> no light gap, no sliver).
        return np.clip(ndimage.gaussian_filter(m.astype(np.float32), 2.0) * 1.5, 0, 1)

    # ---- forearms = SKIN forearm + hand + watch (the elbow/lower-arm bone) -----
    skin = char & (R > 135) & (R - B > 20) & (R - G > 6) & (bright > 116) & (bright < 236) & ~beige
    arm_band = skin & (yy > shoulder_y + 12) & (yy < y0 + 0.60 * Hb)
    vert = np.array([[0, 1, 0], [0, 1, 0], [0, 1, 0]], bool)

    def arm_blob(sidemask):
        lbl, n = ndimage.label(arm_band & sidemask)
        keep = np.zeros_like(arm_band)
        for i in range(1, n + 1):
            m = lbl == i
            if m.sum() > 6000:
                keep |= m
        m = ndimage.binary_dilation(keep, structure=vert, iterations=18)
        m = ndimage.binary_erosion(m, structure=vert, iterations=18)
        return ndimage.binary_fill_holes(m) & char
    foreL_b = arm_blob(xx < inseam_x)
    foreR_b = arm_blob(xx >= inseam_x)
    cuffL_y = int(np.where(foreL_b)[0].min())
    cuffR_y = int(np.where(foreR_b)[0].min())

    def forearm_layer(blob):
        ys_b, xs_b = np.where(blob)
        top = ys_b.min()
        cuff = float(xs_b[ys_b < top + 10].mean())
        soft = ramp_up(yy, top - 2, top + 22)
        return charf * soft * softmask(blob), (cuff, float(top + 6))
    foreL, pivL = forearm_layer(foreL_b)
    foreR, pivR = forearm_layer(foreR_b)

    # ---- upper arms = the dark sleeve, shoulder -> elbow (the upper-arm bone) ---
    # Cut the lateral sleeve from the torso along the raglan seam. Both are flat
    # charcoal, so the inner cut is invisible at rest and reads as the body side
    # (flat dark) when the arm lifts.
    dark = char & (bright < 100)
    span = (yy - AY(0.20)) / (AY(0.40) - AY(0.20))
    innerR = AX(0.60) + span * (AX(0.645) - AX(0.60))      # right arm inner boundary
    innerL = AX(0.40) + span * (AX(0.355) - AX(0.40))      # left  arm inner boundary
    uaR_b = largest(dark & (yy >= AY(0.185)) & (yy <= cuffR_y + 24) & (xx > innerR - 6) & (xx >= inseam_x))
    uaL_b = largest(dark & (yy >= AY(0.185)) & (yy <= cuffL_y + 24) & (xx < innerL + 6) & (xx < inseam_x))
    upperArmR = charf * softmask(uaR_b) * ramp_dn(yy, cuffR_y + 8, cuffR_y + 28)   # feather elbow overlap
    upperArmL = charf * softmask(uaL_b) * ramp_dn(yy, cuffL_y + 8, cuffL_y + 28)
    pivUAR = (float(AX(0.625)), float(AY(0.215)))           # shoulder joints (top-inner)
    pivUAL = (float(AX(0.375)), float(AY(0.215)))

    # ---- head (hair+face+neck), opaque to the collar then feather out ----------
    head = charf * ramp_dn(yy, neck_y + 8, neck_y + 8 + FEATHER * 2)

    # ---- torso/spine: a clean BODY contour (no arm bulges), feathered at the
    # sides, with the arm-covered areas bled flat from the central shirt/trouser.
    # So when an arm lifts you see a smooth torso side, not the arm's old outline.
    # ---- torso/spine: full silhouette minus the WHOLE arm footprint -----------
    # Removing the arms (with a soft edge) means a lifted arm reveals a clean body
    # edge / the beige thigh behind it, never the arm's dark imprint; the arms,
    # drawn on top, cover the soft seam at rest.
    # torso-removal is eroded vs the arm layers, so the arms (drawn on top) always
    # over-cover the seam at rest; a lifted arm leaves only a thin dark margin that
    # vanishes against a dark background.
    arm_soft = softmask(ndimage.binary_erosion(uaL_b | uaR_b | foreL_b | foreR_b, iterations=4))
    spine_band = ramp_up(yy, neck_y - 36, neck_y + 6) * ramp_dn(yy, hem, hem + FEATHER * 2)
    torso = charf * spine_band * (1.0 - arm_soft)

    # ---- legs: thigh + shin per side, split by the inseam, overlap at knee -----
    side_L = xx <= inseam_x + 6
    side_R = xx >= inseam_x - 6
    thigh_band = ramp_up(yy, hip_y - 0.05 * Hb, hip_y - 0.02 * Hb) * ramp_dn(yy, knee_y, knee_y + FEATHER)
    shin_band = ramp_up(yy, knee_y - FEATHER, knee_y)
    thighL = charf * thigh_band * side_L
    thighR = charf * thigh_band * side_R
    shinL = charf * shin_band * side_L
    shinR = charf * shin_band * side_R

    # ---- inpaint the limb footprints by bleeding flat garment colour -----------
    # Garment-aware (split at the belt) and never sourcing the near-white halo.
    mn = rgb.min(axis=2)
    halo = mn >= 238
    belt = waist_y + 0.02 * Hb
    arm_cover = ndimage.binary_dilation(foreL_b | foreR_b | uaL_b | uaR_b, iterations=20)

    def repaint(layer_alpha):
        solid = layer_alpha > 0.02
        hole = solid & arm_cover
        valid = solid & ~arm_cover & ~halo
        dark_src = ndimage.binary_erosion(valid & (bright < 110), iterations=1)
        beige_src = ndimage.binary_erosion(valid & beige, iterations=1)
        out = rgb.copy()
        if dark_src.any():
            out = nearest_fill(out, dark_src, hole & (yy < belt))
        if beige_src.any():
            out = nearest_fill(out, beige_src, hole & (yy >= belt))
        return out
    torso_rgb = repaint(torso)
    thighL_rgb = repaint(thighL)
    thighR_rgb = repaint(thighR)

    parts = {
        "upperLegL": (thighL, thighL_rgb, (AX(J["hipL"]), AY(J["hip_y"])), "hips", 1),
        "upperLegR": (thighR, thighR_rgb, (AX(J["hipR"]), AY(J["hip_y"])), "hips", 1),
        "lowerLegL": (shinL, rgb, (AX(J["kneeL"]), AY(J["knee_y"])), "upperLegL", 2),
        "lowerLegR": (shinR, rgb, (AX(J["kneeR"]), AY(J["knee_y"])), "upperLegR", 2),
        "spine":     (torso, torso_rgb, (cx(waist_y), waist_y), "hips", 3),
        "upperArmL": (upperArmL, rgb, pivUAL, "spine", 4),
        "upperArmR": (upperArmR, rgb, pivUAR, "spine", 4),
        "head":      (head, rgb, (cx(neck_y), neck_y), "spine", 5),
        "lowerArmL": (foreL, rgb, pivL, "upperArmL", 6),
        "lowerArmR": (foreR, rgb, pivR, "upperArmR", 6),
    }

    os.makedirs(os.path.join(OUT_DIR, "parts"), exist_ok=True)
    os.makedirs(os.path.join(OUT_DIR, "live2d"), exist_ok=True)
    os.makedirs(os.path.join(OUT_DIR, "debug"), exist_ok=True)

    canvas = {"w": round(W * EXPORT), "h": round(H * EXPORT)}
    rig_parts, l2d = [], []
    full_layers = {}  # name -> full-size RGBA (for debug reassembly)

    for name, (alpha, src_rgb, pivot, parent, z) in parts.items():
        a = np.clip(alpha, 0, 1)
        rgba = np.dstack([src_rgb, (a * 255).astype(np.uint8)])
        full_layers[name] = rgba
        # Live2D wants full-canvas layers (so they line up on import)
        Image.fromarray(rgba, "RGBA").resize((canvas["w"], canvas["h"]),
                                              Image.LANCZOS).save(
            os.path.join(OUT_DIR, "live2d", f"{name}.png"))
        l2d.append({"name": name, "z": z, "file": f"{name}.png"})
        # cropped layer for the web rig
        ys2, xs2 = np.where(a > 0.004)
        bx0, bx1, by0, by1 = xs2.min(), xs2.max(), ys2.min(), ys2.max()
        crop = Image.fromarray(rgba[by0:by1 + 1, bx0:bx1 + 1], "RGBA")
        ew, eh = round(crop.width * EXPORT), round(crop.height * EXPORT)
        crop = crop.resize((ew, eh), Image.LANCZOS)
        crop.save(os.path.join(OUT_DIR, "parts", f"{name}.png"))
        rig_parts.append({
            "name": name, "src": f"parts/{name}.png", "parent": parent, "z": z,
            "x": round(bx0 * EXPORT), "y": round(by0 * EXPORT), "w": ew, "h": eh,
            "pivot": [round(pivot[0] * EXPORT), round(pivot[1] * EXPORT)],
        })

    joints = {k: ([round(AX(J[k]) * EXPORT)] if k.endswith(("L", "R")) and not k.endswith("_y")
                  else round(AY(J[k]) * EXPORT)) for k in J}
    rig = {"canvas": canvas, "scale": EXPORT,
           "bbox": [round(x0 * EXPORT), round(y0 * EXPORT), round(Wb * EXPORT), round(Hb * EXPORT)],
           "root_pivot": [round(cx(waist_y) * EXPORT), round(hip_y * EXPORT)],
           "parts": sorted(rig_parts, key=lambda p: p["z"])}
    with open(os.path.join(OUT_DIR, "rig.json"), "w") as f:
        json.dump(rig, f, indent=1)
    with open(os.path.join(OUT_DIR, "live2d", "layers.json"), "w") as f:
        json.dump({"canvas": canvas, "layers": sorted(l2d, key=lambda p: p["z"])}, f, indent=1)

    # ---- debug: reassemble at rest (z order) -----------------------------------
    comp = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    for name, spec in sorted(parts.items(), key=lambda kv: kv[1][4]):
        comp.alpha_composite(Image.fromarray(full_layers[name], "RGBA"))
    comp.resize((W // 4, H // 4)).save(os.path.join(OUT_DIR, "debug", "reassembled.png"))

    # ---- debug: contact sheet of individual parts ------------------------------
    print("canvas", canvas, "parts:", [p["name"] for p in rig["parts"]])
    print("wrote rig.json, live2d/, parts/")


if __name__ == "__main__":
    main()
