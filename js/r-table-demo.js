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
  const table = ['<table>', '<tr><th colspan="2">Ejemplo', '<tr><th>Provincia<th>Tasa', '<tr><td>Sevilla<td>18,4 %', '<tr><td>Cádiz<td>', '</table>'];
  const tibble = ['# html_table()', 'provincia  tasa', 'Sevilla    18,4 %', 'Cádiz      NA'];
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
    src.replaceChildren();
    dom.replaceChildren();
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
    view.dataset.step = String(step);
  }
  const steps = [
    () => {
      note.textContent = 'html_table() lee una table, no un diseño que solo parece una tabla.';
      const end = type(src, table, 160, 180);
      type(dom, tibble, end + 160, 140);
      later(end + 900, () => settle('!', 'El th con colspan no es una columna: hay que mirar el encabezado.', 'diff'));
    },
    () => {
      note.textContent = 'La celda se ve numérica. El valor sigue siendo texto.';
      type(src, ['<td>18,4 %</td>'], 200, 0);
      type(dom, ['tasa: character', '"18,4 %"', 'coma decimal · unidad %'], 700, 280);
      later(1700, () => settle('≠', 'Separador, unidad y vacíos no se adivinan por el aspecto.', 'diff'));
    },
    () => {
      note.textContent = 'Buscar la tabla en la respuesta, no solo en la pantalla.';
      checks.forEach((check, i) => later(300 + i * 800, () => check.classList.add('is-on')));
      later(500, () => js.classList.add('is-on'));
      later(300 + checks.length * 800 + 200, () => settle('→', 'Si la pinta JavaScript, html_table() sobre el HTML inicial no la ve.', 'diff'));
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
    tourTimers.push(setTimeout(() => play(1), 3200), setTimeout(() => play(2), 6200));
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
