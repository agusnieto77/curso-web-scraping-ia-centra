'use strict';
(() => {
  const root = document.querySelector('.inspect');
  if (!root) return;
  const items = [...root.querySelectorAll('.editorial-list li')];
  const mock = root.querySelector('.dt');
  const tabs = [...mock.querySelectorAll('.dt-tab')];
  const panes = [...mock.querySelectorAll('.dt-pane')];
  const cards = [...mock.querySelectorAll('.dt-card')];
  const lines = [...mock.querySelectorAll('.dt-line')];
  const input = mock.querySelector('.dt-input');
  const output = mock.querySelector('.dt-output');
  const rows = [...mock.querySelectorAll('.dt-row:not(.dt-head)')];
  const note = mock.querySelector('.dt-note');
  const query = 'document.querySelectorAll("article h2 a")';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let timers = [];
  let tourTimers = [];

  function later(ms, fn) {
    timers.push(setTimeout(fn, reduced ? 0 : ms));
  }
  function clear() {
    timers.forEach(clearTimeout);
    timers = [];
    mock.querySelectorAll('.is-title,.is-box,.is-repeat,.is-match,.is-on').forEach(el => el.classList.remove('is-title', 'is-box', 'is-repeat', 'is-match', 'is-on'));
    cards[3].classList.remove('is-loaded');
    input.textContent = '';
    output.textContent = '';
    note.textContent = '';
  }
  function select(step) {
    items.forEach((item, i) => {
      item.classList.toggle('is-active', i === step);
      item.setAttribute('aria-pressed', String(i === step));
    });
    tabs.forEach((tab, i) => tab.setAttribute('aria-selected', String(i === step)));
    panes.forEach((pane, i) => { pane.hidden = i !== step; });
  }
  const steps = [
    () => {
      later(300, () => { lines[2].classList.add('is-on'); cards[0].classList.add('is-title'); note.textContent = 'Un título real: el nodo a dentro de h2.'; });
      later(1700, () => { lines[2].classList.remove('is-on'); cards[0].classList.remove('is-title'); lines[1].classList.add('is-on'); cards[0].classList.add('is-box'); note.textContent = 'Su contenedor: article.noticia.'; });
      later(3100, () => { [1, 4, 5].forEach(i => lines[i].classList.add('is-on')); cards.slice(0, 3).forEach(card => card.classList.add('is-repeat')); note.textContent = 'El contenedor se repite: una noticia, un registro.'; });
    },
    () => {
      [...query].forEach((char, i) => later(200 + i * 45, () => { input.textContent += char; }));
      const done = 200 + query.length * 45 + 400;
      later(done, () => { output.textContent = '▸ NodeList(3) [a, a, a]'; cards.slice(0, 3).forEach(card => card.classList.add('is-match')); note.textContent = '3 coincidencias = 3 noticias visibles.'; });
    },
    () => {
      later(200, () => rows[0].classList.add('is-on'));
      later(800, () => { rows[1].classList.add('is-on'); note.textContent = 'El documento ya trae tres noticias en el HTML.'; });
      later(2200, () => { rows[2].classList.add('is-on'); cards[3].classList.add('is-loaded'); note.textContent = 'La cuarta llega después, con un fetch: no está en el HTML inicial.'; });
    }
  ];
  function play(step) {
    clear();
    select(step);
    steps[step]();
  }
  function stopTour() {
    tourTimers.forEach(clearTimeout);
    tourTimers = [];
  }
  function tour() {
    stopTour();
    play(0);
    if (reduced) return;
    tourTimers.push(setTimeout(() => play(1), 5200), setTimeout(() => play(2), 8800));
  }
  function bind(element, step) {
    element.addEventListener('click', () => { stopTour(); play(step); });
    element.addEventListener('keydown', event => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      event.stopPropagation();
      stopTour();
      play(step);
    });
  }
  items.forEach((item, i) => {
    item.tabIndex = 0;
    item.setAttribute('role', 'button');
    bind(item, i);
  });
  tabs.forEach((tab, i) => bind(tab, i));
  mock.querySelector('.dt-replay').addEventListener('click', tour);
  const slide = root.closest('.slide');
  slide.addEventListener('slideshow', tour);
  if (slide.classList.contains('active')) tour();
  else select(0);
})();
