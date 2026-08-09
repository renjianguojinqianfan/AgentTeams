# servevo-eval

质检评估子图（servevo / GOAI 2026 智服参赛）：客服会话质检评分 + 缺失证据段。

> **归属声明**：本模块评估图结构迁移自
> [interview-agent](https://github.com/)（AGPL-3.0），
> 源项目：`E:\code\interview-agent\interview-agent-python`
> `backend/app/graphs/evaluation.py` 及其 domain/infrastructure 依赖按 AGPL-3.0 许可适配。
> 完整许可文本见 `LICENSE`（AGPL-3.0）。任何分发须保留本声明。

## 用法

```bash
pip install -e .

# 质检一个会话（qa 为 JSON 文件：{"session_id":..., "records":[{question,category,user_answer}]}）
servevo-eval evaluate --qa qa.json --kb ../../knowledge/product-knowledge/v1/references --json
```

## 设计

- 图：fan-out 批评估（prepare → Send(evaluate_batch×N, 信号量并发) → merge → summarize → build_report），沿用源两级降级
- 维度：客服质检 rubric（准确性/完整性/合规安全/服务态度/效率），写入 `prompts/*.st`
- 报告：总体分 + 分类分 + 逐题分 + **缺失证据段**；低置信/解析失败 → 只标注不评分 + 标记需人工复核
- LLM：Higress OpenAI 兼容通道（env：`LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`），不硬编码
- 知识基线：复用 `servevo_rag.knowledge.load_knowledge` 生成 reference 上下文（DRY）

## 验证

```bash
python -m pytest tests/ -v
python scripts/demo_eval.sh
```