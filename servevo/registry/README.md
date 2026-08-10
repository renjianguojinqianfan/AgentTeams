# servevo-registry

知识 Registry：version+label 寻址 + 发布/灰度/回滚 + 审批流（servevo / GOAI 2026 智服参赛）。

## 设计（对应规划 §4.3）

- **双轨 URI 抽象**：`file://`/`http://` 通道发同一个知识包（Nacos 不在默认部署栈，Demo 用 file://）
- **label 寻址**：`stable` 生产 / `canary` 灰度；回滚 = 切 label（回滚优先于自动化率，四准则）
- **审批流（HITL）**：知识变更 → 提交审批 → 审批通过 → label 提升发布
- 纯函数/轻状态，零外依赖，确定性可复现

## 用法

```bash
servevo-registry register --name product-knowledge --version v1 --uri file://... --approved
servevo-registry publish --version v1 --label stable          # 发布
servevo-registry publish --version v2 --label canary          # 灰度
servevo-registry publish --version v2 --label stable          # 提升稳定
servevo-registry rollback --label stable --to v1              # 回滚
servevo-registry approve --id c1 --status approved --by servevo-qc
```

## 验证

```bash
python -m pytest tests/ -v   # 8 绿（纯函数，无依赖）
```