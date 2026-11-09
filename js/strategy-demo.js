'use strict';
(() => {
  const demos = [...document.querySelectorAll('.st-demo')];
  if (!demos.length) return;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const players = demos.map(demo => {
    const parts = [...demo.querySelectorAll('[data-at]')];
    const last = Math.max(...parts.map(part => Number(part.dataset.at)));
    let timers = [];
    function apply(step) {
      parts.forEach(part => part.classList.toggle('is-on', Number(part.dataset.at) <= step));
    }
    function play(delay = 0) {
      timers.forEach(clearTimeout);
      timers = [];
      if (reduced) return apply(last);
      apply(0);
      for (let step = 1; step <= last; step++) timers.push(setTimeout(() => apply(step), delay + step * 900));
    }
    demo.querySelector('.st-replay').addEventListener('click', () => play());
    return { play, apply: () => apply(last), last };
  });
  function tour() {
    let delay = 0;
    players.forEach(player => {
      player.play(delay);
      delay += (player.last + 1) * 900;
    });
  }
  const slide = demos[0].closest('.slide');
  slide.addEventListener('slideshow', tour);
  if (slide.classList.contains('active')) tour();
  else players.forEach(player => player.apply());
})();
