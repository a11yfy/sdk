# a11yfy Python SDK

Official Python SDK for the [a11yfy](https://a11yfy.com) PDF accessibility
remediation API. Upload a PDF, get back a PDF/UA-compliant, screen-reader-friendly
document — with a verifiable compliance certificate.

## Installation

```sh
pip install a11yfy
```

Requires Python 3.10+.

## Quickstart

```python
from a11yfy import A11yfy

client = A11yfy(token="ak_live_...")  # or set A11YFY_API_KEY env var

result = client.remediate("document.pdf")   # upload + poll + result, one call
print(result.output_url)                    # presigned URL of the remediated PDF
if result.certificate:
    print(result.certificate.download_url)  # compliance certificate PDF
    print(result.certificate.verify_url)    # public verification page
```

`remediate()` raises `JobFailedError` when the job fails and
`RemediationTimeoutError` when the wait budget (default 30 min) elapses —
the job keeps running server-side and can still be polled.

## Low-level API

```python
job = client.jobs.create_job(file=("doc.pdf", pdf_bytes))
status = client.jobs.get_job(job.job_id)             # pending|processing|done|failed|partial
result = client.jobs.get_job_result(job.job_id)

page = client.jobs.list_jobs(limit=50)               # newest first, cursor pagination
more = client.jobs.list_jobs(cursor=page.next_cursor)

certs = client.certificates.find_certificates(job_id=job.job_id)
certs = client.certificates.find_certificates(output_sha256="<sha256-of-output-pdf>")
pdf_bytes = b"".join(client.certificates.download_certificate(certs.certificates[0].certificate_id))

balance = client.billing.get_balance()
usage = client.billing.get_usage()
```

## Async

```python
from a11yfy import AsyncA11yfy

client = AsyncA11yfy(token="ak_live_...")
result = await client.remediate("document.pdf")
```

## Webhooks

Pass `webhook_url` to get an HMAC-signed callback when the job finishes,
then verify it with the Stripe-style helper:

```python
from a11yfy import Webhook, WebhookVerificationError

@app.post("/a11yfy-webhook")
def handle(request):
    try:
        event = Webhook.construct_event(
            payload=request.body,                                # RAW bytes!
            signature_header=request.headers["X-A11yfy-Signature"],
            secret=os.environ["A11YFY_WEBHOOK_SECRET"],
        )
    except WebhookVerificationError:
        return Response(status=400)
    if event.is_success:
        download(event.output_url)
    return Response(status=200)
```

## Configuration

| Option | Default | Notes |
|---|---|---|
| `token` | `A11YFY_API_KEY` env var | `ak_live_...` / `ak_test_...` |
| `base_url` | `https://a11yfy.com` | override for sandbox environments |
| `timeout` | 60 s per request | HTTP timeout |
| `remediate(poll_interval=)` | 5 s | fixed-interval status polling |
| `remediate(timeout=)` | 1800 s | overall wait budget |

Duplicate submissions are deduplicated automatically: `remediate()` sends the
file's SHA-256 as `Idempotency-Key`, so retrying the same file within 24h
returns the same job instead of billing twice.

## Docs

- API reference: https://a11yfy.com/docs
- Full endpoint reference for this SDK: [`src/a11yfy/reference.md`](./src/a11yfy/reference.md)

## License

MIT
