"""CLI：servevo-audit record|ledger|artifact。

- record <event> <action> <actor> [--payload json]     记一条审计
- ledger <version> --solved N --escalated N --total N --qc X --reg-pass N --reg-total N   记指标台账
- artifact <key> <file>                                 归档一个文件到存储
"""

from __future__ import annotations

import argparse
import json
import sys

from .audit import AuditLog
from .ledger import MetricsLedger, resolution_metrics
from .storage import LocalStorage, MinioStorage, create_storage, json_bytes


def _parse_payload(text: str | None) -> dict:
    if not text:
        return {}
    return json.loads(text)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="servevo-audit")
    sub = p.add_subparsers(dest="cmd", required=True)

    st = sub.add_parser("record", help="记一条审计")
    st.add_argument("event")
    st.add_argument("action")
    st.add_argument("actor")
    st.add_argument("--payload", default=None)
    st.add_argument("--artifact", default=None)

    lg = sub.add_parser("ledger", help="记一条指标台账")
    lg.add_argument("version")
    lg.add_argument("--solved", type=int, default=0)
    lg.add_argument("--escalated", type=int, default=0)
    lg.add_argument("--total", type=int, default=0)
    lg.add_argument("--qc", type=float, default=0.0)
    lg.add_argument("--reg-pass", type=int, default=0)
    lg.add_argument("--reg-total", type=int, default=0)

    ar = sub.add_parser("artifact", help="归档一个文件")
    ar.add_argument("prefix")
    ar.add_argument("filename")

    args = p.parse_args(argv)

    storage: LocalStorage | MinioStorage = create_storage()

    if args.cmd == "record":
        rec = AuditLog(storage).append(
            event=args.event, action=args.action, actor=args.actor,
            payload=_parse_payload(args.payload), artifact_ref=args.artifact,
        )
        print(json.dumps(rec, ensure_ascii=False, indent=2))
    elif args.cmd == "ledger":
        m = resolution_metrics(args.solved, args.escalated, args.total, args.qc, args.reg_pass, args.reg_total)
        rec = MetricsLedger(storage).append(args.version, m)
        print(json.dumps(rec, ensure_ascii=False, indent=2))
    elif args.cmd == "artifact":
        key = LocalStorage.generate_key(args.prefix, args.filename)
        data = json_bytes({"placeholder": True, "filename": args.filename})
        info = storage.upload(data, key)
        print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())