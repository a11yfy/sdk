"""remediate() flow-tesztek stubolt jobs-klienssel (nincs hálózat)."""

import types

import pytest

from a11yfy import A11yfy, JobFailedError, RemediationTimeoutError
from a11yfy.custom_client import _prepare_file


class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class StubJobs:
    """create→(processing…)→terminal szekvenciát játszik le."""

    def __init__(self, statuses, result_status="done"):
        self.statuses = list(statuses)
        self.result_status = result_status
        self.created_with = None

    def create_job(self, **kwargs):
        self.created_with = kwargs
        return _Obj(job_id="job-1", status="pending", created_at="2026-07-10T00:00:00Z")

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


def test_prepare_file_variants(tmp_path):
    # path
    p = tmp_path / "doc.pdf"
    p.write_bytes(b"%PDF data")
    (name, data), digest = _prepare_file(str(p))
    assert name == "doc.pdf" and data == b"%PDF data" and len(digest) == 64
    # bytes
    (_, data2), digest2 = _prepare_file(b"%PDF data")
    assert digest2 == digest
    # stream: nincs hash
    import io

    stream = io.BytesIO(b"x")
    passthrough, digest3 = _prepare_file(stream)
    assert passthrough is stream and digest3 is None


def test_env_var_token(monkeypatch):
    monkeypatch.setenv("A11YFY_API_KEY", "ak_test_env")
    client = A11yfy()  # token nélkül — env-ből jön
    assert client is not None
