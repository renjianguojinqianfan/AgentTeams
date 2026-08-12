# servevo — 智服：会自我进化的客服 Agent 飞轮

GOAI 2026 · Agent Infra 新智基座赛道参赛作品增量目录。

**零侵入约定**：官方 AgentTeams 源码一律不改，全部增量收敛在本目录；角色人设经 Worker YAML 的 `identity/soul/agents` 字段声明，由 controller 生成 SOUL.md/AGENTS.md。

## 目录规划

```
servevo/
├── README.md            本文件
├── CONTEXT.md           领域词汇表（质检/缺失证据/rubric/置信度）
├── verify.sh            统一质量闸门（make verify：7 模块单测+Skills+Team+密钥+零侵入+闭环诚实性）
├── .githooks/           pre-commit 快速绊线 / pre-push 全量闸门
├── rag/ eval/ coach/ audit/ regression/ registry/ observability/
│                        7 个独立模块（各带 servevo_* 包 + CLI + 单测）
├── knowledge/           product-knowledge/v1（SKILL.md + references/{faq,products,warranty-policy}.md）
├── skills/              四类 Skill 包（各带独立评测入口 skill_test.py）
│   ├── product-knowledge/  qc-standard/  coach-scenario/  regression-verify/
├── team/                yamls/（team.yaml + 4 份 Worker YAML）+ souls/（4 SOUL.md）+ scripts/setup.sh
├── regression/testset/  50 题测试集（cafe-testset-v1.json，含 5 预埋缺口题）
├── scripts/             closedloop_e2e.py（进化闭环 e2e，真 LLM，v1/v2 诚实对照）
├── docs/                规划 v3.2 + P 系列设计 + adr/ + agents/ + Windows踩坑手册 + 开发流程
└── tmp/                 验证快照（答辩证据，不进 git）
```

## 双闭环

- 服务闭环：客服主岗应答，高危操作经质检·审批官审批（职责分离）
- 进化闭环：质检抽检 → 陪练重训+知识修订 → 审批 → 知识包版本发布（Registry 寻址）→ 回归验证 → v1/v2 指标对照

## 归属声明

底座能力迁移自 interview-agent（AGPL-3.0，派生自 Snailclimb/interview-guide，同协议）；AgentTeams 平台源码版权归 agentscope-ai 社区。
