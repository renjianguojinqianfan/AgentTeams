# servevo 一键质量门禁（servevo 内 Makefile，不触碰官方）。
# 用法：在 servevo/ 目录下 `make verify`；或从仓库根 `make -C servevo verify`。
.PHONY: verify test

# 统一质量闸门：4 模块单测 + 密钥枯死 + 零侵入核对（对应 make verify）
verify:
	bash verify.sh

# 快速单测（hook pre-commit 用，跳过密钥/零侵入重量检查）
test:
	SERVEVO_FAST=1 bash verify.sh