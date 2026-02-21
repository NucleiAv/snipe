

'use strict';

(function initCursor() {
  const dot = document.getElementById('cursorDot');
  const ring = document.getElementById('cursorRing');
  if (!dot || !ring) return;

  let mouseX = 0, mouseY = 0;
  let ringX = 0, ringY = 0;
  let rafId;

  const lerp = (a, b, t) => a + (b - a) * t;

  document.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
  });

  function animateCursor() {
    
    dot.style.transform = `translate(${mouseX - 6}px, ${mouseY - 6}px)`;

    
    ringX = lerp(ringX, mouseX, 0.12);
    ringY = lerp(ringY, mouseY, 0.12);
    ring.style.transform = `translate(${ringX - 20}px, ${ringY - 20}px)`;

    rafId = requestAnimationFrame(animateCursor);
  }

  animateCursor();

  
  const hoverTargets = 'a, button, [role="tab"], .feat-card, .api-card, .step-card, .stat-pill';

  document.addEventListener('mouseover', (e) => {
    if (e.target.closest(hoverTargets)) {
      document.body.classList.add('cursor-hover');
    }
  });

  document.addEventListener('mouseout', (e) => {
    if (e.target.closest(hoverTargets)) {
      document.body.classList.remove('cursor-hover');
    }
  });

  document.addEventListener('mouseleave', () => {
    dot.style.opacity = '0';
    ring.style.opacity = '0';
  });

  document.addEventListener('mouseenter', () => {
    dot.style.opacity = '1';
    ring.style.opacity = '1';
  });
})();

(function initParticles() {
  const canvas = document.getElementById('particleCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  const CONFIG = {
    count: Math.min(70, Math.floor(window.innerWidth / 18)),
    maxDist: 140,
    minRadius: 1,
    maxRadius: 2.2,
    speed: 0.25,
    color: '34, 211, 238',
    lineOpacity: 0.12,
    dotOpacity: 0.35,
  };

  let particles = [];
  let W = 0, H = 0;
  let rafId;

  function resize() {
    W = canvas.width = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }

  resize();
  window.addEventListener('resize', resize);

  class Particle {
    constructor() { this.reset(true); }

    reset(initial = false) {
      this.x = Math.random() * W;
      this.y = initial ? Math.random() * H : -10;
      this.vx = (Math.random() - 0.5) * CONFIG.speed;
      this.vy = (Math.random() - 0.5) * CONFIG.speed;
      this.r = CONFIG.minRadius + Math.random() * (CONFIG.maxRadius - CONFIG.minRadius);
      this.alpha = 0.15 + Math.random() * 0.5;
    }

    update() {
      this.x += this.vx;
      this.y += this.vy;

      if (this.x < 0 || this.x > W) this.vx *= -1;
      if (this.y < 0 || this.y > H) this.vy *= -1;

      
      this.x = Math.max(0, Math.min(W, this.x));
      this.y = Math.max(0, Math.min(H, this.y));
    }

    draw() {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${CONFIG.color}, ${this.alpha * CONFIG.dotOpacity})`;
      ctx.fill();
    }
  }

  
  for (let i = 0; i < CONFIG.count; i++) {
    particles.push(new Particle());
  }

  function drawLines() {
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const a = particles[i], b = particles[j];
        const dx = a.x - b.x, dy = a.y - b.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < CONFIG.maxDist) {
          const t = 1 - dist / CONFIG.maxDist;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.strokeStyle = `rgba(${CONFIG.color}, ${t * CONFIG.lineOpacity})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }
  }

  function tick() {
    ctx.clearRect(0, 0, W, H);
    particles.forEach(p => { p.update(); p.draw(); });
    drawLines();
    rafId = requestAnimationFrame(tick);
  }

  tick();

  
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      cancelAnimationFrame(rafId);
    } else {
      tick();
    }
  });
})();

(function initNav() {
  const header = document.getElementById('navHeader');
  const burger = document.getElementById('navBurger');
  const links = document.getElementById('navLinks');

  if (!header) return;

  
  let lastScroll = 0;
  window.addEventListener('scroll', () => {
    const y = window.scrollY;
    header.classList.toggle('scrolled', y > 40);
    lastScroll = y;
  }, { passive: true });

  
  if (burger && links) {
    burger.addEventListener('click', () => {
      const expanded = burger.getAttribute('aria-expanded') === 'true';
      burger.setAttribute('aria-expanded', String(!expanded));
      links.classList.toggle('open', !expanded);
    });

    
    links.querySelectorAll('.nav-link').forEach(link => {
      link.addEventListener('click', () => {
        links.classList.remove('open');
        burger.setAttribute('aria-expanded', 'false');
      });
    });

    
    document.addEventListener('click', (e) => {
      if (!header.contains(e.target)) {
        links.classList.remove('open');
        burger.setAttribute('aria-expanded', 'false');
      }
    });
  }
})();

(function initScrollAnimations() {
  const elements = document.querySelectorAll('[data-animate]');
  if (!elements.length) return;

  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if (prefersReduced) {
    elements.forEach(el => el.classList.add('visible'));
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const delay = parseInt(entry.target.dataset.delay || '0', 10);
        setTimeout(() => {
          entry.target.classList.add('visible');
        }, delay);
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.12,
    rootMargin: '0px 0px -40px 0px',
  });

  elements.forEach(el => observer.observe(el));
})();

(function initTabs() {
  const tabs = document.querySelectorAll('.qs-tab');
  const panels = document.querySelectorAll('.qs-panel');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;

      tabs.forEach(t => {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
      });

      panels.forEach(p => {
        p.classList.remove('active');
        p.hidden = true;
      });

      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');

      const panel = document.getElementById(`tab-${target}`);
      if (panel) {
        panel.classList.add('active');
        panel.hidden = false;
      }
    });
  });
})();

(function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      const href = this.getAttribute('href');
      if (href === '#') return;

      const target = document.querySelector(href);
      if (!target) return;

      e.preventDefault();

      const offset = 80; 
      const top = target.getBoundingClientRect().top + window.scrollY - offset;

      window.scrollTo({ top, behavior: 'smooth' });
    });
  });
})();

(function initHeroVideo() {
  const video = document.getElementById('heroLogoAnim');
  const track = document.querySelector('.hero-splash-track');
  const hint = document.querySelector('.hero-scroll-hint');

  
  if (video) {
    video.play().catch(() => { }); 
  }

  
  let ticking = false;
  window.addEventListener('scroll', () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      ticking = false;
      const trackH = track ? track.offsetHeight - window.innerHeight : window.innerHeight;
      const progress = Math.min(1, Math.max(0, window.scrollY / trackH));

      if (hint) hint.classList.toggle('hidden', progress > 0.10);

      
      const splash = document.querySelector('.hero-splash');
      if (splash) {
        const fadeStart = 0.70;
        const opacity = progress < fadeStart
          ? 1
          : 1 - ((progress - fadeStart) / (1 - fadeStart));
        splash.style.opacity = opacity.toFixed(3);
      }
    });
  }, { passive: true });

  
  const content = document.getElementById('heroContent');
  if (content) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      content.classList.add('in-view');
    } else {
      const io = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            content.classList.add('in-view');
            io.unobserve(content);
          }
        });
      }, { threshold: 0.08 });
      io.observe(content);
    }
  }
})();

(function initTerminalReplay() {
  const terminal = document.querySelector('.terminal-window');
  if (!terminal || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  let played = false;

  const io = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting && !played) {
        played = true;
        
        
      }
    });
  }, { threshold: 0.5 });

  io.observe(terminal);
})();

(function initParallax() {
  
  
  
  
  
})();
