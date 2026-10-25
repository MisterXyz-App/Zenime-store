// Edge Function: dayy-create-invoice  (deploy di Supabase VPS Zenime)
//
// Versi "QRIS Dayy" dari aulaa-create-invoice. Logic klaim SAMA PERSIS
// (RPC create_premium_claim / create_coin_claim, tabel premium_claims /
// coin_claims) -- cuma panggilan gateway diganti ke paygate pribadi.
//
//   Request body : { "zenime_code": "ZN-XXXXXX", "package_id": "<id>",
//                    "product_type"?: "premium" | "coin" }
//   Response 200 : sama dengan aulaa-create-invoice (reference_id, amount,
//                  qr_image, ... + coin_amount untuk coin)
//
// Env vars (taruh di .env VPS):
//   PAYGATE_URL        https://mafnnqttvkdgqqxczqyt.supabase.co/functions/v1/paygate
//   PAYGATE_API_KEY    = PAYGATE_API_KEY di project paygate
//   DAYY_CALLBACK_URL  https://<domain-store>/webhooks/dayy
//
// Catatan:
// - ref paygate = claim.merchant_ref (unik, prefix ZNM-/ZNC-), jadi webhook
//   Flask bisa langsung manggil mark_premium_claim_paid / mark_coin_claim_paid.
// - Paygate nambah kode unik ke nominal (mis. 15000 -> 15137). Kolom amount
//   klaim di-update ke nominal akhir supaya halaman /pembayaran nampilin
//   angka yang harus dibayar. QR-nya sendiri sudah mengunci nominal itu.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import QRCode from "https://esm.sh/qrcode@1.5.4";

const PAYGATE_URL = (Deno.env.get("PAYGATE_URL") ?? "").replace(/\/+$/, "");
const PAYGATE_API_KEY = Deno.env.get("PAYGATE_API_KEY") ?? "";
const DAYY_CALLBACK_URL = Deno.env.get("DAYY_CALLBACK_URL") ?? "";

const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
  };
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders(), "Content-Type": "application/json" },
  });
}

function minutesUntil(iso: string | null | undefined): number {
  if (!iso) return 15;
  const mins = Math.floor((new Date(iso).getTime() - Date.now()) / 60_000);
  if (!Number.isFinite(mins)) return 15;
  return Math.min(120, Math.max(1, mins));
}

// deno-lint-ignore no-explicit-any
async function createPaygateTx(claim: any, productType: string) {
  const res = await fetch(`${PAYGATE_URL}/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-api-key": PAYGATE_API_KEY },
    body: JSON.stringify({
      amount: Number(claim.amount),
      ref: claim.merchant_ref,
      expire_minutes: minutesUntil(claim.expires_at),
      callback_url: DAYY_CALLBACK_URL || undefined,
      metadata: { claim_id: claim.claim_id, product_type: productType, source: "zenime-store" },
    }),
    signal: AbortSignal.timeout(10_000),
  });
  let data: Record<string, unknown> = {};
  try {
    data = await res.json();
  } catch { /* biarin kosong */ }
  return { ok: res.ok, status: res.status, data };
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders() });

  try {
    if (!PAYGATE_URL || !PAYGATE_API_KEY) {
      return json({ error_code: "upstream_error", message: "PAYGATE_URL / PAYGATE_API_KEY belum diisi" }, 500);
    }

    const body = await req.json();
    const zenimeCode = String(body.zenime_code ?? "").trim().toUpperCase();
    const packageId = String(body.package_id ?? "").trim();
    const productType = String(body.product_type ?? "premium").trim().toLowerCase();
    const isCoin = productType === "coin";

    if (!zenimeCode || !packageId) {
      return json({ error_code: "invalid_request", message: "zenime_code dan package_id wajib diisi" }, 400);
    }

    const { data: claimRows, error: claimError } = isCoin
      ? await supabase.rpc("create_coin_claim", { p_zenime_code: zenimeCode, p_package_id: packageId })
      : await supabase.rpc("create_premium_claim", { p_zenime_code: zenimeCode, p_package_id: packageId });

    if (claimError) {
      const msg = claimError.message ?? "";
      if (msg.includes("ACCOUNT_NOT_FOUND")) {
        return json({ error_code: "account_not_found", message: "Kode Zenime tidak ditemukan" }, 404);
      }
      if (msg.includes("INVALID_PACKAGE")) {
        return json({ error_code: "invalid_package", message: "Paket tidak ditemukan atau tidak aktif" }, 400);
      }
      return json({ error_code: "upstream_error", message: msg }, 400);
    }

    const claim = claimRows[0];
    const table = isCoin ? "coin_claims" : "premium_claims";

    const pg = await createPaygateTx(claim, isCoin ? "coin" : "premium");
    const tx = pg.data as Record<string, unknown>;
    if (!pg.ok || !tx?.qris_string) {
      await supabase.from(table).update({ status: "failed" }).eq("id", claim.claim_id);
      return json({
        error_code: "upstream_error",
        message: String(tx?.error ?? "Gagal membuat tagihan QRIS Dayy"),
      }, 502);
    }

    const finalAmount = Number(tx.final_amount ?? claim.amount);
    let qrImage: string | null = null;
    try {
      qrImage = await QRCode.toDataURL(String(tx.qris_string), { width: 400, margin: 1 });
    } catch (err) {
      console.error("Gagal generate QR image:", err);
    }

    // Simpan QR + id tagihan paygate. Coba sekalian update amount ke nominal
    // akhir; kalau kolom/aturan amount menolak, simpan tanpa amount.
    const base = { qr: qrImage, trx_id: String(tx.id) };
    const upd = await supabase.from(table).update({ ...base, amount: finalAmount }).eq("id", claim.claim_id);
    if (upd.error) {
      console.error("Update amount klaim gagal, simpan tanpa amount:", upd.error.message);
      await supabase.from(table).update(base).eq("id", claim.claim_id);
    }

    const responseBody: Record<string, unknown> = {
      reference_id: claim.claim_id,
      amount: finalAmount,
      package_id: packageId,
      package_label: claim.package_label,
      zenime_code: zenimeCode,
      qr_image: qrImage,
      checkout_url: null,
      status: "pending",
      created_at: new Date().toISOString(),
      expires_at: claim.expires_at,
    };
    if (isCoin) responseBody.coin_amount = claim.coin_amount ?? 0;
    return json(responseBody);
  } catch (err) {
    return json({ error_code: "server_error", message: String(err) }, 500);
  }
});
