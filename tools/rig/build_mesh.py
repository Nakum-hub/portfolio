#!/usr/bin/env python3
"""
build_mesh.py — turn character.png into a SINGLE skinned mesh (one texture) plus a
humanoid skeleton, for smooth Live2D/Spine-style deformation (linear blend
skinning). No separate cut-out parts: the whole character is one continuous mesh,
so it always reads as one intact, consistent figure and bends smoothly at joints.

Output: mesh.json {tex(base64), texW, texH, verts, uvs, tris, wIdx, wWt, bones}
        debug/weights.png (vertices coloured by dominant bone)
        debug/mesh.png    (wireframe over the character)
"""
import base64, io, json, os
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = os.path.dirname(__file__)
SRC = os.path.join(HERE, "..", "..", "character.png")
TEX_H = 1024          # texture height (px); crisp but small
STEP = 15             # mesh grid spacing (px) in texture space
FALLOFF = 3.2         # skinning weight falloff power


def char_mask(rgb):
    lbl, n = ndimage.label(rgb.min(axis=2) < 232)
    sizes = ndimage.sum(np.ones_like(lbl), lbl, range(1, n + 1))
    return lbl == (np.argmax(sizes) + 1)


def seg_dist(px, py, ax, ay, bx, by):
    """distance from points (px,py) to segment a-b (vectorised)."""
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    L2 = vx * vx + vy * vy + 1e-9
    t = np.clip((wx * vx + wy * vy) / L2, 0, 1)
    cx, cy = ax + t * vx, ay + t * vy
    return np.hypot(px - cx, py - cy)


def main():
    im = Image.open(SRC).convert("RGB")
    W, H = im.size
    rgb = np.array(im).astype(np.int16)
    m = ndimage.binary_erosion(char_mask(rgb), iterations=1)
    ys, xs = np.where(m)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    Wb, Hb = x1 - x0, y1 - y0

    # --- texture: the whole character on transparent bg, cropped + downscaled ---
    rgba = np.dstack([np.array(im), (m * 255).astype(np.uint8)])[y0:y1 + 1, x0:x1 + 1]
    scale = TEX_H / (Hb + 1)
    texW, texH = max(1, round((Wb + 1) * scale)), TEX_H
    tex = Image.fromarray(rgba, "RGBA").resize((texW, texH), Image.LANCZOS)
    alpha = np.array(tex)[:, :, 3]

    def TX(fx): return fx * texW           # frac of width  -> texture x
    def TY(fy): return fy * texH           # frac of height -> texture y

    # --- colour/part masks at texture resolution (anatomical regions) ----------
    trgb = np.array(tex)[:, :, :3].astype(int)
    Rc, Gc, Bc = trgb[:, :, 0], trgb[:, :, 1], trgb[:, :, 2]
    bright = trgb.mean(2)
    cM = alpha > 24
    beige = cM & (bright > 158) & (np.abs(Rc - Gc) < 26) & ((Rc - Bc) < 48)
    skin = cM & (Rc > 135) & (Rc - Bc > 20) & (Rc - Gc > 6) & (bright > 116) & (bright < 236) & ~beige
    dark = cM & (bright < 100)
    YY = np.repeat(np.arange(texH)[:, None], texW, 1)
    XX = np.repeat(np.arange(texW)[None, :], texH, 0)

    def largest(m):
        lbl, n = ndimage.label(m)
        if n == 0:
            return m
        return lbl == (1 + int(np.argmax(ndimage.sum(np.ones_like(lbl), lbl, range(1, n + 1)))))

    neck_y, sh_y, el_y = TY(0.19), TY(0.215), TY(0.40)
    waist_y, hip_y, knee_y = TY(0.47), TY(0.585), TY(0.74)
    cxv = TX(0.5)
    vstruct = np.array([[0, 1, 0], [0, 1, 0], [0, 1, 0]], bool)

    # forearms (skin, watch bridged), per side
    def forearm(side):
        band = skin & (YY > sh_y + 6) & (YY < TY(0.60)) & side
        lbl, n = ndimage.label(band)
        keep = np.zeros_like(band)
        for i in range(1, n + 1):
            mm = lbl == i
            if mm.sum() > 600:
                keep |= mm
        keep = ndimage.binary_dilation(keep, structure=vstruct, iterations=9)
        keep = ndimage.binary_erosion(keep, structure=vstruct, iterations=9)
        return ndimage.binary_fill_holes(keep) & cM
    foreL = forearm(XX < cxv)
    foreR = forearm(XX >= cxv)
    cuffL = np.where(foreL)[0].min() if foreL.any() else el_y
    cuffR = np.where(foreR)[0].min() if foreR.any() else el_y

    # upper-arm sleeves (dark, lateral, shoulder->cuff)
    spanR = np.clip((YY - sh_y) / max(1, (el_y - sh_y)), 0, 1)
    innerR = TX(0.62) + spanR * (TX(0.665) - TX(0.62))
    innerL = TX(0.38) + spanR * (TX(0.335) - TX(0.38))
    uaR = largest(dark & (YY >= sh_y - 6) & (YY <= cuffR + 12) & (XX > innerR) & (XX >= cxv))
    uaL = largest(dark & (YY >= sh_y - 6) & (YY <= cuffL + 12) & (XX < innerL) & (XX < cxv))

    # legs split by the inseam and the knee
    sideL, sideR = XX <= cxv, XX > cxv
    thighL = cM & (YY >= hip_y - TY(0.05)) & (YY < knee_y) & sideL & ~foreL & ~uaL
    thighR = cM & (YY >= hip_y - TY(0.05)) & (YY < knee_y) & sideR & ~foreR & ~uaR
    shinL = cM & (YY >= knee_y) & sideL
    shinR = cM & (YY >= knee_y) & sideR
    headM = cM & (YY < neck_y)

    # --- per-pixel bone label (priority) ---------------------------------------
    NB = 11  # hips,spine,head,upperArmL,lowerArmL,upperArmR,lowerArmR,upperLegL,lowerLegL,upperLegR,lowerLegR
    bidx = {n: i for i, n in enumerate(
        ["hips", "spine", "head", "upperArmL", "lowerArmL", "upperArmR", "lowerArmR",
         "upperLegL", "lowerLegL", "upperLegR", "lowerLegR"])}
    label = np.full((texH, texW), bidx["spine"], int)     # default torso = spine
    label[(YY >= waist_y) & (YY < hip_y)] = bidx["hips"]   # pelvis band -> stable hips
    for m, name in [(thighL, "upperLegL"), (thighR, "upperLegR"), (shinL, "lowerLegL"),
                    (shinR, "lowerLegR"), (uaL, "upperArmL"), (uaR, "upperArmR"),
                    (foreL, "lowerArmL"), (foreR, "lowerArmR"), (headM, "head")]:
        label[m] = bidx[name]
    label[~cM] = -1


    # --- humanoid skeleton (joint positions as fractions of the texture) --------
    J = {
        "hips": (0.50, 0.56), "waist": (0.50, 0.47), "neck": (0.50, 0.17),
        "headTop": (0.50, 0.02),
        "shoulderL": (0.34, 0.215), "elbowL": (0.27, 0.40), "handL": (0.30, 0.56),
        "shoulderR": (0.66, 0.215), "elbowR": (0.73, 0.40), "handR": (0.70, 0.56),
        "hipL": (0.43, 0.585), "kneeL": (0.40, 0.74), "ankleL": (0.42, 0.95),
        "hipR": (0.57, 0.585), "kneeR": (0.60, 0.74), "ankleR": (0.58, 0.95),
    }
    Jp = {k: (TX(v[0]), TY(v[1])) for k, v in J.items()}

    # --- mesh: regular grid clipped to the silhouette ---------------------------
    gx = np.arange(0, texW + STEP, STEP)
    gy = np.arange(0, texH + STEP, STEP)
    cols, rows = len(gx), len(gy)

    def inside(ix, iy):
        x, y = min(int(gx[ix]), texW - 1), min(int(gy[iy]), texH - 1)
        x2, y2 = max(0, x - STEP // 2), max(0, y - STEP // 2)
        return alpha[y2:y + 1, x2:x + 1].max() > 24 if (y >= 0 and x >= 0) else False

    vid = {}
    verts, uvs = [], []

    def vert(ix, iy):
        key = (ix, iy)
        if key not in vid:
            x, y = float(gx[ix]), float(gy[iy])
            vid[key] = len(verts)
            verts.append((x, y)); uvs.append((x / texW, y / texH))
        return vid[key]

    tris = []
    for iy in range(rows - 1):
        for ix in range(cols - 1):
            # keep a cell if any of its 4 corners' neighbourhoods are inside
            if not (inside(ix, iy) or inside(ix + 1, iy) or inside(ix, iy + 1) or inside(ix + 1, iy + 1)):
                continue
            a = vert(ix, iy); b = vert(ix + 1, iy)
            c = vert(ix, iy + 1); d = vert(ix + 1, iy + 1)
            tris += [[a, b, d], [a, d, c]]

    verts = np.array(verts, float)
    px, py = verts[:, 0], verts[:, 1]

    # --- skinning weights: anatomical label per vertex, smoothed across joints --
    # nearest labelled pixel for each vertex (so transparent grid verts get a part)
    lab_idx = ndimage.distance_transform_edt(label < 0, return_distances=False,
                                             return_indices=True)
    vlabel = np.empty(len(verts), int)
    for i in range(len(verts)):
        x = min(int(round(px[i])), texW - 1); y = min(int(round(py[i])), texH - 1)
        lv = label[y, x]
        if lv < 0:
            lv = label[lab_idx[0][y, x], lab_idx[1][y, x]]
        vlabel[i] = max(0, lv)

    W = np.zeros((len(verts), NB))
    W[np.arange(len(verts)), vlabel] = 1.0
    # build grid adjacency from vid, then Laplacian-smooth the weight field so the
    # mesh blends ONLY across joints (interiors stay ~pure -> no torso dragging).
    nbrs = [[] for _ in range(len(verts))]
    for (ix, iy), vi in vid.items():
        for jx, jy in ((ix + 1, iy), (ix - 1, iy), (ix, iy + 1), (ix, iy - 1)):
            vj = vid.get((jx, jy))
            if vj is not None:
                nbrs[vi].append(vj)
    for _ in range(8):
        Wn = W.copy()
        for vi in range(len(verts)):
            if nbrs[vi]:
                Wn[vi] = (W[vi] + W[nbrs[vi]].sum(0)) / (1 + len(nbrs[vi]))
        W = Wn
    order = np.argsort(-W, axis=1)[:, :3]
    wIdx = order.astype(int)
    wWt = np.take_along_axis(W, order, axis=1)
    wWt = wWt / np.clip(wWt.sum(axis=1, keepdims=True), 1e-6, None)

    # bones (head joint = pivot; parent index)
    BONES = [
        ("hips", -1, "hips", "waist"), ("spine", 0, "waist", "neck"), ("head", 1, "neck", "headTop"),
        ("upperArmL", 1, "shoulderL", "elbowL"), ("lowerArmL", 3, "elbowL", "handL"),
        ("upperArmR", 1, "shoulderR", "elbowR"), ("lowerArmR", 5, "elbowR", "handR"),
        ("upperLegL", 0, "hipL", "kneeL"), ("lowerLegL", 7, "kneeL", "ankleL"),
        ("upperLegR", 0, "hipR", "kneeR"), ("lowerLegR", 9, "kneeR", "ankleR"),
    ]

    # --- write mesh.json --------------------------------------------------------
    buf = io.BytesIO(); tex.save(buf, "PNG")
    bones_out = [{"name": n, "parent": par,
                  "pivot": [round(Jp[hj][0], 2), round(Jp[hj][1], 2)],
                  "tail": [round(Jp[tj][0], 2), round(Jp[tj][1], 2)]} for n, par, hj, tj in BONES]
    mesh = {
        "tex": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(),
        "texW": texW, "texH": texH,
        "verts": [[round(v[0], 2), round(v[1], 2)] for v in verts],
        "uvs": [[round(u[0], 5), round(u[1], 5)] for u in uvs],
        "tris": tris,
        "wIdx": wIdx.tolist(), "wWt": [[round(w, 4) for w in row] for row in wWt],
        "bones": bones_out,
    }
    with open(os.path.join(HERE, "mesh.json"), "w") as f:
        json.dump(mesh, f)
    print("verts", len(verts), "tris", len(tris), "bones", len(BONES), "tex", (texW, texH))

    # --- debug: weights (colour by dominant bone) + wireframe -------------------
    os.makedirs(os.path.join(HERE, "debug"), exist_ok=True)
    palette = np.random.RandomState(3).randint(40, 230, (len(BONES), 3))
    wimg = Image.fromarray(np.array(tex)).convert("RGBA")
    dr = ImageDraw.Draw(wimg)
    for i, (vx, vy) in enumerate(verts):
        c = tuple(palette[wIdx[i, 0]])
        dr.ellipse([vx - 3, vy - 3, vx + 3, vy + 3], fill=c + (255,))
    for n, par, hj, tj in BONES:
        ax, ay = Jp[hj]; bx, by = Jp[tj]
        dr.line([ax, ay, bx, by], fill=(255, 255, 255, 255), width=2)
    wimg.save(os.path.join(HERE, "debug", "weights.png"))

    mimg = Image.fromarray(np.array(tex)).convert("RGBA")
    dm = ImageDraw.Draw(mimg)
    for t in tris:
        p = [tuple(verts[t[k]]) for k in range(3)]
        dm.line([p[0], p[1], p[2], p[0]], fill=(0, 200, 255, 120), width=1)
    mimg.save(os.path.join(HERE, "debug", "mesh.png"))


if __name__ == "__main__":
    main()
