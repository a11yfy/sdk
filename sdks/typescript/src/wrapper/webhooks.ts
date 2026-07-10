// Hand-written overlay — NOT generated. Protected by .fernignore.
//
// Webhook signature verification (Stripe constructEvent pattern), matched to
// the a11yfy contract (API-CONTRACT.md §5.3):
//   header:  X-A11yfy-Signature: ts=<unix_seconds>;h1=<hex_hmac>
//   signed:  "{ts}:{raw_request_body}"        <-- COLON separator!
//   algo:    HMAC-SHA256, hex, constant-time compare, 300s replay window

import { createHmac, timingSafeEqual } from "node:crypto";

/** Replay-protection window in seconds (contract §5.3). */
export const DEFAULT_TOLERANCE_SECONDS = 300;

/** The webhook signature could not be verified. */
export class WebhookVerificationError extends Error {
    constructor(message: string) {
        super(message);
        this.name = "WebhookVerificationError";
    }
}

/** Verified webhook payload (terminal job notification, contract §5.2). */
export interface WebhookEvent {
    job_id: string;
    status: "done" | "failed" | "partial";
    credits_used?: number;
    output_url?: string;
    error?: string;
    completed_at?: string;
}

function parseHeader(header: string): { ts: number; h1: string } {
    let ts: string | undefined;
    let h1: string | undefined;
    for (const part of header.split(";")) {
        const idx = part.indexOf("=");
        if (idx <= 0) continue;
        const key = part.slice(0, idx).trim();
        const value = part.slice(idx + 1).trim();
        if (key === "ts") ts = value;
        else if (key === "h1") h1 = value;
    }
    if (!ts || !h1 || !/^\d+$/.test(ts)) {
        throw new WebhookVerificationError(
            "Unable to extract ts and h1 from the X-A11yfy-Signature header.",
        );
    }
    return { ts: Number(ts), h1 };
}

/**
 * Verify and parse an a11yfy webhook delivery.
 *
 * @example
 * import { Webhooks } from "@a11yfy/sdk";
 *
 * const event = Webhooks.constructEvent(
 *     rawBody,                                   // RAW string/Buffer!
 *     req.headers["x-a11yfy-signature"] as string,
 *     process.env.A11YFY_WEBHOOK_SECRET!,
 * );
 * if (event.status === "done") download(event.output_url!);
 */
export const Webhooks = {
    constructEvent(
        payload: string | Buffer,
        signatureHeader: string,
        secret: string,
        toleranceSeconds: number = DEFAULT_TOLERANCE_SECONDS,
    ): WebhookEvent {
        const raw = typeof payload === "string" ? Buffer.from(payload, "utf-8") : payload;
        const { ts, h1 } = parseHeader(signatureHeader);

        if (toleranceSeconds && Math.abs(Date.now() / 1000 - ts) > toleranceSeconds) {
            throw new WebhookVerificationError(
                `Timestamp outside the ${toleranceSeconds}s tolerance zone.`,
            );
        }

        const signedPayload = Buffer.concat([Buffer.from(`${ts}:`, "ascii"), raw]);
        const expected = createHmac("sha256", secret).update(signedPayload).digest("hex");
        const a = Buffer.from(expected, "utf-8");
        const b = Buffer.from(h1, "utf-8");
        if (a.length !== b.length || !timingSafeEqual(a, b)) {
            throw new WebhookVerificationError(
                "Signature mismatch — payload was not signed with this secret.",
            );
        }

        try {
            return JSON.parse(raw.toString("utf-8")) as WebhookEvent;
        } catch {
            throw new WebhookVerificationError("Payload is not valid JSON.");
        }
    },
};
