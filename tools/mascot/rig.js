/* ===== Living character rig — procedural, not clips. =====
   A 3-part cut-out (head / torso+arms / legs) from the character design, animated every
   frame as ONE kinematic chain: a single lean toward the cursor flows from the feet up
   through hips, torso and head (each adds a little), so the whole body turns together
   instead of the parts sliding separately. Plus breathing. No recorded frames. */
window.Mascot=(function(){
  var el=document.getElementById('mascot'); if(!el) return {};
  var cv=el.querySelector('.mascot__cv'); if(!cv) return {};
  var ctx=cv.getContext('2d');
  var RM=window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var RIG=__RIG__;                 /* {parts:{head,upper,lower}, neck,waist,feet:[x,y], crop:[x0,y0,x1,y1]} */
  var imgs={}, ready=0, need=3;
  ['lower','upper','head'].forEach(function(k){ var im=new Image();
    im.onload=im.onerror=function(){ imgs[k]=im.naturalWidth?im:null; ready++; }; im.src=RIG.parts[k]; });

  var cx0=RIG.crop[0],cy0=RIG.crop[1],cx1=RIG.crop[2],cy1=RIG.crop[3];
  var CW=cx1-cx0, CH=cy1-cy0, S=520/CH;
  var DPR=Math.min(2,window.devicePixelRatio||1);
  cv.width=Math.round(CW*S*DPR); cv.height=Math.round(CH*S*DPR);

  /* cursor aim, normalized & smoothed */
  var px=0.5, py=0.42, ax=0, ay=0, active=0;
  function onMove(e){ var r=cv.getBoundingClientRect();
    px=(e.clientX-r.left)/r.width; py=(e.clientY-r.top)/r.height; active=1; }
  if(!RM){ window.addEventListener('mousemove',onMove,{passive:true}); }

  function base(){ ctx.setTransform(S*DPR,0,0,S*DPR, -cx0*S*DPR, -cy0*S*DPR); }
  function part(k){ var im=imgs[k]; if(im) ctx.drawImage(im,0,0); }
  function piv(name,ang){ var p=RIG[name]; ctx.translate(p[0],p[1]); ctx.rotate(ang); ctx.translate(-p[0],-p[1]); }
  var clamp=function(v,a,b){ return v<a?a:v>b?b:v; };

  var t0=performance.now();
  function frame(now){
    var t=(now-t0)/1000;
    ctx.setTransform(1,0,0,1,0,0); ctx.clearRect(0,0,cv.width,cv.height);

    /* one aim signal toward the cursor (or a slow idle drift when away) */
    var tax=active?clamp((px-0.5)*2.0,-1,1):0.5*Math.sin(t*2*Math.PI/7.5);
    var tay=active?clamp((py-0.42)*1.6,-1,1):0.35*Math.sin(t*2*Math.PI/6.0+0.6);
    ax+=(tax-ax)*0.045; ay+=(tay-ay)*0.045;             /* heavy smoothing = no jitter */

    var lean=0.085*ax;                                  /* total body turn toward cursor (rad) */
    var nod =0.05*ay;                                   /* up/down look */
    var breath=(Math.sin(t*2*Math.PI/4.8)+1)/2;
    var breatheScale=1+0.011*breath, lift=8*breath;

    /* distribute the SAME lean up the chain (fractions sum ~1) so the body moves as one */
    var Lfeet=lean*0.14, Lwaist=lean*0.40, Lneck=lean*0.34, Lhead=lean*0.12;

    base();
    /* feet planted; whole body leans from the ankles */
    piv('feet', Lfeet); part('lower');
    /* torso continues the lean around the waist (inherits the feet lean) + breathing */
    piv('waist', Lwaist);
    ctx.translate(0,-lift);
    ctx.save(); ctx.translate(RIG.waist[0],RIG.waist[1]); ctx.scale(1,breatheScale);
      ctx.translate(-RIG.waist[0],-RIG.waist[1]); part('upper'); ctx.restore();
    /* head continues the lean around the neck (inherits torso) + a small extra turn/nod */
    piv('neck', Lneck+Lhead);
    ctx.translate(0, nod*18);
    part('head');

    raf=requestAnimationFrame(frame);
  }
  var raf=null;
  function start(){ if(raf) return; if(RM){ base(); part('lower'); part('upper'); part('head'); return; } t0=performance.now(); raf=requestAnimationFrame(frame); }

  function whenReady(cb){ (function w(){ ready>=need?cb():setTimeout(w,40); })(); }
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