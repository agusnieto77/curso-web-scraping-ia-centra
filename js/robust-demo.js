'use strict';
(() => {
  const root = document.querySelector('.robust');
  if (!root) return;
  const items = [...root.querySelectorAll('.editorial-list li')];
  const view = root.querySelector('.rb');
  const panes = [...view.querySelectorAll('.rb-pane')];
  const sign = view.querySelector('.rd-sign');
  const verdict = view.querySelector('.rd-text');
  const note = view.querySelector('.dt-note');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const GAP = 1100;
  const steps = [
    {
      notes: ['Dos selectores encuentran los mismos 3 títulos.', 'Ambos funcionan… por ahora.', 'El sitio cambia: nueva clase generada y un div extra.', 'El selector largo deja de encontrar nodos.'],
      verdict: ['✓', 'article h2 a describe la estructura; no depende del diseño.', 'same']
    },
    {
      notes: ['La noticia B no tiene fecha.', 'Por columnas: 3 títulos y 2 fechas se desalinean.', 'Por registro: cada campo se busca dentro de su article.'],
      verdict: ['✓', 'Un registro por article: lo que falta queda como NA.', 'same']
    },
    {
      notes: ['Contar antes de guardar.', 'Los campos ausentes deben quedar registrados.', 'Otro tipo de página puede usar otra estructura.'],
      verdict: ['!', 'Validar en varias páginas antes de recolectar en serie.', 'diff']
    }
  ];
  let timers = [];
  let tourTimers = [];

  function lastAt(pane) {
    return Math.max(...[...pane.querySelectorAll('[data-at]')].map(el => Number(el.dataset.at)));
  }
  function settle(values) {
    sign.textContent = values[0];
    verdict.textContent = values[1];
    view.dataset.verdict = values[2];
  }
  function play(step) {
    timers.forEach(clearTimeout);
    timers = [];
    items.forEach((item, i) => {
      item.classList.toggle('is-active', i === step);
      item.setAttribute('aria-pressed', String(i === step));
    });
    panes.forEach((pane, i) => { pane.hidden = i !== step; });
    const pane = panes[step];
    const parts = [...pane.querySelectorAll('[data-at]')];
    const last = lastAt(pane);
    settle(['', '', '']);
    const apply = at => {
      parts.forEach(part => part.classList.toggle('is-on', Number(part.dataset.at) <= at));
      note.textContent = steps[step].notes[at] || note.textContent;
      if (at === last) timers.push(setTimeout(() => settle(steps[step].verdict), reduced ? 0 : 500));
    };
    if (reduced) return apply(last);
    apply(0);
    for (let at = 1; at <= last; at++) timers.push(setTimeout(() => apply(at), at * GAP));
  }
  function stopTour() {
    tourTimers.forEach(clearTimeout);
    tourTimers = [];
  }
  function tour() {
    stopTour();
    play(0);
    if (reduced) return;
    let delay = 0;
    panes.slice(0, -1).forEach((pane, i) => {
      delay += (lastAt(pane) + 2) * GAP;
      tourTimers.push(setTimeout(() => play(i + 1), delay));
    });
  }
  items.forEach((item, i) => {
    item.tabIndex = 0;
    item.setAttribute('role', 'button');
    item.addEventListener('click', () => { stopTour(); play(i); });
    item.addEventListener('keydown', event => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      event.stopPropagation();
      stopTour();
      play(i);
    });
  });
  view.querySelector('.rb-replay').addEventListener('click', tour);
  const slide = root.closest('.slide');
  slide.addEventListener('slideshow', tour);
  if (slide.classList.contains('active')) tour();
  else play(0);
})();
