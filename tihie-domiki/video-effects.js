(()=>{
  const hero=document.querySelector('.hero');
  const video=document.querySelector('.hero-video');
  const nav=document.querySelector('.nav');
  const reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if(video){
    const show=()=>hero&&hero.classList.add('video-ready');
    const fallback=()=>{
      video.style.display='none';
      hero&&hero.classList.remove('video-ready');
    };
    video.addEventListener('loadeddata',show,{once:true});
    video.addEventListener('canplay',show,{once:true});
    video.addEventListener('error',fallback,{once:true});
    const playAttempt=video.play();
    if(playAttempt&&playAttempt.catch)playAttempt.catch(()=>{});
    setTimeout(()=>{if(video.readyState<2)fallback()},9000);
  }

  requestAnimationFrame(()=>document.body.classList.add('site-ready'));

  const targets=document.querySelectorAll('.section .head,.section .cards,.about,.darkbox,.gallery,.reviews,.faq,.cta');
  if(reduce){
    targets.forEach(element=>element.classList.add('scroll-reveal','visible'));
  }else{
    targets.forEach(element=>element.classList.add('scroll-reveal'));
    const observer=new IntersectionObserver(entries=>{
      entries.forEach(entry=>{
        if(entry.isIntersecting){
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    },{threshold:.12,rootMargin:'0px 0px -45px'});
    targets.forEach(element=>observer.observe(element));
  }

  const onScroll=()=>nav&&nav.classList.toggle('video-scrolled',window.scrollY>45);
  addEventListener('scroll',onScroll,{passive:true});
  onScroll();
})();