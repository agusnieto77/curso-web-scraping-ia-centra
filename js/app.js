'use strict';
(() => {
  const slides = [...document.querySelectorAll('.slide')];
  const previous = document.querySelector('#prev');
  const next = document.querySelector('#next');
  const counter = document.querySelector('#counter');
  const progress = document.querySelector('progress');
  let current = 0;
  function show(index, updateHash = true) {
    const target = Math.max(0, Math.min(slides.length - 1, index));
    const changed = target !== current;
    current = target;
    slides.forEach((slide, i) => {
      slide.hidden = i !== current;
      slide.classList.toggle('active', i === current);
    });
    if (changed) slides[current].dispatchEvent(new Event('slideshow'));
    previous.disabled = current === 0;
    next.disabled = current === slides.length - 1;
    counter.textContent = `${String(current + 1).padStart(2, '0')} / ${String(slides.length).padStart(2, '0')}`;
    progress.value = current + 1;
    progress.max = slides.length;
    if (updateHash) history.replaceState(null, '', `#${current + 1}`);
    window.scrollTo(0, 0);
  }
  function fromHash() {
    const value = /^#([1-9]\d*)$/.exec(location.hash);
    show(value ? Number(value[1]) - 1 : 0, false);
  }
  previous.addEventListener('click', () => show(current - 1));
  next.addEventListener('click', () => show(current + 1));
  document.addEventListener('keydown', event => {
    if (event.altKey || event.ctrlKey || event.metaKey || /INPUT|TEXTAREA|SELECT|BUTTON|A/.test(event.target.tagName)) return;
    if (['ArrowRight', 'PageDown', ' '].includes(event.key)) { event.preventDefault(); show(current + 1); }
    if (['ArrowLeft', 'PageUp'].includes(event.key)) { event.preventDefault(); show(current - 1); }
    if (event.key === 'Home') { event.preventDefault(); show(0); }
    if (event.key === 'End') { event.preventDefault(); show(slides.length - 1); }
    if (event.key.toLowerCase() === 'f') {
      if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
      else document.documentElement.requestFullscreen?.().catch(() => {});
    }
  });
  document.querySelectorAll('[role="tablist"]').forEach(list => {
    const tabs = [...list.querySelectorAll('[role="tab"]')];
    const panel = tab => document.getElementById(tab.getAttribute('aria-controls'));
    function select(tab) {
      tabs.forEach(t => {
        const selected = t === tab;
        t.setAttribute('aria-selected', String(selected));
        t.tabIndex = selected ? 0 : -1;
        panel(t).hidden = !selected;
        panel(t).dispatchEvent(new Event(selected ? 'tabshow' : 'tabhide'));
      });
    }
    tabs.forEach((tab, i) => {
      tab.addEventListener('click', () => select(tab));
      tab.addEventListener('keydown', event => {
        if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
        event.preventDefault();
        const target = tabs[(i + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length];
        select(target);
        target.focus();
      });
    });
  });
  const brand = document.querySelector('.brand[data-campus]');
  if (brand && location.pathname.includes('/pluginfile.php/')) brand.href = brand.dataset.campus;
  window.addEventListener('hashchange', fromHash);
  fromHash();
})();
