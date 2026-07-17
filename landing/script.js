/* ============================================
   whaagent Landing — Scripts
   Theme toggle, auto-switch, scroll animations
   ============================================ */

(function () {
  'use strict';

  // --- Theme System ---
  const html = document.documentElement;
  const themeToggle = document.getElementById('theme-toggle');

  // Set initial dark theme
  html.setAttribute('data-theme', 'dark');

  // Theme toggle handler
  if (themeToggle) {
    themeToggle.addEventListener('click', function () {
      const current = html.getAttribute('data-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      html.setAttribute('data-theme', next);
      localStorage.setItem('whaagent-theme', next);
    });
  }

  // Auto-switch from dark to light after 3 seconds
  setTimeout(function () {
    const savedTheme = localStorage.getItem('whaagent-theme');
    if (!savedTheme) {
      html.setAttribute('data-theme', 'light');
    }
  }, 3000);

  // --- Scroll Reveal ---
  const revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
        }
      });
    },
    { threshold: 0.08, rootMargin: '0px 0px -60px 0px' }
  );

  document.querySelectorAll('.reveal, .reveal-left, .reveal-right, .reveal-scale').forEach((el) => {
    revealObserver.observe(el);
  });

  // --- Header Scroll Effect ---
  const header = document.getElementById('header');
  if (header) {
    let lastScroll = 0;
    window.addEventListener(
      'scroll',
      () => {
        const scrollY = window.scrollY;
        if (scrollY > 20) {
          header.style.borderBottomColor = 'var(--nav-border)';
          header.style.background = 'var(--nav-bg)';
        } else {
          header.style.borderBottomColor = 'transparent';
          header.style.background = 'var(--nav-bg)';
        }
        lastScroll = scrollY;
      },
      { passive: true }
    );
  }

  // --- Hero Parallax ---
  const heroContent = document.querySelector('.hero-content');
  if (heroContent) {
    window.addEventListener(
      'scroll',
      () => {
        const scrollY = window.scrollY;
        if (scrollY < 600) {
          heroContent.style.transform = `translateY(${scrollY * 0.08}px)`;
          heroContent.style.opacity = 1 - scrollY / 500;
        }
      },
      { passive: true }
    );
  }

  // --- Blob Parallax on Mouse Move ---
  const blobs = document.querySelectorAll('.blob');
  if (blobs.length > 0) {
    let mouseX = 0;
    let mouseY = 0;
    let currentX = 0;
    let currentY = 0;

    document.addEventListener(
      'mousemove',
      (e) => {
        mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
        mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
      },
      { passive: true }
    );

    function animateBlobs() {
      currentX += (mouseX - currentX) * 0.02;
      currentY += (mouseY - currentY) * 0.02;

      blobs.forEach((blob, i) => {
        const factor = (i + 1) * 8;
        blob.style.transform = `translate(${currentX * factor}px, ${currentY * factor}px)`;
      });

      requestAnimationFrame(animateBlobs);
    }

    animateBlobs();
  }

  // --- Smooth Scroll for Anchor Links ---
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener('click', function (e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // --- Counter Animation for Stats ---
  const statNumbers = document.querySelectorAll('.stat-card .text-3xl');
  const counterObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const el = entry.target;
          const text = el.textContent;
          const num = parseInt(text);
          if (!isNaN(num) && num > 0 && num < 100) {
            let current = 0;
            const duration = 1200;
            const step = num / (duration / 16);
            function count() {
              current += step;
              if (current >= num) {
                el.textContent = text;
                return;
              }
              el.textContent = Math.floor(current);
              requestAnimationFrame(count);
            }
            count();
          }
          counterObserver.unobserve(el);
        }
      });
    },
    { threshold: 0.5 }
  );

  statNumbers.forEach((el) => counterObserver.observe(el));
})();
