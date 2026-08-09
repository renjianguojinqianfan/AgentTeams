# ADR-002-Worker接入方式：copaw 原生路线

## 状态
- **状态**: Accepted
- **日期**: 2026-08-09（决策于 P2.2，归档于此）

## 背景
P2.2 实测 Worker 两条接入路线：
- **A）copaw runtime + --package 技能包**：官方 worker 镜像 + identity/soul/agents 字段声明人设 + skills 注入
- **B）自定义 image**：自建镜像装载角色代码与知识

约束：官方源码零侵入（不改 install/ 脚本），知识可版本化、可灰度回滚。

## 决策
**采用 A 路线**：copaw 原生 runtime + `--package` 技能包 + Worker YAML 人设字段；B 保留为兜底（不实施）。

## 证据（P2.2-Worker接入方式对比备忘.md）
1. P2.4 实测：zip（`skills/product-knowledge/...` 布局）→ `agt create worker --package file:///tmp/import/...` → MinIO → 容器三层落地 ✅
2. copaw 启动 2/2 agents，AgentConfigWatcher 运行中；工作区 SOUL.md/AGENTS.md 灌入
3. 关键机制已实证：manifest 注册（见 ADR-001）

## 后果
+ 零侵入红线保持，官方升级可持续跟随
+ demo 路线 = 每角色一份 Worker YAML（identity/soul/agents 字段），controller 生成 SOUL/AGENTS 进 workspace，entrypoint 读定角色 → P4 team.yaml/setup.sh 直接复用
- copaw 依赖注入包布局约定（skills/ 前缀），知识包制作须遵守 zip 布局（P2.2 §6 复现段）
- Worker 模型切换必须 `agt update worker/managers --model`（数据卷残留旧模型，踩坑手册红线）