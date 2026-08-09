---
name: product-knowledge
description: 查询星辰咖啡机（Star Coffee）产品线、保修政策、退换货政策、常见故障处理的标准知识。在处理客户关于产品参数、价格、保修、退换货、故障咨询时，必须先查本技能 references 后再回答。
version: 1.0.0
label: v1
---

# 星辰咖啡机产品知识（v1）

本技能是客服应答的知识依据，全部事实以 `references/` 内文档为准。回答客户前必须检索对应文档，禁止凭记忆作答。

## 使用流程

1. 判断客户问题类型：产品参数（`references/products.md`）／保修（`references/warranty-policy.md`）／退换货（`references/warranty-policy.md`）／故障处理（`references/faq.md`）
2. 检索对应文档，引用原文事实
3. 不确定或查不到 → 明确告知客户"需要转人工核实"，禁止编造

## 版本

- v1（本版本）：初始知识基线
