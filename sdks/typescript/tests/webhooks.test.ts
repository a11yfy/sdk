// Webhook-verify tesztek — a contract (§5.3) sémája ellen.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";

import { Webhooks, WebhookVerificationError } from "../src/wrapper/webhooks.js";

const SECRET = "whsec_test_secret";

function sign(payload: string, ts: number, secret: string = SECRET): string {
    const h1 = createHmac("sha256", secret).update(`${ts}:${payload}`).digest("hex");
    return `ts=${ts};h1=${h1}`;
}

const payload = JSON.stringify({
    job_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    status: "done",
    credits_used: 12,
    output_url: "https://example.com/out.pdf",
    completed_at: "2026-07-10T10:31:00.000Z",
});

test("valid signature roundtrip", () => {
    const ts = Math.floor(Date.now() / 1000);
    const event = Webhooks.constructEvent(payload, sign(payload, ts), SECRET);
    assert.equal(event.status, "done");
    assert.equal(event.credits_used, 12);
});

test("Buffer payload accepted", () => {
    const ts = Math.floor(Date.now() / 1000);
    const event = Webhooks.constructEvent(Buffer.from(payload), sign(payload, ts), SECRET);
    assert.equal(event.job_id, "a1b2c3d4-e5f6-7890-abcd-ef1234567890");
});

test("tampered payload rejected", () => {
    const ts = Math.floor(Date.now() / 1000);
    const header = sign(payload, ts);
    const tampered = payload.replace('"credits_used":12', '"credits_used":0');
    assert.throws(
        () => Webhooks.constructEvent(tampered, header, SECRET),
        WebhookVerificationError,
    );
});

test("wrong secret rejected", () => {
    const ts = Math.floor(Date.now() / 1000);
    assert.throws(
        () => Webhooks.constructEvent(payload, sign(payload, ts), "wrong"),
        WebhookVerificationError,
    );
});

test("expired timestamp rejected", () => {
    const ts = Math.floor(Date.now() / 1000) - 301;
    assert.throws(
        () => Webhooks.constructEvent(payload, sign(payload, ts), SECRET),
        /tolerance/,
    );
});

test("malformed header rejected", () => {
    assert.throws(() => Webhooks.constructEvent(payload, "nonsense", SECRET), /ts and h1/);
});
