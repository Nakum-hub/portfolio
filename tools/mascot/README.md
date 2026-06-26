# Mascot — living character (procedural rig)

The companion in the bottom-left of the portfolio is a **procedurally animated character**,
not a video or a sprite flipbook. The character design is segmented into a small skeleton and
animated **by math every frame** — the way pros bring a 2-D character to life (Live2D / Spine /
Rive style). Nothing is pre-recorded.

> **What "real motion" means here.** Each frame the rig computes the pose: continuous
> **breathing**, a **weight-shift sway**, and a **head that looks toward the visitor's cursor**
> (with idle drift when the pointer is away). The character is always **full-body, head-to-shoes,
> front-and-centre**, at a constant size.

## The live rig

| File | Role |
| --- | --- |
| `rig.js` | The runtime. A 3-part skeleton (head / torso+arms / legs) drawn on a `<canvas>`; every frame it applies breathing, sway and head look-at around the joint pivots. `__RIG__` (part images + pivots) is filled in at build time. |
| `build_rig.py` | The builder. Keys the white background out of `character.png`, cuts the three parts with feathered overlapping seams, computes the neck/waist pivots, downscales the parts to WebP data URIs, fills `rig.js`, and splices the mascot block into `index.html`. |
| `rig_parts/` | The cut parts (`head/upper/lower.webp`) + `rig.json`, for inspection. |

Rebuild after changing the design or the rig: `python3 tools/mascot/build_rig.py`.

### How the rig is cut (and why it's seam-free)

The arms hang flush against the torso in this illustration, so the body splits cleanly into
**head** (above the collar), **torso+arms**, and **legs**. Parts overlap and are feathered at the
seams, and the **legs stay opaque under the shirt hem**, so sway/breathing never opens a gap.
Pivots: the **neck** (head tilt/turn) and the **waist** (torso sway + breathing); the legs are
planted. Draw order is legs → torso → head.

> **Honest limit.** Because the arms aren't separable in this single front illustration, the rig
> animates head + torso + legs (which is what makes a 2-D character read as *alive*). Big arm /
> finger gestures (a wave) would need either **extra reference art with the arm raised/separated**,
> or a **Live2D / Spine / Rive** rig authored in that tool, or a **3-D (VRM) avatar**. Those are the
> studio routes; this rig is the fully-automatic one buildable from the art we have.

## Motion reference (recorded clips — kept, not played)

The reference video and the recorded clips under `clips/` (built by `build_clip.py` from
`sources/`) are **kept only as motion reference** — they show how the gestures should *look*.
They are **not** embedded or played on the page. Treat them as the brief for new rig motions, or
as source if we ever switch to a clip-based fallback.

## API

```js
Mascot.look(x, y)   // make the head look toward a point (x,y in 0..1 of the canvas)
Mascot.rest()       // stop tracking; return to idle drift
Mascot.el           // the mascot element
```

Under `prefers-reduced-motion` the character stands still (no breathing/sway/tracking).
