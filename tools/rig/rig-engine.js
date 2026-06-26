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

  // ---- rig-inspection overlay: bones + joint dots --------------------------
  var BONES = [["root", "spine"], ["spine", "head"], ["spine", "upperArmL"],
    ["upperArmL", "lowerArmL"], ["spine", "upperArmR"], ["upperArmR", "lowerArmR"],
    ["root", "upperLegL"], ["upperLegL", "lowerLegL"], ["root", "upperLegR"],
    ["upperLegR", "lowerLegR"]];
  var skel = document.createElementNS(SVGNS, "g");
  skel.setAttribute("opacity", "0");
  var lines = BONES.map(function () {
    var l = document.createElementNS(SVGNS, "line");
    l.setAttribute("stroke", "#5eead4"); l.setAttribute("stroke-width", "5");
    l.setAttribute("stroke-linecap", "round"); skel.appendChild(l); return l;
  });
  var dots = {};
  ["root", "spine", "head", "upperArmL", "lowerArmL", "upperArmR", "lowerArmR",
    "upperLegL", "lowerLegL", "upperLegR", "lowerLegR"].forEach(function (n) {
    var c = document.createElementNS(SVGNS, "circle");
    c.setAttribute("r", n === "root" ? "11" : "8");
    c.setAttribute("fill", n === "root" ? "#a78bfa" : "#fb7185");
    c.setAttribute("stroke", "#fff"); c.setAttribute("stroke-width", "2");
    skel.appendChild(c); dots[n] = c;
  });
  svg.appendChild(skel);

  function pt(m, x, y) { return [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]]; }
  function jointPos(name) {
    if (name === "root") return pt(world("hips"), ROOT[0], ROOT[1]);
    return pt(world(name), P[name].pivot[0], P[name].pivot[1]);
  }
  function updateSkel() {
    BONES.forEach(function (b, i) {
      var a = jointPos(b[0]), c = jointPos(b[1]);
      lines[i].setAttribute("x1", a[0]); lines[i].setAttribute("y1", a[1]);
      lines[i].setAttribute("x2", c[0]); lines[i].setAttribute("y2", c[1]);
    });
    for (var n in dots) { var q = jointPos(n); dots[n].setAttribute("cx", q[0]); dots[n].setAttribute("cy", q[1]); }
  }

  // how far each part drifts from the body in "Rig view" (canvas units)
  var EXP = {
    head: [0, -78], spine: [0, 0],
    upperArmL: [-78, -6], lowerArmL: [-132, 46], upperArmR: [78, -6], lowerArmR: [132, 46],
    upperLegL: [-44, 74], lowerLegL: [-60, 156], upperLegR: [44, 74], lowerLegR: [60, 156]
  };

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
  var rigView = false, expl = 0;          // rig-inspection explode amount 0..1
  var TAU = Math.PI * 2;

  function setMode(m) {
    if (m === "walk") { walking = !walking; mode = walking ? "walk" : "idle"; modeT = 0; return; }
    mode = m; modeT = 0;
  }
  // ease in-out
  function ez(x) { return x < 0 ? 0 : x > 1 ? 1 : x * x * (3 - 2 * x); }
  // one-shot envelope: ease up, hold, ease back down over duration D
  function env(tt, D) {
    return tt < 0.45 ? ez(tt / 0.45) : tt > D - 0.5 ? 1 - ez((tt - (D - 0.5)) / 0.5) : 1;
  }

  function frame(now) {
    var t = (now - t0) / 1000;
    var away = (now - pointerSeen) > 2600;
    if (away && !REST) { lookT.x = Math.sin(t * 0.45) * 0.5; lookT.y = 0.12 + Math.sin(t * 0.3) * 0.18; }
    look.x += (lookT.x - look.x) * 0.06; look.y += (lookT.y - look.y) * 0.06;

    var br = 0.5 + 0.5 * Math.sin(TAU * t / 4.0);      // breathing 0..1
    var a = REST ? 0 : 1;

    // ---- idle baseline (always) — breath, weight-shift sway, arm micro-sway --
    pose.hips      = { x: 0, y: a * (-1.2 * br), ang: a * 0.012 * Math.sin(TAU * t / 6.2) };
    pose.spine     = { ang: a * 0.018 * Math.sin(TAU * t / 6.2 + 0.4), sx: 1, sy: 1 + a * 0.014 * br };
    pose.head      = { ang: a * 0.02 * Math.sin(TAU * t / 5.0), tx: 0, ty: 0 };
    pose.upperArmL = { ang: a * 0.02 * Math.sin(TAU * t / 6.2) };
    pose.upperArmR = { ang: a * 0.02 * Math.sin(TAU * t / 6.2 + Math.PI) };
    pose.lowerArmL = { ang: a * 0.025 * Math.sin(TAU * t / 6.2) };
    pose.lowerArmR = { ang: a * 0.025 * Math.sin(TAU * t / 6.2 + Math.PI) };
    pose.upperLegL = { ang: 0 }; pose.upperLegR = { ang: 0 };
    pose.lowerLegL = { ang: 0 }; pose.lowerLegR = { ang: 0 };

    pose.head.ang += look.x * 0.20;                    // look-at (additive)
    pose.head.tx = look.x * 7; pose.head.ty = look.y * 4;

    modeT += 1 / 60;
    // Right arm hangs down; negative shoulder angle swings it out-and-up to the
    // character's left (image right). Left arm mirrors with a positive angle.
    if (mode === "wave") {                             // raise R arm, wave the hand
      var D = 3.2, k = env(modeT, D);
      pose.upperArmR.ang += k * -2.0;
      pose.lowerArmR.ang += k * (-0.5 + 0.45 * Math.sin((modeT) * 9));
      pose.head.ang += k * 0.06;
      if (modeT > D) setMode("idle");
    }
    if (mode === "point") {                            // extend R arm out, steady
      var Dp = 2.4, kp = env(modeT, Dp);
      pose.upperArmR.ang += kp * -1.4;
      pose.lowerArmR.ang += kp * -0.15;
      pose.spine.ang += kp * -0.02;
      if (modeT > Dp) setMode("idle");
    }
    if (mode === "cheer") {                            // both arms up
      var Dc = 2.6, kc = env(modeT, Dc), b = Math.sin(modeT * 7) * 0.12;
      pose.upperArmR.ang += kc * (-2.5 + b);
      pose.upperArmL.ang += kc * (2.5 - b);
      pose.lowerArmR.ang += kc * -0.2; pose.lowerArmL.ang += kc * 0.2;
      pose.hips.y += a * -kc * 3 * (0.5 + 0.5 * Math.sin(modeT * 7));
      if (modeT > Dc) setMode("idle");
    }
    if (mode === "walk") {                             // in-place stride
      var ph = t * TAU * 1.5;
      pose.upperLegL.ang = Math.sin(ph) * 0.15;
      pose.upperLegR.ang = Math.sin(ph + Math.PI) * 0.15;
      pose.lowerLegL.ang = Math.max(0, -Math.sin(ph)) * 0.34;
      pose.lowerLegR.ang = Math.max(0, -Math.sin(ph + Math.PI)) * 0.34;
      pose.hips.y += -Math.abs(Math.sin(ph)) * 3;
      pose.upperArmL.ang += Math.sin(ph) * 0.14;       // arms counter-swing
      pose.upperArmR.ang += Math.sin(ph + Math.PI) * 0.14;
      pose.spine.ang += Math.sin(ph) * 0.008;
    }

    applyAll();
    // ---- rig view: drift parts apart + show the skeleton ------------------
    expl += ((rigView ? 1 : 0) - expl) * 0.12;
    if (expl > 0.002) {
      RIG.parts.forEach(function (p) {
        var e = EXP[p.name]; if (!e) return;
        var s = pose[p.name] || (pose[p.name] = {});
        s.tx = (s.tx || 0) + expl * e[0]; s.ty = (s.ty || 0) + expl * e[1];
      });
      applyAll();
    }
    skel.setAttribute("opacity", expl.toFixed(3));
    if (expl > 0.002) updateSkel();
    requestAnimationFrame(frame);
  }
  applyAll();
  requestAnimationFrame(frame);

  // ---- public API ----------------------------------------------------------
  window.Rig = {
    wave: function () { setMode("wave"); },
    point: function () { setMode("point"); },
    cheer: function () { setMode("cheer"); },
    walk: function () { setMode("walk"); },
    rest: function () { walking = false; mode = "idle"; modeT = 0; },
    rig: function (on) { rigView = on == null ? !rigView : !!on; return rigView; },
    look: function (x, y) { lookT.x = x; lookT.y = y == null ? 0 : y; pointerSeen = performance.now(); },
    _setMode: setMode, _pose: function () { return pose; }
  };
})();
