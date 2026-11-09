'use strict';
(() => {
  const demos = [...document.querySelectorAll('.rx')];
  if (!demos.length) return;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const modes = {
    text: [
      { on: 'src', out: '' },
      { on: 'expr', out: '' },
      { on: 'out', out: '«Feijóo promete…»' }
    ],
    attr: [
      { on: 'src', out: '' },
      { on: 'expr', out: '/andalucia/2026/10/21/…' },
      { on: 'out', out: 'https://www.elmundo.es/andalucia/2026/10/21/…' }
    ],
    meta: [
      { on: 'src', out: 'texto visible: «21 oct»' },
      { on: 'expr', out: 'texto visible: «21 oct»' },
      { on: 'out', out: '2026-10-21' }
    ]
  };
  const players = demos.map((demo, order) => {
    const steps = modes[demo.dataset.mode];
    const src = demo.querySelector('.rx-src');
    const expr = demo.querySelector('.rx-expr');
    const out = demo.querySelector('.rx-out');
    const nodes = { src, expr, out };
    let timers = [];
    function apply(index) {
      const step = steps[index] || steps.at(-1);
      Object.entries(nodes).forEach(([key, node]) => node.classList.toggle('is-on', key === step.on || (key === 'out' && step.on === 'out')));
      src.classList.toggle('is-on', step.on === 'src' || index === steps.length - 1);
      expr.classList.toggle('is-on', step.on === 'expr' || index === steps.length - 1);
      out.textContent = step.out;
    }
    function play(delay = 0) {
      timers.forEach(clearTimeout);
      timers = [];
      if (reduced) return apply(steps.length - 1);
      apply(0);
      steps.forEach((_, i) => {
        if (i === 0) return;
        timers.push(setTimeout(() => apply(i), delay + i * 1100));
      });
    }
    demo.querySelector('.rx-replay').addEventListener('click', () => play());
    return { play, apply: () => apply(steps.length - 1), last: steps.length - 1, order };
  });
  function tour() {
    players.forEach(player => player.play(player.order * 400));
  }
  const slide = demos[0].closest('.slide');
  slide.addEventListener('slideshow', tour);
  if (slide.classList.contains('active')) tour();
  else players.forEach(player => player.apply());
})();
