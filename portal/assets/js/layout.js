// Layout Component - Simple Solutions Ecosystem
// Centralized Header & Footer Renderer

function renderSharedHeader(activePage = 'ecosystem') {
  const mount = document.getElementById('site-header');
  if (!mount) return;

  const isEcosystem = activePage === 'ecosystem' || activePage === 'index';
  const isBespoke = activePage === 'bespoke';

  const ecosystemLinkClass = isEcosystem
    ? 'text-sm font-semibold text-primary transition-colors flex items-center gap-1.5'
    : 'text-sm font-semibold text-slate-600 hover:text-primary transition-colors';

  const bespokeLinkClass = isBespoke
    ? 'text-sm font-semibold text-primary transition-colors flex items-center gap-1.5'
    : 'text-sm font-semibold text-slate-600 hover:text-primary transition-colors';

  const mobileEcosystemClass = isEcosystem
    ? 'text-sm font-bold text-primary flex items-center gap-2'
    : 'text-sm font-bold text-slate-700 hover:text-primary';

  const mobileBespokeClass = isBespoke
    ? 'text-sm font-bold text-primary flex items-center gap-2'
    : 'text-sm font-bold text-slate-700 hover:text-primary';

  // Desktop CTA based on page
  const desktopCtaHtml = isEcosystem
    ? `<button onclick="openModal('loginModal')" class="bg-primary px-4 py-2 rounded-lg text-sm font-semibold text-white hover:bg-primary-light transition-all shadow-sm">Client Login</button>`
    : `<a href="https://calendar.app.google/xwA29eip7c7uDqPt6" target="_blank" rel="noopener noreferrer" class="bg-primary px-4 py-2 rounded-lg text-sm font-semibold text-white hover:bg-primary-light transition-all shadow-sm">Book Scoping Call</a>`;

  // Mobile CTA based on page
  const mobileCtaHtml = isEcosystem
    ? `<button onclick="toggleMobileMenu(); openModal('loginModal')" class="w-full rounded-lg bg-primary py-2.5 text-center text-sm font-bold text-white hover:bg-primary-light shadow-sm">Client Login</button>`
    : `<a href="https://calendar.app.google/xwA29eip7c7uDqPt6" target="_blank" rel="noopener noreferrer" class="w-full rounded-lg bg-primary py-2.5 text-center text-sm font-bold text-white hover:bg-primary-light shadow-sm">Book Scoping Call</a>`;

  mount.innerHTML = `
  <header class="fixed inset-x-0 top-0 z-50 border-b border-border/80 bg-white/90 backdrop-blur-md">
    <div class="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-6 lg:px-8">
      
      <!-- Brand Logo -->
      <a href="index.html" class="flex items-center gap-3">
        <img src="assets/logos/business/simple_bg-removed.png" alt="Simple Solutions" class="h-9 w-auto object-contain">
        <div class="hidden sm:block text-left">
          <div class="font-serif text-lg font-bold tracking-tight text-primary leading-none">Simple Solutions</div>
          <div class="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest text-slate-500 mt-1">
            <span class="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span> Modular Operating Layer
          </div>
        </div>
      </a>

      <!-- Desktop Navigation (Two Primary Links Only) -->
      <nav class="hidden md:flex items-center gap-8">
        <a href="index.html" class="${ecosystemLinkClass}">
          ${isEcosystem ? '<span class="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>' : ''} The Ecosystem
        </a>
        <a href="bespoke.html" class="${bespokeLinkClass}">
          ${isBespoke ? '<span class="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>' : ''} Bespoke Systems
        </a>
      </nav>

      <!-- Desktop CTA -->
      <div class="hidden md:flex items-center gap-3">
        ${desktopCtaHtml}
      </div>

      <!-- Mobile Menu Toggle -->
      <button onclick="toggleMobileMenu()" class="md:hidden p-2 text-slate-600 hover:text-primary focus:outline-none" aria-label="Toggle Navigation">
        <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/>
        </svg>
      </button>
    </div>

    <!-- Mobile Menu Drawer -->
    <div id="mobileMenu" class="hidden border-t border-border bg-white/95 backdrop-blur-md px-5 py-4 shadow-lg md:hidden">
      <div class="flex flex-col gap-4 text-left">
        <a href="index.html" onclick="toggleMobileMenu()" class="${mobileEcosystemClass}">
          ${isEcosystem ? '<span class="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>' : ''} The Ecosystem
        </a>
        <a href="bespoke.html" onclick="toggleMobileMenu()" class="${mobileBespokeClass}">
          ${isBespoke ? '<span class="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>' : ''} Bespoke Systems
        </a>
        <div class="border-t border-border pt-4 flex flex-col gap-3">
          ${mobileCtaHtml}
        </div>
      </div>
    </div>
  </header>`;
}

function renderSharedFooter() {
  const mount = document.getElementById('site-footer');
  if (!mount) return;

  mount.innerHTML = `
  <footer class="border-t border-slate-200/80 bg-white/70 backdrop-blur-md py-16">
    <div class="mx-auto max-w-7xl px-5 sm:px-6 lg:px-8 text-left">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-12 border-b border-border pb-12 mb-8">
        
        <!-- Col 1: Bio -->
        <div class="md:col-span-1">
          <div class="flex items-center gap-2 mb-3">
            <img src="assets/logos/business/simple_bg-removed.png" alt="Simple Solutions" class="h-7 w-auto object-contain">
            <span class="font-serif font-bold text-lg text-primary">Simple Solutions</span>
          </div>
          <p class="text-xs text-slate-500 leading-relaxed mb-4">
            Modular, offline-first operational software for commercial agriculture, packhouses, logistics, and heavy industry.
          </p>
          <p class="text-[11px] text-slate-400 font-medium">📍 Stellenbosch &amp; Durban, South Africa</p>
          <p class="text-[11px] text-slate-400 font-medium mt-1">✉️ info@simpleza.co.za</p>
        </div>

        <!-- Col 2: The Ecosystem -->
        <div>
          <h5 class="font-bold text-primary text-xs uppercase tracking-wider mb-4 font-mono">The Ecosystem</h5>
          <div class="flex flex-col gap-2.5 text-xs text-slate-600">
            <a href="index.html#ecosystem" class="hover:text-primary transition-colors">The Vault</a>
            <a href="index.html#ecosystem" class="hover:text-primary transition-colors">Spray Trace</a>
            <a href="index.html#ecosystem" class="hover:text-primary transition-colors">Supply Conduit</a>
            <a href="index.html#ecosystem" class="hover:text-primary transition-colors">Packhouse Pass</a>
          </div>
        </div>

        <!-- Col 3: Bespoke Engineering -->
        <div>
          <h5 class="font-bold text-primary text-xs uppercase tracking-wider mb-4 font-mono">Bespoke Engineering</h5>
          <div class="flex flex-col gap-2.5 text-xs text-slate-600">
            <a href="bespoke.html#capabilities" class="hover:text-primary transition-colors">Proprietary Web Apps &amp; Portals</a>
            <a href="bespoke.html#capabilities" class="hover:text-primary transition-colors">Hardware &amp; Scale Integration</a>
            <a href="bespoke.html#capabilities" class="hover:text-primary transition-colors">Workflow Automation &amp; Dashboards</a>
            <a href="bespoke.html#pricing" class="hover:text-primary transition-colors">Commercial Framework &amp; Sprints</a>
            <a href="bespoke.html#proof" class="hover:text-primary transition-colors">Client Reviews &amp; Feedback</a>
          </div>
        </div>

        <!-- Col 4: Legal -->
        <div>
          <h5 class="font-bold text-primary text-xs uppercase tracking-wider mb-4 font-mono">Legal &amp; Assurance</h5>
          <div class="flex flex-col gap-2.5 text-xs text-slate-600">
            <a href="../packages/ui/assets/legal/WEBSITE%20%26%20PORTAL%20POPIA%20PRIVACY%20POLICY.pdf" target="_blank" class="hover:text-primary transition-colors">POPIA Privacy Policy</a>
            <a href="../packages/ui/assets/legal/MASTER%20TERMS%20OF%20SERVICE%20%26%20STATUTORY%20OHSA%20LIABILITY%20WAIVER.pdf" target="_blank" class="hover:text-primary transition-colors">Terms of Service</a>
            <a href="../packages/ui/assets/legal/STATUTORY%20RISK%20ASSESSMENT%20TEMPLATE%20NOTICE%20%26%20APPOINTEE%20SCHEDULE.pdf" target="_blank" class="hover:text-primary transition-colors">Statutory Audit Disclaimer</a>
          </div>
        </div>

      </div>

      <div class="flex flex-col sm:flex-row items-center justify-between text-xs text-slate-400">
        <p>&copy; 2026 Simple Solutions. All rights reserved.</p>
        <p class="mt-2 sm:mt-0 font-mono text-[11px]">BUILT FOR FRONTLINE OPERATIONS • NOT SPREADSHEETS</p>
      </div>
    </div>
  </footer>`;
}

// Auto-initialize if containers exist and data-page attribute is present
document.addEventListener('DOMContentLoaded', () => {
  const headerMount = document.getElementById('site-header');
  if (headerMount && !headerMount.innerHTML.trim()) {
    const page = headerMount.getAttribute('data-active-page') || 'ecosystem';
    renderSharedHeader(page);
  }
  const footerMount = document.getElementById('site-footer');
  if (footerMount && !footerMount.innerHTML.trim()) {
    renderSharedFooter();
  }
});
