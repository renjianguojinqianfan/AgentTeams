# AgentTeams Windows 本地部署踩坑手册

> 环境：Win11 + Docker Desktop 29.6.1（WSL2 后端，用户级安装）+ MINGW64 bash
> 验证日期：2026-08-07 | 版本：AgentTeams v1.2.1 embedded 模式
> 结论：全链路已跑通（admin → Manager → Worker alice → 回报），LLM 用千问免费额度

---

## 一、环境启动

| 坑 | 现象 | 解法 |
|---|---|---|
| Docker daemon 未运行 | `failed to connect to npipe dockerDesktopLinuxEngine` | Docker Desktop 是**用户级安装**，路径在 `%LOCALAPPDATA%\Programs\DockerDesktop\Docker Desktop.exe`，不在 Program Files。启动后约 5s 就绪 |

---

## 二、安装器

| 坑 | 现象 | 解法 |
|---|---|---|
| bash 安装器 socket bug | `docker: invalid spec: :/var/run/docker.sock: empty section between colons` | 脚本 4015 行无条件挂载 `${CONTAINER_SOCK}`，Windows 上探测为空。**Windows 必须用 ps1 安装器**（用 `//var/run/docker.sock` npipe 写法） |
| PS 5.1 中文乱码 | `快速开? ... 标记")"无效`，解析失败 | ps1 是 UTF-8 无 BOM，PS 5.1 按 GBK 读。**先转 BOM 副本再执行**：`[IO.File]::WriteAllText($dst, [IO.File]::ReadAllText($src,[Text.Encoding]::UTF8), (New-Object Text.UTF8Encoding $true))` |
| 非交互模式卡升级菜单 | 检测到旧 env 文件后弹"请选择升级方式"等待输入 | 旧安装的 `~/agentteams-manager.env` 会触发升级路径。删掉 env 文件走全新安装 |
| 时区探测失败 | `Could not detect timezone automatically` | 无碍，自动落到 Asia/Shanghai 默认值，registry 自动选杭州阿里云源 |

**可用安装命令（BOM 副本 + 非交互）：**

```powershell
Set-Location E:\code\AgentTeams-source\AgentTeams
$env:AGENTTEAMS_NON_INTERACTIVE = "1"
$env:AGENTTEAMS_LLM_PROVIDER = "openai-compat"
$env:AGENTTEAMS_OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:AGENTTEAMS_LLM_API_KEY = $env:DASHSCOPE_API_KEY
$env:AGENTTEAMS_DEFAULT_MODEL = "qwen3.7-max"   # 见"模型额度策略"
$env:AGENTTEAMS_MATRIX_E2EE = "0"
& "<BOM副本路径>\agentteams-install-bom.ps1"
```

---

## 三、Controller

| 坑 | 现象 | 解法 |
|---|---|---|
| 缺 AppService token | controller 进程崩溃循环，`panic: AGENTTEAMS_MATRIX_APPSERVICE_AS_TOKEN is required`，supervisord FATAL | **ps1 安装器不生成 token（bug），bash 版生成**。手动补：`openssl rand -hex 32` 各生成 as/hs token，加入容器 env 重建容器 |
| 手动重建容器 | — | 用 `--env-file` + 原参数：`docker run -d --name agentteams-controller --network agentteams-net --network-alias matrix-local.agentteams.io --network-alias aigw-local.agentteams.io --network-alias fs-local.agentteams.io --restart unless-stopped --env-file ctrl.env -v //var/run/docker.sock:/var/run/docker.sock -v agentteams-data:/data -v "C:/Users/DELL/agentteams-manager:/root/agentteams-fs/agents/manager" -p 127.0.0.1:18001:8001 -p 127.0.0.1:18080:8080 -p 127.0.0.1:18088:8088 <embedded镜像>` |
| 换模型后 Manager 仍用旧模型 | `MODEL_UNAUTHORIZED_ACCESS: Unauthorized access to model: qwen-plus` | Manager 资源的模型**持久化在数据卷**，不随容器 env 变。必须 `agt update manager --name default --model <新模型>`，controller 会自动重建 manager 容器 |

**controller 内部日志位置**（排障必看）：
- 进程崩溃：`docker exec agentteams-controller tail /var/log/agentteams/agentteams-controller-error.log`
- 基建状态：`docker logs agentteams-controller`（Tuwunel/MinIO/Higress ready 计时）

---

## 四、LLM 与千问免费额度

| 坑 | 现象 | 解法 |
|---|---|---|
| 百炼免费额度用尽 | preflight 403：`Free quota exhausted ... AllocationQuota.FreeTierOnly` | sk-ws- 工作区 key 是"仅免费额度"模式，**免费额度按模型独立发放**，换有余额的模型即可 |
| 查余额 | — | `qianwen usage free-tier --format json`，过滤 `status==valid && unit==tokens`，按 `resetDate` 排序 |
| qianwen CLI 登录 | `start`/`explorer` 拉起浏览器**可能无弹窗** | `--init-only` 拿 verification_url，**直接贴给用户手动打开**，然后 `--complete` 轮询；设备码有效期 300s，过期需重新 init |
| Token Plan ≠ 免费额度 | — | sk-sp- key 走 token-plan.cn-beijing.maas.aliyuncs.com，是订阅制；本方案用的是标准端点 dashscope.aliyuncs.com 的按模型免费额度，两者勿混 |

**模型额度策略（2026-08-13 实测，账号：人间过尽千帆）**

| 模型 | 余额 | 过期 | 用途规划 |
|---|---|---|---|
| qwen3.7-max | **0（已耗尽）** | 8/20 | 已耗尽，勿选 |
| qwen3.7-plus | 999K | 9/01 | 次优先消耗（8 月；B5 全量 50 题对照用） |
| qwen3.8-max | 999K | 11/01 | **封存，留给赛程（复赛9/3、决赛9/22）** |
| qwen3.7-flash | 320K | 10/23 | Worker 高频廉价档（闭环/演示用，单次闭环约耗 80K，注意剩余） |

> 查额度：`qianwen usage free-tier --format json`，过滤 `status==valid && unit==tokens`，按 `resetDate` 排序。

---

## 五、Matrix / copaw 消息链路

| 坑 | 现象 | 解法 |
|---|---|---|
| 群房消息不响应 | Manager 收到消息但无动作，日志 `is_dm=False` | 群房需 **@提及唤醒**（groups.*.requireMention=true）；测试用 admin-manager 双人 DM 房间（is_dm=True 免提及） |
| replay-task.sh 跑不了 | `jq: command not found` | Windows 无 jq。替代方案：`closedloop_test.py`（docker exec 直连容器内 Tuwunel `http://127.0.0.1:6167`，自带登录/找房/发消息/轮询回复，按 origin_server_ts 过滤旧消息） |
| env 文件 BOM | replay 脚本报 `﻿# AgentTeams...: invalid variable name` | ps1 写出的 env 带 UTF-8 BOM：`sed -i '1s/^\xEF\xBB\xBF//' ~/agentteams-manager.env` |
| **Worker matrix channel 冷启动不拉起** | alice 收不到任何消息，日志无 MatrixChannel 行 | copaw 只在**配置 hash 变更事件**时 pre-start channel。修复流程：`docker restart agentteams-worker-<name>` → 等日志出现 `AgentConfigWatcher started`（约 50s）→ **改动 agent.json 的 channels.matrix 内容**（如加 `"deny_message": " "`，touch mtime 无效）→ watcher 触发 `Pre-starting new channel: matrix` |
| 不要用 API 热重载 | PUT `/api/agents/default/config/channels/matrix` 触发 zero-downtime reload，**重载后 watcher 和 channel 全死**，进程假死 | 避免 API reload；用"重启容器 + 改文件"的组合 |
| 栈重建后房间损坏 | 发消息报 `non-create event for room of unknown version` | 旧房间状态损坏且 Manager 可能持有旧房间 ID。**重建 worker**（`agt delete worker x && agt create worker --name x`）生成新房间 |
| Manager 消息格式泄漏 | 回复里出现 `sequence_number=... TextContent(...)` 原始对象 repr | copaw-worker 已知表面 bug，不影响链路，复赛前观察是否修复 |
| **Worker YAML 的 identity/soul/agents 必须用块标量内联 string** | `agt apply -f servevo-cs.yaml` 报 `HTTP 400: cannot unmarshal array into Go struct field ...agents of type string` | 官方 CRD（`agentteams-controller/api/v1beta1/types.go`）的 `identity/soul/agents` 均为 **string**，`soul` 是 SOUL.md **内容**非文件名。须写成 `identity: \|` / `soul: \|` / `agents: \|` 多行块标量（参考 `servevo/team/yamls/*.yaml`）。嵌套对象/文件名引用会 apply 失败建队失败 |

---

## 六、日常操作速查

```bash
# 健康检查
docker exec agentteams-controller agt llm-preflight          # LLM 连通性
docker exec agentteams-controller agt get workers            # worker 列表
docker exec agentteams-controller agt get managers           # manager 状态（看 MODEL 列是否残留旧模型）

# Worker 生命周期
docker exec agentteams-controller agt create worker --name alice
docker exec agentteams-controller agt delete worker alice
# ⚠️ 新建 worker 后若 channel 不起，走"五.4"的修复流程

# 闭环测试（宿主机）
python -X utf8 closedloop_test.py "任务内容" 180
# 脚本位置：C:\Users\DELL\.qwenworkcn\workspace\msiqgmqp8i1rcbcw\closedloop_test.py

# 端口表（均绑定 127.0.0.1）
# 18080 Higress 网关 | 18001 Higress 控制台 | 18088 Element Web | 容器内 6167 Tuwunel / 9000 MinIO
```

---

## 七、已验证的完整闭环（2026-08-07 12:30）

```
admin(DM房) → Manager(qwen3.7-max)：请把 1+1=？ 转给 alice
Manager → alice房间：派任务 + 要求回复后 @manager
alice(qwen3.7-max)：收到 → LLM 作答 "1 + 1 = 2 ✅" → @manager
Manager：确认收到 → admin 追问后转达 alice 原话 + 时间戳
```

---

## 八、servevo 质量闸门（verify）运行提示

| 坑 | 现象 | 解法 |
|---|---|---|
| 裸 shell 无 TMPDIR | `bash servevo/verify.sh` 到 Skills 步骤报 `TMPDIR: unbound variable`（`set -u` + `${SERVEVO_PYCACHE:-$TMPDIR/...}`） | 补环境：`TMPDIR=/tmp bash servevo/verify.sh`，或预置 `SERVEVO_PYCACHE` |
| 真实应答要点匹配漏判 | 价格题答作「价格为¥1999」已修（runner 匹配器 token 化 + 剥货币/markdown/中文标点）；仍有两类 **kp 数据设计局限**：compound kp 被连接词隔断（kp「运费星辰承担」对「运费**由**星辰承担」）、kp 概念不在应答（kp「以旧换新 300」对「补贴 ¥300」） | 属测试集 kp 措辞问题，非匹配器缺陷；改 kp 数据需独立评审（影响 passed 率与 v1/v2 判定） |
