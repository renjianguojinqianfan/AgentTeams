# 客服进化飞轮 × AgentTeams 复赛详细规划

> 版本 v3.2 · 2026-08-08 · v3.2 变化：Worker 接入改为平台原生声明式（共用镜像+每角色 YAML 的 identity/soul/agents，§4.1/4.2）、§7 四个 Skill 独立演示动作、§5 人机回环效率指标、§1.1 答辩差异化一句话、P0/P1 标记完成
> 版本 v3.1 · 2026-08-07 · v3.1 变化：AgentLoop 升为"持续进化"维度正式映射（§4.4，官方原文核实）、可观测三类数据映射（§2）、Skill 规格补字段（§7）、工具契约 MCP 兼容声明（§3）
> v3.0 变化：五角色收敛为三角色（防拼盘）、新增量化对照演示设计、四条工程准则、Registry 知识版本化双轨
> GOAI Agent Infra 新智基座赛道 · 复赛提交截止 9/3 · 初赛材料截止 **8/16**
> 基座仓库：https://github.com/agentscope-ai/AgentTeams · 参赛 fork：https://github.com/renjianguojinqianfan/AgentTeams（servevo 分支）· 本地部署已全链路验证（见《Windows部署踩坑手册.md》）
> 作品名：**智服 ZhiFu**（8/7 用户确认，简介/报名表/PPT 已同步）

---

## 0. 一句话定位（答辩/PPT 统一口径）

> **一个客服 Agent 的进化飞轮——质检/审批官保证闭环可信，陪练官保证闭环会进化，全部能力沉淀为可复用 Skill。**

命中四个得分面：多 Agent 协同（职责分离）· Skill 工程（评测/调优技能包）· 持续进化（AgentLoop 观测叙事）· 运行验证（v1/v2 量化对照）。

> **AgentLoop 口径（v3.1 修正）**：官方公告原文——赛道从"团队协同、可验证可回滚、持续进化"三个维度考察，分别对应 AgentTeams 协同底座与 **AgentLoop 观测评估飞轮**两大基础设施。因此 AgentLoop 不是可选增强项，而是"持续进化"维度的官方映射，所有材料（架构图/答辩）必须体现。注意：AgentLoop 是**阿里云产品**（ARMS 底座），非可 clone 的开源仓库；AgentTeams 已内置接入钩子（`AGENTTEAMS_CMS_*` 一组环境变量走 OTLP 上报，需云上 workspace+license key），详见 §4.4。

---

## 1. 场景定义与立项故事

### 1.1 立项故事（PPT 开场叙事）

- Klarna AI 客服先替代 700 名人工坐席，后因服务质量问题重新回招人工——**没有质检与进化闭环的 AI 客服不可持续**（调研 01 号报告）
- 行业现状：人工质检覆盖率 <5%、漏检 15–25%；竞品（Fin/Sierra/Decagon/得助）要么只拼解决率，要么质检陪练只针对人工坐席
- **市场空白点：训练对象是 AI Agent 自身的"质检→陪练→自进化"闭环**
- 答辩一句话差异点（反复强化）：**"别人的质检和陪练是给人用的，智服的质检和陪练是给 AI 用的——我们解决的不是'人如何管好 AI'，而是'AI 如何自己管好自己'。"**
- 官方四个参考方向含"智能客服自主闭环"——方向命中，但同向队伍必多，差异化=进化环的工程化（量化对照 + Registry 版本化），PPT 必须前置回答"和其他客服队有什么不同"

### 1.2 双闭环设计（PPT 画"环"不画"清单"）

```
服务闭环（保可信）：
客户会话 → 客服主岗(RAG应答) ──常规→ 直接回复（会话留痕）
                        └─高危操作/超权限→ 质检·审批官审批(HITL) → 执行 → 回复客户

进化闭环（保会进化）：
会话 transcripts → 质检·审批官(抽检评分+rubric) → 薄弱点报告(bad cases)
  → Leader 触发进化 → 陪练官(生成陪练剧本让主岗重练 + 知识修订草案)
  → 质检·审批官审批(HITL，版本化可回滚) → 知识包 v2 发布(Registry label 切换)
  → 回归复测(50题预置测试集) → 指标对比(v1 vs v2) → 归档审计
```

### 1.3 角色收敛说明（v3.0 关键决策）

五角色方案（前线/升级专家/质检/陪练 + Leader）已废弃：官方提示"小闭环胜过功能庞杂大平台"，角色数量不是得分点，**双闭环结构才是**。收敛为 3 职能 + Leader：

| 角色 | 职责 | 吸收的旧职能 |
|---|---|---|
| servevo-leader | 协调官：接单分派、触发进化、汇报 | 原 Leader |
| servevo-cs（客服主岗） | 执行：RAG 应答、高危操作发起审批 | 原前线客服 + 升级专家（升级故事线降级为口头举例） |
| servevo-qc（质检·审批官） | 审计：抽检评分、高危操作与知识变更审批 | 原质检官 + 审批职能 |
| servevo-coach（陪练官） | 进化：陪练剧本、知识修订草案、回归测试 | 原陪练官 + Agent 评测工厂理念 |

---

## 2. 评分维度对齐

| 评分维度 | 权重 | 本方案落点 |
|---|---:|---|
| 场景价值与行业可复制性 | 25% | 客服是普适刚需；换一份产品知识包=换一家企业；Skill 跨行业可迁移 |
| 多 Agent 协同与自主闭环 | 25% | 3+1 角色双闭环；进化由 Leader 自主编排，人类只审批关键决策（职责分离=合规刚需叙事） |
| Skill 工程体系与生态复用 | 25% | 四类 Skill 包全部带**独立评测入口**（rubric+用例集）；知识即 Skill，走 Registry |
| 工程落地与运行验证及安全审计 | 20% | **v1/v2 量化对照**+回滚优先于自动化率+报告强制"缺失证据"段+全链路归档 MinIO；可观测三类数据全覆盖（Trace=Matrix回放/Metrics=v1v2台账/Log=MinIO，见 §4.4） |
| 开放与开源贡献 | 5% | fork 公开 + Skill 包可独立复用 + 合成数据集与测试集开源 |

---

## 3. 四条工程设计准则（v3.0 新增，源自赛道导师公开工程判断）

1. **Mock 与真实工具同一 Schema 契约**——工单系统/CRM 的 mock 与真实实现共用同一接口定义，评委问"能接真系统吗"→"换实现不换契约"；契约按 MCP 工具同构设计（name/入参 schema/错误码），后续迁移 MCP 仅需协议适配（AgentTeams 经 Higress 原生支持 MCP 注册，v1.0.6 起）
2. **每个 Skill 可独立评测**——质检/陪练/知识/回归四个 Skill 各带可运行评测入口（rubric + 用例集），Skill 维度得分面直接拉满
3. **报告强制包含"缺失证据"段**——所有质检/进化报告写明"本次因缺什么数据未能验证什么"，主动暴露局限=可信度加分
4. **可回滚性优先于自动化率**——叙事顺序：先讲知识版本回滚能力，再讲自动调优

---

## 4. 总体架构

### 4.1 部署视图

```
Human×2：客户（模拟）· 客服主管（审批/插话）
   │  Element Web
Manager（平台标准，不改）
   ▼
servevo-team
   ├── servevo-leader   协调官（Team Leader）：分诊派单、触发进化、汇报
   ├── servevo-cs       客服主岗：RAG 应答 + 高危操作报批（复用 rag_agent 图）
   ├── servevo-qc       质检·审批官：rubric 评分 + HITL 审批（复用 evaluation 图）
   └── servevo-coach    陪练官：陪练剧本 + 知识修订 + 回归（复用 adaptive_interview 图）
基础设施（官方自带）：Tuwunel(Matrix) · Higress(LLM网关) · MinIO(共享文件/证据) · controller
```

- 4 个自建 Agent **共用同一镜像，角色按平台原生方式声明**：每角色一份 Worker YAML，通过 `identity/soul/agents` 字段定义人设；controller 据此生成 SOUL.md/AGENTS.md（含团队协调上下文注入，源码已核实 `agentconfig/`）并同步进 workspace，entrypoint 读取定角色——声明式管理、可独立扩缩容；`SERVEVO_ROLE` 仅作镜像内部实现兜底
- 委派边界遵循官方：Manager 只与 Leader 通信；Worker 房间权限对齐 groupAllowFrom
- **本地已实测**：embedded 栈（controller+manager+worker）全链路跑通，Worker 经 Matrix 收发消息、LLM 走网关（踩坑细节见《Windows部署踩坑手册.md》）

### 4.2 技术选型

| 项 | 选型 | 理由 |
|---|---|---|
| 接入 | 自定义 image（共用）+ 每角色 Worker YAML（identity/soul/agents 声明人设） | 平台原生声明式路径，controller 生成 SOUL.md/AGENTS.md；零侵入源码；本地已验证 agt create worker |
| IM | matrix-nio（若走自定义 image）/ copaw runtime（若走 package） | P2 实测后定夺 |
| 编排 | 保留 LangGraph 三图（rag/evaluation/adaptive） | 资产复用最大化 |
| 知识库 | **知识即 Skill**：Q&A 条目打包为 Skill，Registry 版本化 | 落入官方 STS 管辖域（skill/*），天然接入发布/灰度/回滚叙事 |
| LLM | langchain_openai → Higress 网关 | 凭证零暴露；免费额度模型策略见 §10 风险表 |

### 4.3 知识版本化与 Registry（双轨）

官方机制已核实（v1.1.2+）：包寻址支持 `nacos://host:8848/ns/pkg/v1` 与 `label:latest` 双模式，STS 资源域 `skill/*`、`agentSpec/*`——**version+label 就是现成的发布/灰度/回滚机制**。

| 轨 | 用途 | 做法 |
|---|---|---|
| 叙事轨（PPT/答辩） | 工程差异化："平台亲儿子" | 知识包走 Registry：`servevo-kb:stable` 生产 / `servevo-kb:canary` 灰度 / 回滚=切 label；审批=label 提升 |
| 演示轨（Demo 保底） | 复赛 Demo 必跑通 | Nacos 不在默认部署栈，Demo 用 `file://`/`http://` 通道发同一个包（URI 统一抽象），Nacos 接通是加分项不是前提 |

### 4.4 AgentLoop 观测接入（"持续进化"维度的官方映射）

**事实核查结论（2026-08-07）**：
- 官方公告原文：三维度分别对应 AgentTeams 与 AgentLoop 两大基础设施——AgentLoop 是正式评分映射，不是加分项
- 但 AgentLoop 本体是**阿里云产品**（CMS 2.0/ARMS 底座），无可 clone 的开源仓库；落地路径=AgentTeams 官方文档 `docs/cms-integration.md`（v1.0.9+）：OTLP 协议上报 Trace+Metrics，配置 `AGENTTEAMS_CMS_TRACES_ENABLED / AGENTTEAMS_CMS_ENDPOINT / AGENTTEAMS_CMS_LICENSE_KEY / AGENTTEAMS_CMS_WORKSPACE / AGENTTEAMS_CMS_SERVICE_NAME` 一组环境变量即可，Manager 与全部 Worker 自动接入

**分阶段计划**：

| 阶段 | 动作 | 依赖 |
|---|---|---|
| 初赛（PPT） | 架构图画出 AgentLoop 位置 + 接入方案页（env 配置清单直接引用官方文档） | 无云依赖 |
| 复赛（Demo） | 钉群申请选手云资源 → 开通 CMS 2.0 工作空间 → 开 Trace/Metrics 上报，展示调用链+token/延迟面板 | 阿里云资源申请 |
| 兜底（无资源） | 自建等价观测并明示等价关系（见下表），答辩讲清"同一套 OTLP 契约，差一个云 endpoint" | 无 |

**可观测三类数据覆盖（无论是否接云都成立）**：

| 类 | 自建覆盖 | AgentLoop 增强 |
|---|---|---|
| Trace | Matrix 房间消息全程可回放=多 Agent 消息流转天然链路 | CMS 调用链（LLM 请求级） |
| Metrics | v1/v2 指标台账（解决率/质检分/回归通过率 jsonl 时序） | token 消耗/延迟面板 |
| Log | MinIO 归档（transcripts/质检报告/审计链） | — |


---

## 5. 量化对照演示设计（v3.0 新增，"运行验证"20% 的核心得分点）

**原则：进化必须是可验证的数据，不是叙事。**

1. **预置测试集**：50 题（星辰咖啡机场景：产品/保修/退换货/政策），含预埋缺口题
2. **退化版 v1**：旧知识包（未进化）跑全测试集，记录指标基线
3. **进化**：飞轮跑一轮（质检→陪练→知识修订→审批→发布 v2）——diff 是**知识包/Skill 的版本差异**，可审计，不是 prompt 调整
4. **进化版 v2**：同测试集复跑，指标对比展示：
   - 解决率 ↑ / 转人工率 ↓ / 质检平均分 ↑ / 回归通过率 100%
   - **人机回环效率**：每轮进化人工干预次数、审批平均响应时长——证明 HITL 是可控治理而非瓶颈（呼应安全审计维度）
5. **指标采集**：自建台账（jsonl 落 MinIO）为主，AgentLoop 观测接入为增强项（官方第二基点，接上即"持续进化"维度直接证据）

> 演示确定性：v1/v2 差异来自确定性知识条目写入，不赌 LLM 现场发挥；测试集与评分 rubric 全部入库开源。

---

## 6. 资产复用映射（interview-agent-python → 新场景）

| 现有资产 | 新用途 | 改造点 |
|---|---|---|
| `graphs/rag_agent.py`（analyze→search→evaluate→refine→answer） | 客服主岗应答 | pgvector→知识 Skill 包检索 |
| `graphs/adaptive_interview.py`（ReAct+追问+interrupt） | 陪练官：刁钻客户陪练 + 回归测试执行 | 提示词换客服语境；interrupt→房间审批消息 |
| `graphs/evaluation.py`（fan-out 批评估+汇总） | 质检评分 + 测试集批量评测 | 维度改为客服质检 rubric；增加"缺失证据"输出段 |
| `tools/interview_tools.py` 出题能力 | 陪练剧本 + 回归测试题生成 | 题库源=质检 bad cases |
| `app/skills/`（SKILL.md+meta+references） | 四类 Skill 包（见 §7） | 重排为 AgentTeams skills 布局 |
| HITL interrupt/resume | 高危操作审批 + 知识变更审批 | 房间消息 approve/reject |
| decision_trace / audit.py | 审计证据链 | 扩展为进化台账（指标 jsonl） |

---

## 7. Skill 体系（四类可复用技能包，各带独立评测入口）

| Skill 包 | 内容 | 独立评测入口 | 复用方式 |
|---|---|---|---|
| `product-knowledge-*` | 产品知识条目（知识即 Skill） | 回归测试集通过率 | 换企业=换此包 |
| `qc-standard-*` | 质检 rubric 与评分细则 | 预埋样本评分一致性测试 | 按行业定制（电商/SaaS/金融） |
| `coach-scenario-*` | 陪练剧本模板（刁钻客户人设+考察点） | 剧本覆盖率检查 | 复用人设机制跨场景 |
| `regression-verify-*` | 测试集执行与指标采集 | 自测（对已知答案集） | 通用，与行业无关 |

**每个 Skill 的独立演示动作（各 1–2 分钟，复赛 Demo 与答辩备用）**：
- product-knowledge：现场换一份产品知识包 → 回归通过率变化 → 证明"换企业=换包"
- qc-standard：预埋样本跑评分一致性 → 同一会话评 3 次分数稳定 → 证明 rubric 不漂
- coach-scenario：生成剧本后自动输出考察点覆盖清单 → 证明剧本不漏维度
- regression-verify：一键跑完 50 题测试集 → 输出 v1/v2 对比报告（总入口）

> qc 降级策略（LLM-as-Judge 鲁棒性）：评分置信度低或格式解析失败 → 自动降级"只标注不评分"，**并标记"需人工复核"**——与"缺失证据"段同一设计准则。

- docs 中演示"10 分钟接入一家新企业"：替换 product-knowledge 包 → 全流程直接跑通
- 报告模板内置"缺失证据"段（准则 3）
- **每个 SKILL.md 附规格块（v3.1）**：除名称/用途/输入输出外，补齐 ① 失败处理机制 ② 安全边界 ③ 与多 Agent 协同流程的关系。注：此 9 维清单未在官方公告逐字出现（来源或为宣讲/钉群细则，待确认），但补齐成本低且直接强化 25% Skill 维度，按最佳实践执行；若初赛 PPT 需引用"官方要求"措辞，先在选手群核实原文再写

---

## 8. Demo 剧本与决赛故事线

### 8.1 复赛录屏剧本（≤8 分钟）

| 幕 | 剧情 | 展示点 |
|---|---|---|
| 1 | 客户会话：常规题答对 + 预埋缺口题（政策已更新知识未同步）触发低置信 | 服务闭环；主岗发起审批 |
| 2 | 质检·审批官抽检全部会话 → 薄弱点报告（含"缺失证据"段） | 结果验证 + 证据沉淀 |
| 3 | 陪练官生成陪练剧本，主岗重练失败案例；产出知识修订草案 | 进化闭环启动 |
| 4 | 审批官审批 → 知识包 v2 发布（label 切换叙事） | Skill 工程 + 安全审计 |
| 5 | **量化对照**：50 题测试集 v1 vs v2 指标对比（解决率/质检分/回归通过率） | 运行验证核心得分点 |
| 6 | 回放房间消息 + MinIO 审计归档（transcripts/报告/审批/版本 diff） | 全程可审计可回滚 |

### 8.2 决赛答辩故事线（9/22，戏剧性设计）

一条完整故事线演到底：**用户差评 → 质检触发 → 陪练重训 → 规则更新 → 同题复测通过**。客服场景可直播演绎（对比后台流程型方案只能给评委看日志），现场分友好。

---

## 9. 里程碑（8/7 → 9/3；今天起跑，不等初赛结果）

### P0 仓库骨架（8/7–8/9）✅ 已完成

| # | 任务 | 验收 |
|---|---|---|
| 0.1 | 重建 GitHub fork（删模板仓库→fork 官方 AgentTeams） | ✅ fork 为官方真 fork；本地 origin=fork / upstream=官方，main 同步至 #1149 |
| 0.2 | `servevo/` 目录骨架 + README（全部增量收敛于此，官方源码零侵入） | ✅ servevo 分支已推送，骨架 README 含目录规划与归属声明 |

### P1 初赛材料改版（8/7–8/15，**关键路径，8/16 截止**）✅ 已完成（8/8 提前）

| # | 任务 | 验收 |
|---|---|---|
| 1.1 | 作品名/报名表更新（智面→智服） | ✅ 报名表定稿 |
| 1.2 | 500 字简介重写（Klarna 故事+双闭环+量化对照+空白点） | ✅ 定稿 |
| 1.3 | PPT 改版：场景/架构/评分对齐页重做；**前置回答"和其他客服队的差异"**；画环不画清单；**架构图含 AgentLoop 位置+接入方案页（§4.4）** | ✅ 19 页改版完成，审计+视觉 QA 通过 |
| 1.4 | 开源计划页：LICENSE 选型（建议 Apache-2.0，与上游兼容待核）+ 数据集/Skill 仓库结构 | ✅ PPT 第六章含协议+长期维护 |

### P2 环境与接入（8/7–8/12，本地部署已提前完成大半）

| # | 任务 | 状态/验收 |
|---|---|---|
| 2.1 | AgentTeams 本地部署跑通 | ✅ 已完成（embedded 栈全链路，见踩坑手册） |
| 2.2 | Worker 接入方式定夺：copaw runtime+package vs 自定义 image | 实测对比备忘 |
| 2.3 | 最小角色 bot：ready+收发 | 房间收发成功 |
| 2.4 | MinIO 读写 + 知识包 file:// 通道验证 | shared 区上传成功 |

### P3 图迁移与单 Worker E2E（8/12–8/22）

| # | 任务 | 验收 |
|---|---|---|
| 3.1 | RAG 图迁移（知识 Skill 包版） | task→应答成功 |
| 3.2 | 评估图迁移（质检 rubric + 缺失证据段） | 质检报告输出 |
| 3.3 | 自适应图迁移（陪练/回归模式） | 陪练闭环 |
| 3.4 | storage/audit/台账模块 | 产物+审计+指标 jsonl 落 MinIO |

### P4 团队化 + 进化闭环（8/22–8/30）

| # | 任务 | 验收 |
|---|---|---|
| 4.1 | Leader 编排（分诊/触发进化/汇报） | 一句话启动全流程 |
| 4.2 | 4 个 SOUL.md 定稿 | 角色行为符合人设 |
| 4.3 | 进化机制：知识包版本化+审批流+回滚 | 审批→发布→可回滚 |
| 4.4 | 50 题测试集 + v1/v2 量化对照脚本 | 指标对比可复现 |
| 4.5 | 四类 Skill 包重排 + team.yaml + setup.sh | 一键建队 |
| 4.6 | AgentLoop/CMS 观测接入（§4.4）：钉群申请云资源→开 `AGENTTEAMS_CMS_*` 上报；申请不到→自建等价观测+答辩讲清 OTLP 同契约 | Trace/Metrics 面板或等价物 |

### P5 Demo 与交付（9/1–9/3）

| # | 任务 | 验收 |
|---|---|---|
| 5.1 | 剧本彩排×3（含 v1/v2 稳定性） | 无人工救场 |
| 5.2 | 录屏+截图 | ≤8min，指标对比曲线出现 |
| 5.3 | 文档定稿（README/架构/Skill/审计安全） | 陌生人可部署 |
| 5.4 | 代码包清理+提交 | 提交回执 |

---

## 10. 风险与预案

| 风险 | 概率 | 预案 |
|---|---|---|
| P1 材料与开发并行挤压 | 高 | 材料优先（初赛不过一切白搭）；开发已提前并行启动 |
| **免费额度模型过期**：qwen3.7-max 8/20 过期，正处开发窗口 | 高 | 按过期时间就近消耗：8 月用 qwen3.7-max/plus，9/1 起切 qwen3.8-max（11/01 过期，覆盖赛程）；Worker 高频调用走 qwen3.7-flash |
| 质检评分不稳（LLM-as-judge 偏差） | 中 | rubric 写死在 qc-standard Skill；演示用预埋样本保证稳定 |
| 进化演示翻车 | 中 | v1/v2 差异=确定性知识条目写入；测试集固定 |
| 多 Agent 级联失败 | 中 | 任务协议结构化+角色契约明确；每步超时降级到 Leader |
| Worker 自定义 image 接入受阻 | 中 | 已验证 copaw runtime 可用，退回 Worker package 路径 |
| **AgentLoop 云资源申请不到** | 中 | 早申请（P2 阶段钉群提）；兜底=自建 Trace/Metrics/Log 等价物+答辩讲清 OTLP 同契约（§4.4） |
| 时间不够 | 中 | 保底版=服务环跑通+v1/v2 对照；Registry 叙事轨与 AgentLoop 云接入降级为等价物 |

## 11. 提交前检查清单

- [ ] fork 基于官方最新 main，增量全部在 `servevo/`，官方源码零侵入
- [ ] setup.sh 干净环境一键起 Team（附《Windows部署踩坑手册》）
- [ ] Demo 六幕可复现，录屏 ≤8min，**v1/v2 指标对比曲线出现**
- [ ] 3+1 角色、双闭环、HITL×2、审计归档、证据沉淀逐项有落点
- [ ] 四类 SKILL.md 包各带独立评测入口，"换企业=换知识包"有演示；规格块含失败处理/安全边界/协同关系
- [ ] 报告模板含"缺失证据"段；回滚能力叙事在自动化率之前
- [ ] AgentLoop 已接入（Trace/Metrics 面板）或等价物+OTLP 同契约说明到位；架构图体现双基座
- [ ] 无真实 API Key 残留；LICENSE 与上游归属声明

---

## 附：调研与验证依据

- 场景调研五份报告：`E:\code\demo\场景调研\01–05`（01 客服 / 02 研发应急 / 03 招聘 / 04 数据分析 / 05 投研与合同）
- 平台源码笔记：`E:\code\AgentTeams-source\notes`（wiki）；关键事实——Nacos 远程 skills/agentSpec（v1.1.2，STS 域 skill/*）、包 URI version+label 寻址、teamharness 任务运行时缺口（accept_task_result/resolve_project 未实现，兜底暂缓）
- 部署验证：`E:\code\AgentTeams-source\Windows部署踩坑手册.md`（全链路实测记录）
