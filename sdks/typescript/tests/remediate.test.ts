// remediate() flow-tesztek stubolt jobs-klienssel (nincs hálózat).
import { test } from "node:test";
import assert from "node:assert/strict";

import {
    A11yfyClient,
    JobFailedError,
    RemediationTimeoutError,
} from "../src/wrapper/A11yfyClient.js";

function makeClient(statuses: string[], resultStatus = "done") {
    const client = new A11yfyClient({ token: "ak_test_x" });
    const calls: Record<string, unknown>[] = [];
    const stub = {
        async createJob(request: Record<string, unknown>) {
            calls.push(request);
            return { job_id: "job-1", status: "pending", created_at: "2026-07-10T00:00:00Z" };
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
