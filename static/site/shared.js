/* ═══════════════════════════════════════════
   SentYacht — Shared JavaScript
   ═══════════════════════════════════════════ */

/* ─── Scroll Reveal ─── */
function initReveal() {
  const els = document.querySelectorAll('.reveal');
  if (!els.length) return;
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const delay = parseInt(entry.target.dataset.delay || '0');
        setTimeout(() => entry.target.classList.add('visible'), delay);
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
  els.forEach(el => observer.observe(el));
}

/* ─── Navbar Scroll ─── */
function initNavbar() {
  const nav = document.getElementById('navbar');
  if (!nav) return;
  let ticking = false;
  window.addEventListener('scroll', () => {
    if (!ticking) {
      requestAnimationFrame(() => {
        if (window.scrollY > 60) {
          nav.classList.remove('nav-transparent');
          nav.classList.add('nav-solid');
        } else {
          nav.classList.remove('nav-solid');
          nav.classList.add('nav-transparent');
        }
        ticking = false;
      });
      ticking = true;
    }
  }, { passive: true });
}

/* ─── Mobile Menu ─── */
function initMobileMenu() {
  const btn = document.getElementById('mobile-menu-btn');
  const menu = document.getElementById('mobile-menu');
  if (!btn || !menu) return;

  btn.addEventListener('click', () => {
    const isOpen = menu.classList.contains('open');
    menu.classList.toggle('open');
    btn.classList.toggle('hamburger-active');
    document.body.style.overflow = isOpen ? '' : 'hidden';
    btn.setAttribute('aria-expanded', !isOpen);
  });

  menu.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      menu.classList.remove('open');
      btn.classList.remove('hamburger-active');
      document.body.style.overflow = '';
      btn.setAttribute('aria-expanded', 'false');
    });
  });
}

/* ─── Cookie Consent ─── */
function initCookies() {
  const banner = document.getElementById('cookie-banner');
  if (!banner || localStorage.getItem('sy-cookies')) return;

  setTimeout(() => banner.classList.add('visible'), 1500);

  document.getElementById('cookie-accept')?.addEventListener('click', () => {
    localStorage.setItem('sy-cookies', 'accepted');
    banner.classList.remove('visible');
  });
  document.getElementById('cookie-reject')?.addEventListener('click', () => {
    localStorage.setItem('sy-cookies', 'rejected');
    banner.classList.remove('visible');
  });
}

/* ─── Language Switcher ─── */
function initLangSwitch() {
  const switcher = document.getElementById('lang-switch');
  if (!switcher) return;
  switcher.addEventListener('click', (e) => {
    e.preventDefault();
    const target = switcher.getAttribute('href');
    if (target) window.location.href = target;
  });
}

/* ─── Init All ─── */
document.addEventListener('DOMContentLoaded', () => {
  initReveal();
  initNavbar();
  initMobileMenu();
  initCookies();
  initLangSwitch();
});
