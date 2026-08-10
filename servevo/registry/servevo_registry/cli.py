"""CLI：servevo-registry（含持久化，重启恢复发布/回滚/审批状态）。

- register --name N --version V --uri file://...
- publish --version V --label stable|canary --force     发布/灰度
- rollback --label stable --to V                        回滚
- approve --id C --version V --status approved|rejected --by X  审批
每次命令 load -> 操作 -> save（状态落盘，MED6）。
"""

from __future__ import annotations

import argparse
import sys

from .persistence import FileStorage, load_registry, save_registry
from .registry import (
    APPROVED,
    Approval,
    KnowledgeRegistry,
    KnowledgeVersion,
    LABEL_CANARY,
    LABEL_STABLE,
    PENDING,
)

_DEFAULT_KEY = "registry/state.json"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="servevo-registry")
    p.add_argument("--store", default=_DEFAULT_KEY, help="持久化存储 key")
    p.add_argument("--dir", default="tmp/servevo-registry", help="本地存储根目录")
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
    app.add_argument("--version", default="")
    app.add_argument("--status", choices=[APPROVED, "rejected"], required=True)
    app.add_argument("--by", required=True)

    args = p.parse_args(argv)
    store = FileStorage(root=args.dir)
    r = load_registry(store, args.store)

    if args.cmd == "register":
        r.register(KnowledgeVersion(args.version, args.name, args.uri, approved=args.approved))
        print(f"已注册 {args.name}@{args.version} -> {args.uri}")
    elif args.cmd == "publish":
        # 未注册的版本先落一个占位；--force 视为已批准（强制发布）
        if args.version not in r.versions:
            r.versions[args.version] = KnowledgeVersion(args.version, "_", "_", approved=args.force)
        if args.force:
            # 无论是否已注册，force 都强制置为已批准再发布（覆盖已注册未审批情况）
            r.versions[args.version] = KnowledgeVersion(
                version=r.versions[args.version].version,
                name=r.versions[args.version].name,
                uri=r.versions[args.version].uri,
                section_root=r.versions[args.version].section_root,
                approved=True,
                label=r.versions[args.version].label,
            )
        ok = r.promote(args.version, args.label, approval=None if args.force else r.approved_for(args.version))
        if not ok and not args.force:
            print(f"未发布 {args.version} 到 {args.label}（需先审批或 --force）")
            save_registry(r, store, args.store)
            return 1
        print(f"已发布 {args.version} 到 {args.label}" + ("（force）" if args.force else ""))
    elif args.cmd == "rollback":
        ok = r.rollback(args.label, args.to)
        print(f"{'已' if ok else '未'}回滚 {args.label} -> {args.to}")
        if not ok:
            save_registry(r, store, args.store)
            return 1
    elif args.cmd == "approve":
        version = args.version or r.current(LABEL_STABLE) or "_"
        approval = Approval(args.id, version, "UPDATE", LABEL_STABLE, "_", status=PENDING)
        r.approvals.append(approval)
        ok = r.decide_approval(args.id, args.status, args.by)
        print(f"审批 {args.id} = {args.status} (by {args.by})")
        if not ok:
            save_registry(r, store, args.store)
            return 1

    save_registry(r, store, args.store)
    return 0


if __name__ == "__main__":
    sys.exit(main())
