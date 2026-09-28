// Portal Core Scripts - Simple Solutions Ecosystem
// Zero-build vanilla JS for modals, tabs, carousels, and mobile navigation

function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) {
    modal.classList.remove('hidden');
    document.body.classList.add('overflow-hidden');
    if (id === 'videoModal') {
      const iframe = document.getElementById('videoIframe');
      if (iframe && iframe.getAttribute('data-src')) {
        iframe.src = iframe.getAttribute('data-src');
      }
    }
  }
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) {
    modal.classList.add('hidden');
    document.body.classList.remove('overflow-hidden');
    if (id === 'videoModal') {
      const iframe = document.getElementById('videoIframe');
      if (iframe) {
        iframe.src = '';
      }
    }
  }
}

function switchTab(tabId) {
  const tabs = ['vault', 'spray', 'fleet', 'packhouse'];
  tabs.forEach(t => {
    const btn = document.getElementById(`btn-${t}`);
    const content = document.getElementById(`tab-${t}`);
    if (!btn || !content) return;
    
    if (t === tabId) {
      btn.className = 'tab-active flex items-center gap-2.5 px-5 py-3 rounded-xl text-sm transition-all border shadow-sm';
      content.classList.remove('hidden');
      content.classList.add('block');
    } else {
      btn.className = 'tab-inactive flex items-center gap-2.5 px-5 py-3 rounded-xl text-sm transition-all border';
      content.classList.add('hidden');
      content.classList.remove('block');
    }
  });
}

function scrollCarousel(id, amount) {
  const carousel = document.getElementById(id);
  if (carousel) {
    carousel.scrollBy({ left: amount, behavior: 'smooth' });
  }
}

function toggleMobileMenu() {
  const menu = document.getElementById('mobileMenu');
  if (menu) {
    menu.classList.toggle('hidden');
  }
}

// Global Escape listener for modals
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    ['videoModal', 'loginModal', 'checkoutModal'].forEach(id => closeModal(id));
  }
});
