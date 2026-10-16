// ============================================================================
// Simple Solutions Ecosystem: Initialize Paystack Checkout Edge Function
// Runtime: Deno (Native Deno.serve)
// Path: supabase/functions/initialize-checkout/index.ts
// ============================================================================

export const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

interface InitializeCheckoutPayload {
  plan_code?: string;
  company_name?: string;
  full_name?: string;
  email?: string;
  phone?: string;
  vat_number?: string;
  callback_url?: string;
}

Deno.serve(async (req: Request) => {
  // 1. CORS Preflight
  if (req.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: corsHeaders,
    });
  }

  // 2. Validate HTTP Method
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed. Use POST." }), {
      status: 405,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  // 3. Environment Verification
  const paystackSecret = Deno.env.get("PAYSTACK_SECRET_KEY") || "";
  if (!paystackSecret) {
    console.error("[Initialize Checkout] Missing PAYSTACK_SECRET_KEY environment variable.");
    return new Response(
      JSON.stringify({ error: "Server configuration error: payment provider key missing." }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }

  // 4. Parse Request Body
  let payload: InitializeCheckoutPayload;
  try {
    payload = await req.json();
  } catch (err) {
    console.error("[Initialize Checkout] Malformed JSON payload:", err);
    return new Response(JSON.stringify({ error: "Invalid JSON payload." }), {
      status: 400,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const {
    plan_code,
    company_name,
    full_name,
    email,
    phone,
    vat_number,
    callback_url,
  } = payload;

  // 5. Request Validation
  const trimmedEmail = (email || "").trim();
  const trimmedCompanyName = (company_name || "").trim();
  const trimmedPlanCode = (plan_code || "").trim();
  const trimmedFullName = (full_name || "").trim();
  const trimmedPhone = (phone || "").trim();
  const trimmedVat = (vat_number || "").trim();

  if (!trimmedEmail) {
    return new Response(
      JSON.stringify({ error: "Validation error: 'email' is required." }),
      {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }

  if (!trimmedCompanyName) {
    return new Response(
      JSON.stringify({ error: "Validation error: 'company_name' is required." }),
      {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }

  if (!trimmedPlanCode) {
    return new Response(
      JSON.stringify({ error: "Validation error: 'plan_code' is required." }),
      {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }

  // 6. Assemble Paystack Transaction Initialize Request
  // Default callback URL fallback per spec
  const resolvedCallbackUrl =
    (callback_url && callback_url.trim()) ||
    "https://portal.simplesolutions.co.za/welcome.html";

  const paystackPayload = {
    email: trimmedEmail,
    plan: trimmedPlanCode,
    callback_url: resolvedCallbackUrl,
    metadata: {
      company_name: trimmedCompanyName,
      full_name: trimmedFullName || trimmedCompanyName,
      phone: trimmedPhone || null,
      vat_number: trimmedVat || null,
      plan_code: trimmedPlanCode,
      custom_fields: [
        {
          display_name: "Estate / Company",
          variable_name: "company_name",
          value: trimmedCompanyName,
        },
        {
          display_name: "Operational Lead",
          variable_name: "full_name",
          value: trimmedFullName || "N/A",
        },
        {
          display_name: "Contact Phone",
          variable_name: "phone",
          value: trimmedPhone || "N/A",
        },
        {
          display_name: "VAT Number",
          variable_name: "vat_number",
          value: trimmedVat || "N/A",
        },
        {
          display_name: "Plan Code",
          variable_name: "plan_code",
          value: trimmedPlanCode,
        },
      ],
    },
  };

  console.log(
    `[Initialize Checkout] Initiating Paystack checkout for ${trimmedEmail} (Company: ${trimmedCompanyName}, Plan: ${trimmedPlanCode})`
  );

  // 7. Invoke Paystack API
  try {
    const paystackResponse = await fetch("https://api.paystack.co/transaction/initialize", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${paystackSecret}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(paystackPayload),
    });

    const paystackData = await paystackResponse.json();

    if (!paystackResponse.ok || !paystackData.status) {
      console.error("[Initialize Checkout] Paystack API error:", paystackData);
      return new Response(
        JSON.stringify({
          error:
            paystackData.message ||
            "Payment gateway rejected checkout initialization.",
        }),
        {
          status: paystackResponse.status >= 400 && paystackResponse.status < 500 ? paystackResponse.status : 502,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    const authorizationUrl = paystackData.data?.authorization_url;
    if (!authorizationUrl) {
      console.error("[Initialize Checkout] Paystack returned no authorization_url:", paystackData);
      return new Response(
        JSON.stringify({ error: "Payment gateway response did not include a valid authorization URL." }),
        {
          status: 502,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    console.log(`[Initialize Checkout] Successfully created checkout authorization URL: ${authorizationUrl}`);

    return new Response(
      JSON.stringify({
        authorization_url: authorizationUrl,
      }),
      {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  } catch (err: any) {
    console.error("[Initialize Checkout] Network or runtime exception:", err);
    return new Response(
      JSON.stringify({ error: err.message || "Failed to communicate with payment gateway." }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});
