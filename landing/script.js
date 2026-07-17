/* ============================================
   whaagent Landing — Scripts
   Scroll animations, parallax, header effects
   ============================================ */

(function () {
  'use strict';

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
          header.style.borderBottomColor = 'var(--border)';
          header.style.background = 'rgba(250,250,250,0.92)';
        } else {
          header.style.borderBottomColor = 'rgba(228,228,231,0.3)';
          header.style.background = 'rgba(250,250,250,0.8)';
        }
        lastScroll = scrollY;
      },
      { passive: true }
    );

    // Dark mode header
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      window.addEventListener(
        'scroll',
        () => {
          const scrollY = window.scrollY;
          if (scrollY > 20) {
            header.style.background = 'rgba(9,9,11,0.92)';
          } else {
            header.style.background = 'rgba(9,9,11,0.8)';
          }
        },
        { passive: true }
      );
    }
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
