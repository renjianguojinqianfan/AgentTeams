# servevo Team（3 职能 + Leader）

智服客服进化团队：平台原生声明式建队（P4.1/P4.2/P4.5b）。

## 角色（4 Worker）

| Worker | 角色 | 职责 | SOUL |
|---|---|---|---|
| servevo-leader | team_leader | 分诊派单、触发进化、汇报 | `souls/servevo-leader-SOUL.md` |
| servevo-cs | worker | RAG 应答、高危操作发起审批 | `souls/servevo-cs-SOUL.md` |
| servevo-qc | worker | 抽检评分、高危/知识变更审批 | `souls/servevo-qc-SOUL.md` |
| servevo-coach | worker | 陪练剧本、知识修订、回归测试 | `souls/servevo-coach-SOUL.md` |

## 文件

- `yamls/team.yaml`：Team CR（恰一个 team_leader + 3 worker + 人类 coordinator）
- `yamls/servevo-{leader,cs,qc,coach}.yaml`：Worker CR（identity/soul/agents 声明人设）
- `souls/*-SOUL.md`：4 角色人设
- `scripts/setup.sh`：一键建队

## 双闭环编排（P4.1）

- **服务闭环**：客户 → Leader 分诊 → servevo-cs 应答 → 高危发起 servevo-qc 审批
- **进化闭环**：servevo-qc 质检缺口 → servevo-coach 陪练重训 + 知识修订草案 → servevo-qc 审批 → registry 发布 v2 → regression-verify 回归复测 → Leader 汇报指标

## 一句话启动全流程

> "客户咨询 K2 保修期，请 servevo-cs 应答；若质检发现缺口，触发进化闭环并汇报指标。"

## 建队

```bash
bash servevo/team/scripts/setup.sh   # 需 agt 可用（Docker 运行中）
```

## 验证

```bash
bash servevo/verify.sh   # 全量闸门（含 Skills 评测）
```