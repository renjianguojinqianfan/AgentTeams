# 开发流程

详细描述 servevo 的完整开发工作流。镜像 interview-agent `docs/workflow.md`（PBH/harness 产物），适配 servevo 参赛增量。

## 流程总览

```
规划 -> TDD -> /code-review -> /neat-freak（上下文同步） -> commit -> push
```

不得颠倒。每个阶段的产出是下一阶段的输入。

## 0. 规划

### 时机
写任何代码之前。

### 内容
1. 读取 issue / spec / 规划文档（P 里程碑）
2. 探索代码库（现有模块 rag/eval/coach/audit/regression/registry/observability 的既有模式）
3. 识别设计决策，需时向用户提问
4. 制定实施计划（文件清单 + 顺序 + TDD 分组）
5. 用户确认后进入 TDD

### 不绑定技能
由 `/implement` 编排。需压力测试计划用 `/grilling`；维护领域术语用 `/domain-modeling`。

## 1. TDD（测试驱动开发）

### vertical slice 原则
测试与实现交替推进（red -> green 循环）。**禁止水平切片**（不得先写完所有实现再写所有测试）。

### 适用范围
- 适用：service 纯函数、graph 节点、CLI、域算法
- 不适用：dataclass/schema（由上层测试覆盖）
- 重构不适用：属 review 阶段

### 测试隔离
LLM 用 Fake invoker / Fake chat client（无网络）；`servevo/verify.sh` 逐模块跑（避免 test_graph.py 同名冲突）。

## 2. /code-review（代码审查）

### 时机
TDD 完成、`make verify` 通过后。

### 范围
`git diff <fixed-point>...HEAD`，fixed point = 本模块/issue 开始前的 HEAD。

### 双轴并行
- **Standards 轴**：AGENTS.md 约定（无硬编码 key / 零侵入 / 缺失证据 / 确定性）+ Fowler 代码异味
- **Spec 轴**：是否忠实实现 P 里程碑验收标准（如 P3.2 质检报告、P4.4 量化对照）
两个子 agent 并行，聚合后修复。

### 提交前置（关键）
**`make verify` 绿只是前置条件，`/code-review` 通过才是提交闸门。** 每个模块/issue 提交前必须 code-review，**不攒批**——不得攒到阶段末统一审。

### 为什么在 /neat-freak 之前
code-review 审查纯净代码 diff；neat-freak 先跑会混入文档改动，干扰 Spec 子代理。

### 两层 review
- **单模块 review**：每模块 `make verify` 后、提交前
- **阶段 review**：整阶段（如 P4）所有模块完成后，fixed point=阶段起点，对照规划验收

### 复审阈值
首轮 review 后若改动满足任一，需对增量再跑一轮：
- 改动超出原 finding 范围
- 触碰模块接口 / 跨模块契约
- 新增公共抽象文件

纯 finding 响应式小修无需复审。

### 豁免 review
纯文档 / 配置 / 依赖升级 / 单行修复可标注「豁免 review」跳过。

### GC loop（防复发）
review 发现 HARD 违反时，修复须同步增结构测试或规则防同类违规复发（如 test_architecture.py 或守卫位）。纯 SOFT 小修无需新增。

## 3. /neat-freak（上下文同步）

### 时机
code-review 完成（含 findings 修复）后、commit 前。

### 范围
按 AGENTS.md 文件清单逐项检查：AGENTS.md / CONTEXT.md / ADR / 设计档 / 踩坑手册 / review-plan 是否需同步。

### 为什么在 /code-review 之后
- code-review 可能修复 bug 改变行为，neat-freak 感知最终状态，文档更准确
- neat-freak 只改文档不改代码逻辑，不影响 review 结论

### 执行流程
1. **盘点**：只产清理计划，不改文件
2. **执行**：用户确认后落地

## 4. commit（提交）

### 前置条件
- `make verify` 通过
- /code-review findings 已修复
- /neat-freak 上下文同步完成
- 已获用户确认（**禁止未经确认的提交**）

### 原子提交
大改动拆多个原子 commit（如：模块代码 -> 测试 -> 文档）。每阶段只 `git add` 该阶段明确路径，绝不用 `git add .`。

### commit message 格式
`<type>(<scope>): <subject>`，type = feat/fix/docs/chore/build。subject 中文一句话。

## 5. push

pre-push 全量闸门自动触发（`make verify` 全量）。push 需用户确认（AGENTS.md 行为边界）。

## 关键转折点操作

以下转折点重新加载对应 skill 逐字对照，不凭记忆：

| 转折点 | 重新加载 | 对照内容 |
|--------|---------|---------|
| 规划完成准备实现 | `/implement` | 确认进入 TDD |
| 实现完成准备 review | `/implement` | 确认进入 review 阶段 |
| review 完成 | `/neat-freak` | 执行上下文同步 |
| 上下文同步完成准备提交 | `/implement` | 逐字对照 §9 流程顺序 |

## 异常流程技能

| 触发条件 | 技能 | 说明 |
|---------|------|------|
| 用户想压力测试计划 | `/grilling` | 规划阶段追问发现盲点 |
| review 发现顽固 bug | `/diagnosing-bugs` | 诊断循环定位根因 |
| 引入复杂领域术语 | `/domain-modeling` | 维护 CONTEXT.md + ADR |
| TDD 产生碎片提交 | `/squash-and-split` | 压缩为语义化原子提交 |
| 遇到合并冲突 | `/resolving-merge-conflicts` | 解决 merge/rebase 冲突 |
| 对话过长需交接 | `/handoff` | 压缩为交接文档 |