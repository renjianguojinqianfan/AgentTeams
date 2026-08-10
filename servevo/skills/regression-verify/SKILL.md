---
name: regression-verify
description: 测试集执行与指标采集：50 题预置测试集跑 v1/v2，输出量化对照报告（解决率/转人工率/质检分/回归通过率 + 缺失证据）。进化闭环的验证总入口。
version: 1.0.0
label: v1
eval: skill_test.py   # 独立评测入口：自测（对已知答案集）
---

# 回归验证（regression-verify）

## 用途

一键跑完 50 题测试集 → 输出 v1/v2 对比报告（总入口）。对应规划 §5 量化对照与进化闭环回归复测。

## 输入 / 输出

- **输入**：知识包版本（v1/v2 的 references 目录）
- **输出**：量化对照报告（解决率 / 转人工率 / 质检分 / 回归通过率 / 缺口题 + 缺失证据段）

## 规格块（v3.1）

- **输入**：测试集 + 知识包版本
- **输出**：指标对比报告 + 逐题结果
- **失败处理**：某题生成失败 → 计未解决 + 缺失证据；测试集校验失败 → 拒绝运行
- **安全边界**：测试集固定入库（确定性，不赌 LLM）；指标口径单一函数
- **多 Agent 协同**：Leader 触发进化后由本 Skill 跑回归复测；servevo-qc 审批发布后复跑

## 实现

在 `servevo/regression/`（testset + runner + compare），测试集在 `servevo/regression/testset/cafe-testset-v1.json`。