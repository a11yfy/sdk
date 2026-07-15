// remediate() flow-tesztek stubolt jobs-klienssel (nincs hálózat).
import { test } from "node:test";
import assert from "node:assert/strict";

import {
    A11yfyClient,
    JobFailedError,
    RemediationTimeoutError,
} from "../src/wrapper/A11yfyClient.js";

function makeClient(statuses: string[], resultStatus = "done", createStatusCode = 202) {
    const client = new A11yfyClient({ token: "ak_test_x" });
    const calls: Record<string, unknown>[] = [];
    const stub = {
        // A generált kliens HttpResponsePromise-t ad (withRawResponse) — a
        // wrapper createJob (6-SDK-P0.2) ezen keresztül olvassa a státuszkódot.
        createJob(request: Record<string, unknown>) {
            calls.push(request);
            const data = {
                job_id: "job-1",
                status: "pending",
                created_at: "2026-07-10T00:00:00Z",
                webhook: { url: "https://example.com/hook", signing_secret: "whsec_abc123" },
            };
            const promise = Promise.resolve(data) as Promise<typeof data> & {
                withRawResponse: () => Promise<{ data: typeof data; rawResponse: { status: number } }>;
            };
            promise.withRawResponse = async () => ({
                data,
                rawResponse: { status: createStatusCode },
            });
            return promise;
        },
        async getJob(_req: { id: string }) {
            return { job_id: "job-1", status: statuses.shift() ?? "done", credits_used: null };
        },
        async getJobResult(_req: { id: string }) {
            return {
                job_id: "job-1",
                status: resultStatus,
                credits_used: 8,
                output_url: resultStatus === "done" ? "https://example.com/out.pdf" : null,
            };
        },
    };
    Object.defineProperty(client, "jobs", { value: stub });
    return { client, calls };
}

test("remediate success flow + auto idempotency key", async () => {
    const { client, calls } = makeClient(["processing", "done"]);
    const result = await client.remediate(Buffer.from("%PDF fake"), { pollIntervalMs: 1 });
    assert.equal(result.status, "done");
    assert.ok(result.output_url);
    const key = calls[0]!["Idempotency-Key"] as string;
    assert.equal(key.length, 64); // sha256 hex
});

test("remediate failed → JobFailedError", async () => {
    const { client } = makeClient(["failed"], "failed");
    await assert.rejects(
        client.remediate(Buffer.from("%PDF"), { pollIntervalMs: 1 }),
        JobFailedError,
    );
});

test("remediate timeout → RemediationTimeoutError", async () => {
    const { client } = makeClient(Array(100).fill("processing"));
    await assert.rejects(
        client.remediate(Buffer.from("%PDF"), { pollIntervalMs: 5, timeoutMs: 15 }),
        RemediationTimeoutError,
    );
});

test("explicit idempotency key wins", async () => {
    const { client, calls } = makeClient(["done"]);
    await client.remediate(Buffer.from("%PDF"), { pollIntervalMs: 1, idempotencyKey: "my-key" });
    assert.equal(calls[0]!["Idempotency-Key"], "my-key");
});

test("createJob 202 → JobAcceptedResponse a signing_secret-tel (6-SDK-P0.2)", async () => {
    const { client } = makeClient(["done"], "done", 202);
    const job = await client.createJob({ file: new Blob(["%PDF"]), "Idempotency-Key": "k" });
    assert.equal(job.job_id, "job-1");
    assert.ok("webhook" in job && job.webhook);
    assert.equal((job as { webhook: { signing_secret: string } }).webhook.signing_secret, "whsec_abc123");
});
