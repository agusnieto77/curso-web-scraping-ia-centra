'use strict';
/* Motor compartido de las animaciones de la clase 04.
   Tres mecanismos: paneles por pasos (pane), consola por fases (console) y escenas SVG (scene).
   Cada demo registra su configuración y el motor monta todo al terminar el documento. */
window.PY = (() => {
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const registry = { pane: [], console: [], scene: [] };

  function bindStep(element, handler) {
    element.addEventListener('click', handler);
    element.addEventListener('keydown', event => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      event.stopPropagation();
      handler();
    });
  }

  /* Paneles: una diapositiva con N paneles y una lista de pasos que los va revelando. */
  function paneDemo(root, config) {
    const items = [...root.querySelectorAll('.editorial-list li')];
    const view = root.querySelector('.rb');
    const panes = [...view.querySelectorAll('.rb-pane')];
    const sign = view.querySelector('.rd-sign');
    const verdict = view.querySelector('.rd-text');
    const note = view.querySelector('.dt-note');
    const gap = config.gap || 1100;
    let timers = [];
    let tourTimers = [];

    const lastAt = pane => Math.max(...[...pane.querySelectorAll('[data-at]')].map(el => Number(el.dataset.at)));
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
        note.textContent = config.steps[step].notes[at] || note.textContent;
        if (at === last) timers.push(setTimeout(() => settle(config.steps[step].verdict), reduced ? 0 : 500));
      };
      if (reduced) return apply(last);
      apply(0);
      for (let at = 1; at <= last; at++) timers.push(setTimeout(() => apply(at), at * gap));
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
        delay += (lastAt(pane) + 2) * gap;
        tourTimers.push(setTimeout(() => play(i + 1), delay));
      });
    }
    items.forEach((item, i) => {
      item.tabIndex = 0;
      item.setAttribute('role', 'button');
      bindStep(item, () => {
        stopTour();
        play(i);
      });
    });
    const replay = view.querySelector('.rb-replay');
    if (replay) replay.addEventListener('click', tour);
    const slide = root.closest('.slide');
    slide.addEventListener('slideshow', tour);
    if (slide.classList.contains('active')) tour();
    else play(0);
  }

  /* Consola: fases encadenadas (pestañas) que se escriben línea a línea. */
  function consoleDemo(root, config) {
    const items = [...root.querySelectorAll('.editorial-list li')];
    const tabs = [...root.querySelectorAll('.dt-tab')];
    const consoleEl = root.querySelector('.py-console');
    const note = root.querySelector('.dt-note');
    let timers = [];
    let tourTimers = [];

    function later(ms, fn) {
      timers.push(setTimeout(fn, reduced ? 0 : ms));
    }
    function clear() {
      timers.forEach(clearTimeout);
      timers = [];
      consoleEl.replaceChildren();
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
      row.className = 'py-line ' + (kind === 'cmd' ? 'cmd' : kind);
      if (kind === 'cmd') {
        const prompt = document.createElement('span');
        prompt.className = 'dt-prompt';
        prompt.textContent = '>>> ';
        row.append(prompt, document.createTextNode(text));
      } else row.textContent = text;
      consoleEl.append(row);
      requestAnimationFrame(() => row.classList.add('is-in'));
    }
    function play(step) {
      clear();
      select(step);
      const phase = config.phases[step];
      note.textContent = phase.note;
      phase.lines.forEach((entry, i) => later(180 + i * 420, () => line(entry[0], entry[1])));
    }
    function stopTour() {
      tourTimers.forEach(clearTimeout);
      tourTimers = [];
    }
    function duration(step) {
      return 180 + config.phases[step].lines.length * 420 + 1200;
    }
    function tour() {
      stopTour();
      play(0);
      if (reduced) return;
      let delay = duration(0);
      config.phases.slice(1).forEach((_, i) => {
        tourTimers.push(setTimeout(() => play(i + 1), delay));
        delay += duration(i + 1);
      });
    }
    items.forEach((item, i) => {
      item.tabIndex = 0;
      item.setAttribute('role', 'button');
      bindStep(item, () => {
        stopTour();
        play(i);
      });
    });
    tabs.forEach((tab, i) => {
      bindStep(tab, () => {
        stopTour();
        play(i);
      });
    });
    const replay = root.querySelector('.dt-replay');
    if (replay) replay.addEventListener('click', tour);
    const slide = root.closest('.slide');
    slide.addEventListener('slideshow', tour);
    if (slide.classList.contains('active')) tour();
    else select(0);
  }

  /* Escenas: grupos SVG con data-at que aparecen de uno en uno. */
  function sceneDemo(root, config) {
    const parts = [...root.querySelectorAll('[data-at]')];
    const last = Math.max(...parts.map(part => Number(part.dataset.at)));
    const note = root.querySelector('.dt-note');
    const itemSteps = config.itemSteps || null;
    const items = itemSteps ? [...root.querySelectorAll('.editorial-list li')] : [];
    const gap = config.gap || 900;
    let timers = [];

    function apply(step) {
      parts.forEach(part => part.classList.toggle('is-on', Number(part.dataset.at) <= step));
      root.querySelectorAll('.hot').forEach(el => el.classList.remove('hot'));
      (config.hot || []).forEach(rule => {
        if (step < rule.at) return;
        root.querySelectorAll(rule.selector).forEach(el => el.classList.add('hot'));
      });
      if (itemSteps) {
        let active = -1;
        itemSteps.forEach((at, i) => { if (at <= step) active = i; });
        items.forEach((item, i) => {
          item.classList.toggle('is-active', i === active);
          item.setAttribute('aria-pressed', String(i === active));
        });
      }
      if (note && config.notes) note.textContent = config.notes[step] || '';
    }
    function play(from = 0) {
      timers.forEach(clearTimeout);
      timers = [];
      if (reduced) return apply(last);
      apply(from);
      for (let step = from + 1; step <= last; step++) timers.push(setTimeout(() => apply(step), step * gap));
    }
    items.forEach((item, i) => {
      item.tabIndex = 0;
      item.setAttribute('role', 'button');
      bindStep(item, () => play(itemSteps[i]));
    });
    const replay = root.querySelector('.st-replay');
    if (replay) replay.addEventListener('click', () => play());
    const slide = root.closest('.slide');
    slide.addEventListener('slideshow', () => play());
    if (slide.classList.contains('active')) play();
    else apply(last);
  }

  function mount() {
    registry.pane.forEach(config => document.querySelectorAll(config.selector).forEach(root => paneDemo(root, config)));
    registry.console.forEach(config => document.querySelectorAll(config.selector).forEach(root => consoleDemo(root, config)));
    registry.scene.forEach(config => document.querySelectorAll(config.selector).forEach(root => sceneDemo(root, config)));
  }

  document.addEventListener('DOMContentLoaded', mount);

  return {
    pane: config => registry.pane.push(config),
    console: config => registry.console.push(config),
    scene: config => registry.scene.push(config)
  };
})();
