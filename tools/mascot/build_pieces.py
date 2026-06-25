#!/usr/bin/env python3
"""
Build the mascot's limb pieces from the full-body reference video.

The character is a pure side profile (frame at ~13.2s of the reference clip).
We cut it into four reusable pieces -- upper (head+torso, arm carved out),
arm, thigh, shin(+shoe) -- trim them to a shared canvas so their pixel
coordinates line up, and emit:

  - <piece>.webp        the limb art (transparent, shared canvas)
  - <piece>.b64         base64 of the webp, ready to paste into index.html
  - skel.json           skeleton landmarks (pivots) in shared-canvas coords

The in-browser rig (see index.html -> window.Mascot) loads these four pieces
once and drives EVERY gesture by rotating them about the skeleton joints, so
adding a new gesture never needs new art -- just joint-angle data.

Usage:
    python3 tools/mascot/build_pieces.py \
        --video "Remove background project - June 23, 2026 at 14.30.43.mp4" \
        --ss 13.2 --out tools/mascot/out

Requires: ffmpeg on PATH, Pillow, numpy.
"""
import argparse, base64, json, os, subprocess, tempfile
from PIL import Image
import numpy as np

# Landmarks (in the ORIGINAL extracted frame's pixel coords) for the side
# profile. Re-measure these if you change the source frame.
LAND = dict(shoulderY=600, hemY=1228, kneeY=1675,
            hipX=1110, ARM_TH=46, handBottomY=1470)


def extract_frame(video, ss):
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    # -ss AFTER -i = accurate (frame-exact) seek.
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-i", video, "-ss", str(ss), "-frames:v", "1", path], check=True)
    return path


def build(video, ss, outdir):
    os.makedirs(outdir, exist_ok=True)
    frame = extract_frame(video, ss)
    im = Image.open(frame).convert("RGBA")
    a = np.array(im).astype(int)
    al, r, g, b = a[:, :, 3], a[:, :, 0], a[:, :, 1], a[:, :, 2]
    lum = np.maximum(np.maximum(r, g), b)
    solid = (al > 20) & (lum > 16)
    clean = np.array(im); clean[~solid] = 0
    src = Image.fromarray(clean, "RGBA")

    ys, xs = np.where(solid)
    X0, X1, Y0, Y1 = xs.min(), xs.max(), ys.min(), ys.max()
    PAD = 14
    cx0, cy0, cx1, cy1 = X0 - PAD, Y0 - PAD, X1 + PAD, Y1 + PAD
    src = src.crop((cx0, cy0, cx1, cy1))
    W, H = src.size
    arr = np.array(src); A = arr[:, :, 3] > 20
    R, G, B = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
    L = np.maximum(np.maximum(R, G), B)
    pants = (R > 150) & (G > 138) & (B > 118) & (L > 150) & A

    shoulderY = LAND["shoulderY"] - cy0
    hemY = LAND["hemY"] - cy0
    kneeY = LAND["kneeY"] - cy0
    footY = Y1 - cy0
    hipX = LAND["hipX"] - cx0
    ARM_TH = LAND["ARM_TH"]
    handBottom = LAND["handBottomY"] - cy0

    def front_edge(y):
        xx = np.where(A[y])[0]
        return xx.max() if len(xx) else None

    def blank():
        return np.zeros((H, W), bool)

    # ARM: a front strip above the hem + the sleeve/hand below the hem.
    arm = blank()
    for y in range(shoulderY, min(hemY, H)):
        xr = front_edge(y)
        if xr is None:
            continue
        x_back = max(0, xr - ARM_TH)
        arm[y, x_back:xr + 1] = A[y, x_back:xr + 1]
    for y in range(hemY, min(handBottom, H)):
        nonpants = A[y] & (~pants[y])
        xx = np.where(nonpants)[0]
        if len(xx) == 0:
            continue
        xr = xx.max(); x_back = max(xr - ARM_TH - 30, 0)
        sel = np.zeros(W, bool); sel[x_back:xr + 1] = nonpants[x_back:xr + 1]
        arm[y] = sel

    # UPPER (head + torso) with the arm strip carved out of the torso front.
    upper = blank()
    for y in range(0, hemY):
        xx = np.where(A[y])[0]
        if len(xx) == 0:
            continue
        upper[y, xx.min():xx.max() + 1] = A[y, xx.min():xx.max() + 1]
        if y >= shoulderY:
            xr = front_edge(y)
            if xr is not None:
                upper[y, xr - ARM_TH + 1:xr + 1] = False

    # THIGH and SHIN(+shoe)
    thigh = blank()
    for y in range(max(hemY - 18, 0), kneeY):
        xx = np.where(A[y] & pants[y])[0]
        if len(xx) == 0:
            xx = np.where(A[y])[0]
        if len(xx):
            thigh[y, xx.min():xx.max() + 1] = A[y, xx.min():xx.max() + 1]
    shin = blank()
    for y in range(max(kneeY - 10, 0), min(footY + 1, H)):
        xx = np.where(A[y])[0]
        if len(xx):
            shin[y, xx.min():xx.max() + 1] = A[y, xx.min():xx.max() + 1]

    def piece(mask):
        out = np.zeros((H, W, 4), np.uint8); out[mask] = arr[mask]
        return Image.fromarray(out, "RGBA")

    pieces = {"upper": piece(upper), "arm": piece(arm),
              "thigh": piece(thigh), "shin": piece(shin)}

    # Trim to a SHARED bounding box so every piece shares one coordinate frame.
    def bbox(p):
        m = np.array(p)[:, :, 3] > 8; yy, xx = np.where(m)
        return xx.min(), yy.min(), xx.max(), yy.max()
    bxs = [bbox(p) for p in pieces.values()]
    bx0 = min(b[0] for b in bxs); by0 = min(b[1] for b in bxs)
    bx1 = max(b[2] for b in bxs); by1 = max(b[3] for b in bxs)
    pad = 4
    bx0 = max(0, bx0 - pad); by0 = max(0, by0 - pad)
    bx1 = min(W, bx1 + pad); by1 = min(H, by1 + pad)

    # Joints computed from the pieces themselves (then shifted to shared coords).
    am = arm; ays, axs = np.where(am)
    arm_piv_x = int(np.median(axs[ays < ays.min() + 40]))
    arm_piv_y = int(ays.min()) + 6
    tys, txs = np.where(thigh)
    knee_local_y = int(tys.max()) - 4

    out_b64 = {}
    for k, p in pieces.items():
        c = p.crop((bx0, by0, bx1, by1))
        wp = os.path.join(outdir, f"{k}.webp")
        c.save(wp, "WEBP", quality=92, method=6)
        data = open(wp, "rb").read()
        open(os.path.join(outdir, f"{k}.b64"), "w").write(base64.b64encode(data).decode())
        out_b64[k] = len(data)

    skel = dict(cw=int(bx1 - bx0), ch=int(by1 - by0),
                hip=[int(hipX - bx0), int(hemY - by0)],
                arm=[int(arm_piv_x - bx0), int(arm_piv_y - by0)],
                kneeLocalY=int(knee_local_y - by0),
                hemY=int(hemY - by0), footY=int(footY - by0))
    json.dump(skel, open(os.path.join(outdir, "skel.json"), "w"), indent=2)
    os.remove(frame)
    print("pieces (bytes):", out_b64)
    print("skel:", json.dumps(skel))
    print(f"wrote *.webp, *.b64 and skel.json to {outdir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="path to the reference mp4")
    ap.add_argument("--ss", type=float, default=13.2, help="timestamp (s) of the side-profile frame")
    ap.add_argument("--out", default="tools/mascot/out")
    args = ap.parse_args()
    build(args.video, args.ss, args.out)
