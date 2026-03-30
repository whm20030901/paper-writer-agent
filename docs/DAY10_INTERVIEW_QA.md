# Day10：面试问答提纲（架构 / 权衡 / 扩展）

## 1. 架构分层为什么这样拆？
- API 层只做协议与参数校验。
- Service 层做用例编排与事务边界。
- Pipeline/Agent 层做策略与生成闭环。
- RunStore 负责可追溯持久化与聚合统计。

## 2. 为什么要有 idempotency key？
- 防止客户端重试导致重复 run 与重复计费。
- 结合 request fingerprint 可以识别“同 key 不同请求体”的冲突。

## 3. 为什么采用 SQLite 作为第一版？
- 单机演示/面试成本低，迁移简单。
- 通过 SQL 过滤、索引与回填，保证在中小规模下可用。
- 后续可无缝迁移到 PostgreSQL（Repository 层接口不变）。

## 4. LLM 不可用时如何保证服务可用？
- `LLMClient` 内置重试 + 退避。
- 超限后回退到本地模板生成，主链路不中断。

## 5. 你如何衡量系统质量？
- 线上：`avg_quality_score`、`avg_duration_ms`、`success_rate`。
- 内容：citation coverage、evidence linkage、revision plan 落地率。

## 6. 下一个版本你会做什么？
- Day11+: 引入离线评测 runner（批量执行 `eval_samples`）。
- 增加 diff 结构化视图与修订计划“部分应用”。
- 引入 tracing（OpenTelemetry）与异常告警。
