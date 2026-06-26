#!/usr/bin/env python3
"""bundle_mesh.py — pack mesh.json + mesh-engine.js into one self-contained
character-mesh.html (WebGL skinned single-mesh character)."""
import json, os
HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "..", "..", "character-mesh.html")

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Character (mesh rig) — Naveen T S</title>
<style>
  :root{--bg:#0b0d10;--panel:rgba(255,255,255,.06);--line:rgba(255,255,255,.14);--ink:#eef1f4;--mint:#5eead4;}
  *{box-sizing:border-box;margin:0;padding:0}html,body{height:100%}
  body{background:radial-gradient(120% 80% at 50% 0%,#11151b 0%,var(--bg) 60%);color:var(--ink);
       font-family:'Inter',system-ui,sans-serif;display:flex;flex-direction:column;align-items:center;
       justify-content:flex-end;min-height:100svh;overflow:hidden;}
  .stage{position:relative;flex:1;width:100%;display:flex;align-items:flex-end;justify-content:center;}
  #rigCanvas{height:min(88svh,800px);width:auto;aspect-ratio:var(--ar,9/32);display:block;
             filter:drop-shadow(0 26px 30px rgba(0,0,0,.45));}
  .controls{display:flex;gap:10px;flex-wrap:wrap;justify-content:center;padding:18px 16px 26px;}
  button{font:600 14px 'Inter',sans-serif;color:var(--ink);cursor:pointer;background:var(--panel);
         border:1px solid var(--line);border-radius:12px;padding:11px 18px;transition:.18s;}
  button:hover{border-color:var(--mint);color:var(--mint);transform:translateY(-1px);}
  .hint{position:fixed;top:16px;left:0;right:0;text-align:center;color:#9aa2ad;font-size:13px;}
</style></head><body>
  <p class="hint">Mesh-deformed rig — one continuous figure. Try the buttons.</p>
  <div class="stage"><canvas id="rigCanvas"></canvas></div>
  <div class="controls">
    <button onclick="Rig.wave()">👋 Wave</button>
    <button onclick="Rig.point()">👉 Point</button>
    <button onclick="Rig.cheer()">🙌 Cheer</button>
    <button onclick="Rig.walk()">🚶 Walk</button>
    <button onclick="Rig.rest()">🧍 Idle</button>
  </div>
  <script>window.__MESH__ = /*__MESH__*/;</script>
  <script>document.getElementById('rigCanvas').style.setProperty('--ar', window.__MESH__.texW+'/'+window.__MESH__.texH);</script>
  <script>/*__ENGINE__*/</script>
</body></html>
"""

def main():
    mesh = json.load(open(os.path.join(HERE, "mesh.json")))
    mesh["mount"] = "rigCanvas"
    engine = open(os.path.join(HERE, "mesh-engine.js")).read()
    html = TEMPLATE.replace("/*__MESH__*/", json.dumps(mesh)).replace("/*__ENGINE__*/", engine)
    open(OUT, "w").write(html)
    print("wrote", OUT, round(os.path.getsize(OUT) / 1024), "KB")

if __name__ == "__main__":
    main()
