/* ===== Living character rig — procedural, not clips. =====
   A 3-part cut-out skeleton (head / torso+arms / legs) from the character design,
   driven every frame by math: breathing, weight-shift sway, and a head that looks
   toward the cursor with idle drift. No recorded frames. */
window.Mascot=(function(){
  var el=document.getElementById('mascot'); if(!el) return {};
  var cv=el.querySelector('.mascot__cv'); if(!cv) return {};
  var ctx=cv.getContext('2d');
  var RM=window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* rig geometry, in source-image pixels */
  var RIG=__RIG__;                 /* {parts:{head,upper,lower}(dataURI), neck:[x,y], waist:[x,y], crop:[x0,y0,x1,y1]} */
  var imgs={}, ready=0, need=3;
  ['lower','upper','head'].forEach(function(k){ var im=new Image();
    im.onload=im.onerror=function(){ imgs[k]=im.naturalWidth?im:null; ready++; }; im.src=RIG.parts[k]; });

  /* canvas resolution scaled to the crop box */
  var cx0=RIG.crop[0],cy0=RIG.crop[1],cx1=RIG.crop[2],cy1=RIG.crop[3];
  var CW=cx1-cx0, CH=cy1-cy0, S=520/CH;          /* internal height ~520, device-scaled below */
  var DPR=Math.min(2,window.devicePixelRatio||1);
  cv.width=Math.round(CW*S*DPR); cv.height=Math.round(CH*S*DPR);

  /* live look-at target (cursor), smoothed */
  var px=0.5, py=0.30, hx=0.5, hy=0.30, active=0;
  function onMove(e){ var r=cv.getBoundingClientRect();
    px=(e.clientX-r.left)/r.width; py=(e.clientY-r.top)/r.height; active=1; }
  if(!RM){ window.addEventListener('mousemove',onMove,{passive:true}); }

  function base(){ ctx.setTransform(S*DPR,0,0,S*DPR, -cx0*S*DPR, -cy0*S*DPR); }
  function part(k){ var im=imgs[k]; if(im) ctx.drawImage(im,0,0); }

  var t0=performance.now();
  function frame(now){
    var t=(now-t0)/1000;
    ctx.setTransform(1,0,0,1,0,0); ctx.clearRect(0,0,cv.width,cv.height);

    /* --- procedural parameters --- */
    var breath=(Math.sin(t*2*Math.PI/4.4)+1)/2;        /* 0..1 */
    var breatheScale=1+0.016*breath;                   /* chest expands */
    var lift=14*breath;                                /* whole upper rises a touch (src px) */
    var sway=0.022*Math.sin(t*2*Math.PI/6.2);          /* radians, gentle weight shift */
    var swayX=7*Math.sin(t*2*Math.PI/6.2);

    /* head: ease toward cursor, or idle-drift when the pointer is away/idle */
    var tx=active?(px-0.5):0.18*Math.sin(t*2*Math.PI/7);
    var ty=active?(py-0.30):0.12*Math.sin(t*2*Math.PI/5+0.7);
    hx+=(tx-hx)*0.06; hy+=(ty-hy)*0.06;
    var lookX=Math.max(-26,Math.min(26, hx*60));       /* src px */
    var lookY=Math.max(-16,Math.min(22, hy*60));
    var tilt=Math.max(-0.09,Math.min(0.09, hx*0.22));  /* radians */

    var nx=RIG.neck[0], ny=RIG.neck[1], wx=RIG.waist[0], wy=RIG.waist[1];

    /* LEGS — planted */
    base(); part('lower');

    /* TORSO + HEAD share the sway + breathing lift around the waist */
    base();
    ctx.translate(wx,wy); ctx.rotate(sway); ctx.translate(-wx+swayX,-wy);
    ctx.translate(0,-lift);
    ctx.save();                                        /* torso also breathes (vertical scale) */
      ctx.translate(wx,wy); ctx.scale(1,breatheScale); ctx.translate(-wx,-wy);
      part('upper');
    ctx.restore();
    ctx.save();                                        /* head: tilt + look, around the neck */
      ctx.translate(nx+lookX,ny+lookY); ctx.rotate(tilt); ctx.translate(-nx,-ny);
      part('head');
    ctx.restore();

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