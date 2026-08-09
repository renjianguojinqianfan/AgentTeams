"""产物存储：本地文件系统（默认）或 MinIO（S3 兼容）双后端。

环境变量（不硬编码）：
- 后端选择：S3_ENDPOINT 非空 → MinIO；否则 → 本地目录（SERVEVO_STORAGE_DIR 或 tmp）
- MinIO：S3_ENDPOINT / S3_ACCESS_KEY / S3_SECRET_KEY / S3_BUCKET / S3_REGION
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_STORAGE_DIR = "tmp/servevo-storage"


def _sanitize(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._\-]", "_", text)


def compute_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class LocalStorage:
    """本地文件系统存储（默认，host 侧可验证，零外依赖）。"""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or os.environ.get("SERVEVO_STORAGE_DIR", _STORAGE_DIR))
        self.root.mkdir(parents=True, exist_ok=True)

    def _key_path(self, key: str) -> Path:
        # 防路径穿越
        safe = key.lstrip("/").replace("\\", "/")
        p = (self.root / safe).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise ValueError(f"非法存储 key: {key}")
        return p

    def upload(self, data: bytes, key: str) -> dict[str, Any]:
        p = self._key_path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return {"key": key, "size": len(data), "sha256": compute_hash(data)}

    def download(self, key: str) -> bytes:
        return self._key_path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._key_path(key).exists()

    def delete(self, key: str) -> None:
        p = self._key_path(key)
        if p.exists():
            p.unlink()

    @staticmethod
    def generate_key(prefix: str, filename: str) -> str:
        date = datetime.now(UTC).strftime("%Y/%m/%d")
        uid = uuid.uuid4().hex[:12]
        return f"{prefix}/{date}/{uid}_{_sanitize(filename)}"


class MinioStorage:
    """MinIO（S3 兼容）存储。"""

    def __init__(self, endpoint: str | None = None, bucket: str | None = None) -> None:
        import boto3  # 惰性导入

        self.endpoint = endpoint or os.environ.get("S3_ENDPOINT", "http://127.0.0.1:9000")
        self.bucket = bucket or os.environ.get("S3_BUCKET", "agentteams-storage")
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY", "admin"),
            aws_secret_access_key=os.environ.get("S3_SECRET_KEY", ""),
            region_name=os.environ.get("S3_REGION", "us-east-1"),
        )

    def upload(self, data: bytes, key: str) -> dict[str, Any]:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)
        return {"key": key, "size": len(data), "sha256": compute_hash(data)}

    def download(self, key: str) -> bytes:
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


def create_storage() -> LocalStorage | MinioStorage:
    """按环境变量选择后端。"""
    if os.environ.get("S3_ENDPOINT"):
        return MinioStorage()
    return LocalStorage()


def json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")