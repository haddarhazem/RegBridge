(() => {
  const progress = document.querySelector('[data-page-progress]');
  const setProgress = () => {
    if (!progress) return;
    const max = Math.max(document.documentElement.scrollHeight - window.innerHeight, 1);
    progress.style.width = `${Math.min(100, (window.scrollY / max) * 100)}%`;
  };
  window.addEventListener('scroll', setProgress, { passive: true });
  window.addEventListener('resize', setProgress, { passive: true });
  setProgress();

  const menu = document.querySelector('.menu-toggle');
  const nav = document.querySelector('#site-nav');
  if (menu && nav) {
    menu.addEventListener('click', () => {
      const open = menu.getAttribute('aria-expanded') === 'true';
      menu.setAttribute('aria-expanded', String(!open));
      nav.classList.toggle('is-open', !open);
      menu.textContent = open ? 'Menu' : 'Fermer';
    });
    nav.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => {
      menu.setAttribute('aria-expanded', 'false');
      nav.classList.remove('is-open');
      menu.textContent = 'Menu';
    }));
  }

  const pages = [...document.querySelectorAll('[data-page]')];
  const pageObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => entry.target.classList.toggle('is-active', entry.isIntersecting));
  }, { threshold: 0.52 });
  pages.forEach((page) => pageObserver.observe(page));

  if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) entry.target.classList.add('is-visible');
      });
    }, { threshold: 0.12 });
    document.querySelectorAll('[data-reveal]').forEach((node) => observer.observe(node));
  } else {
    document.querySelectorAll('[data-reveal]').forEach((node) => node.classList.add('is-visible'));
  }
})();
