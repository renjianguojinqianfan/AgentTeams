# servevo-audit

审计/台账模块（servevo / GOAI 2026 智服参赛）：产物归档 + 审计链 + 指标 jsonl。

> **归属声明**：存储设计参考 interview-agent `infrastructure/storage/s3.py`（AGPL-3.0），
> 源项目：`E:\code\interview-agent\interview-agent-python`。本地文件后端为
> servevo 自建等价物（MinIO 不可达时同契约降级，见 AGENTS.md「双基座叙事」）。

## 用法

```bash
pip install -e .

# 本地后端（host 可验证，默认）
servevo-audit ledger v1 --solved 8 --escalated 2 --total 10 --qc 76.5 --reg-pass 10 --reg-total 10
servevo-audit record qc.report approve servevo-qc --payload '{"session":"s1"}'

# MinIO 后端（生产）：设 S3_ENDPOINT 等环境变量后同上
```

## 设计

- **Storage 双后端**：LocalStorage（默认，`SERVEVO_STORAGE_DIR`）/ MinioStorage（S3 兼容，`S3_*` env）
- **AuditLog**：追加式 jsonl 审计链，每条含 ts/event/action/actor/payload/hash（sha256）
- **MetricsLedger**：按知识包版本的指标 jsonl 时序；`resolution_metrics` 聚合解决率/转人工率/质检分/回归通过率
- **红线**：key 不硬编码（env 注入）；路径穿越防护；MinIO 不可达时本地等价物同契约

## 验证

```bash
python -m pytest tests/ -v
```

P3.4 验收口径：产物+审计+指标 jsonl 落存储（host 用本地后端，MinIO creds 已用 mc 实测可达）。