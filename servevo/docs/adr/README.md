# servevo ADR（架构决策记录）

> 唯一事实源：本目录。规划文档引用 ADR 编号，AGENTS.md 只保留指针。
> 规矩：推翻 ADR 必须写新的 Superseded ADR 并升规划版本号，不静默改。

## 索引

| 编号 | 标题 | 状态 | 日期 | 决策点 |
|---|---|---|---|---|
| [ADR-001](ADR-001-knowledge-consumption.md) | 知识消费方式：R（主动检索 references） | Accepted | 2026-08-09 | R vs C |
| [ADR-002](ADR-002-worker-runtime.md) | Worker 接入：copaw 原生路线 | Accepted | 2026-08-09 | copaw+package vs 自定义镜像 |

## 模板

```markdown
# ADR-NNN-<简短标题>

- **状态**: Proposed | Accepted | Deprecated | Superseded by ADR-XXX
- **日期**: YYYY-MM-DD

## 背景
问题上下文、约束（红线）、备选方案。

## 决策
一至三句可执行的结论。

## 后果
采纳后的正向/负向影响、必须跟进的落地项。

## 证据
实证来源：备忘章节 / 实验命令 / 文件路径。
```

## 规矩

1. 每条 ADR 一个文件，`ADR-NNN-<kebab-case>.md`
2. 每 Session 最多沉淀 1～2 条，有实证才写（证据栏必须非空）
3. 被推翻的 ADR 标 `Superseded by ADR-XXX`，不删除原文