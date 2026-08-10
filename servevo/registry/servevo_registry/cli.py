"""CLI：servevo-registry。

- register --name N --version V --uri file://...
- publish --version V --label stable|canary       发布/灰度（需版本已 is_approved 或 --approve）
- rollback --label stable --to V                   回滚
- approve --id C --status approved|rejected --by X  审批
"""

from __future__ import annotations

import argparse
import sys

from .registry import (
    APPROVED,
    Approval,
    KnowledgeRegistry,
    KnowledgeVersion,
    LABEL_CANARY,
    LABEL_STABLE,
    PENDING,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="servevo-registry")
    sub = p.add_subparsers(dest="cmd", required=True)

    reg = sub.add_parser("register")
    reg.add_argument("--name", required=True)
    reg.add_argument("--version", required=True)
    reg.add_argument("--uri", required=True)
    reg.add_argument("--approved", action="store_true")

    pub = sub.add_parser("publish")
    pub.add_argument("--version", required=True)
    pub.add_argument("--label", choices=[LABEL_STABLE, LABEL_CANARY], default=LABEL_STABLE)
    pub.add_argument("--force", action="store_true", help="跳过审批直接发布（Demo 用）")

    rb = sub.add_parser("rollback")
    rb.add_argument("--label", choices=[LABEL_STABLE, LABEL_CANARY], default=LABEL_STABLE)
    rb.add_argument("--to", required=True)

    app = sub.add_parser("approve")
    app.add_argument("--id", required=True)
    app.add_argument("--status", choices=[APPROVED, "rejected"], required=True)
    app.add_argument("--by", required=True)

    args = p.parse_args(argv)
    reg = KnowledgeRegistry()

    if args.cmd == "register":
        reg.register(KnowledgeVersion(args.version, args.name, args.uri, approved=args.approved))
        print(f"已注册 {args.name}@{args.version} -> {args.uri}")
    elif args.cmd == "publish":
        ver = KnowledgeVersion(args.version, "_", "_", approved=args.force)
        reg.versions[args.version] = ver
        ok = reg.promote(args.version, args.label)
        print(f"{'已' if ok else '未'}发布 {args.version} 到 {args.label}（需审批）" if not args.force
              else f"已发布 {args.version} 到 {args.label}（force）")
        if not ok:
            return 1
    elif args.cmd == "rollback":
        ok = reg.rollback(args.label, args.to)
        print(f"{'已' if ok else '未'}回滚 {args.label} -> {args.to}")
        if not ok:
            return 1
    elif args.cmd == "approve":
        approval = Approval(args.id, "_", "UPDATE", LABEL_STABLE, "_", status=PENDING)
        reg.approvals.append(approval)
        ok = reg.decide_approval(args.id, args.status, args.by)
        print(f"审批 {args.id} = {args.status} (by {args.by})")
        if not ok:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())