import time

import pytest

from llm_gateway.cache.ledger import LocalLedger, cache_key
from llm_gateway.cache.s3 import S3Ledger


def test_local_roundtrip_and_expiry(tmp_path):
    ledger = LocalLedger(str(tmp_path), ttl_seconds=1)
    key = cache_key(tier="fast", models=("m",), prompt="hello", temperature=0.2, max_tokens=16)
    ledger.set(key, {"output": "pong"})
    assert ledger.get(key)["output"] == "pong"
    time.sleep(1.1)
    assert ledger.get(key) is None


def test_local_key_must_be_a_digest(tmp_path):
    ledger = LocalLedger(str(tmp_path), ttl_seconds=10)
    with pytest.raises(ValueError):
        ledger.get("../secrets")


class FakeBody:
    def __init__(self, payload: bytes):
        self.payload = payload

    def read(self):
        return self.payload


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.puts = []

    def put_object(self, **kwargs):
        self.puts.append(kwargs)
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs["Body"]

    def get_object(self, **kwargs):
        body = self.objects[(kwargs["Bucket"], kwargs["Key"])]
        return {"Body": FakeBody(body)}


def test_s3_put_encrypts_and_pins_owner():
    client = FakeS3()
    ledger = S3Ledger(
        bucket="bucket",
        prefix="llm-gateway/cache",
        ttl_seconds=60,
        region="us-east-1",
        expected_owner="111122223333",
        client=client,
    )
    key = cache_key(tier="fast", models=("m",), prompt="hello", temperature=0, max_tokens=8)
    ledger.set(key, {"output": "ok"})
    put = client.puts[0]
    assert put["ServerSideEncryption"] == "AES256"
    assert put["ExpectedBucketOwner"] == "111122223333"
    assert put["Key"] == f"llm-gateway/cache/{key}"
    assert ledger.get(key)["output"] == "ok"
