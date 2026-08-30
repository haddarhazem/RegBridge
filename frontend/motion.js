/* One scroll source for the landing story. Components subscribe to the
 * smoothed value; they never install their own input handlers. */
class MotionProvider {
  constructor() {
    this.reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.target = 0;
    this.progress = 0;
    this.listeners = new Set();
    this.ticking = false;
    this.onScroll = () => {
      this.target = this.read();
      this.schedule();
    };
    this.onResize = () => {
      this.target = this.read();
      this.schedule();
    };
    window.addEventListener('scroll', this.onScroll, { passive: true });
    window.addEventListener('resize', this.onResize, { passive: true });
    this.target = this.read();
    this.schedule();
  }

  read() {
    const max = Math.max(document.documentElement.scrollHeight - window.innerHeight, 1);
    return Math.min(1, Math.max(0, window.scrollY / max));
  }

  schedule() {
    if (this.ticking) return;
    this.ticking = true;
    requestAnimationFrame(() => this.update());
  }

  update() {
    this.progress = this.reduced ? this.target : this.progress + (this.target - this.progress) * 0.18;
    if (Math.abs(this.target - this.progress) < 0.0008) this.progress = this.target;
    this.listeners.forEach((listener) => listener(this.progress, this.target));
    if (!this.reduced && this.progress !== this.target) {
      requestAnimationFrame(() => this.update());
    } else {
      this.ticking = false;
    }
  }

  subscribe(listener) {
    this.listeners.add(listener);
    listener(this.progress, this.target);
    return () => this.listeners.delete(listener);
  }
}

class ScrollProgress {
  constructor(provider) {
    this.node = document.querySelector('[data-page-progress]');
    this.scene = document.querySelector('[data-scene-number]');
    provider.subscribe((progress) => {
      if (this.node) this.node.style.width = `${progress * 100}%`;
      if (this.scene) {
        const stops = [0, 0.18, 0.32, 0.53, 0.70, 0.88, 1];
        const index = stops.findLastIndex((stop) => progress >= stop);
        this.scene.textContent = String(Math.min(index + 1, 6)).padStart(2, '0');
      }
    });
  }
}

window.RegBridgeMotion = { MotionProvider, ScrollProgress };
