# Mascot — living character (single-entity warp)

The companion in the portfolio is a **single, intact character** that is animated, not a
video and not a sprite flipbook, and **not cut into parts**. The whole illustration is one
texture, warped smoothly each frame — the way a 2-D character is brought to life (Live2D
principle) — so it can **never separate into pieces and never shows a seam**.

> **What "real motion" means here.** Each frame the figure is drawn as a stack of thin
> horizontal slices whose horizontal offset eases from **0 at the feet** to a gentle lean at
> the **head** — a smooth bend **toward the visitor's cursor** — plus a subtle **breathing**
> stretch through the chest. Feet stay planted. It is always **full-body, head-to-shoes,
> front-and-centre**, one continuous image.

## Files

| File | Role |
| --- | --- |
| `rig.js` | The runtime. Draws the one texture as ~hundreds of overlapping slices, bending toward the cursor (smoothstep from feet→head) with a breathing stretch. `__RIG__` (texture + feet/head/centre) is filled at build time. Honours `prefers-reduced-motion` (stands still). |
| `build_rig.py` | The builder. Keys the white background out of `character.png`, crops to a padded box, downscales to a single WebP data URI, measures feet/head/centre, fills `rig.js`, and splices the mascot block into `index.html`. |
| `rig_parts/char.webp` | The single keyed texture + `rig.json`, for inspection. |

Rebuild after changing the design or the motion: `python3 tools/mascot/build_rig.py`.

### Why a warp (one texture) and not cut-out parts

Cutting the character into head/torso/legs lets the pieces move independently — under motion
that reads as **separate parts and seams**, which is a non-starter for a portfolio. Warping a
**single texture** keeps the body one intact entity by construction: there is nothing to come
apart. The slices overlap by a fraction of a pixel so there are no horizontal lines, and the
bend curve keeps the legs straight while the upper body leans, so it reads as a natural sway.

## Motion reference (recorded clips — kept, not played)

The reference video and the recorded clips under `clips/` (and `build_clip.py`) are kept only
as **motion reference** — how the gestures should look. They are not embedded or played.

## Honest limit & studio upgrade path

This warp gives a living idle + cursor lean from a single front illustration. **Big arm/finger
gestures (a wave)** are not possible from one still — for those the professional routes are a
**Live2D / Spine / Rive** rig (mesh + bones authored in their editor) or a **3-D VRM** avatar.
Those need manual asset work; this is the fully-automatic, seam-free option from the art we have.

## API

```js
Mascot.look(x, y)   // aim toward a point (x,y in 0..1 of the canvas)
Mascot.rest()       // stop tracking, return to idle drift
```
