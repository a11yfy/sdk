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
from .core.request_options import RequestOptions
from .types.job_result_response import JobResultResponse

if typing.TYPE_CHECKING:
    from . import core

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


def _prepare_file(file: FileInput) -> typing.Tuple[typing.Any, typing.Optional[str]]:
    """Normalize the input to a (core.File, sha256|None) pair.

    Paths and bytes are read fully so the SHA-256 can double as an
    Idempotency-Key (same file → same job within 24h, no double billing).
    Streams are passed through untouched (no hash — a random UUID key is
    generated instead; supply idempotency_key explicitly if you need
    dedup for streams).
    """
    if isinstance(file, (str, os.PathLike)):
        path = os.fspath(file)
        with open(path, "rb") as fh:
            data = fh.read()
        return (os.path.basename(path), data), hashlib.sha256(data).hexdigest()
    if isinstance(file, bytes):
        return ("document.pdf", file), hashlib.sha256(file).hexdigest()
    if isinstance(file, tuple):
        name, data = file
        return (name, data), hashlib.sha256(data).hexdigest()
    # file-like stream — pass through
    return file, None


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
        file_arg, digest = _prepare_file(file)
        # Streams have no hash — fall back to a random UUID so the required
        # Idempotency-Key header is always present (server rejects without it).
        key = idempotency_key or digest or str(uuid.uuid4())
        job = self.jobs.create_job(
            file=file_arg,
            webhook_url=webhook_url,
            idempotency_key=key,
            request_options=request_options,
        )
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
        file_arg, digest = _prepare_file(file)
        # Streams have no hash — fall back to a random UUID so the required
        # Idempotency-Key header is always present (server rejects without it).
        key = idempotency_key or digest or str(uuid.uuid4())
        job = await self.jobs.create_job(
            file=file_arg,
            webhook_url=webhook_url,
            idempotency_key=key,
            request_options=request_options,
        )
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
