# Character rig — humanoid 2-D cut-out

A real, controllable **2-D humanoid rig** built from the single front
illustration `character.png`. The illustration is sliced into body-part layers
named like a VRM humanoid skeleton, pinned at anatomical joints, and posed by
**live math** every frame (forward kinematics) — breathing, weight-shift sway, a
cursor look-at, a **wave**, a **point**, a both-arms **cheer**, and an in-place
**walk**. Nothing is a recorded clip or video; every pose is computed.

> The character is **never altered** — layers are cut straight from the original
> pixels, so the face, outfit and skin tone are identical to the source art.

## Files

| File | What it is |
|---|---|
| `build_rig.py` | Segments `character.png` → part layers + `rig.json` (joints, pivots, parenting). Re-run if the source art changes. |
| `rig-engine.js` | The FK solver + animation engine (idle / wave / point / cheer / walk / look-at). |
| `bundle.py` | Packs everything into the self-contained `../character-rig.html`. |
| `rig.json` | Canvas size, per-part placement, joint pivots, parent links, z-order. |
| `parts/*.png` | Cropped RGBA body-part layers used by the web rig. |
| `live2d/*.png` + `layers.json` | Full-canvas layers + manifest for a **Live2D / Cubism** rig (see `live2d/IMPORT-GUIDE.md`). |

## Rig anatomy (VRM-style humanoid bones)

```
hips (root)
├── spine  (waist pivot — sway + breathing)
│   ├── head        (neck pivot — tilt + look-at)
│   ├── upperArmL → lowerArmL    (shoulder → elbow; left hand)
│   └── upperArmR → lowerArmR    (shoulder → elbow; right hand + watch)
├── upperLegL → lowerLegL        (hip → knee)
└── upperLegR → lowerLegR        (hip → knee)
```

**Why it looks seam-free.** The shirt is one flat charcoal and the trousers one
flat beige, so limbs can be cut at their joints and the flat colour inpainted
behind them. The **dark upper-arm sleeve** is cut from the torso along the raglan
seam (dark-on-dark → invisible). The **moving forearm is skin-only** (a real
skin/sleeve colour edge). The whole arm footprint is removed from the torso with
a soft seam the arms cover at rest, so a lifted arm reveals a clean body edge /
the beige thigh behind it rather than the arm's imprint.

## Build

```bash
pip install pillow numpy scipy
python3 tools/rig/build_rig.py      # -> rig.json, parts/, live2d/
python3 tools/rig/bundle.py         # -> character-rig.html (self-contained)
```

## Preview

Open `character-rig.html` in any browser. Move the cursor — he follows it. Use
the buttons for **Wave / Point / Cheer / Walk / Idle**. Honors
`prefers-reduced-motion`.

## Embed in the site

It is one self-contained file, so the simplest embed is an iframe:

```html
<iframe src="character-rig.html" title="Character"
        style="border:0;width:340px;height:560px;background:transparent"></iframe>
```

To drive it from your own code instead, load `rig-engine.js` with a
`window.__RIG__` object (see `bundle.py`) and call `Rig.wave()`, `Rig.point()`,
`Rig.cheer()`, `Rig.walk()`, `Rig.rest()`, or `Rig.look(x, y)` (x,y in −1..1).

## Limits & upgrade path

A single front illustration has no side/back, so this is a front-facing
rigid-part rig: great for an alive idle, look-at, and front gestures (wave,
point, cheer, walk). Big arm raises reveal a slightly narrower torso side (the
body behind the arm isn't in the source art). For mesh-deformed hair/cloth and
studio-grade gestures, the `live2d/` layers are ready to import into Live2D
Cubism (`live2d/IMPORT-GUIDE.md`).
