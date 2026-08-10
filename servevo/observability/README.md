# servevo-obs

可观测（AgentLoop/CMS 接入 + 自建等价物）：Trace/Metrics/Log（规划 §4.4）。

## 设计（诚实边界）

- **云接入**：配置 `AGENTTEAMS_CMS_TRACES_ENABLED / _ENDPOINT / _LICENSE_KEY / _WORKSPACE / _SERVICE_NAME` → 官方 AgentLoop 经这组 env 走 OTLP 上报（本模块不重复实现 OTLP，不引入 opentelemetry 依赖）
- **自建等价物**：无云资源时，本模块始终落本地 jsonl 台账（Metrics/Log）作为等价审计轨迹；答辩讲清"OTLP 同契约，差一个云 endpoint"
- 三类数据：Metrics（指标 jsonl）/ Log（归档 jsonl）/ Trace（Matrix 房间回放，天然）

## 用法

```bash
servevo-obs status                          # 显示观测模式（cloud/local/none）
servevo-obs emit --name resolution_rate --value 0.9 --tag kb=v2
```

## 验证

```bash
python -m pytest tests/ -v   # 6 绿（纯函数，无云依赖）
```