# servevo-rag

知识 Skill 包版 RAG 应答（servevo / GOAI 2026 智服参赛）。

> **归属声明**：本模块图结构迁移自
> [interview-agent](https://github.com/)（AGPL-3.0），
> 源项目：`E:\code\interview-agent\interview-agent-python`
> `backend/app/graphs/rag_agent.py` 与 `rag_tools.py` 按 AGPL-3.0 许可适配。
> 完整许可文本见 `LICENSE`（AGPL-3.0）。任何分发须保留本声明。

## 用法

```bash
pip install -e .
servevo-rag query "K2 的保修期是多久？" \
  --kb ../../knowledge/product-knowledge/v1/references
```

## 设计

- 检索：2-gram + BM25 简化 + 路由表加权，零 DB/向量依赖（红线）
- 图：langgraph 单节点线迁原图（analyze → search → evaluate → refine 循环 → answer）
- LLM：Higress OpenAI 兼容通道（env：`LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`），不硬编码

## 验证

```bash
python -m pytest tests/ -v
python scripts/demo_question.sh "K2 保修多久"
```