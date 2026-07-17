/* ============================================
   whaagent Landing — Animations + Theme
   ============================================ */

(function () {
  'use strict';

  // ---- Theme Toggle ----
  const html = document.documentElement;
  const toggle = document.getElementById('theme-toggle');

  function getPreferredTheme() {
    const saved = localStorage.getItem('theme');
    if (saved) return saved;
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }

  function setTheme(theme) {
    html.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }

  setTheme(getPreferredTheme());

  toggle.addEventListener('click', () => {
    const current = html.getAttribute('data-theme');
    setTheme(current === 'dark' ? 'light' : 'dark');
  });

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!localStorage.getItem('theme')) {
      setTheme(e.matches ? 'dark' : 'light');
    }
  });

  // ---- GSAP Setup ----
  gsap.registerPlugin(ScrollTrigger);

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if (reducedMotion) {
    gsap.globalTimeline.timeScale(100);
    document.querySelectorAll('.anim-fade-up, .anim-split, .anim-scale-in, .scroll-reveal').forEach(el => {
      el.style.opacity = '1';
      el.style.transform = 'none';
    });
    return;
  }

  // ---- Text Splitting Utility ----
  function splitText(el) {
    const text = el.textContent;
    el.innerHTML = '';
    const words = text.split(/\s+/);
    words.forEach((word, i) => {
      const span = document.createElement('span');
      span.style.display = 'inline-block';
      span.style.overflow = 'hidden';
      const inner = document.createElement('span');
      inner.textContent = word;
      inner.style.display = 'inline-block';
      inner.classList.add('split-word');
      span.appendChild(inner);
      el.appendChild(span);
      if (i < words.length - 1) {
        el.appendChild(document.createTextNode(' '));
      }
    });
    return el.querySelectorAll('.split-word');
  }

  // ---- Hero Entry Animation ----
  const heroTl = gsap.timeline({ delay: 0.2 });

  // Badge
  heroTl.to('.hero-badge', {
    opacity: 1,
    y: 0,
    duration: 0.6,
    ease: 'power3.out',
  });

  // Split text lines
  document.querySelectorAll('.hero-title .line').forEach((line, i) => {
    const words = splitText(line);
    heroTl.to(words, {
      opacity: 1,
      y: 0,
      duration: 0.5,
      stagger: 0.04,
      ease: 'power3.out',
    }, 0.15 + i * 0.12);
  });

  // Subtext
  heroTl.to('.hero-sub', {
    opacity: 1,
    y: 0,
    duration: 0.6,
    ease: 'power3.out',
  }, 0.5);

  // CTAs
  heroTl.to('.hero-ctas', {
    opacity: 1,
    y: 0,
    duration: 0.6,
    ease: 'power3.out',
  }, 0.65);

  // Video
  heroTl.to('.hero-video', {
    opacity: 1,
    scale: 1,
    duration: 0.8,
    ease: 'power3.out',
  }, 0.3);

  // ---- Orb Floating Animation ----
  gsap.to('.orb-1', {
    x: 30,
    y: 20,
    duration: 8,
    repeat: -1,
    yoyo: true,
    ease: 'sine.inOut',
  });

  gsap.to('.orb-2', {
    x: -25,
    y: -15,
    duration: 10,
    repeat: -1,
    yoyo: true,
    ease: 'sine.inOut',
  });

  gsap.to('.orb-3', {
    x: 20,
    y: -20,
    duration: 12,
    repeat: -1,
    yoyo: true,
    ease: 'sine.inOut',
  });

  // ---- Scroll Reveal ----
  document.querySelectorAll('.scroll-reveal').forEach((el) => {
    const delay = parseFloat(el.dataset.delay) || 0;

    gsap.to(el, {
      scrollTrigger: {
        trigger: el,
        start: 'top 88%',
        once: true,
      },
      opacity: 1,
      y: 0,
      duration: 0.7,
      delay: delay,
      ease: 'power3.out',
    });
  });

  // ---- Section Title Split Text Animation ----
  document.querySelectorAll('.split-text').forEach((el) => {
    const words = splitText(el);

    ScrollTrigger.create({
      trigger: el,
      start: 'top 85%',
      once: true,
      onEnter: () => {
        gsap.to(words, {
          opacity: 1,
          y: 0,
          duration: 0.5,
          stagger: 0.04,
          ease: 'power3.out',
        });
      },
    });
  });

  // ---- Stat Counter Animation ----
  document.querySelectorAll('.stat-number[data-count]').forEach((el) => {
    const target = parseInt(el.dataset.count, 10);

    ScrollTrigger.create({
      trigger: el,
      start: 'top 90%',
      once: true,
      onEnter: () => {
        gsap.to({ val: 0 }, {
          val: target,
          duration: 1.2,
          ease: 'power2.out',
          onUpdate: function () {
            el.textContent = Math.round(this.targets()[0].val);
          },
        });
      },
    });
  });

  // ---- Nav Scroll Effect ----
  let lastScroll = 0;
  const nav = document.getElementById('nav');

  window.addEventListener('scroll', () => {
    const scrollY = window.scrollY;

    if (scrollY > 50) {
      nav.style.borderBottomColor = 'var(--nav-border)';
    } else {
      nav.style.borderBottomColor = 'transparent';
    }

    lastScroll = scrollY;
  }, { passive: true });

  // ---- Smooth Anchor Scroll ----
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener('click', (e) => {
      const id = anchor.getAttribute('href');
      if (id === '#') return;
      const target = document.querySelector(id);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

})();
