<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
  <img src="assets/logo-light.svg" alt="a11yfy" width="360">
</picture>

### Make any PDF accessible — with one API call

Official SDKs for the [a11yfy](https://a11yfy.com) PDF accessibility remediation API.
Upload a PDF, get back a **PDF/UA-compliant**, screen-reader-friendly document —
with a **verifiable compliance certificate**.

[![CI](https://github.com/a11yfy/sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/a11yfy/sdk/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/a11yfy?label=a11yfy&logo=pypi&logoColor=white)](https://pypi.org/project/a11yfy/)
[![npm](https://img.shields.io/npm/v/%40a11yfy%2Fsdk?label=%40a11yfy%2Fsdk&logo=npm)](https://www.npmjs.com/package/@a11yfy/sdk)
[![License: MIT](https://img.shields.io/badge/license-MIT-04342C.svg)](./LICENSE)

[Quickstart](#quickstart) · [How it works](#how-it-works) · [Certificates](#compliance-certificates) · [Webhooks](#webhooks) · [API docs](https://a11yfy.com/docs)

</div>

---

## Why

The **European Accessibility Act (EAA)** requires digital documents to be
accessible. Most PDFs aren't. a11yfy fixes them automatically:

- 🏷️ **Full PDF/UA-1 tagging** — headings, lists, tables, reading order, figures with AI alt text
- ✅ **Machine-validated** — every output is checked with veraPDF before you get it
- 📜 **Compliance certificate** — Ed25519-signed, publicly verifiable proof for audits
- 💰 **No double billing** — retrying the same file within 24h returns the same job
- 🆓 **Already compliant? Free.** — compliant PDFs are detected up front and returned without consuming credits

## Packages

| Package | Registry | Requirements | Source |
|---|---|---|---|
| `a11yfy` | [PyPI](https://pypi.org/project/a11yfy/) | Python ≥ 3.10 | [`sdks/python`](./sdks/python) |
| `@a11yfy/sdk` | [npm](https://www.npmjs.com/package/@a11yfy/sdk) | Node.js ≥ 20 | [`sdks/typescript`](./sdks/typescript) |

Both are server-side SDKs — the API key is a secret, keep it out of browsers.
Get your key at [a11yfy.com](https://a11yfy.com) → *Settings → API keys*.

## Quickstart

### Python

```sh
pip install a11yfy
```

```python
from a11yfy import A11yfy

client = A11yfy()  # reads A11YFY_API_KEY from the environment

result = client.remediate("document.pdf")   # upload + process + wait, one call
print(result.before.issues, "→", result.after.issues)   # e.g. 47 → 0
print(result.output_url)                    # the remediated, accessible PDF
print(result.certificate.verify_url)        # public proof of compliance
```

### Node.js

```sh
npm install @a11yfy/sdk
```

```ts
import { A11yfyClient } from "@a11yfy/sdk";

const client = new A11yfyClient(); // reads A11YFY_API_KEY from the environment

const result = await client.remediate("document.pdf");
console.log(`${result.before?.issues} → ${result.after?.issues}`); // e.g. 47 → 0
console.log(result.output_url);              // the remediated, accessible PDF
console.log(result.certificate?.verify_url); // public proof of compliance
```

`remediate()` accepts a file path, raw bytes/`Buffer`, or a stream. Path inputs
are streamed — hashing and upload never load the whole file into memory, so
documents up to the 300 MB limit are fine. It throws a typed `JobFailedError` /
`RemediationTimeoutError` — a timed-out job keeps running server-side and can
still be polled.

## How it works

```
 your PDF ──▶ POST /v1/jobs ──▶ diagnostics ──▶ remediation ──▶ veraPDF check
                                                                     │
 result ◀── GET /v1/jobs/:id/result ◀── certificate issued ◀── PASS ─┘
```

The high-level `remediate()` wraps the full flow. The low-level clients expose
every endpoint:

```python
job    = client.jobs.create_job(file=("doc.pdf", pdf_bytes))
status = client.jobs.get_job(job.job_id)          # pending → processing → done
result = client.jobs.get_job_result(job.job_id)

page   = client.jobs.list_jobs(limit=50)          # newest first, cursor pagination
certs  = client.certificates.find_certificates(job_id=job.job_id)
balance = client.billing.get_balance()
```

```ts
const job    = await client.jobs.createJob({ file });
const status = await client.jobs.getJob({ id: job.job_id });
const result = await client.jobs.getJobResult({ id: job.job_id });

const page   = await client.jobs.listJobs({ limit: 50 });
const certs  = await client.certificates.findCertificates({ job_id: job.job_id });
const balance = await client.billing.getBalance();
```

## Compliance certificates

Every remediated PDF that passes machine validation gets an **immutable,
Ed25519-signed certificate**. Retrieve it any time — by job, or by the SHA-256
of the output file itself:

```python
certs = client.certificates.find_certificates(output_sha256=sha256_of_pdf)
pdf = b"".join(client.certificates.download_certificate(certs.certificates[0].certificate_id))
```

Anyone can verify a certificate without an API key at its `verify_url`
(`https://a11yfy.com/en/verify/A11Y-2026-07-...`) — hash match proves the
exact file was certified.

## Webhooks

Skip polling: pass a `webhook_url` and verify the HMAC-signed callback with
the built-in helper (constant-time compare, replay protection). The signing
secret is returned **once**, in the job-creation response that first registers
the `webhook_url` (`signing_secret` — it stays visible in the web UI under
*Settings → Organization → API keys*):

```python
from a11yfy import Webhook, WebhookVerificationError

event = Webhook.construct_event(raw_body, sig_header, secret)
if event.is_success:
    download(event.output_url)
```

```ts
import { Webhooks } from "@a11yfy/sdk";

const event = Webhooks.constructEvent(rawBody, sigHeader, secret);
if (event.status === "done") download(event.output_url!);
```

## Development

Both SDKs are generated from the API's OpenAPI 3.1 spec with
[Fern](https://buildwithfern.com), plus a hand-written, `.fernignore`-protected
overlay per language (`remediate()`, webhook verification, typed errors).

```sh
npm install -g fern-api
./scripts/sync-openapi.sh              # sync spec from the main repo + regenerate

cd sdks/python && uv sync && uv run pytest
cd sdks/typescript && npm install && npm run check && npm test && npm run build
```

Releases use tag-triggered [Trusted Publishing](./.github/workflows/publish.yml)
(OIDC — no registry tokens stored): bump the version, push `py-v<x.y.z>` or
`js-v<x.y.z>`.

## Links

- 📖 [API reference](https://a11yfy.com/docs) — interactive OpenAPI docs
- 🔍 [Certificate verification](https://a11yfy.com/en/verify)
- 🌐 [a11yfy.com](https://a11yfy.com)

## License

[MIT](./LICENSE)
