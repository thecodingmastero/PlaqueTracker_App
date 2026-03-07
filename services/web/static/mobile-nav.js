(function () {
  function initMobileNav() {
    const navbars = document.querySelectorAll('.navbar.navbar-expand-lg');
    navbars.forEach((navbar, index) => {
      const container = navbar.querySelector('.container-fluid, .container');
      const collapse = navbar.querySelector('.collapse.navbar-collapse');
      if (!container || !collapse) return;

      if (!collapse.id) {
        collapse.id = `navbarMenu${index + 1}`;
      }

      let toggler = navbar.querySelector('.navbar-toggler');
      if (!toggler) {
        toggler = document.createElement('button');
        toggler.className = 'navbar-toggler';
        toggler.type = 'button';
        toggler.setAttribute('aria-label', 'Toggle navigation');
        const icon = document.createElement('span');
        icon.className = 'navbar-toggler-icon';
        toggler.appendChild(icon);

        const brand = container.querySelector('.navbar-brand');
        if (brand && brand.nextSibling) {
          container.insertBefore(toggler, brand.nextSibling);
        } else {
          container.insertBefore(toggler, collapse);
        }
      }

      toggler.setAttribute('aria-controls', collapse.id);
      toggler.setAttribute('aria-expanded', 'false');

      toggler.addEventListener('click', () => {
        const isOpen = collapse.classList.toggle('show');
        toggler.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      });

      collapse.querySelectorAll('a.nav-link').forEach((link) => {
        link.addEventListener('click', () => {
          if (window.innerWidth < 992) {
            collapse.classList.remove('show');
            toggler.setAttribute('aria-expanded', 'false');
          }
        });
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMobileNav);
  } else {
    initMobileNav();
  }
})();
