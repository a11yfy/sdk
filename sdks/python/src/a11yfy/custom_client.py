# Hand-written overlay — NOT generated. Protected by .fernignore.
#
# High-level convenience layer on top of the generated BaseA11yfy client
# (Replicate `run()` pattern): `client.remediate("doc.pdf")` uploads the file,
# polls the job until it reaches a terminal state and returns the final result.
#
# The low-level surface stays available: `client.jobs.*`, `client.certificates.*`,
# `client.billing.*`.

from __future__ import annotations

import asyncio
import hashlib
import os
import time
import typing
import uuid

from .client import AsyncBaseA11yfy, BaseA11yfy
from .core.pydantic_utilities import parse_obj_as
from .core.request_options import RequestOptions
from .types.job_accepted_response import JobAcceptedResponse
from .types.job_already_valid_response import JobAlreadyValidResponse
from .types.job_result_response import JobResultResponse

if typing.TYPE_CHECKING:
    from . import core

#: create_job valódi válasz-uniója (audit 6-SDK-P0.2): a szerver 202-re
#: JobAcceptedResponse-t ad (benne az EGYSZER kiadott webhook.signing_secret),
#: 200-ra JobAlreadyValidResponse-t. A generált raw_client minden 2xx-et
#: AlreadyValid-ként parszolt — a signing_secret elveszett.
JobCreateResponse = typing.Union[JobAcceptedResponse, JobAlreadyValidResponse]


def _parse_create_job(http_response: typing.Any) -> JobCreateResponse:
    """Státuszkód-helyes 202/200 parszolás a with_raw_response eredményéből."""
    raw = http_response.response  # httpx.Response
    if raw.status_code == 202:
        return typing.cast(
            JobAcceptedResponse,
            parse_obj_as(type_=JobAcceptedResponse, object_=raw.json()),  # type: ignore[arg-type]
        )
    return http_response.data

#: Terminal job states — polling stops on any of these.
_TERMINAL_STATUSES = frozenset({"done", "failed", "partial"})

#: Default fixed poll interval (seconds). Long-running jobs poll at a fixed
#: interval by design; exponential backoff applies to HTTP retries only.
DEFAULT_POLL_INTERVAL = 5.0

#: Default overall wait budget (seconds) for `remediate()`.
DEFAULT_TIMEOUT = 1800.0

#: Grace window (seconds) to wait for the compliance certificate after 'done'.
#: The certificate is issued moments AFTER the job flips to done (best-effort,
#: server-side ordering) — a short re-poll makes result.certificate reliable.
DEFAULT_CERTIFICATE_WAIT = 20.0
_CERT_POLL_INTERVAL = 2.0


def _certificate_expected(result: JobResultResponse) -> bool:
    """Cert only exists for compliant (veraPDF-pass) outputs."""
    return (
        result.status == "done"
        and result.certificate is None
        and result.after is not None
        and result.after.issues == 0
    )


class RemediationTimeoutError(Exception):
    """The job did not reach a terminal state within the wait budget.

    The job keeps running server-side; poll `client.jobs.get_job(job_id)`
    to continue tracking it.
    """

    def __init__(self, job_id: str, waited_seconds: float) -> None:
        super().__init__(
            f"Job {job_id} did not finish within {waited_seconds:.0f}s. "
            f"It is still running server-side — poll jobs.get_job({job_id!r}) to continue."
        )
        self.job_id = job_id


class JobFailedError(Exception):
    """The job reached the 'failed' terminal state."""

    def __init__(self, result: JobResultResponse) -> None:
        super().__init__(f"Job {result.job_id} failed.")
        self.result = result
        self.job_id = result.job_id


FileInput = typing.Union[str, os.PathLike, bytes, typing.IO[bytes], typing.Tuple[str, bytes]]

#: Chunk-méret a streaming SHA-256-hoz (1 MiB).
_SHA_CHUNK = 1024 * 1024


def _sha256_file(path: str) -> str:
    """Chunkolt SHA-256 — a fájl SOSEM kerül egyben memóriába (6-SDK-P0.1)."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_SHA_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _prepare_file(
    file: FileInput,
) -> typing.Tuple[typing.Any, typing.Optional[str], typing.Callable[[], None]]:
    """Normalize the input to a (core.File, sha256|None, closer) triple.

    Path input (audit 6-SDK-P0.1): a SHA-256 chunkolva számolódik, és a
    multipart-feltöltés nyitott fájl-handle-ből streamel — egy 300 MB-os PDF
    sem kerül egyben memóriába. (Az httpx a seekable fájlt render előtt
    seek(0)-val visszatekeri, így az HTTP-retry is biztonságos.) A handle-t
    a visszaadott `closer` zárja — a hívó felelőssége (try/finally).

    Bytes/tuple input: változatlan (a hívó már memóriában tartja).
    Streams are passed through untouched (no hash — a random UUID key is
    generated instead; supply idempotency_key explicitly if you need
    dedup for streams).
    """
    if isinstance(file, (str, os.PathLike)):
        path = os.fspath(file)
        digest = _sha256_file(path)
        fh = open(path, "rb")  # noqa: SIM115 — a closer zárja (streaming upload)
        return (os.path.basename(path), fh), digest, fh.close
    if isinstance(file, bytes):
        return ("document.pdf", file), hashlib.sha256(file).hexdigest(), lambda: None
    if isinstance(file, tuple):
        name, data = file
        return (name, data), hashlib.sha256(data).hexdigest(), lambda: None
    # file-like stream — pass through
    return file, None, lambda: None


class A11yfy(BaseA11yfy):
    """a11yfy API client.

    Usage:
        from a11yfy import A11yfy

        client = A11yfy(token="ak_live_...")
        result = client.remediate("document.pdf")
        print(result.output_url, result.certificate)
    """

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # Env-var fallback: A11YFY_API_KEY (explicit token param wins).
        if "token" not in kwargs or kwargs["token"] is None:
            env_token = os.environ.get("A11YFY_API_KEY")
            if env_token:
                kwargs["token"] = env_token
        super().__init__(*args, **kwargs)

    def create_job(
        self,
        *,
        file: typing.Any,
        webhook_url: typing.Optional[str] = None,
        idempotency_key: str,
        request_options: typing.Optional[RequestOptions] = None,
    ) -> JobCreateResponse:
        """Típushelyes create_job (audit 6-SDK-P0.2).

        A 202-es válasz JobAcceptedResponse-ként jön vissza — benne a
        `webhook.signing_secret`, amit a szerver CSAK EGYSZER ad ki. A
        generált `jobs.create_job` minden 2xx-et JobAlreadyValidResponse-ként
        parszolt, így a secret némán elveszett. Webhookos integrációnál
        EZT a metódust használd a `jobs.create_job` helyett.
        """
        response = self.jobs.with_raw_response.create_job(
            file=file,
            webhook_url=webhook_url,
            idempotency_key=idempotency_key,
            request_options=request_options,
        )
        return _parse_create_job(response)

    def remediate(
        self,
        file: FileInput,
        *,
        webhook_url: typing.Optional[str] = None,
        idempotency_key: typing.Optional[str] = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        timeout: typing.Optional[float] = DEFAULT_TIMEOUT,
        certificate_wait: float = DEFAULT_CERTIFICATE_WAIT,
        request_options: typing.Optional[RequestOptions] = None,
    ) -> JobResultResponse:
        """Upload a PDF, wait for remediation and return the final result.

        Raises JobFailedError when the job fails, RemediationTimeoutError
        when `timeout` elapses before a terminal state.
        """
        file_arg, digest, close_file = _prepare_file(file)
        # Streams have no hash — fall back to a random UUID so the required
        # Idempotency-Key header is always present (server rejects without it).
        key = idempotency_key or digest or str(uuid.uuid4())
        try:
            job = self.create_job(
                file=file_arg,
                webhook_url=webhook_url,
                idempotency_key=key,
                request_options=request_options,
            )
        finally:
            close_file()
        started = time.monotonic()
        while True:
            status = self.jobs.get_job(job.job_id, request_options=request_options)
            if status.status in _TERMINAL_STATUSES:
                break
            waited = time.monotonic() - started
            if timeout is not None and waited + poll_interval > timeout:
                raise RemediationTimeoutError(job.job_id, waited)
            time.sleep(poll_interval)
        result = self.jobs.get_job_result(job.job_id, request_options=request_options)
        if result.status == "failed":
            raise JobFailedError(result)
        # Cert grace-poll: a tanúsítvány a done UTÁN pár másodperccel készül el.
        cert_deadline = time.monotonic() + certificate_wait
        while _certificate_expected(result) and time.monotonic() < cert_deadline:
            time.sleep(_CERT_POLL_INTERVAL)
            result = self.jobs.get_job_result(job.job_id, request_options=request_options)
        return result


class AsyncA11yfy(AsyncBaseA11yfy):
    """Async a11yfy API client — see A11yfy for usage; all methods are awaitable."""

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        if "token" not in kwargs or kwargs["token"] is None:
            env_token = os.environ.get("A11YFY_API_KEY")
            if env_token:
                kwargs["token"] = env_token
        super().__init__(*args, **kwargs)

    async def create_job(
        self,
        *,
        file: typing.Any,
        webhook_url: typing.Optional[str] = None,
        idempotency_key: str,
        request_options: typing.Optional[RequestOptions] = None,
    ) -> JobCreateResponse:
        """Async típushelyes create_job — lásd A11yfy.create_job (6-SDK-P0.2)."""
        response = await self.jobs.with_raw_response.create_job(
            file=file,
            webhook_url=webhook_url,
            idempotency_key=idempotency_key,
            request_options=request_options,
        )
        return _parse_create_job(response)

    async def remediate(
        self,
        file: FileInput,
        *,
        webhook_url: typing.Optional[str] = None,
        idempotency_key: typing.Optional[str] = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        timeout: typing.Optional[float] = DEFAULT_TIMEOUT,
        certificate_wait: float = DEFAULT_CERTIFICATE_WAIT,
        request_options: typing.Optional[RequestOptions] = None,
    ) -> JobResultResponse:
        """Async variant of A11yfy.remediate()."""
        file_arg, digest, close_file = _prepare_file(file)
        # Streams have no hash — fall back to a random UUID so the required
        # Idempotency-Key header is always present (server rejects without it).
        key = idempotency_key or digest or str(uuid.uuid4())
        try:
            job = await self.create_job(
                file=file_arg,
                webhook_url=webhook_url,
                idempotency_key=key,
                request_options=request_options,
            )
        finally:
            close_file()
        started = time.monotonic()
        while True:
            status = await self.jobs.get_job(job.job_id, request_options=request_options)
            if status.status in _TERMINAL_STATUSES:
                break
            waited = time.monotonic() - started
            if timeout is not None and waited + poll_interval > timeout:
                raise RemediationTimeoutError(job.job_id, waited)
            await asyncio.sleep(poll_interval)
        result = await self.jobs.get_job_result(job.job_id, request_options=request_options)
        if result.status == "failed":
            raise JobFailedError(result)
        cert_deadline = time.monotonic() + certificate_wait
        while _certificate_expected(result) and time.monotonic() < cert_deadline:
            await asyncio.sleep(_CERT_POLL_INTERVAL)
            result = await self.jobs.get_job_result(job.job_id, request_options=request_options)
        return result
