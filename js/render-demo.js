'use strict';
(() => {
  const root = document.querySelector('.compare');
  if (!root) return;
  const items = [...root.querySelectorAll('.editorial-list li')];
  const view = root.querySelector('.rd');
  const src = view.querySelector('.rd-src');
  const dom = view.querySelector('.rd-dom');
  const js = view.querySelector('.rd-js');
  const sign = view.querySelector('.rd-sign');
  const verdict = view.querySelector('.rd-text');
  const checks = [...view.querySelectorAll('.rd-check')];
  const note = view.querySelector('.dt-note');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const list = ['<ul id="listado">', '  <li>Noticia 1</li>', '  <li>Noticia 2</li>', '  <li>Noticia 3</li>', '</ul>'];
  const empty = ['<ul id="listado"></ul>', '<script src="app.js">'];
  let timers = [];
  let tourTimers = [];

  function later(ms, fn) {
    timers.push(setTimeout(fn, reduced ? 0 : ms));
  }
  function line(pane, text, extra = '') {
    const row = document.createElement('div');
    row.className = 'rd-line ' + extra;
    row.textContent = text;
    pane.append(row);
    requestAnimationFrame(() => row.classList.add('is-in'));
    return row;
  }
  function type(pane, lines, start, gap, extra) {
    lines.forEach((text, i) => later(start + i * gap, () => line(pane, text, extra)));
    return start + lines.length * gap;
  }
  function settle(symbol, text, state) {
    sign.textContent = symbol;
    verdict.textContent = text;
    view.dataset.verdict = state;
  }
  function clear() {
    timers.forEach(clearTimeout);
    timers = [];
    src.textContent = '';
    dom.textContent = '';
    js.classList.remove('is-on');
    checks.forEach(check => check.classList.remove('is-on'));
    settle('', '', '');
    note.textContent = '';
  }
  function select(step) {
    items.forEach((item, i) => {
      item.classList.toggle('is-active', i === step);
      item.setAttribute('aria-pressed', String(i === step));
    });
    view.dataset.step = step;
  }
  const steps = [
    () => {
      note.textContent = 'La respuesta del servidor ya trae las noticias.';
      const end = type(src, list, 200, 260);
      type(dom, list, end + 200, 120);
      later(end + 1000, () => settle('=', 'Mismo contenido: alcanza con descargar el HTML.', 'same'));
    },
    () => {
      note.textContent = 'La respuesta llega con la lista vacía y un script.';
      const end = type(src, empty, 200, 300);
      type(dom, ['<ul id="listado">'], end + 200, 0);
      later(end + 900, () => { js.classList.add('is-on'); note.textContent = 'JavaScript se ejecuta en el navegador y completa la lista.'; });
      const filled = type(dom, list.slice(1, 4), end + 1500, 320, 'is-new');
      type(dom, ['</ul>'], filled, 0);
      later(filled + 500, () => settle('≠', 'El contenido lo agregó JavaScript después de cargar.', 'diff'));
    },
    () => {
      note.textContent = 'Buscar el mismo dato en los tres lugares.';
      checks.forEach((check, i) => later(300 + i * 900, () => check.classList.add('is-on')));
      later(300 + checks.length * 900 + 200, () => settle('→', 'Dinámica: pedir noticias.json o usar un navegador automatizado.', 'diff'));
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
    tourTimers.push(setTimeout(() => play(1), 4600), setTimeout(() => play(2), 4600 + 5600));
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
  view.querySelector('.rd-replay').addEventListener('click', tour);
  const slide = root.closest('.slide');
  slide.addEventListener('slideshow', tour);
  if (slide.classList.contains('active')) tour();
  else select(0);
})();
