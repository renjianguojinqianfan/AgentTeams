"""CLI：servevo-obs status | emit。

- status：显示当前观测模式（cloud/local/none）与 CMS 配置检查
- emit：发一条指标/日志（自建等价物）
"""

from __future__ import annotations

import argparse
import sys

from .cms import load_cms_config, mode
from .emitter import Observability


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="servevo-obs")
    sub = p.add_subparsers(dest="cmd", required=True)

    st = sub.add_parser("status")
    e = sub.add_parser("emit")
    e.add_argument("--name", required=True)
    e.add_argument("--value", type=float, required=True)
    e.add_argument("--tag", action="append", default=[])

    args = p.parse_args(argv)
    cfg = load_cms_config()

    if args.cmd == "status":
        print(f"观测模式: {mode(cfg)}")
        print(f"云接入: {'是' if cfg.cloud_connected else '否（用自建等价物，OTLP 同契约）'}")
        print(f"已配置 env: {cfg.configured_vars or '无'}")
        return 0

    obs = Observability(cfg)
    tags = dict(t.split("=", 1) for t in args.tag if "=" in t)
    obs.emit_metric(args.name, args.value, tags)
    print(f"已上报指标 {args.name}={args.value} (mode={obs.mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())