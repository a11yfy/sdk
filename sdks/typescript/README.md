# a11yfy Node.js SDK

Official Node.js SDK for the [a11yfy](https://a11yfy.com) PDF accessibility
remediation API. Upload a PDF, get back a PDF/UA-compliant, screen-reader-friendly
document — with a verifiable compliance certificate.

## Installation

```sh
npm install @a11yfy/sdk
```

Requires Node.js 20+. Server-side only (the API key is a secret).

## Quickstart

```ts
import { A11yfyClient } from "@a11yfy/sdk";

const client = new A11yfyClient({ token: process.env.A11YFY_API_KEY! });

const result = await client.remediate("document.pdf"); // upload + poll + result
console.log(result.output_url);                        // presigned URL of the remediated PDF
if (result.certificate) {
    console.log(result.certificate.download_url);      // compliance certificate PDF
    console.log(result.certificate.verify_url);        // public verification page
}
```

`remediate()` accepts a file path, `Buffer`, `File`/`Blob` or stream. It throws
`JobFailedError` when the job fails and `RemediationTimeoutError` when the wait
budget (default 30 min) elapses — the job keeps running server-side.

## Low-level API

```ts
const job = await client.jobs.createJob({ file: new File([bytes], "doc.pdf") });
const status = await client.jobs.getJob({ id: job.job_id });   // pending|processing|done|failed|partial
const result = await client.jobs.getJobResult({ id: job.job_id });

const page = await client.jobs.listJobs({ limit: 50 }); // newest first, cursor pagination
const more = await client.jobs.listJobs({ cursor: page.next_cursor! });

const certs = await client.certificates.findCertificates({ job_id: job.job_id });
const bySha = await client.certificates.findCertificates({ output_sha256: "<sha256>" });
const pdf = await client.certificates.downloadCertificate({ certId: certs.certificates[0]!.certificate_id });

const balance = await client.billing.getBalance();
const usage = await client.billing.getUsage();
```

## Webhooks

Pass `webhookUrl` to get an HMAC-signed callback when the job finishes, then
verify it with the Stripe-style helper:

```ts
import { Webhooks, WebhookVerificationError } from "@a11yfy/sdk";

app.post("/a11yfy-webhook", (req, res) => {
    let event;
    try {
        event = Webhooks.constructEvent(
            req.rawBody,                                    // RAW string/Buffer!
            req.headers["x-a11yfy-signature"] as string,
            process.env.A11YFY_WEBHOOK_SECRET!,
        );
    } catch (err) {
        if (err instanceof WebhookVerificationError) return res.sendStatus(400);
        throw err;
    }
    if (event.status === "done") download(event.output_url!);
    res.sendStatus(200);
});
```

## Configuration

| Option | Default | Notes |
|---|---|---|
| `token` | `A11YFY_API_KEY` env var | `ak_live_...` / `ak_test_...` |
| `baseUrl` | `https://a11yfy.com` | override for sandbox environments |
| `remediate({ pollIntervalMs })` | 5000 | fixed-interval status polling |
| `remediate({ timeoutMs })` | 1 800 000 | overall wait budget |

Duplicate submissions are deduplicated automatically: `remediate()` sends the
file's SHA-256 as `Idempotency-Key`, so retrying the same file within 24h
returns the same job instead of billing twice.

## Docs

API reference: https://a11yfy.com/docs

## License

MIT
