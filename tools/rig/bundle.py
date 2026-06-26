#!/usr/bin/env python3
"""bundle.py — pack rig.json + parts/*.png + rig-engine.js into ONE self-contained
`character-rig.html` (no external files, no network). Open it in any browser, or
drop it into the portfolio with a single <iframe>."""
import base64, json, os

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..", "..")
OUT = os.path.join(ROOT, "character-rig.html")


def b64(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def main():
    rig = json.load(open(os.path.join(HERE, "rig.json")))
    for p in rig["parts"]:
        p["href"] = b64(os.path.join(HERE, p["src"]))
        p.pop("src", None)
    rig["mount"] = "rigSvg"
    engine = open(os.path.join(HERE, "rig-engine.js")).read()
    html = TEMPLATE.replace("/*__RIG__*/", json.dumps(rig)).replace("/*__ENGINE__*/", engine)
    with open(OUT, "w") as f:
        f.write(html)
    print("wrote", OUT, round(os.path.getsize(OUT) / 1024), "KB")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Character rig — Naveen T S</title>
<style>
  :root{ --bg:#0b0d10; --panel:rgba(255,255,255,.06); --line:rgba(255,255,255,.14);
         --ink:#eef1f4; --dim:#9aa2ad; --mint:#5eead4; }
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{height:100%}
  body{background:radial-gradient(120% 80% at 50% 0%, #11151b 0%, var(--bg) 60%);
       color:var(--ink); font-family:'Inter',system-ui,sans-serif; display:flex;
       flex-direction:column; align-items:center; justify-content:flex-end;
       min-height:100svh; overflow:hidden;}
  .stage{position:relative; flex:1; width:100%; display:flex; align-items:flex-end;
         justify-content:center;}
  #rigSvg{height:min(86svh,760px); width:auto; display:block;
          filter:drop-shadow(0 26px 30px rgba(0,0,0,.45));}
  .shadow{position:absolute; bottom:6%; left:50%; transform:translateX(-50%);
          width:min(30vw,230px); height:26px; border-radius:50%;
          background:radial-gradient(ellipse at center, rgba(0,0,0,.45), transparent 70%);
          filter:blur(3px); z-index:-1;}
  .controls{display:flex; gap:10px; flex-wrap:wrap; justify-content:center;
            padding:18px 16px 26px;}
  button{font:600 14px 'Inter',sans-serif; color:var(--ink); cursor:pointer;
          background:var(--panel); border:1px solid var(--line); border-radius:12px;
          padding:11px 18px; backdrop-filter:blur(6px); transition:.18s;}
  button:hover{border-color:var(--mint); color:var(--mint); transform:translateY(-1px);}
  button:active{transform:translateY(0);}
  .hint{position:fixed; top:16px; left:0; right:0; text-align:center; color:var(--dim);
        font-size:13px; letter-spacing:.02em;}
</style>
</head>
<body>
  <p class="hint">Move your cursor — he follows it. Try the buttons.</p>
  <div class="stage">
    <div class="shadow"></div>
    <svg id="rigSvg" xmlns="http://www.w3.org/2000/svg" role="img"
         aria-label="Animated character"></svg>
  </div>
  <div class="controls">
    <button onclick="Rig.wave()">👋 Wave</button>
    <button onclick="Rig.gesture()">💬 Gesture</button>
    <button onclick="Rig.walk()">🚶 Walk</button>
    <button onclick="Rig.rest()">🧍 Idle</button>
  </div>
  <script>window.__RIG__ = /*__RIG__*/;</script>
  <script>/*__ENGINE__*/</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
