# Reference
## Jobs
<details><summary><code>client.jobs.<a href="src/a11yfy/jobs/client.py">list_jobs</a>(...) -> JobListResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns the jobs of the organization, newest first, with cursor-based
pagination. Pass the returned `next_cursor` as `?cursor=` to fetch the
next page; `next_cursor: null` means there are no more results.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from a11yfy import BaseA11yfy
from a11yfy.environment import BaseA11yfyEnvironment

client = BaseA11yfy(
    token="<token>",
    environment=BaseA11yfyEnvironment.DEFAULT,
)

client.jobs.list_jobs()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**limit:** `typing.Optional[int]` — Page size (1–100, default 20)
    
</dd>
</dl>

<dl>
<dd>

**cursor:** `typing.Optional[str]` — Opaque pagination cursor from a previous response
    
</dd>
</dl>

<dl>
<dd>

**status:** `typing.Optional[ListJobsRequestStatus]` — Filter by job status
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/a11yfy/jobs/client.py">create_job</a>(...) -> JobAcceptedResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Single call that launches the full remediation pipeline:
diagnostics → credit reservation → processing.
Returns a `job_id` immediately for status polling.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from a11yfy import BaseA11yfy
from a11yfy.environment import BaseA11yfyEnvironment

client = BaseA11yfy(
    token="<token>",
    environment=BaseA11yfyEnvironment.DEFAULT,
)

client.jobs.create_job(
    idempotency_key="550e8400-e29b-41d4-a716-446655440000",
    file="example_file",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**idempotency_key:** `typing.Optional[str]` — Deduplication key — reused within 24h returns the stored response
    
</dd>
</dl>

<dl>
<dd>

**file:** `typing.Optional[core.File]` — PDF file to remediate
    
</dd>
</dl>

<dl>
<dd>

**webhook_url:** `typing.Optional[str]` — Optional callback URL for HMAC-signed completion webhook
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/a11yfy/jobs/client.py">get_job</a>(...) -> JobStatusResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns the current job status: `pending`, `processing`, `done`, or `failed`.
Can be polled during processing.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from a11yfy import BaseA11yfy
from a11yfy.environment import BaseA11yfyEnvironment

client = BaseA11yfy(
    token="<token>",
    environment=BaseA11yfyEnvironment.DEFAULT,
)

client.jobs.get_job(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Job identifier from POST /v1/jobs response
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/a11yfy/jobs/client.py">get_job_result</a>(...) -> JobResultResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns the completed job result: output URL, credits consumed,
pre/post remediation diagnostics.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from a11yfy import BaseA11yfy
from a11yfy.environment import BaseA11yfyEnvironment

client = BaseA11yfy(
    token="<token>",
    environment=BaseA11yfyEnvironment.DEFAULT,
)

client.jobs.get_job_result(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Job identifier from POST /v1/jobs response
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

## Billing
<details><summary><code>client.billing.<a href="src/a11yfy/billing/client.py">get_balance</a>() -> BalanceResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns the organization's current credit balance with breakdown:
subscription credits, one-time purchase credits, and total.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from a11yfy import BaseA11yfy
from a11yfy.environment import BaseA11yfyEnvironment

client = BaseA11yfy(
    token="<token>",
    environment=BaseA11yfyEnvironment.DEFAULT,
)

client.billing.get_balance()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.billing.<a href="src/a11yfy/billing/client.py">get_usage</a>() -> UsageResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns the list of past jobs with credit consumption and timestamps.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from a11yfy import BaseA11yfy
from a11yfy.environment import BaseA11yfyEnvironment

client = BaseA11yfy(
    token="<token>",
    environment=BaseA11yfyEnvironment.DEFAULT,
)

client.billing.get_usage()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

## Certificates
<details><summary><code>client.certificates.<a href="src/a11yfy/certificates/client.py">find_certificates</a>(...) -> CertificateListResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Looks up compliance certificates by the job that produced them
(`job_id`) or by the SHA-256 of the remediated PDF (`output_sha256`).
Provide exactly one of the two parameters. Returns the full supersede
chain, newest first — the entry with `superseded_by: null` is current.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from a11yfy import BaseA11yfy
from a11yfy.environment import BaseA11yfyEnvironment

client = BaseA11yfy(
    token="<token>",
    environment=BaseA11yfyEnvironment.DEFAULT,
)

client.certificates.find_certificates()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**job_id:** `typing.Optional[str]` — Job identifier from POST /v1/jobs response
    
</dd>
</dl>

<dl>
<dd>

**output_sha256:** `typing.Optional[str]` — SHA-256 hash (lowercase hex) of the remediated PDF file
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.certificates.<a href="src/a11yfy/certificates/client.py">get_certificate</a>(...) -> CertificateInfo</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns the metadata of a single compliance certificate, including its
download and public verification URLs.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from a11yfy import BaseA11yfy
from a11yfy.environment import BaseA11yfyEnvironment

client = BaseA11yfy(
    token="<token>",
    environment=BaseA11yfyEnvironment.DEFAULT,
)

client.certificates.get_certificate(
    cert_id="A11Y-2026-07-3F9K2M",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**cert_id:** `str` — Certificate identifier
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.certificates.<a href="src/a11yfy/certificates/client.py">download_certificate</a>(...) -> typing.Iterator[bytes]</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Streams the certificate as a PDF/UA-compliant PDF file. The file is
immutable: re-issued certificates get a new identifier, the old file
never changes.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from a11yfy import BaseA11yfy
from a11yfy.environment import BaseA11yfyEnvironment

client = BaseA11yfy(
    token="<token>",
    environment=BaseA11yfyEnvironment.DEFAULT,
)

client.certificates.download_certificate(
    cert_id="certId",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**cert_id:** `str` — Certificate identifier
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

