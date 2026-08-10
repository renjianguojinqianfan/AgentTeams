# servevo-regression

回归测试集 + v1/v2 量化对照（servevo / GOAI 2026 智服参赛）。

## 内容

- `testset/cafe-testset-v1.json`：50 题预置测试集（产品/保修/退换货/政策/故障），含 5 题预埋缺口题（政策已更新但 v1 知识未同步）
- `compare.py`：v1/v2 指标对比（纯函数，确定性可复现）
- `runner.py`：用 servevo_rag 主岗跑测试集，产出聚合指标（resolved/转人工/质检分/缺口检测）

## 用法

```bash
# 校验测试集
servevo-regression validate testset/cafe-testset-v1.json

# 对比 v1/v2 指标（需先跑出 v1/v2 台账）
servevo-regression compare --v1 v1.json --v2 v2.json
```

## 设计

- 确定性（规划 §5）：测试集固定入库，v1/v2 差异 = 知识包版本 diff，不赌 LLM
- 缺口题：v1 知识未同步 → 无来源 → resolved=False → 计入 gap_detected（缺失证据段）
- 指标：解决率↑ / 转人工率↓ / 质检分↑ / 回归通过率（对应 §5 量化对照）

## 验证

```bash
python -m pytest tests/ -v   # 8 绿（fake LLM，无 Docker/网络）
```