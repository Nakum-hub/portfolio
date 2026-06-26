/* mesh-engine.js — WebGL linear-blend-skinning for ONE textured character mesh.
 * The whole illustration is a single mesh (one texture); a humanoid skeleton bends
 * it smoothly via per-vertex weights (the Live2D/Spine approach), so it always
 * reads as one intact figure and never tears at the joints. Stands upright,
 * front-facing — no body lean. */
(function () {
  "use strict";
  var MESH = window.__MESH__;
  var cv = document.getElementById(MESH.mount || "rigCanvas");
  var gl = cv.getContext("webgl", { premultipliedAlpha: false, antialias: true });
  if (!gl) { console.error("WebGL unavailable"); return; }

  // ---- 3x3 affine (column-major for GLSL mat3) -----------------------------
  function I() { return [1, 0, 0, 0, 1, 0, 0, 0, 1]; }
  function mul(A, B) {
    var C = new Array(9);
    for (var c = 0; c < 3; c++) for (var r = 0; r < 3; r++)
      C[c * 3 + r] = A[r] * B[c * 3] + A[3 + r] * B[c * 3 + 1] + A[6 + r] * B[c * 3 + 2];
    return C;
  }
  function T(x, y) { return [1, 0, 0, 0, 1, 0, x, y, 1]; }
  function R(a) { var c = Math.cos(a), s = Math.sin(a); return [c, s, 0, -s, c, 0, 0, 0, 1]; }
  function S(x, y) { return [x, 0, 0, 0, y, 0, 0, 0, 1]; }
  function local(piv, ang, sx, sy) {
    return mul(T(piv[0], piv[1]), mul(R(ang || 0), mul(S(sx == null ? 1 : sx, sy == null ? 1 : sy), T(-piv[0], -piv[1]))));
  }

  var B = MESH.bones, NB = B.length;

  // ---- GL program ----------------------------------------------------------
  var vs =
    "attribute vec2 aPos; attribute vec2 aUV; attribute vec3 aIdx; attribute vec3 aWt;" +
    "uniform mat3 uBones[" + NB + "]; uniform vec2 uTex; varying vec2 vUV;" +
    "void main(){ vec3 p=vec3(aPos,1.0);" +
    " vec3 q = aWt.x*(uBones[int(aIdx.x)]*p) + aWt.y*(uBones[int(aIdx.y)]*p) + aWt.z*(uBones[int(aIdx.z)]*p);" +
    " vUV=aUV; gl_Position=vec4((q.x/uTex.x)*2.0-1.0, 1.0-(q.y/uTex.y)*2.0, 0.0, 1.0); }";
  var fs =
    "precision mediump float; uniform sampler2D uS; varying vec2 vUV;" +
    "void main(){ vec4 c=texture2D(uS,vUV); if(c.a<0.004) discard; gl_FragColor=vec4(c.rgb*c.a, c.a); }";
  function sh(t, src) { var s = gl.createShader(t); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) console.error(gl.getShaderInfoLog(s)); return s; }
  var prog = gl.createProgram();
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(prog); gl.useProgram(prog);

  function buf(data, attr, size) {
    var b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(data), gl.STATIC_DRAW);
    var l = gl.getAttribLocation(prog, attr); gl.enableVertexAttribArray(l);
    gl.vertexAttribPointer(l, size, gl.FLOAT, false, 0, 0);
  }
  buf([].concat.apply([], MESH.verts), "aPos", 2);
  buf([].concat.apply([], MESH.uvs), "aUV", 2);
  buf([].concat.apply([], MESH.wIdx), "aIdx", 3);
  buf([].concat.apply([], MESH.wWt), "aWt", 3);
  var ib = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib);
  gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array([].concat.apply([], MESH.tris)), gl.STATIC_DRAW);
  var nIdx = MESH.tris.length * 3;

  var tex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  var img = new Image();
  var ready = false;
  img.onload = function () {
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
    ready = true;
  };
  img.src = MESH.tex;

  gl.uniform2f(gl.getUniformLocation(prog, "uTex"), MESH.texW, MESH.texH);
  var uBones = gl.getUniformLocation(prog, "uBones[0]");
  gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
  gl.clearColor(0, 0, 0, 0);

  function resize() {
    var dpr = Math.min(2, window.devicePixelRatio || 1);
    var w = cv.clientWidth, h = cv.clientHeight;
    cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
    gl.viewport(0, 0, cv.width, cv.height);
  }
  window.addEventListener("resize", resize); resize();

  // ---- skeleton FK ---------------------------------------------------------
  var pose = {};                       // bonename -> {ang, sx, sy}
  var worldCache = {};
  function world(i) {
    if (worldCache[i]) return worldCache[i];
    var b = B[i], p = pose[b.name] || {};
    var L = local(b.pivot, p.ang, p.sx, p.sy);
    var w = b.parent < 0 ? L : mul(world(b.parent), L);
    worldCache[i] = w; return w;
  }
  function boneMatrices() {
    worldCache = {};
    var out = new Float32Array(NB * 9);
    for (var i = 0; i < NB; i++) { var w = world(i); for (var k = 0; k < 9; k++) out[i * 9 + k] = w[k]; }
    return out;
  }

  // ---- animation -----------------------------------------------------------
  var REST = !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
  var mode = "idle", modeT = 0, walking = false, t0 = performance.now(), TAU = Math.PI * 2;
  function setMode(m) {
    if (m === "walk") { walking = !walking; mode = walking ? "walk" : "idle"; modeT = 0; return; }
    mode = m; modeT = 0;
  }
  function ez(x) { return x < 0 ? 0 : x > 1 ? 1 : x * x * (3 - 2 * x); }
  function env(tt, D) { return tt < 0.5 ? ez(tt / 0.5) : tt > D - 0.5 ? 1 - ez((tt - (D - 0.5)) / 0.5) : 1; }

  function frame(now) {
    var t = (now - t0) / 1000, a = REST ? 0 : 1;
    var br = 0.5 + 0.5 * Math.sin(TAU * t / 4.2);
    // upright idle: the face stays rigid & forward (no scale, no turn); the torso
    // keeps its shape (only the faintest breathing). Nothing reshapes the body.
    pose.hips = { ang: 0 };
    pose.spine = { ang: 0, sx: 1, sy: 1 + a * 0.006 * br };
    pose.head = { ang: 0 };
    pose.upperArmL = { ang: a * 0.015 * Math.sin(TAU * t / 5.5) };
    pose.upperArmR = { ang: a * 0.015 * Math.sin(TAU * t / 5.5 + Math.PI) };
    pose.lowerArmL = { ang: a * 0.02 * Math.sin(TAU * t / 5.5) };
    pose.lowerArmR = { ang: a * 0.02 * Math.sin(TAU * t / 5.5 + Math.PI) };
    pose.upperLegL = { ang: 0 }; pose.upperLegR = { ang: 0 };
    pose.lowerLegL = { ang: 0 }; pose.lowerLegR = { ang: 0 };

    modeT += 1 / 60;
    if (mode === "wave") {                  // forearm-led wave (shirt barely moves)
      var k = env(modeT, 3.2);
      pose.upperArmR.ang += k * -0.42;
      pose.lowerArmR.ang += k * (-1.25 + 0.42 * Math.sin(modeT * 9));
      if (modeT > 3.2) setMode("idle");
    } else if (mode === "point") {
      var kp = env(modeT, 2.4);
      pose.upperArmR.ang += kp * -0.62; pose.lowerArmR.ang += kp * -0.62;
      if (modeT > 2.4) setMode("idle");
    } else if (mode === "cheer") {          // raise both forearms (celebratory)
      var kc = env(modeT, 2.6), b2 = Math.sin(modeT * 7) * 0.12;
      pose.upperArmR.ang += kc * -0.5; pose.upperArmL.ang += kc * 0.5;
      pose.lowerArmR.ang += kc * (-1.3 + b2); pose.lowerArmL.ang += kc * (1.3 - b2);
      if (modeT > 2.6) setMode("idle");
    } else if (mode === "walk") {
      var ph = t * TAU * 1.5;
      pose.upperLegL.ang = Math.sin(ph) * 0.16; pose.upperLegR.ang = Math.sin(ph + Math.PI) * 0.16;
      pose.lowerLegL.ang = Math.max(0, -Math.sin(ph)) * 0.34;
      pose.lowerLegR.ang = Math.max(0, -Math.sin(ph + Math.PI)) * 0.34;
      pose.upperArmL.ang += Math.sin(ph) * 0.12; pose.upperArmR.ang += Math.sin(ph + Math.PI) * 0.12;
    }

    if (ready) {
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniformMatrix3fv(uBones, false, boneMatrices());
      gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.drawElements(gl.TRIANGLES, nIdx, gl.UNSIGNED_SHORT, 0);
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  window.Rig = {
    wave: function () { setMode("wave"); }, point: function () { setMode("point"); },
    cheer: function () { setMode("cheer"); }, walk: function () { setMode("walk"); },
    rest: function () { walking = false; mode = "idle"; modeT = 0; }
  };
})();
