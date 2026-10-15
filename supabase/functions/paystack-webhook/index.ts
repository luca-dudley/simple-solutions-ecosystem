// ============================================================================
// Simple Solutions Ecosystem: Paystack Subscription Webhook Edge Function
// Runtime: Deno (Native Deno.serve)
// Path: supabase/functions/paystack-webhook/index.ts
// ============================================================================

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";

// Paystack Plan Code to public.billing_tier Enum Mapping
export const PLAN_TIER_MAP: Record<string, string> = {
  "PLN_rxhjg4j2icqyd8i": "bundle",               // Full Site Bundle (R2,250/mo)
  "PLN_3xf464fdsv96ezp": "standalone_vault",      // The Vault Core (R550/mo)
  "PLN_4veaygp3t3iiont": "standalone_conduit",    // Supply Conduit (R550/mo)
  "PLN_qafs5ik0lh12gan": "standalone_spray",      // Spray Trace V1 (R550/mo)
  "PLN_h3jrnmwcn5yfwri": "standalone_packhouse",  // Packhouse Pass (R550/mo)
};

/**
 * Verify Paystack HMAC SHA512 signature from request headers.
 */
async function verifyPaystackSignature(
  rawBody: string,
  signature: string | null,
  secretKey: string
): Promise<boolean> {
  if (!signature || !secretKey) return false;

  try {
    const encoder = new TextEncoder();
    const key = await crypto.subtle.importKey(
      "raw",
      encoder.encode(secretKey),
      { name: "HMAC", hash: "SHA-512" },
      false,
      ["sign", "verify"]
    );

    const signatureBuffer = await crypto.subtle.sign(
      "HMAC",
      key,
      encoder.encode(rawBody)
    );

    const hashArray = Array.from(new Uint8Array(signatureBuffer));
    const hexHash = hashArray
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");

    return hexHash.toLowerCase() === signature.trim().toLowerCase();
  } catch (err) {
    console.error("[Paystack Webhook] Signature verification error:", err);
    return false;
  }
}

Deno.serve(async (req: Request) => {
  // CORS Preflight
  if (req.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, x-paystack-signature",
      },
    });
  }

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { "Content-Type": "application/json" },
    });
  }

  const paystackSecret = Deno.env.get("PAYSTACK_SECRET_KEY") || "";
  const supabaseUrl = Deno.env.get("SUPABASE_URL") || "";
  const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";

  if (!paystackSecret) {
    console.error("[Paystack Webhook] Missing PAYSTACK_SECRET_KEY environment variable.");
    return new Response(JSON.stringify({ error: "Server configuration error" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  // 1. Signature Authentication
  const signature = req.headers.get("x-paystack-signature");
  const rawBody = await req.text();

  const isValid = await verifyPaystackSignature(rawBody, signature, paystackSecret);
  if (!isValid) {
    console.error("[Paystack Webhook] 401 Unauthorized: HMAC SHA512 signature mismatch.");
    return new Response(JSON.stringify({ error: "Invalid signature" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  // 2. Parse Webhook Event Payload
  let payload: any;
  try {
    payload = JSON.parse(rawBody);
  } catch (err) {
    console.error("[Paystack Webhook] Malformed JSON payload:", err);
    return new Response(JSON.stringify({ error: "Invalid JSON" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const eventType: string = payload.event || "";
  const eventData: any = payload.data || {};
  console.log(`[Paystack Webhook] Received authenticated event: ${eventType}`);

  const supabaseAdmin = createClient(supabaseUrl, supabaseServiceKey);

  // 3. Process Event Types
  try {
    switch (eventType) {
      case "charge.success":
      case "subscription.create": {
        // Extract customer_code, subscription_code, plan_code, and company_id
        const metadata = eventData.metadata || {};
        const customerCode =
          eventData.customer?.customer_code ||
          eventData.customer_code ||
          metadata.customer_code;
        const subscriptionCode =
          eventData.subscription_code ||
          eventData.plan?.subscription_code ||
          metadata.subscription_code;
        const planCode =
          eventData.plan?.plan_code ||
          eventData.plan_code ||
          metadata.plan_code;

        // Support direct company_id or nested custom_fields
        let companyId = metadata.company_id || metadata.companyId;
        if (!companyId && Array.isArray(metadata.custom_fields)) {
          const match = metadata.custom_fields.find(
            (f: any) => f.variable_name === "company_id" || f.variable_name === "companyId"
          );
          if (match) companyId = match.value;
        }

        // Map plan code to public.billing_tier enum
        const mappedTier = planCode ? PLAN_TIER_MAP[planCode] || null : null;

        console.log(
          `[Paystack Webhook] Ingesting ${eventType} for companyId=${companyId}, plan=${planCode} (tier=${mappedTier}), subCode=${subscriptionCode}`
        );

        if (companyId) {
          // Fetch existing company to merge billing_metadata cleanly
          const { data: company, error: fetchErr } = await supabaseAdmin
            .from("companies")
            .select("id, billing_metadata, billing_tier")
            .eq("id", companyId)
            .single();

          if (fetchErr || !company) {
            console.error(
              `[Paystack Webhook] Company not found for id=${companyId}:`,
              fetchErr?.message
            );
          } else {
            const currentMeta = company.billing_metadata || {};
            const updatedMeta = {
              ...currentMeta,
              customer_code: customerCode || currentMeta.customer_code || null,
              subscription_code: subscriptionCode || currentMeta.subscription_code || null,
              plan_code: planCode || currentMeta.plan_code || null,
              status: "active",
              last_payment_date: eventData.paid_at || new Date().toISOString(),
              updated_at: new Date().toISOString(),
            };

            const updatePayload: Record<string, any> = {
              is_active: true,
              billing_metadata: updatedMeta,
              updated_at: new Date().toISOString(),
            };

            if (mappedTier) {
              updatePayload.billing_tier = mappedTier;
            }

            const { error: updateErr } = await supabaseAdmin
              .from("companies")
              .update(updatePayload)
              .eq("id", companyId);

            if (updateErr) {
              console.error(
                `[Paystack Webhook] Failed to update company ${companyId}:`,
                updateErr.message
              );
            } else {
              console.log(
                `[Paystack Webhook] Successfully activated company ${companyId} on tier ${mappedTier || company.billing_tier}`
              );
            }
          }
        } else if (subscriptionCode) {
          // Fallback: match by existing subscription_code in billing_metadata
          const { data: companies, error: searchErr } = await supabaseAdmin
            .from("companies")
            .select("id, billing_metadata")
            .eq("billing_metadata->>subscription_code", subscriptionCode);

          if (!searchErr && companies && companies.length > 0) {
            for (const comp of companies) {
              const updatedMeta = {
                ...(comp.billing_metadata || {}),
                status: "active",
                customer_code: customerCode || comp.billing_metadata?.customer_code,
                last_payment_date: eventData.paid_at || new Date().toISOString(),
                updated_at: new Date().toISOString(),
              };

              const updateData: Record<string, any> = {
                is_active: true,
                billing_metadata: updatedMeta,
                updated_at: new Date().toISOString(),
              };
              if (mappedTier) updateData.billing_tier = mappedTier;

              await supabaseAdmin.from("companies").update(updateData).eq("id", comp.id);
            }
          }
        }
        break;
      }

      case "invoice.payment_failed":
      case "subscription.disable": {
        const subscriptionCode =
          eventData.subscription_code ||
          eventData.subscription?.subscription_code ||
          eventData.metadata?.subscription_code;

        console.log(
          `[Paystack Webhook] Processing ${eventType} for subscriptionCode=${subscriptionCode}`
        );

        if (subscriptionCode) {
          // Find company by subscription_code in billing_metadata
          const { data: companies, error: searchErr } = await supabaseAdmin
            .from("companies")
            .select("id, billing_metadata")
            .eq("billing_metadata->>subscription_code", subscriptionCode);

          if (!searchErr && companies && companies.length > 0) {
            for (const comp of companies) {
              const currentMeta = comp.billing_metadata || {};
              const targetStatus = eventType === "invoice.payment_failed" ? "past_due" : "disabled";

              const updatedMeta = {
                ...currentMeta,
                status: targetStatus,
                updated_at: new Date().toISOString(),
              };

              const { error: updateErr } = await supabaseAdmin
                .from("companies")
                .update({
                  billing_metadata: updatedMeta,
                  updated_at: new Date().toISOString(),
                })
                .eq("id", comp.id);

              if (updateErr) {
                console.error(
                  `[Paystack Webhook] Failed to set status to ${targetStatus} for company ${comp.id}:`,
                  updateErr.message
                );
              } else {
                console.log(
                  `[Paystack Webhook] Company ${comp.id} subscription status set to ${targetStatus}`
                );
              }
            }
          }
        }
        break;
      }

      default:
        console.log(`[Paystack Webhook] Unhandled event type: ${eventType} (Acknowledged)`);
        break;
    }

    return new Response(JSON.stringify({ received: true, event: eventType }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err: any) {
    console.error("[Paystack Webhook] Error processing event:", err);
    return new Response(JSON.stringify({ error: err.message || "Internal error" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
});
