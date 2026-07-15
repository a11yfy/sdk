// Hand-written overlay — NOT generated. Protected by .fernignore.
//
// High-level convenience layer on top of the generated client (Replicate
// `run()` pattern): `client.remediate("doc.pdf")` uploads the file, polls the
// job until terminal state and returns the final result. The low-level
// surface stays available: client.jobs.*, client.certificates.*, client.billing.*.

import * as fs from "node:fs";
import * as path from "node:path";
import { createHash, randomUUID } from "node:crypto";

import { A11yfyClient as FernClient } from "../Client.js";
import type * as A11yfy from "../api/index.js";
import type * as core from "../core/index.js";

const TERMINAL_STATUSES = new Set(["done", "failed", "partial"]);

/** Default fixed poll interval (ms). Exponential backoff is for HTTP retries only. */
export const DEFAULT_POLL_INTERVAL_MS = 5_000;
/** Default overall wait budget (ms) for remediate(). */
export const DEFAULT_TIMEOUT_MS = 1_800_000;
/**
 * Grace window (ms) to wait for the compliance certificate after 'done'.
 * The certificate is issued moments AFTER the job flips to done (best-effort,
 * server-side ordering) — a short re-poll makes result.certificate reliable.
 */
export const DEFAULT_CERTIFICATE_WAIT_MS = 20_000;
const CERT_POLL_INTERVAL_MS = 2_000;

function certificateExpected(result: A11yfy.JobResultResponse): boolean {
    return (
        result.status === "done" &&
        result.certificate == null &&
        result.after != null &&
        result.after.issues === 0
    );
}

/** The job did not reach a terminal state within the wait budget (it keeps running server-side). */
export class RemediationTimeoutError extends Error {
    public readonly jobId: string;
    constructor(jobId: string, waitedMs: number) {
        super(
            `Job ${jobId} did not finish within ${Math.round(waitedMs / 1000)}s. ` +
                `It is still running server-side — poll jobs.getJob("${jobId}") to continue.`,
        );
        this.name = "RemediationTimeoutError";
        this.jobId = jobId;
    }
}

/** The job reached the 'failed' terminal state. */
export class JobFailedError extends Error {
    public readonly jobId: string;
    public readonly result: A11yfy.JobResultResponse;
    constructor(result: A11yfy.JobResultResponse) {
        super(`Job ${result.job_id} failed.`);
        this.name = "JobFailedError";
        this.jobId = result.job_id;
        this.result = result;
    }
}

export type FileInput = string | Buffer | core.file.Uploadable;

/**
 * A createJob VALÓDI válasz-uniója (audit 6-SDK-P0.2): a szerver 202-re
 * JobAcceptedResponse-t ad — benne az EGYSZER kiadott webhook.signing_secret —,
 * 200-ra JobAlreadyValidResponse-t. A generált `jobs.createJob` típusa minden
 * 2xx-et AlreadyValid-nek deklarál, így a signing_secret típus-szinten elveszett.
 */
export type JobCreateResponse = A11yfy.JobAcceptedResponse | A11yfy.JobAlreadyValidResponse;

export interface RemediateOptions {
    /** Callback URL for the HMAC-signed completion webhook. */
    webhookUrl?: string;
    /** Explicit Idempotency-Key (defaults to the file's SHA-256 for path/Buffer inputs). */
    idempotencyKey?: string;
    /** Fixed poll interval in ms (default 5000). */
    pollIntervalMs?: number;
    /** Overall wait budget in ms (default 1 800 000 = 30 min); null disables. */
    timeoutMs?: number | null;
    /** Grace window in ms to wait for the certificate after 'done' (default 20 000); 0 disables. */
    certificateWaitMs?: number;
}

/** Chunkolt SHA-256 fájlból — a fájl SOSEM kerül egyben memóriába (6-SDK-P0.1). */
async function sha256File(filePath: string): Promise<string> {
    const hash = createHash("sha256");
    for await (const chunk of fs.createReadStream(filePath)) {
        hash.update(chunk as Buffer);
    }
    return hash.digest("hex");
}

async function prepareFile(file: FileInput): Promise<{ upload: core.file.Uploadable; sha256?: string }> {
    if (typeof file === "string") {
        // 6-SDK-P0.1: streaming SHA + fájl-hátterű Blob (fs.openAsBlob, Node 20+)
        // — egy 300 MB-os PDF sem kerül egyben memóriába.
        const sha256 = await sha256File(file);
        const blob = await fs.openAsBlob(file, { type: "application/pdf" });
        return {
            upload: new File([blob], path.basename(file), { type: "application/pdf" }),
            sha256,
        };
    }
    if (Buffer.isBuffer(file)) {
        const sha256 = createHash("sha256").update(file).digest("hex");
        return {
            upload: new File([new Uint8Array(file)], "document.pdf", { type: "application/pdf" }),
            sha256,
        };
    }
    // Uploadable (File/Blob/stream) — pass through, no hash (a random UUID
    // Idempotency-Key is generated; supply idempotencyKey for dedup)
    return { upload: file };
}

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/**
 * a11yfy API client.
 *
 * @example
 * import { A11yfyClient } from "@a11yfy/sdk";
 *
 * const client = new A11yfyClient({ token: process.env.A11YFY_API_KEY! });
 * const result = await client.remediate("document.pdf");
 * console.log(result.output_url, result.certificate);
 */
export class A11yfyClient extends FernClient {
    constructor(options: ConstructorParameters<typeof FernClient>[0] = {} as never) {
        // Env-var fallback: A11YFY_API_KEY (explicit token wins).
        const opts = { ...(options as Record<string, unknown>) };
        if (opts.token == null && process.env.A11YFY_API_KEY) {
            opts.token = process.env.A11YFY_API_KEY;
        }
        super(opts as ConstructorParameters<typeof FernClient>[0]);
    }

    /**
     * Típushelyes createJob (audit 6-SDK-P0.2): 202 → JobAcceptedResponse
     * (benne a webhook.signing_secret, amit a szerver CSAK EGYSZER ad ki),
     * 200 → JobAlreadyValidResponse. Webhookos integrációnál EZT használd a
     * `jobs.createJob` helyett.
     */
    public async createJob(
        request: Parameters<FernClient["jobs"]["createJob"]>[0],
        requestOptions?: Parameters<FernClient["jobs"]["createJob"]>[1],
    ): Promise<JobCreateResponse> {
        const { data, rawResponse } = await this.jobs
            .createJob(request, requestOptions)
            .withRawResponse();
        if (rawResponse.status === 202) {
            return data as unknown as A11yfy.JobAcceptedResponse;
        }
        return data;
    }

    /**
     * Upload a PDF, wait for remediation and return the final result.
     *
     * @throws {JobFailedError} when the job fails
     * @throws {RemediationTimeoutError} when the wait budget elapses first
     */
    public async remediate(
        file: FileInput,
        options: RemediateOptions = {},
    ): Promise<A11yfy.JobResultResponse> {
        const {
            webhookUrl,
            idempotencyKey,
            pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
            timeoutMs = DEFAULT_TIMEOUT_MS,
            certificateWaitMs = DEFAULT_CERTIFICATE_WAIT_MS,
        } = options;

        const { upload, sha256 } = await prepareFile(file);
        // Streams have no hash — fall back to a random UUID so the required
        // Idempotency-Key header is always present (server rejects without it).
        const job = await this.createJob({
            file: upload,
            webhook_url: webhookUrl,
            "Idempotency-Key": idempotencyKey ?? sha256 ?? randomUUID(),
        });

        const started = Date.now();
        for (;;) {
            const status = await this.jobs.getJob({ id: job.job_id });
            if (TERMINAL_STATUSES.has(status.status)) {
                break;
            }
            const waited = Date.now() - started;
            if (timeoutMs != null && waited + pollIntervalMs > timeoutMs) {
                throw new RemediationTimeoutError(job.job_id, waited);
            }
            await sleep(pollIntervalMs);
        }

        let result = await this.jobs.getJobResult({ id: job.job_id });
        if (result.status === "failed") {
            throw new JobFailedError(result);
        }
        // Cert grace-poll: a tanúsítvány a done UTÁN pár másodperccel készül el.
        const certDeadline = Date.now() + certificateWaitMs;
        while (certificateExpected(result) && Date.now() < certDeadline) {
            await sleep(CERT_POLL_INTERVAL_MS);
            result = await this.jobs.getJobResult({ id: job.job_id });
        }
        return result;
    }
}
