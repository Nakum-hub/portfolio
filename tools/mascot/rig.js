/* ===== Living character — ONE entity, warped (not cut into parts, never seams). =====
   The whole illustration is a single texture. Each frame it is drawn as a stack of thin
   horizontal slices whose horizontal offset eases from 0 at the feet to a gentle lean at
   the head (a smooth bend toward the cursor), plus a subtle breathing stretch through the
   chest. Because it is one continuous image, the body always stays intact — no separate
   head/torso/legs, no seams. No recorded frames. */
window.Mascot=(function(){
  var el=document.getElementById('mascot'); if(!el) return {};
  var cv=el.querySelector('.mascot__cv'); if(!cv) return {};
  var ctx=cv.getContext('2d');
  var RM=window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var RIG=__RIG__;                       /* {tex, TW, TH, feetY, headY, cx} in texture px */
  var tex=new Image(), loaded=false;
  tex.onload=function(){ loaded=true; }; tex.onerror=function(){ loaded=true; }; tex.src=RIG.tex;

  var TW=RIG.TW, TH=RIG.TH;
  var DPR=Math.min(2,window.devicePixelRatio||1);
  cv.width=Math.round(TW*DPR); cv.height=Math.round(TH*DPR);

  var px=0.5, py=0.42, ax=0, ay=0, active=0;
  function onMove(e){ var r=cv.getBoundingClientRect();
    px=(e.clientX-r.left)/r.width; py=(e.clientY-r.top)/r.height; active=1; }
  if(!RM){ window.addEventListener('mousemove',onMove,{passive:true}); }

  var clamp=function(v,a,b){ return v<a?a:v>b?b:v; };
  function smooth(e0,e1,x){ x=clamp((x-e0)/(e1-e0),0,1); return x*x*(3-2*x); }  /* smoothstep */

  var SH=2;                                          /* slice height (texture px) */
  var bodyH=RIG.feetY-RIG.headY;
  var t0=performance.now();
  function frame(now){
    var t=(now-t0)/1000;
    ctx.setTransform(DPR,0,0,DPR,0,0); ctx.clearRect(0,0,TW,TH);

    var tax=active?clamp((px-0.5)*2.0,-1,1):0.55*Math.sin(t*2*Math.PI/7.5);
    var tay=active?clamp((py-0.42)*1.4,-1,1):0;
    ax+=(tax-ax)*0.05; ay+=(tay-ay)*0.05;

    var lean=26*ax;                                  /* head-level horizontal lean (tex px) */
    var breath=(Math.sin(t*2*Math.PI/4.8)+1)/2;      /* 0..1 */

    /* below the feet (shoe soles / shadow contact) — drawn unwarped so the feet stay planted */
    ctx.drawImage(tex, 0, RIG.feetY, TW, TH-RIG.feetY, 0, RIG.feetY, TW, TH-RIG.feetY);

    /* feet -> head, accumulating a small breathing stretch through the torso */
    var accum=0;
    for(var sy=RIG.feetY; sy>RIG.headY; sy-=SH){
      var top=Math.max(RIG.headY, sy-SH), h=sy-top;
      var f=(RIG.feetY-(sy-h*0.5))/bodyH;            /* 0 feet .. 1 head */
      var bend=lean*smooth(0.18,1.0,f);              /* legs stay straight, upper leans */
      var dip =(8*ay)*smooth(0.45,1.0,f);            /* slight nod toward vertical aim */
      var stretch=1+breath*0.022*Math.sin(Math.PI*clamp((f-0.18)/0.62,0,1)); /* chest breathes */
      var dH=h*stretch;
      var dyB=RIG.feetY-accum;
      ctx.drawImage(tex, 0, top, TW, h, bend, dyB-dH+dip, TW, dH+0.7);
      accum+=dH;
    }
    raf=requestAnimationFrame(frame);
  }
  var raf=null;
  function start(){ if(raf) return;
    if(RM){ ctx.setTransform(DPR,0,0,DPR,0,0); ctx.clearRect(0,0,TW,TH); ctx.drawImage(tex,0,0); return; }
    t0=performance.now(); raf=requestAnimationFrame(frame); }

  function whenReady(cb){ (function w(){ loaded?cb():setTimeout(w,40); })(); }
  var api={el:el,look:function(x,y){px=x;py=y;active=1;},rest:function(){active=0;}};
  whenReady(function(){
    el.classList.add('arrived');
    var pre=document.getElementById('preloader');
    if(pre && !pre.classList.contains('done')){
      var obs=new MutationObserver(function(){ if(pre.classList.contains('done')){ obs.disconnect(); el.style.opacity='1'; start(); } });
      obs.observe(pre,{attributes:true,attributeFilter:['class']});
    } else { el.style.opacity='1'; start(); }
  });
  return api;
})();