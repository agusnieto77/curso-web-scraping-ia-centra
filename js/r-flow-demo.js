'use strict';
(() => {
  const root = document.querySelector('.inspect');
  if (!root) return;
  const items = [...root.querySelectorAll('.editorial-list li')];
  const mock = root.querySelector('.rp');
  const tabs = [...mock.querySelectorAll('.dt-tab')];
  const console = mock.querySelector('.rp-console');
  const note = mock.querySelector('.dt-note');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const phases = [
    {
      lines: [
        ['cmd', 'pagina <- read_html(url)'],
        ['out', 'xml_document'],
        ['dim', 'elmundo.es/andalucia.html']
      ],
      note: 'Leer: si fallan la red o el HTML, el error aparece aquí.'
    },
    {
      lines: [
        ['cmd', 'arts <- html_elements(pagina, "article")'],
        ['out', '{xml_nodeset (3)}'],
        ['cmd', 'html_text2(html_element(arts, "h2"))'],
        ['out', '"Isabel Mayo…"  "Mellado…"  "Cámara…"'],
        ['cmd', 'html_attr(html_element(arts, "a"), "href")']
      ],
      note: 'Seleccionar acota el registro; extraer saca cada valor.'
    },
    {
      lines: [
        ['cmd', 'tabla <- tibble(titulo, url, fecha)'],
        ['out', '# 3 × 3'],
        ['cmd', 'mutate(titulo = str_squish(titulo))'],
        ['cmd', 'write_csv(tabla, "andalucia.csv")'],
        ['dim', 'andalucia.csv']
      ],
      note: 'Transformar y guardar van después, con los vectores ya alineados.'
    }
  ];
  let timers = [];
  let tourTimers = [];

  function later(ms, fn) {
    timers.push(setTimeout(fn, reduced ? 0 : ms));
  }
  function clear() {
    timers.forEach(clearTimeout);
    timers = [];
    console.replaceChildren();
    note.textContent = '';
  }
  function select(step) {
    items.forEach((item, i) => {
      item.classList.toggle('is-active', i === step);
      item.setAttribute('aria-pressed', String(i === step));
    });
    tabs.forEach((tab, i) => tab.setAttribute('aria-selected', String(i === step)));
  }
  function line(kind, text) {
    const row = document.createElement('div');
    row.className = 'rp-line ' + (kind === 'cmd' ? 'cmd' : kind);
    if (kind === 'cmd') {
      const prompt = document.createElement('span');
      prompt.className = 'dt-prompt';
      prompt.textContent = '> ';
      row.append(prompt, document.createTextNode(text));
    } else row.textContent = text;
    console.append(row);
    requestAnimationFrame(() => row.classList.add('is-in'));
  }
  function play(step) {
    clear();
    select(step);
    const phase = phases[step];
    note.textContent = phase.note;
    phase.lines.forEach((entry, i) => later(180 + i * 420, () => line(entry[0], entry[1])));
  }
  function stopTour() {
    tourTimers.forEach(clearTimeout);
    tourTimers = [];
  }
  function duration(step) {
    return 180 + phases[step].lines.length * 420 + 1200;
  }
  function tour() {
    stopTour();
    play(0);
    if (reduced) return;
    let delay = duration(0);
    for (let step = 1; step < phases.length; step++) {
      const at = delay;
      tourTimers.push(setTimeout(() => play(step), at));
      delay += duration(step);
    }
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
