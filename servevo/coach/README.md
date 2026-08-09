# servevo-coach

陪练官（servevo / GOAI 2026 智服参赛）：刁钻客户陪练 + 知识修订草案 + 回归测试执行。

> **归属声明**：本模块陪练图结构迁移自
> [interview-agent](https://github.com/)（AGPL-3.0），
> 源项目：`E:\code\interview-agent\interview-agent-python`
> `backend/app/graphs/adaptive_interview.py`、`tools/interview_tools.py`、
> `domain/services/adaptive_strategy.py` 按 AGPL-3.0 许可适配。
> 完整许可文本见 `LICENSE`（AGPL-3.0）。任何分发须保留本声明。

## 用法

```bash
pip install -e .

# 陪练模式（LLM 驱动出剧本 + 评估主岗应答）
servevo-coach run --mode coach --kb ../../knowledge/product-knowledge/v1/references --json

# 回归模式（跑预置测试集，判通过）
servevo-coach run --mode regression --kb ../../knowledge/product-knowledge/v1/references \
  --cases scripts/regression_cases.json --json
```

## 设计

- 图：ReAct 循环（init_context → agent_loop ↔ [execute_tool → merge] → finalize），带回边真 Agent 循环
- 工具：generate_scenario / evaluate_answer / lookup_reference / adjust_strategy
- 双模式：coach（刁钻客户陪练）/ regression（预置测试集回归）
- 可审计：decision_trace 记录每步决策
- HITL：approval_mode 开启时剧本出题 interrupt 等待审批（对应房间审批消息）
- LLM：Higress OpenAI 兼容通道（env，不硬编码）（复用 servevo_eval.llm）
- 知识：复用 servevo_rag.knowledge（文件型，绕 pgvector 红线）

## 验证

```bash
python -m pytest tests/ -v
```