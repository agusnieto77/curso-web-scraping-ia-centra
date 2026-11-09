'use strict';
(() => {
  const root = document.querySelector('.ralign');
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
      notes: [
        'La página trae varios article.',
        'El primero es un registro.',
        'El segundo, otro.',
        'html_elements() devuelve el conjunto, no un campo suelto.'
      ],
      verdict: ['3', 'Un article, una fila.', 'same']
    },
    {
      notes: [
        'El campo se busca dentro de ese article.',
        'h2 está: hay título.',
        'a está: hay enlace.',
        'time no está: html_element() deja NA y no acorta el vector.'
      ],
      verdict: ['NA', 'Un resultado por article, aunque falte el nodo.', 'same']
    },
    {
      notes: [
        'Tres títulos, en este orden: A, B y C.',
        'html_elements() de fechas devuelve 2. No reserva el lugar de B.',
        'La posición 2 junta B con 16 oct.',
        '16 oct no es de B: es la fecha de C, que se corrió.',
        'Dentro de cada article, B queda NA y C conserva 16 oct.'
      ],
      verdict: ['≠', 'La lista corta se corre. No unir por posición.', 'diff']
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
      view.dataset.at = String(at);
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
