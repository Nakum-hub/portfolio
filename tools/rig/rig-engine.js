/* rig-engine.js — a tiny forward-kinematics (FK) solver + animation engine for
 * the 2-D cut-out character. Each part is an <image> inside a <g>; every frame
 * we compute each part's *world* transform by composing the local rotate/scale
 * of every joint from the part up to the root (hips). Poses are computed from
 * math + the pointer, never replayed frames. */
(function () {
  "use strict";
  var SVGNS = "http://www.w3.org/2000/svg";
  var RIG = window.__RIG__;
  if (!RIG) { console.error("rig-engine: window.__RIG__ missing"); return; }

  // ---- 2-D affine matrix [a,b,c,d,e,f]  (x' = a*x + c*y + e ; y' = b*x + d*y + f)
  var M = {
    I: [1, 0, 0, 1, 0, 0],
    mul: function (m, n) {
      return [
        m[0] * n[0] + m[2] * n[1], m[1] * n[0] + m[3] * n[1],
        m[0] * n[2] + m[2] * n[3], m[1] * n[2] + m[3] * n[3],
        m[0] * n[4] + m[2] * n[5] + m[4], m[1] * n[4] + m[3] * n[5] + m[5]
      ];
    },
    T: function (x, y) { return [1, 0, 0, 1, x, y]; },
    R: function (a) { var c = Math.cos(a), s = Math.sin(a); return [c, s, -s, c, 0, 0]; },
    S: function (x, y) { return [x, 0, 0, y, 0, 0]; }
  };
  // local transform: rotate by `ang` and scale (sx,sy) about pivot, then nudge (tx,ty)
  function local(piv, ang, sx, sy, tx, ty) {
    return M.mul(M.T(piv[0] + (tx || 0), piv[1] + (ty || 0)),
           M.mul(M.R(ang || 0),
           M.mul(M.S(sx == null ? 1 : sx, sy == null ? 1 : sy),
                 M.T(-piv[0], -piv[1]))));
  }

  // ---- build the SVG scene -------------------------------------------------
  var svg = document.getElementById(RIG.mount || "rigSvg");
  svg.setAttribute("viewBox", "0 0 " + RIG.canvas.w + " " + RIG.canvas.h);
  svg.setAttribute("preserveAspectRatio", "xMidYMax meet");
  var P = {}, G = {};
  RIG.parts.forEach(function (p) {
    P[p.name] = p;
    var g = document.createElementNS(SVGNS, "g");
    var img = document.createElementNS(SVGNS, "image");
    img.setAttribute("x", p.x); img.setAttribute("y", p.y);
    img.setAttribute("width", p.w); img.setAttribute("height", p.h);
    img.setAttribute("href", p.href);
    img.setAttributeNS("http://www.w3.org/1999/xlink", "xlink:href", p.href);
    img.setAttribute("image-rendering", "optimizeQuality");
    g.appendChild(img); svg.appendChild(g); G[p.name] = g;
  });

  var ROOT = RIG.root_pivot;            // [x,y] hips pivot
  var pose = {};                        // per-frame joint state, filled each tick

  function world(name) {                // compose chain part -> ... -> hips -> root
    if (name === "hips") {
      var h = pose.hips || { x: 0, y: 0, ang: 0 };
      return M.mul(M.T(h.x, h.y), local(ROOT, h.ang, 1, 1, 0, 0));
    }
    var p = P[name], s = pose[name] || {};
    return M.mul(world(p.parent), local(p.pivot, s.ang, s.sx, s.sy, s.tx, s.ty));
  }

  function applyAll() {
    RIG.parts.forEach(function (p) {
      var m = world(p.name);
      G[p.name].setAttribute("transform",
        "matrix(" + m.map(function (v) { return v.toFixed(4); }).join(" ") + ")");
    });
  }

  // ---- input: pointer look-at ---------------------------------------------
  var look = { x: 0, y: 0 }, lookT = { x: 0, y: 0 }, pointerSeen = 0;
  function onMove(e) {
    var r = svg.getBoundingClientRect();
    lookT.x = Math.max(-1, Math.min(1, ((e.clientX - r.left) / r.width - 0.5) * 2));
    lookT.y = Math.max(-1, Math.min(1, ((e.clientY - r.top) / r.height - 0.5) * 2));
    pointerSeen = performance.now();
  }
  window.addEventListener("mousemove", onMove);
  window.addEventListener("touchmove", function (e) {
    if (e.touches[0]) onMove(e.touches[0]);
  }, { passive: true });

  // ---- animation state -----------------------------------------------------
  var REST = !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
  var mode = "idle", modeT = 0, walking = false, t0 = performance.now();
  var TAU = Math.PI * 2;

  function setMode(m) {
    if (m === "walk") { walking = !walking; mode = walking ? "walk" : "idle"; modeT = 0; return; }
    mode = m; modeT = 0;
  }
  // ease in-out
  function ez(x) { return x < 0 ? 0 : x > 1 ? 1 : x * x * (3 - 2 * x); }

  function frame(now) {
    var t = (now - t0) / 1000;
    // ease pointer look toward target (idle drift when pointer is away)
    var away = (now - pointerSeen) > 2600;
    if (away && !REST) { lookT.x = Math.sin(t * 0.45) * 0.5; lookT.y = 0.12 + Math.sin(t * 0.3) * 0.18; }
    look.x += (lookT.x - look.x) * 0.06; look.y += (lookT.y - look.y) * 0.06;

    var br = 0.5 + 0.5 * Math.sin(TAU * t / 4.0);      // breathing 0..1
    var amp = REST ? 0 : 1;

    // ---- idle baseline (always) -------------------------------------------
    pose.hips  = { x: 0, y: amp * (-1.2 * br), ang: amp * 0.012 * Math.sin(TAU * t / 6.2) };
    pose.torso = { ang: amp * 0.018 * Math.sin(TAU * t / 6.2 + 0.4), sx: 1, sy: 1 + amp * 0.014 * br };
    pose.head  = { ang: amp * 0.02 * Math.sin(TAU * t / 5.0) , tx: 0, ty: 0 };
    pose.foreL = { ang: amp * 0.03 * Math.sin(TAU * t / 6.2) };
    pose.foreR = { ang: amp * 0.03 * Math.sin(TAU * t / 6.2 + Math.PI) };
    pose.thighL = { ang: 0 }; pose.thighR = { ang: 0 };
    pose.shinL = { ang: 0 };  pose.shinR = { ang: 0 };

    // head look-at (additive)
    pose.head.ang += look.x * 0.20;
    pose.head.tx = look.x * 7; pose.head.ty = look.y * 4;

    modeT += 1 / 60;
    // ---- WAVE: right forearm lifts at the elbow and waves ------------------
    if (mode === "wave") {
      var D = 3.0, raise = -2.25;                      // raise the forearm up-and-out
      var k = modeT < 0.45 ? ez(modeT / 0.45)
            : modeT > D - 0.5 ? 1 - ez((modeT - (D - 0.5)) / 0.5) : 1;
      var wig = (modeT > 0.4 && modeT < D - 0.45) ? Math.sin((modeT - 0.4) * 10) * 0.28 : 0;
      pose.foreR.ang += k * raise + k * wig;
      pose.head.ang += k * 0.05;                        // slight head turn into the wave
      if (modeT > D) setMode("idle");
    }
    // ---- GESTURE: a friendly "talk/present" — open the near forearm + nod --
    if (mode === "gesture") {
      var Dg = 2.6, kg = modeT < 0.4 ? ez(modeT / 0.4)
            : modeT > Dg - 0.5 ? 1 - ez((modeT - (Dg - 0.5)) / 0.5) : 1;
      pose.foreL.ang += kg * (-0.6 + Math.sin(modeT * 5) * 0.12);
      pose.torso.ang += kg * 0.02 * Math.sin(modeT * 4);
      pose.head.ang += kg * (0.06 * Math.sin(modeT * 4));
      if (modeT > Dg) setMode("idle");
    }
    // ---- WALK: in-place stride, knees bend, body bobs, arms counter-swing ---
    if (mode === "walk") {
      var ph = t * TAU * 1.5;
      pose.thighL.ang = Math.sin(ph) * 0.15;
      pose.thighR.ang = Math.sin(ph + Math.PI) * 0.15;
      pose.shinL.ang = Math.max(0, -Math.sin(ph)) * 0.34;
      pose.shinR.ang = Math.max(0, -Math.sin(ph + Math.PI)) * 0.34;
      pose.hips.y += -Math.abs(Math.sin(ph)) * 3;
      pose.foreL.ang += Math.sin(ph) * 0.11;
      pose.foreR.ang += Math.sin(ph + Math.PI) * 0.11;
      pose.torso.ang += Math.sin(ph) * 0.008;
    }

    applyAll();
    requestAnimationFrame(frame);
  }
  applyAll();
  requestAnimationFrame(frame);

  // ---- public API ----------------------------------------------------------
  window.Rig = {
    wave: function () { setMode("wave"); },
    gesture: function () { setMode("gesture"); },
    walk: function () { setMode("walk"); },
    rest: function () { walking = false; mode = "idle"; modeT = 0; },
    look: function (x, y) { lookT.x = x; lookT.y = y == null ? 0 : y; pointerSeen = performance.now(); },
    _setMode: setMode, _pose: function () { return pose; }
  };
})();
