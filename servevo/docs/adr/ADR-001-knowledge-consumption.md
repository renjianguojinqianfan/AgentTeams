# ADR-001-知识消费方式

## 状态
- **状态**: Accepted
- **日期**: 2026-08-09

## 背景

P2.4 知识包 file:// 注入后，product-knowledge 落在两个位置：
- **standard 区** `skills/`（AgentTeams 注入的技能仓库，7 技能）
- copaw 工作区 `skills/` 目录（内置技能池 15 个，注入技能**不镜像**）

因此产生两个候选知识消费方式：
- **R 方案**：agent 按需主动检索 standard 区 references/
- **C 方案**：把知识复制进工作区内置池，强行入 agent 视野

约束：不引入 pgvector 等重依赖；知识库=文件型知识 Skill（MinIO 版本目录）。

## 决策
**采用 R 方案**：知识消费 = agent 主动检索 references/。C 方案不采用。

## 证据（P2.2 备忘 §5.3，2026-08-09）
1. 实证：经 Matrix API 向 cs-demo 提问虚构产品"PHONE-"保修期，agent 自主查阅知识库答"无此产品"并列出真实型号 K1/K2 —— 无幻觉否定，证明 references 可被读取
2. 注册证据：`.copaw/workspaces/default/skill.json` 7 技能 source=customized 含 product-knowledge（manifest 注册制，目录不镜像）
3. 链路证据：message→session 落盘 `.copaw/workspaces/default/sessions/`

## 后果
+ 知识与内置技能零耦合，AgentTeams 注入管线原样可用
+ P3.1 只需补检索节点（keyword 优先，绕 pgvector 红线），不需要复制管线
- 知识命中依赖 agent 主动检索的"念头"——必须在 SOUL/AGENTS 显式声明检索义务（P3 落地项）
- 版本一致性已复核（2026-08-09 上午）：MinIO / 容器 standard 区 / 本地 v1 三区均为 SKILL.md(927B) + 3 references，内容互为一致（此前"6 refs"为状态误判）——后续任何一侧增删须走 P3.4 知识包版本通道回归