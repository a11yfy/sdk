# a11yfy SDKs

Official SDKs for the [a11yfy](https://a11yfy.com) PDF accessibility remediation
API. Upload a PDF, get back a PDF/UA-compliant, screen-reader-friendly document —
with a verifiable compliance certificate.

| Package | Registry | Directory |
|---|---|---|
| `a11yfy` | [PyPI](https://pypi.org/project/a11yfy/) | [`sdks/python`](./sdks/python) |
| `@a11yfy/sdk` | [npm](https://www.npmjs.com/package/@a11yfy/sdk) | [`sdks/typescript`](./sdks/typescript) |

```python
from a11yfy import A11yfy

client = A11yfy(token="ak_live_...")
result = client.remediate("document.pdf")
print(result.output_url, result.certificate.verify_url)
```

```ts
import { A11yfyClient } from "@a11yfy/sdk";

const client = new A11yfyClient({ token: process.env.A11YFY_API_KEY! });
const result = await client.remediate("document.pdf");
console.log(result.output_url, result.certificate?.verify_url);
```

API reference: https://a11yfy.com/docs

## Architecture

Both SDKs are generated from the API's OpenAPI 3.1 spec with
[Fern](https://buildwithfern.com) (single source of truth:
[`fern/openapi/openapi.json`](./fern/openapi/openapi.json), synced from the main
repo), plus a small hand-written overlay per language:

- `remediate()` — upload + poll + result convenience (Replicate `run()` pattern),
  automatic `Idempotency-Key` from the file's SHA-256 (no double billing on retry)
- `Webhook.construct_event()` / `Webhooks.constructEvent()` — Stripe-style
  HMAC webhook verification matched to the a11yfy signature contract
- typed errors: `JobFailedError`, `RemediationTimeoutError`, `WebhookVerificationError`

Overlay files are `.fernignore`-protected; regeneration never touches them.

## Development

```sh
npm install -g fern-api          # Fern CLI
./scripts/sync-openapi.sh        # spec sync a fő repóból + regenerálás (Docker kell)

cd sdks/python && uv sync && uv run pytest
cd sdks/typescript && npm install && npm run check && npm test && npm run build
```

## Release

Trusted Publishing (OIDC, tokens never stored) — see
[`.github/workflows/publish.yml`](./.github/workflows/publish.yml).
Bump the version in `pyproject.toml` / `package.json`, then push the matching
tag: `py-v<version>` (PyPI) or `js-v<version>` (npm).

## License

MIT
