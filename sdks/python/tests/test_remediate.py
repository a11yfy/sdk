"""remediate() flow-tesztek stubolt jobs-klienssel (nincs hálózat)."""

import io
import json

import pytest

from a11yfy import A11yfy, JobFailedError, RemediationTimeoutError
from a11yfy.custom_client import _prepare_file
from a11yfy.types.job_accepted_response import JobAcceptedResponse
from a11yfy.types.job_already_valid_response import JobAlreadyValidResponse


class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _FakeHttpxResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeRawJobs:
    """A with_raw_response felület stubja (audit 6-SDK-P0.2 kontraktus)."""

    def __init__(self, owner, status_code, payload):
        self._owner = owner
        self._status_code = status_code
        self._payload = payload

    def create_job(self, **kwargs):
        self._owner.created_with = kwargs
        return _Obj(
            response=_FakeHttpxResponse(self._status_code, self._payload),
            data=_Obj(job_id=self._payload["job_id"], status="pending"),
        )


#: 202-es szerver-payload — a webhook.signing_secret CSAK itt jön.
_ACCEPTED_PAYLOAD = {
    "job_id": "job-1",
    "status": "pending",
    "created_at": "2026-07-10T00:00:00Z",
    "webhook": {"url": "https://example.com/hook", "signing_secret": "whsec_abc123"},
}


class StubJobs:
    """create→(processing…)→terminal szekvenciát játszik le."""

    def __init__(self, statuses, result_status="done", create_status_code=202):
        self.statuses = list(statuses)
        self.result_status = result_status
        self.created_with = None
        self._create_status_code = create_status_code

    @property
    def with_raw_response(self):
        return _FakeRawJobs(self, self._create_status_code, dict(_ACCEPTED_PAYLOAD))

    def get_job(self, job_id, **kwargs):
        status = self.statuses.pop(0) if self.statuses else "done"
        return _Obj(job_id=job_id, status=status, credits_used=None, error=None)

    def get_job_result(self, job_id, **kwargs):
        return _Obj(
            job_id=job_id,
            status=self.result_status,
            credits_used=8,
            output_url="https://example.com/out.pdf" if self.result_status == "done" else None,
            certificate=None,
            after=None,
        )


def make_client(stub):
    client = A11yfy(token="ak_test_x")
    client._jobs = stub  # cached backing attr a generált propertyhez
    return client


def test_remediate_success_flow():
    stub = StubJobs(["processing", "processing", "done"])
    client = make_client(stub)
    result = client.remediate(b"%PDF-1.7 fake", poll_interval=0.001)
    assert result.status == "done"
    assert result.output_url
    # Idempotency-Key automatikusan a fájl sha256-a
    assert stub.created_with["idempotency_key"] is not None
    assert len(stub.created_with["idempotency_key"]) == 64


def test_remediate_failed_raises():
    stub = StubJobs(["failed"], result_status="failed")
    client = make_client(stub)
    with pytest.raises(JobFailedError) as exc_info:
        client.remediate(b"%PDF fake", poll_interval=0.001)
    assert exc_info.value.job_id == "job-1"


def test_remediate_timeout():
    stub = StubJobs(["processing"] * 100)
    client = make_client(stub)
    with pytest.raises(RemediationTimeoutError):
        client.remediate(b"%PDF fake", poll_interval=0.005, timeout=0.02)


def test_explicit_idempotency_key_wins():
    stub = StubJobs(["done"])
    client = make_client(stub)
    client.remediate(b"%PDF fake", idempotency_key="my-key", poll_interval=0.001)
    assert stub.created_with["idempotency_key"] == "my-key"


def test_create_job_202_returns_accepted_with_signing_secret():
    """6-SDK-P0.2 regresszió: a 202 JobAcceptedResponse-t ad, a
    webhook.signing_secret NEM veszhet el."""
    stub = StubJobs(["done"], create_status_code=202)
    client = make_client(stub)
    job = client.create_job(file=b"%PDF fake", idempotency_key="k")
    assert isinstance(job, JobAcceptedResponse)
    assert job.webhook is not None
    assert job.webhook.signing_secret == "whsec_abc123"


def test_create_job_200_returns_already_valid_data():
    """200 (already_valid): a generált parszolás (data) jön vissza."""
    stub = StubJobs(["done"], create_status_code=200)
    client = make_client(stub)
    job = client.create_job(file=b"%PDF fake", idempotency_key="k")
    # a stub .data-ja _Obj — a lényeg: NEM a 202-es ágon parszolódott
    assert not isinstance(job, JobAcceptedResponse)
    assert job.job_id == "job-1"


def test_prepare_file_variants(tmp_path):
    # path (6-SDK-P0.1): chunkolt SHA + nyitott fájl-handle (streaming upload)
    p = tmp_path / "doc.pdf"
    p.write_bytes(b"%PDF data")
    (name, fh), digest, closer = _prepare_file(str(p))
    assert name == "doc.pdf" and len(digest) == 64
    assert hasattr(fh, "read") and fh.read() == b"%PDF data"
    closer()
    assert fh.closed
    # bytes — változatlan, azonos digest
    (_, data2), digest2, closer2 = _prepare_file(b"%PDF data")
    assert data2 == b"%PDF data" and digest2 == digest
    closer2()  # no-op
    # stream: nincs hash
    stream = io.BytesIO(b"x")
    passthrough, digest3, closer3 = _prepare_file(stream)
    assert passthrough is stream and digest3 is None
    closer3()
    assert not stream.closed


def test_env_var_token(monkeypatch):
    monkeypatch.setenv("A11YFY_API_KEY", "ak_test_env")
    client = A11yfy()  # token nélkül — env-ből jön
    assert client is not None
