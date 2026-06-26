/* ===== Mascot — a gesture player. Plays named, full-body motion clips (data-driven). =====
   Each clip is a horizontal sprite atlas of full-body frames (head-to-shoes), normalized
   to a common canvas + feet baseline so the character is the same size in every gesture.
   Add a new gesture later = register one more entry in CLIPS (built by tools/mascot/build_clip.py). */
window.Mascot=(function(){
  var el=document.getElementById('mascot'); if(!el) return {};
  var cv=el.querySelector('.mascot__cv'), bubble=el.querySelector('.mascot__bubble');
  var ctx=cv.getContext('2d');
  var RM=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var FW=__FW__, FH=__FH__; cv.width=FW; cv.height=FH;

  /* the gesture library — data only */
  var CLIPS=__CLIPS__;                 /* { name:{src, n, fps, loop} } */
  var DEFAULT='idle';                  /* resting clip */

  /* ---- loading ---- */
  var loaded=0, total=0, ready=false;
  function preload(done){
    var names=Object.keys(CLIPS); total=names.length; if(!total){ done&&done(); return; }
    names.forEach(function(nm){
      var im=new Image();
      im.onload=im.onerror=function(){ CLIPS[nm].img=(im.naturalWidth?im:null); if(++loaded===total){ ready=true; done&&done(); } };
      im.src=CLIPS[nm].src;
    });
  }

  /* ---- playback state ---- */
  var cur=null;            /* {name,f,acc} */
  var q=[];                /* queued {name,loop} */
  var fade=null;           /* {fromName,fromF,t} crossfade between clips */
  var FADE=300;            /* ms — reads as a quick turn when the facing changes */
  var raf=null, last=0;

  function stamp(c,f,alpha){
    if(!c||!c.img) return;
    f=((f%c.n)+c.n)%c.n; ctx.globalAlpha=alpha;
    ctx.drawImage(c.img, f*FW,0,FW,FH, 0,0,FW,FH);
  }
  function render(){
    ctx.clearRect(0,0,FW,FH);
    if(fade && CLIPS[fade.fromName]) stamp(CLIPS[fade.fromName], fade.fromF, 1-Math.min(1,fade.t/FADE));
    if(cur) stamp(CLIPS[cur.name], cur.f, fade?Math.min(1,fade.t/FADE):1);
    ctx.globalAlpha=1;
  }
  function advanceQueue(){
    if(q.length){ var nx=q.shift(); startClip(nx.name, nx.loop); }
    else startClip(DEFAULT, true);
  }
  function tick(ts){
    if(!last) last=ts; var dt=ts-last; last=ts;
    if(cur){ var c=CLIPS[cur.name]; cur.acc+=dt; var step=1000/(c.fps||12);
      while(cur.acc>=step){ cur.acc-=step; cur.f++;
        if(cur.f>=c.n){ if(c.loop){ cur.f=0; } else { cur.f=c.n-1; advanceQueue(); break; } } } }
    if(fade){ fade.t+=dt; if(fade.t>=FADE) fade=null; }
    render(); raf=requestAnimationFrame(tick);
  }
  function ensureLoop(){ if(!raf){ last=0; raf=requestAnimationFrame(tick); } }

  function startClip(name, loop){
    if(!CLIPS[name]) return;
    if(cur && cur.name!==name) fade={fromName:cur.name, fromF:cur.f, t:0};
    cur={name:name, f:0, acc:0};
    if(loop!==undefined) CLIPS[name].loop=!!loop;
    ensureLoop();
  }

  /* ---- entrance: stride in (side-on walk), arrive, turn to face you, idle ---- */
  function offX(){ var r=el.getBoundingClientRect(); return -(r.right+34); }
  function walkIn(){
    el.classList.add('arrived');
    if(RM || !CLIPS.walk){ el.style.transform='translateX(0)'; startClip(DEFAULT,true); render(); return api; }
    var x0=offX(), dur=2200, t0=null;
    el.style.transform='translateX('+x0+'px)'; startClip('walk', true);
    function slide(ts){
      if(t0===null) t0=ts;
      var p=Math.min(1,(ts-t0)/dur), e=1-Math.pow(1-p,2.4);
      el.style.transform='translateX('+(x0*(1-e)).toFixed(1)+'px)';
      if(p<1) requestAnimationFrame(slide);
      else { el.style.transform='translateX(0)'; startClip(DEFAULT,true); }   /* crossfade walk->idle = turn */
    }
    requestAnimationFrame(slide);
    return api;
  }

  /* ---- public API ---- */
  function play(name,opts){ opts=opts||{}; q=[]; startClip(name, opts.loop!==undefined?opts.loop:!!CLIPS[name]&&CLIPS[name].loop); return api; }
  function queue(name,opts){ opts=opts||{}; q.push({name:name,loop:!!opts.loop}); ensureLoop(); return api; }
  function list(){ return Object.keys(CLIPS); }
  function has(n){ return !!CLIPS[n]; }
  function say(t,ms){ if(!bubble) return api; bubble.textContent=t; bubble.classList.add('show'); clearTimeout(say._t); if(ms!==0) say._t=setTimeout(function(){bubble.classList.remove('show');},ms||2600); return api; }
  function hush(){ if(bubble) bubble.classList.remove('show'); return api; }
  var api={play:play,queue:queue,walkIn:walkIn,list:list,has:has,say:say,hush:hush,el:el,clips:CLIPS};

  function autostart(){
    if(RM){ cur={name:DEFAULT,f:0,acc:0}; render(); return; }
    var pre=document.getElementById('preloader');
    if(pre && !pre.classList.contains('done')){           /* wait for the splash to lift, so the walk-in is seen */
      var obs=new MutationObserver(function(){ if(pre.classList.contains('done')){ obs.disconnect(); setTimeout(walkIn,260); } });
      obs.observe(pre,{attributes:true,attributeFilter:['class']});
    } else walkIn();
  }
  preload(function(){ if(document.readyState==='complete') autostart(); else window.addEventListener('load',autostart); });
  return api;
})();