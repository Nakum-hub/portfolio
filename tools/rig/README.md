# Character rig — humanoid 2-D cut-out

A real, controllable **2-D humanoid rig** built from the single front illustration
`character.png`. The illustration is sliced into body-part layers, pinned at
anatomical joints, and posed by **live math** every frame (forward kinematics) —
breathing, weight-shift sway, a cursor look-at, a **wave**, a **gesture**, and an
in-place **walk**. Nothing is a recorded clip or video; every pose is computed.

> The character is **never altered** — layers are cut straight from the original
> pixels, so the face, outfit and skin tone are identical to the source art.

## Files

| File | What it is |
|---|---|
| `build_rig.py` | Segments `character.png` → part layers + `rig.json` (joints, pivots, parenting). Re-run if the source art changes. |
| `rig-engine.js` | The FK solver + animation engine (idle / wave / gesture / walk / look-at). |
| `bundle.py` | Packs everything into the self-contained `../character-rig.html`. |
| `rig.json` | Canvas size, per-part placement, joint pivots, parent links, z-order. |
| `parts/*.png` | Cropped RGBA body-part layers used by the web rig. |
| `live2d/*.png` + `layers.json` | Full-canvas layers + manifest for a **Live2D / Cubism** rig (see `live2d/IMPORT-GUIDE.md`). |

## Rig anatomy

```
hips (root)
├── torso  (waist pivot — sway + breathing)
│   ├── head    (neck pivot — tilt + look-at)
│   ├── foreL   (left  cuff pivot — gesture)
│   └── foreR   (right cuff pivot — wave; includes the watch)
├── thighL (hip pivot) → shinL (knee pivot)   ┐ in-place walk
└── thighR (hip pivot) → shinR (knee pivot)   ┘
```

**Why it looks seam-free.** The shirt is one flat charcoal and the trousers one
flat beige, so a limb can be cut at its joint and the flat colour *inpainted*
behind it. The torso and leg layers stay fully opaque across the whole
silhouette, so a lifted forearm reveals clean shirt/trouser underneath — never a
hole. The moving forearm is **skin-only** (the rolled sleeve cuff stays on the
torso), so the cut runs along a real skin/sleeve colour edge and never tears the
dark shirt.

## Build

```bash
pip install pillow numpy scipy
python3 tools/rig/build_rig.py      # -> rig.json, parts/, live2d/
python3 tools/rig/bundle.py         # -> character-rig.html (self-contained)
```

## Preview

Open `character-rig.html` in any browser. Move the cursor — he follows it. Use
the buttons for **Wave / Gesture / Walk / Idle**. Honors `prefers-reduced-motion`.

## Embed in the site

It is one self-contained file, so the simplest embed is an iframe:

```html
<iframe src="character-rig.html" title="Character"
        style="border:0;width:340px;height:560px;background:transparent"></iframe>
```

To drive it from your own code instead, load `rig-engine.js` with a
`window.__RIG__` object (see `bundle.py`) and call `Rig.wave()`, `Rig.gesture()`,
`Rig.walk()`, `Rig.rest()`, or `Rig.look(x, y)` (x,y in −1..1).

## Limits & upgrade path

A single front illustration has no side/back, so this is a front-facing
rigid-part rig: great for an alive idle, look-at, a forearm wave/gesture and a
gentle in-place step. For mesh-deformed hair/cloth and big shoulder gestures, the
`live2d/` layers are ready to import into Live2D Cubism (`live2d/IMPORT-GUIDE.md`).
