# Mascot — full-body gesture system

The companion character in the bottom-left of the portfolio is a **gesture player**.
It is not a single animation: it is an engine that plays **named motion clips** on a
`<canvas>`, where each clip is a small sprite-atlas of full-body frames. Adding a new
gesture later is a **data change**, not new engineering.

> **POLICY — front & centre, full-body only.** Every clip must show the **full body,
> head-to-shoes** (never partial, never cropped), framed **front and centre** (no
> side / left / right posing, no zoom in or out). The character is rendered at a
> constant size. **Back-facing** clips are allowed **only when explicitly requested**.
> The entrance is a front-facing fade-in (no movement, no zoom).

## The two pieces

| File | Role |
| --- | --- |
| `engine.js` | The in-browser player (template). Loads clips, plays/queues them, crossfades between them, runs the walk-in entrance, honours `prefers-reduced-motion`. `__FW__`, `__FH__`, `__CLIPS__` are filled in at build time. |
| `build_clip.py` | The offline builder. Cuts frames, removes the background, **normalizes every frame to one full-body canvas**, packs each clip into a WebP atlas, and injects the engine + clips into `index.html`. |

The reference `*.mp4` in the repo root is the main source (real, front-facing motion).
Built atlases are written to `clips/` for inspection and embedded as data URIs in
`index.html` (the portfolio is a single self-contained file).

> `sources/walk_atlas.webp` is a side-on walk that is **retained but unused** under the
> front-only policy above. A real walk is inherently a side view, so a front-facing walk
> would need front-facing walk reference frames (the video contains none).

## Why "normalize to a common canvas"

The reference video **zooms** and the walk art is a different size, so raw frames would
make the character grow/shrink and hop between gestures. `build_clip.py` therefore scales
every frame so the **head-to-feet height is constant** and pins the **feet to a fixed
baseline**. Result: the character is the exact same size whether walking or idling, and
clips are interchangeable. **Always full-body, head-to-shoes, never cropped.**

## Adding a gesture (the whole workflow)

1. **Find the frames.** Make a contact sheet of the reference clip:
   ```bash
   ffmpeg -i "*.mp4" -vf "fps=2,scale=300:-1" /tmp/sheet_%03d.png
   ```
   Pick a frame range where the **full body and shoes are visible** (the first ~1.5 s of
   the clip is zoomed in to the thigh — avoid it). Frame number = sheet index × 15.
2. **Register it** in `CLIPS` inside `build_clip.py`:
   ```python
   "wave": {"source": "video", "frames": list(range(330, 366, 3)),
            "fps": 12, "loop": False, "mirror": False},
   ```
   - `loop: True` for resting/continuous motions (idle), `False` for one-shots (wave, nod).
   - `pingpong: True` makes a short clip loop seamlessly (plays forward then back).
   - `mirror: True` flips horizontally (rarely needed for front-facing clips).
3. **Build:** `python3 tools/mascot/build_clip.py`
4. **Use it** from the page or console: `Mascot.play('wave')`, `Mascot.queue('idle')`.

## Player API

```js
Mascot.enter()               // entrance: front-facing fade-in, settle into idle (auto-runs)
Mascot.play(name,{loop})     // play a clip now (clears the queue)
Mascot.queue(name,{loop})    // play after the current clip finishes
Mascot.list()                // -> ["idle", ...]
Mascot.has(name)             // is a clip registered?
Mascot.say(text,ms)          // speech bubble; Mascot.hush() to dismiss
```

Under `prefers-reduced-motion` the character simply stands (idle frame), no fade-in.

## Canvas constants (keep stable across clips)

`CW=320, CH=460, BODY_H=392, BASE_Y=CH-34`. Changing these re-scales every gesture, so
rebuild **all** clips if you touch them.
