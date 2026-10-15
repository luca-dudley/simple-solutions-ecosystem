// ============================================================================
// Simple Solutions Ecosystem: Client-Side Paystack Billing Integration
// Architecture: Zero-build pure ES6 Module
// Path: packages/ui/assets/js/paystack-billing.js
// ============================================================================

/**
 * Authoritative Paystack Plan Code Registry
 * Mapped to public.billing_tier enum in PostgreSQL
 */
export const PAYSTACK_PLANS = Object.freeze({
  BUNDLE: "PLN_rxhjg4j2icqyd8i",               // Full Site Bundle (R2,250/mo)
  STANDALONE_VAULT: "PLN_3xf464fdsv96ezp",      // The Vault Core (R550/mo)
  STANDALONE_CONDUIT: "PLN_4veaygp3t3iiont",    // Supply Conduit (R550/mo)
  STANDALONE_SPRAY: "PLN_qafs5ik0lh12gan",      // Spray Trace V1 (R550/mo)
  STANDALONE_PACKHOUSE: "PLN_h3jrnmwcn5yfwri",  // Packhouse Pass (R550/mo)
});

let paystackScriptPromise = null;

/**
 * Dynamically loads Paystack inline JS (v1) if not already present in the DOM.
 * Returns a Promise resolving to the window.PaystackPop constructor.
 */
export function loadPaystackScript() {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Paystack inline JS can only be loaded in a browser environment."));
  }

  if (window.PaystackPop) {
    return Promise.resolve(window.PaystackPop);
  }

  if (paystackScriptPromise) {
    return paystackScriptPromise;
  }

  paystackScriptPromise = new Promise((resolve, reject) => {
    const existingScript = document.querySelector('script[src="https://js.paystack.co/v1/inline.js"]');
    if (existingScript) {
      if (window.PaystackPop) {
        return resolve(window.PaystackPop);
      }
      existingScript.addEventListener("load", () => resolve(window.PaystackPop));
      existingScript.addEventListener("error", () => reject(new Error("Failed to load Paystack inline JS")));
      return;
    }

    const script = document.createElement("script");
    script.src = "https://js.paystack.co/v1/inline.js";
    script.async = true;
    script.onload = () => {
      if (window.PaystackPop) {
        resolve(window.PaystackPop);
      } else {
        reject(new Error("PaystackPop script loaded but global object was not found."));
      }
    };
    script.onerror = () => reject(new Error("Network error loading https://js.paystack.co/v1/inline.js"));
    document.head.appendChild(script);
  });

  return paystackScriptPromise;
}

/**
 * Triggers Paystack modal checkout for a specific subscription plan.
 * 
 * @param {Object} options
 * @param {string} options.planCode - Target Paystack plan code (e.g. from PAYSTACK_PLANS)
 * @param {string} options.companyId - Tenant UUID in public.companies
 * @param {string} options.userEmail - Authenticated user / billing contact email
 * @param {string} [options.publicKey] - Optional Paystack public key override (defaults to window.PAYSTACK_PUBLIC_KEY)
 * @param {Function} [options.onSuccess] - Callback when subscription transaction completes successfully
 * @param {Function} [options.onClose] - Callback when user dismisses the payment modal
 * @param {Object} [options.customMetadata] - Additional metadata parameters
 */
export async function initializePlanCheckout({
  planCode,
  companyId,
  userEmail,
  publicKey,
  onSuccess,
  onClose,
  customMetadata = {},
}) {
  const resolvedKey =
    publicKey ||
    (typeof window !== "undefined" && window.PAYSTACK_PUBLIC_KEY) ||
    (typeof window !== "undefined" && window.__ENV__?.PAYSTACK_PUBLIC_KEY);

  if (!resolvedKey) {
    throw new Error(
      "[Paystack Billing] Missing public key. Pass 'publicKey' or set 'window.PAYSTACK_PUBLIC_KEY'."
    );
  }

  if (!userEmail) {
    throw new Error("[Paystack Billing] User email is required to initialize subscription checkout.");
  }

  if (!planCode) {
    throw new Error("[Paystack Billing] Plan code is required. Choose from PAYSTACK_PLANS.");
  }

  // Ensure Paystack library is ready
  await loadPaystackScript();

  const setupConfig = {
    key: resolvedKey,
    email: userEmail,
    plan: planCode,
    currency: "ZAR",
    metadata: {
      company_id: companyId,
      ...customMetadata,
    },
    callback: function (response) {
      console.log("[Paystack Billing] Payment successful:", response);
      if (typeof onSuccess === "function") {
        onSuccess(response);
      }
    },
    onClose: function () {
      console.log("[Paystack Billing] Checkout modal dismissed by user.");
      if (typeof onClose === "function") {
        onClose();
      }
    },
  };

  if (customMetadata?.owner_name) {
    setupConfig.firstname = customMetadata.owner_name;
  }
  if (customMetadata?.phone) {
    setupConfig.phone = customMetadata.phone;
  }

  const handler = window.PaystackPop.setup(setupConfig);

  handler.openIframe();
  return handler;
}
