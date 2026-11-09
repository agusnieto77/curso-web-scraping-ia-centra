'use strict';
(() => {
  const demos = [...document.querySelectorAll('.sel-demo')];
  if (!demos.length) return;
  const SVG = 'http://www.w3.org/2000/svg';
  const nodes = {
    article: { x: 150, y: 20, label: 'article' },
    h2: { x: 70, y: 80, label: 'h2' },
    p: { x: 220, y: 80, label: 'p' },
    a1: { x: 70, y: 140, label: 'a href' },
    a2: { x: 180, y: 140, label: 'a href' },
    a3: { x: 260, y: 140, label: 'a id' }
  };
  const edges = [['article', 'h2'], ['article', 'p'], ['h2', 'a1'], ['p', 'a2'], ['p', 'a3']];
  const path = [
    { tok: 0, on: ['article'] },
    { tok: 1, on: ['article', 'h2'] },
    { tok: 2, on: ['article', 'h2'], match: ['a1'], miss: ['a2', 'a3'] }
  ];
  const modes = {
    css: { tokens: ['article', ' h2', ' a'], steps: path, result: '1 coincidencia: solo el enlace del título.' },
    attr: {
      tokens: ['a[href]'],
      steps: [
        { tok: 0, match: ['a1'], miss: ['article', 'h2', 'p'] },
        { tok: 0, match: ['a1', 'a2'], miss: ['article', 'h2', 'p'] },
        { tok: 0, match: ['a1', 'a2'], miss: ['article', 'h2', 'p', 'a3'] }
      ],
      result: '2 coincidencias: todo enlace con href.'
    },
    xpath: { tokens: ['//article', '//h2', '/a'], steps: path, result: '1 coincidencia: igual que article h2 a.' }
  };
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  function create(tag, attrs) {
    const element = document.createElementNS(SVG, tag);
    Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
    return element;
  }
  demos.forEach((demo, order) => {
    const mode = modes[demo.dataset.mode];
    const svg = create('svg', { class: 'sel-tree', viewBox: '0 0 300 160', 'aria-hidden': 'true' });
    const lines = edges.map(([from, to]) => {
      const line = create('line', { class: 'sel-edge', x1: nodes[from].x, y1: nodes[from].y + 13, x2: nodes[to].x, y2: nodes[to].y - 13 });
      svg.append(line);
      return { line, from, to };
    });
    const boxes = Object.fromEntries(Object.entries(nodes).map(([id, node]) => {
      const group = create('g', { class: 'sel-node' });
      const label = create('text', { x: node.x, y: node.y + 4 });
      label.textContent = node.label;
      group.append(create('rect', { x: node.x - 32, y: node.y - 13, width: 64, height: 26 }), label);
      svg.append(group);
      return [id, group];
    }));
    const expr = document.createElement('p');
    expr.className = 'sel-expr';
    const tokens = mode.tokens.map(token => expr.appendChild(Object.assign(document.createElement('span'), { textContent: token })));
    const result = document.createElement('div');
    result.className = 'sel-result';
    const count = document.createElement('span');
    count.setAttribute('aria-live', 'polite');
    const replay = Object.assign(document.createElement('button'), { type: 'button', textContent: '↻' });
    replay.setAttribute('aria-label', 'Repetir animación');
    result.append(count, replay);
    demo.append(svg, expr, result);

    let timers = [];
    function apply(index) {
      const step = mode.steps[index] || {};
      const on = step.on || [], match = step.match || [], miss = step.miss || [];
      Object.entries(boxes).forEach(([id, box]) => {
        box.classList.toggle('on', on.includes(id));
        box.classList.toggle('match', match.includes(id));
        box.classList.toggle('miss', miss.includes(id));
      });
      lines.forEach(({ line, from, to }) => line.classList.toggle('on', on.includes(from) && (on.includes(to) || match.includes(to))));
      tokens.forEach((token, i) => {
        token.classList.toggle('on', step.tok !== undefined && i < step.tok);
        token.classList.toggle('now', i === step.tok);
      });
      count.textContent = index === mode.steps.length - 1 ? mode.result : '';
    }
    function play() {
      timers.forEach(clearTimeout);
      timers = [];
      if (reduced) return apply(mode.steps.length - 1);
      apply(-1);
      mode.steps.forEach((_, i) => timers.push(setTimeout(() => apply(i), 400 + order * 500 + i * 1300)));
    }
    replay.addEventListener('click', play);
    const slide = demo.closest('.slide');
    slide.addEventListener('slideshow', play);
    if (slide.classList.contains('active')) play();
    else apply(mode.steps.length - 1);
  });
})();
