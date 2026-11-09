'use strict';
(() => {
  const demo = document.querySelector('.dom-demo');
  if (!demo) return;
  const steps = {
    1: { text: 'Cada etiqueta abre un nodo: con ellas el navegador arma un árbol, el DOM.', css: 'article', xpath: '//article' },
    2: { text: 'Los atributos viajan con su nodo: class ayuda a ubicarlo; href y datetime son el dato.', css: 'time[datetime]', xpath: '//time/@datetime' },
    3: { text: 'article es padre de h2 y time, que son hermanos; a es descendiente de article.', css: 'article.noticia > h2 a', xpath: '//article/h2/a/@href' }
  };
  const buttons = [...demo.querySelectorAll('.dom-steps [data-step]')];
  const text = demo.querySelector('.dom-text');
  const [css, xpath] = demo.querySelectorAll('.dom-selector code');
  const panel = demo.closest('[role="tabpanel"]');
  let timers = [];
  function stop() {
    timers.forEach(clearTimeout);
    timers = [];
  }
  function show(step) {
    demo.dataset.step = step;
    buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.step === String(step))));
    const info = steps[step];
    text.textContent = info ? info.text : '';
    css.textContent = info ? info.css : '';
    xpath.textContent = info ? info.xpath : '';
  }
  function play() {
    stop();
    show(0);
    [1, 2, 3].forEach((step, i) => timers.push(setTimeout(() => show(step), 200 + i * 3600)));
  }
  buttons.forEach(button => button.addEventListener('click', () => {
    stop();
    show(Number(button.dataset.step));
  }));
  demo.querySelector('.dom-replay').addEventListener('click', play);
  panel.addEventListener('tabshow', play);
  panel.addEventListener('tabhide', () => {
    stop();
    show(0);
  });
  demo.querySelectorAll('[data-n]').forEach(element => {
    const peers = demo.querySelectorAll(`[data-n="${element.dataset.n}"]`);
    element.addEventListener('mouseenter', () => peers.forEach(peer => peer.classList.add('hl')));
    element.addEventListener('mouseleave', () => peers.forEach(peer => peer.classList.remove('hl')));
  });
})();
