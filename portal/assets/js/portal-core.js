// ============================================================================
// Portal Core Scripts - Simple Solutions Ecosystem
// Zero-build vanilla ES6 module for modals, tabs, carousels, mobile navigation,
// and Paystack Estate Registration & Payment Gateway orchestration.
// Path: portal/assets/js/portal-core.js
// ============================================================================

const SUPABASE_URL =
  (typeof window !== 'undefined' && window.SUPABASE_URL) ||
  'https://jlwjqdeffpmabrbwozji.supabase.co';

const CHECKOUT_FUNCTION_URL =
  (typeof window !== 'undefined' && window.CHECKOUT_FUNCTION_URL) ||
  `${SUPABASE_URL}/functions/v1/initialize-checkout`;

/**
 * Plan Details Registry (Canonical UI Names & Monthly Prices)
 */
export const PLAN_DETAILS = Object.freeze({
  'PLN_rxhjg4j2icqyd8i': { name: 'Full Ecosystem Bundle', price: 'R1,750 / mo' },
  'PLN_3xf464fdsv96ezp': { name: 'The Vault', price: 'R550 / mo' },
  'PLN_4veaygp3t3iiont': { name: 'Supply Conduit', price: 'R550 / mo' },
  'PLN_qafs5ik0lh12gan': { name: 'Spray Trace', price: 'R550 / mo' },
  'PLN_h3jrnmwcn5yfwri': { name: 'Packhouse Pass', price: 'R550 / mo' },
});

export function showModalError(message) {
  const errorBox = document.getElementById('onboardingErrorNotice');
  const errorText = document.getElementById('onboardingErrorMessage');
  if (errorBox && errorText) {
    errorText.textContent = message;
    errorBox.classList.remove('hidden');
  } else {
    alert(message);
  }
}

export function clearModalError() {
  const errorBox = document.getElementById('onboardingErrorNotice');
  if (errorBox) {
    errorBox.classList.add('hidden');
  }
}

export function openModal(id) {
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

export function closeModal(id) {
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

export function switchTab(tabId) {
  const tabs = ['vault', 'spray', 'fleet', 'packhouse'];
  tabs.forEach((t) => {
    const btn = document.getElementById(`btn-${t}`);
    const content = document.getElementById(`tab-${t}`);
    if (!btn || !content) return;

    if (t === tabId) {
      btn.className =
        'tab-active flex items-center gap-2.5 px-5 py-3 rounded-xl text-sm transition-all border shadow-sm whitespace-nowrap';
      content.classList.remove('hidden');
      content.classList.add('block');
    } else {
      btn.className =
        'tab-inactive flex items-center gap-2.5 px-5 py-3 rounded-xl text-sm transition-all border whitespace-nowrap';
      content.classList.add('hidden');
      content.classList.remove('block');
    }
  });
}

export function scrollCarousel(id, amount) {
  const carousel = document.getElementById(id);
  if (carousel) {
    carousel.scrollBy({ left: amount, behavior: 'smooth' });
  }
}

export function toggleMobileMenu() {
  const menu = document.getElementById('mobileMenu');
  if (menu) {
    menu.classList.toggle('hidden');
  }
}

// Global Escape listener for open modals
if (typeof document !== 'undefined') {
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      ['videoModal', 'loginModal', 'estateOnboardingModal'].forEach((id) =>
        closeModal(id)
      );
    }
  });
}

/**
 * Pre-populates and opens the Estate Onboarding & Payment Gateway Modal
 */
export function openEstateOnboardingModal(planCode, planName, planPrice) {
  clearModalError();
  const resolvedPlanCode = planCode || 'PLN_rxhjg4j2icqyd8i';
  const meta = PLAN_DETAILS[resolvedPlanCode] || {};
  const resolvedName = planName || meta.name || 'Selected Plan';
  const resolvedPrice = planPrice || meta.price || 'R550 / mo';

  const codeInput = document.getElementById('onboardingPlanCode');
  const nameInput = document.getElementById('onboardingPlanName');
  const priceInput = document.getElementById('onboardingPlanPrice');
  const nameText = document.getElementById('onboardingPlanNameText');
  const priceText = document.getElementById('onboardingPlanPriceText');

  if (codeInput) codeInput.value = resolvedPlanCode;
  if (nameInput) nameInput.value = resolvedName;
  if (priceInput) priceInput.value = resolvedPrice;
  if (nameText) nameText.textContent = resolvedName;
  if (priceText) priceText.textContent = resolvedPrice;

  // Restore cached details if available
  const companyInput = document.getElementById('onboardingCompanyName');
  const leadInput = document.getElementById('onboardingLeadName');
  const emailInput = document.getElementById('onboardingEmail');
  const phoneInput = document.getElementById('onboardingPhone');
  const vatInput = document.getElementById('onboardingVatNumber');

  if (companyInput && !companyInput.value) {
    companyInput.value = localStorage.getItem('ecosystem_company_name') || '';
  }
  if (leadInput && !leadInput.value) {
    leadInput.value = localStorage.getItem('ecosystem_owner_name') || '';
  }
  if (emailInput && !emailInput.value) {
    emailInput.value = localStorage.getItem('ecosystem_billing_email') || '';
  }
  if (phoneInput && !phoneInput.value) {
    phoneInput.value = localStorage.getItem('ecosystem_phone') || '';
  }
  if (vatInput && !vatInput.value) {
    vatInput.value = localStorage.getItem('ecosystem_vat') || '';
  }

  openModal('estateOnboardingModal');
}

/**
 * Celebration toast notification following verified payment
 */
export function showCelebrationToast(planName, reference) {
  let toast = document.getElementById('billingToast');
  if (toast) toast.remove();

  toast = document.createElement('div');
  toast.id = 'billingToast';
  toast.className =
    'fixed bottom-6 right-6 z-[200] max-w-sm bg-slate-950 text-white p-5 rounded-2xl shadow-2xl border border-emerald-500/40 flex items-start gap-4 transition-all duration-300 transform translate-y-4 opacity-0';
  toast.innerHTML = `
    <div class="h-10 w-10 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0 text-xl font-bold border border-emerald-500/30">
      ✓
    </div>
    <div class="flex-1 text-left">
      <div class="flex items-center gap-2">
        <h4 class="text-sm font-bold text-white">Payment Verified</h4>
        <span class="text-[9px] font-mono font-bold bg-emerald-950 text-emerald-400 px-1.5 py-0.5 rounded border border-emerald-500/30 uppercase">Active</span>
      </div>
      <p class="text-xs text-slate-300 mt-1 leading-relaxed">
        Subscription for <strong>${planName || 'Selected Plan'}</strong> is active. Ref: <span class="font-mono text-emerald-400">${reference || 'CONFIRMED'}</span>
      </p>
      <div class="mt-3 flex items-center gap-2">
        <a href="dashboard/" class="inline-flex items-center gap-1.5 bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-bold px-3 py-1.5 rounded-lg transition-colors shadow-sm">
          Access Dashboard &rarr;
        </a>
      </div>
    </div>
    <button onclick="document.getElementById('billingToast')?.remove()" class="text-slate-400 hover:text-white text-lg font-bold leading-none">&times;</button>
  `;
  document.body.appendChild(toast);

  requestAnimationFrame(() => {
    toast.classList.remove('translate-y-4', 'opacity-0');
    toast.classList.add('translate-y-0', 'opacity-100');
  });

  setTimeout(() => {
    if (toast && toast.parentNode) {
      toast.classList.add('opacity-0', 'translate-y-4');
      setTimeout(() => toast.remove(), 300);
    }
  }, 10000);
}

/**
 * Setup global listeners for [data-plan] buttons and onboarding form submission
 */
function setupOnboardingFlow() {
  // 1. Intercept all purchase buttons to open Estate Onboarding Modal
  document.addEventListener('click', (e) => {
    const planBtn = e.target.closest('[data-plan]');
    if (!planBtn) return;

    e.preventDefault();

    const planCode = planBtn.getAttribute('data-plan');
    const planName = planBtn.getAttribute('data-plan-name');
    const planPrice = planBtn.getAttribute('data-plan-price');

    openEstateOnboardingModal(planCode, planName, planPrice);
  });

  // 2. Handle Estate Onboarding Form submission
  const onboardingForm = document.getElementById('estateOnboardingForm');
  if (onboardingForm) {
    onboardingForm.addEventListener('submit', async (ev) => {
      ev.preventDefault();

      const companyName = (document.getElementById('onboardingCompanyName')?.value || '').trim();
      const leadName = (document.getElementById('onboardingLeadName')?.value || '').trim();
      const email = (document.getElementById('onboardingEmail')?.value || '').trim();
      const phone = (document.getElementById('onboardingPhone')?.value || '').trim();
      const vatNumber = (document.getElementById('onboardingVatNumber')?.value || '').trim();
      const planCode = document.getElementById('onboardingPlanCode')?.value || 'PLN_rxhjg4j2icqyd8i';
      const planName = document.getElementById('onboardingPlanName')?.value || 'Selected Plan';

      // Validation
      if (!companyName || !leadName || !email || !phone) {
        showModalError('Please complete all required fields (Estate Name, Operational Lead, Phone, and Email).');
        return;
      }

      // Persist values for smooth re-entry
      localStorage.setItem('ecosystem_company_name', companyName);
      localStorage.setItem('ecosystem_owner_name', leadName);
      localStorage.setItem('ecosystem_billing_email', email);
      localStorage.setItem('ecosystem_phone', phone);
      if (vatNumber) {
        localStorage.setItem('ecosystem_vat', vatNumber);
      }

      const submitBtn = document.getElementById('onboardingSubmitBtn');
      const originalBtnHtml = submitBtn ? submitBtn.innerHTML : '';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = `
          <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white inline-block" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span>Securing Payment Gateway...</span>
        `;
      }

      try {
        // Resolve callback URL for post-checkout landing
        const callbackUrl =
          (typeof window !== 'undefined' && window.location && window.location.origin)
            ? `${window.location.origin}/portal/welcome.html`
            : 'https://portal.simplesolutions.co.za/welcome.html';

        console.log(`[Checkout Pipeline] Dispatching checkout request to ${CHECKOUT_FUNCTION_URL}`);

        const response = await fetch(CHECKOUT_FUNCTION_URL, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            plan_code: planCode,
            company_name: companyName,
            full_name: leadName,
            email: email,
            phone: phone,
            vat_number: vatNumber || null,
            callback_url: callbackUrl,
          }),
        });

        const data = await response.json();

        if (!response.ok || !data.authorization_url) {
          throw new Error(data.error || 'Payment gateway initialization failed. Please try again.');
        }

        console.log('[Checkout Pipeline] Redirecting to Paystack gateway:', data.authorization_url);
        // Execute enterprise full-page redirect
        window.location.href = data.authorization_url;
      } catch (err) {
        console.error('[Checkout Pipeline] Gateway initialization error:', err);
        showModalError(err.message || 'Unable to connect to the payment gateway. Please check your connection and try again.');
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnHtml;
        }
      }
    });
  }
}

// Initialize when DOM is ready
if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupOnboardingFlow);
  } else {
    setupOnboardingFlow();
  }
}

// Bind methods to window for backward compatibility with inline HTML onclick handlers
if (typeof window !== 'undefined') {
  window.openModal = openModal;
  window.closeModal = closeModal;
  window.switchTab = switchTab;
  window.scrollCarousel = scrollCarousel;
  window.toggleMobileMenu = toggleMobileMenu;
  window.openEstateOnboardingModal = openEstateOnboardingModal;
  window.showCelebrationToast = showCelebrationToast;
  window.showModalError = showModalError;
  window.clearModalError = clearModalError;
}
