"""S3 Ledger. Objects are private, encrypted, and addressed by hash."""

import json
import time

_HEX = __import__("re").compile(r"^[a-f0-9]{64}$")


class S3Ledger:
    backend = "s3"

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str,
        ttl_seconds: int,
        region: str,
        expected_owner: str = "",
        client=None,
    ) -> None:
        self.bucket = bucket
        self.prefix = prefix if prefix.endswith("/") else f"{prefix}/"
        self.ttl_seconds = ttl_seconds
        self.region = region
        self.expected_owner = expected_owner
        self._client = client

    def client(self):
        if self._client is None:
            import boto3
            from botocore.config import Config

            self._client = boto3.client(
                "s3",
                region_name=self.region,
                config=Config(connect_timeout=2, read_timeout=3, retries={"max_attempts": 2}),
            )
        return self._client

    def probe(self) -> None:
        self.client().head_bucket(Bucket=self.bucket, **self._owner())

    def get(self, key: str) -> dict | None:
        from botocore.exceptions import ClientError

        try:
            obj = self.client().get_object(Bucket=self.bucket, Key=self._object_key(key), **self._owner())
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"NoSuchKey", "404", "NotFound"}:
                return None
            raise
        payload = json.loads(obj["Body"].read())
        if payload["expires_at"] <= time.time():
            return None
        return payload["value"]

    def set(self, key: str, value: dict) -> None:
        body = json.dumps({"expires_at": time.time() + self.ttl_seconds, "value": value}).encode()
        self.client().put_object(
            Bucket=self.bucket,
            Key=self._object_key(key),
            Body=body,
            ContentType="application/json",
            ServerSideEncryption="AES256",
            **self._owner(),
        )

    def _object_key(self, key: str) -> str:
        if not _HEX.fullmatch(key):
            raise ValueError("cache key must be a sha256 hex digest")
        return f"{self.prefix}{key}"

    def _owner(self) -> dict:
        if not self.expected_owner:
            return {}
        return {"ExpectedBucketOwner": self.expected_owner}
