# servevo — 智服：会自我进化的客服 Agent 飞轮

GOAI 2026 · Agent Infra 新智基座赛道参赛作品增量目录。

**零侵入约定**：官方 AgentTeams 源码一律不改，全部增量收敛在本目录；角色人设经 Worker YAML 的 `identity/soul/agents` 字段声明，由 controller 生成 SOUL.md/AGENTS.md。

## 目录规划

```
servevo/
├── README.md            本文件
├── deploy/              team.yaml + 4 份 Worker YAML（leader/cs/qc/coach，共用官方 copaw 镜像）
├── image/               兜底预案（自定义镜像仅当需预装系统依赖时启用；默认不用，见 docs/P2.2）
│   └── graphs/          迁移自底座的三图：rag / evaluation / adaptive
├── skills/              四类 Skill 包（各带独立评测入口 skill_test.py）
│   ├── product-knowledge/
│   ├── qc-standard/
│   ├── coach-scenario/
│   └── regression-verify/
├── data/                50 题测试集 + 星辰咖啡机合成数据集 + 知识包 v1
├── docs/                架构/审计/部署说明（引用《Windows部署踩坑手册》）
└── scripts/             setup.sh 一键建队 + v1/v2 量化对照脚本
```

## 双闭环

- 服务闭环：客服主岗应答，高危操作经质检·审批官审批（职责分离）
- 进化闭环：质检抽检 → 陪练重训+知识修订 → 审批 → 知识包版本发布（Registry 寻址）→ 回归验证 → v1/v2 指标对照

## 归属声明

底座能力迁移自 interview-agent（AGPL-3.0，派生自 Snailclimb/interview-guide，同协议）；AgentTeams 平台源码版权归 agentscope-ai 社区。
