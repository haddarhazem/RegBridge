(() => {
  const { MotionProvider, ScrollProgress } = window.RegBridgeMotion;
  const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
  const lerp = (from, to, amount) => from + (to - from) * amount;

  // Four points make each state fade in, hold, and fade out while neighbouring
  // states overlap. No scene is selected by a rounded scroll position.
  const blend = (progress, start, enterEnd, exitStart, end) => {
    if (progress < start || progress >= end) return 0;
    if (progress === start) return start === 0 ? 1 : 0;
    if (progress < enterEnd) return clamp((progress - start) / (enterEnd - start));
    if (progress <= exitStart) return 1;
    return clamp(1 - (progress - exitStart) / (end - exitStart));
  };

  const exclusiveFade = (progress, start, end, edge = 0.035) => {
    if (progress < start || progress >= end) return 0;
    if (progress === start) return start === 0 ? 1 : 0;
    const fade = Math.min(edge, (end - start) / 4);
    if (progress < start + fade) return (progress - start) / fade;
    if (progress > end - fade) return (end - progress) / fade;
    return 1;
  };

  class LandingStory {
    constructor(element, provider) {
      this.element = element;
      this.provider = provider;
      this.contents = [...element.querySelectorAll('[data-scene-content]')];
      this.layers = [...element.querySelectorAll('[data-panel-layer]')];
      this.panel = element.querySelector('[data-morph-panel]');
      this.signals = [...element.querySelectorAll('[data-signal]')];
      this.roleHeadlines = [...element.querySelectorAll('[data-role-headline]')];
      this.tabs = [...element.querySelectorAll('[data-role-tab]')];
      this.systemNodes = [...element.querySelectorAll('.system-rail span')];
      this.panelIndex = element.querySelector('[data-panel-index]');
      this.panelRoleLabel = element.querySelector('[data-panel-role-label]');
      this.panelRoleCopy = element.querySelector('[data-panel-role-copy]');
      this.panelSignal = [...element.querySelectorAll('[data-panel-signal]')];
      this.trustLabel = element.querySelector('[data-trust-label]');
      this.trustCopy = element.querySelector('[data-trust-copy]');
      this.mobile = window.matchMedia('(max-width: 600px)');
      provider.subscribe((progress) => this.update(progress));
      this.tabs.forEach((tab) => tab.addEventListener('click', () => {
        const role = Number(tab.dataset.roleTab);
        const targets = [0.35, 0.42, 0.49];
        window.scrollTo({ top: targets[role] * Math.max(document.documentElement.scrollHeight - window.innerHeight, 1), behavior: 'smooth' });
      }));
    }

    setVisibility(node, amount, lift = 22) {
      if (!node) return;
      node.style.opacity = String(amount);
      node.style.transform = `translateY(${(1 - amount) * lift}px)`;
      node.style.pointerEvents = amount > 0.2 ? 'auto' : 'none';
    }

    update(progress) {
      const isMobile = this.mobile.matches;
      const reduced = this.provider.reduced;
      this.element.style.setProperty('--story-progress', progress.toFixed(4));

      const contentRanges = [
        [0, 0.18],
        [0.18, 0.32],
        [0.32, 0.53],
        [0.53, 0.70],
        [0.70, 0.88],
      ];
      if (isMobile || reduced) {
        this.contents.forEach((node) => this.setVisibility(node, 1, 0));
        this.layers.forEach((node) => this.setVisibility(node, 1, 0));
        this.roleHeadlines.forEach((node) => node.classList.add('active'));
        this.signals.forEach((node) => this.setVisibility(node, 1, 0));
        if (this.panel) {
          this.panel.style.transform = 'none';
          this.panel.style.setProperty('--panel-scale', 1);
          this.panel.style.setProperty('--panel-inverse-scale', 1);
        }
        return;
      }

      this.contents.forEach((node, index) => this.setVisibility(node, exclusiveFade(progress, ...contentRanges[index])));

      const panelRanges = [
        [0, 0.18],
        [0.18, 0.32],
        [0.32, 0.53],
        [0.53, 0.70],
        [0.70, 0.88],
        [0.88, 1.01],
      ];
      this.layers.forEach((node, index) => this.setVisibility(node, exclusiveFade(progress, ...panelRanges[index]), 12));

      if (this.panel) {
        const frames = [
          [0, 0, 1],
          [0.22, -58, 2.65],
          [0.45, -8, 1.02],
          [0.62, -40, 0.94],
          [0.78, -4, 1.04],
          [0.95, -25, 0.72],
        ];
        let left = frames[0];
        let right = frames[frames.length - 1];
        for (let index = 1; index < frames.length; index += 1) {
          if (progress <= frames[index][0]) { right = frames[index]; left = frames[index - 1]; break; }
        }
        const amount = right[0] === left[0] ? 0 : clamp((progress - left[0]) / (right[0] - left[0]));
        const translateX = lerp(left[1], right[1], amount);
        const scale = lerp(left[2], right[2], amount);
        this.panel.style.setProperty('--panel-scale', scale);
        this.panel.style.setProperty('--panel-inverse-scale', 1 / scale);
        this.panel.style.transform = `translate(${translateX}%, ${lerp(0, 88, blend(progress, 0.45, 0.62, 0.78, 0.95))}%) scale(${scale})`;
      }

      const roleProgress = clamp((progress - 0.27) / 0.26);
      const roleWeights = [
        exclusiveFade(roleProgress, 0, 0.32),
        exclusiveFade(roleProgress, 0.32, 0.68),
        exclusiveFade(roleProgress, 0.68, 1.01),
      ];
      this.roleHeadlines.forEach((node, index) => {
        this.setVisibility(node, roleWeights[index], 18);
        node.classList.toggle('active', roleWeights[index] > 0);
      });
      const roleIndex = roleWeights.indexOf(Math.max(...roleWeights));
      const roles = [
        ['01 / STARTUP', 'Du projet initial à la roadmap et au suivi de conformité.'],
        ['02 / INVESTISSEUR', 'Filtrer des opportunités avec des données autorisées et des preuves.'],
        ['03 / RECHERCHE', 'Déposer, vérifier et collaborer autour de sources explicites.'],
      ];
      if (roleIndex >= 0) {
        if (this.panelRoleLabel) this.panelRoleLabel.textContent = roles[roleIndex][0];
        if (this.panelRoleCopy) this.panelRoleCopy.textContent = roles[roleIndex][1];
        this.tabs.forEach((tab, index) => {
          const active = index === roleIndex;
          tab.classList.toggle('is-active', active);
          tab.setAttribute('aria-pressed', String(active));
        });
      }

      const systemProgress = clamp((progress - 0.48) / 0.22);
      const systemIndex = Math.min(3, Math.floor(systemProgress * 4));
      this.systemNodes.forEach((node, index) => node.classList.toggle('active', index === systemIndex));
      const trustProgress = clamp((progress - 0.65) / 0.23);
      const trustIndex = Math.min(3, Math.floor(trustProgress * 4));
      const trust = [
        ['SOURCE', 'Chaque conclusion importante conserve une référence.'],
        ['VERSION', 'Chaque résultat garde son entrée exacte.'],
        ['PERMISSION', 'Chaque accès possède une portée explicite.'],
        ['VALIDATION', 'Chaque fait sensible est confirmé.'],
      ];
      if (this.trustLabel) this.trustLabel.textContent = trust[trustIndex][0];
      if (this.trustCopy) this.trustCopy.textContent = trust[trustIndex][1];

      const signalRanges = {
        france: [0.12, 0.25],
        startup: [0.25, 0.40],
        investor: [0.40, 0.53],
        researcher: [0.53, 0.66],
        trust: [0.70, 0.88],
      };
      this.signals.forEach((node) => {
        const amount = exclusiveFade(progress, ...signalRanges[node.dataset.signal]);
        this.setVisibility(node, amount, 10);
      });

      if (this.panelIndex) {
        const sceneStops = [0, 0.18, 0.32, 0.53, 0.70, 0.88];
        let scene = 1;
        sceneStops.forEach((stop, index) => { if (progress >= stop) scene = index + 1; });
        this.panelIndex.textContent = `${String(Math.min(scene, 6)).padStart(2, '0')} / 06`;
      }
    }
  }

  const provider = new MotionProvider();
  new ScrollProgress(provider);
  const story = document.querySelector('[data-story]');
  if (story) new LandingStory(story, provider);

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
})();
