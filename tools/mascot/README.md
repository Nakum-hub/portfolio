# Mascot gesture system

The portfolio's companion character is a **full-body skeletal rig** driven by a
**library of motion clips**. The whole engine lives in `index.html` under
`window.Mascot`; this folder holds the offline tooling that produces the rig art.

## How it works

1. **Cut once.** `build_pieces.py` takes the full-body side-profile frame from
   the reference video and cuts the character (head → toe, including shoes) into
   four reusable pieces: `upper` (head + torso, with the arm carved out), `arm`,
   `thigh`, and `shin` (+ shoe). They are trimmed to a **shared canvas** so their
   pixel coordinates line up, then base64'd into `index.html`.

2. **Pose with a skeleton.** The rig knows a few joints (`skel.json`): the **hip**
   (root), the **shoulder** (arm pivot), and the **knee**. To draw a pose it
   rotates each piece about its joint:

   - `upper` rotates about the hip (torso lean),
   - `thigh` rotates about the hip, `shin` rotates about the knee (which itself
     rides on the end of the thigh) → a bent knee,
   - `arm` rotates about the shoulder (arm swing),
   - the far leg is the same `thigh`/`shin` drawn **darkened and behind** for depth.

3. **Animate with clips.** A *gesture* is just a function of normalised time
   `t ∈ [0,1)` returning joint angles. Because every gesture reuses the same four
   pieces, **adding a gesture needs no new art** — only data.

## The pose object

```js
{
  thN, thF,   // near / far thigh angle  (degrees)
  knN, knF,   // near / far knee bend    (degrees, >= 0)
  aN,         // near arm swing          (degrees)
  bob,        // vertical hip rise       (pixels)
  lean        // torso lean              (degrees)
}
```

Anything omitted defaults to 0 (a neutral standing pose).

## Adding a gesture

Edit the `GESTURES` object in `index.html`:

```js
GESTURES.wave = {
  dur: 1.4, loop: false,
  pose: function (t) {
    var th = Math.PI * 2 * t;
    return { aN: -40 + 18 * Math.sin(th * 3), lean: 1 };  // raise + waggle the arm
  }
};
```

Then trigger it: `Mascot.play('wave')`, or queue it: `Mascot.queue('wave')`.
`Mascot.list()` returns the available gesture names. The bundled clips are
`walk` (a natural human gait — opposite arm/leg swing, knee flex, hip bob,
torso counter-rotation) and `idle` (quiet breathing).

## Player API

| Call | Effect |
| --- | --- |
| `Mascot.walkIn()` | stride in from off-screen-left, then settle into `idle` |
| `Mascot.play(name, {loop})` | play a gesture (loops if the clip says so, or force with `loop`) |
| `Mascot.queue(name)` | play `name` after the current (non-looping) clip ends |
| `Mascot.face('left'\|'right')` | flip the facing direction |
| `Mascot.list()` | array of gesture names |

## Regenerating the art

```bash
python3 tools/mascot/build_pieces.py \
  --video "Remove background project - June 23, 2026 at 14.30.43.mp4" \
  --ss 13.2 --out tools/mascot/out
```

This writes `upper.b64`, `arm.b64`, `thigh.b64`, `shin.b64` and `skel.json`.
Paste each `.b64` into the matching entry of the `SRC` object in `index.html`,
and copy `skel.json`'s numbers into the `SK` object if landmarks changed.

> The reference video shows only standing poses, so the walk is **rigged**, not
> filmed. For an even more lifelike gait, drop in a short side-view walking clip
> and re-measure the landmarks in `build_pieces.py`.
