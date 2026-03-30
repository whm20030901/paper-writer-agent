# Paper Writer Agent

一个面向 **AI Agent 工程师面试 + 可部署上线** 的论文写作助手项目。

## 1. 企业级目标

本项目在“可演示”基础上，补齐了上线所需的核心工程要素：

- 模块化领域层（RAG、Memory、MCP、Skills、Agents）
- 可部署 API 层（FastAPI）
- 配置管理（环境变量）
- 结构化日志（基础观测能力）
- 容器化部署（Docker）
- 自动化测试（pipeline + API）
- LangGraph 工作流编排 + 本地回退
- 可选接入 OpenAI 兼容 Chat Completions（通过环境变量开关）

---

## 2. 推荐项目结构（已实现）

```text
paper_writer_agent/
├── agents.py                  # 顶层 Writer/Reviewer + Sub-agents + LangGraph
├── rag.py                     # RAG 检索引擎
├── memory.py                  # Working/LongTerm memory + manager
├── mcp_registry.py            # MCP 风格工具注册/调用
├── skills.py                  # 技能能力包
├── context_engineering.py     # 上下文拼装
├── main.py                    # CLI / pipeline bootstrap
├── core/
│   ├── config.py              # 环境配置
│   └── logging.py             # 日志配置
└── api/
    ├── app.py                 # FastAPI app factory
    └── schemas.py             # API 请求响应模型

paper_writer_agent/services/
├── paper_service.py           # 业务服务层（pipeline + store）
└── run_store.py               # 运行记录持久化

tests/
├── test_workflow.py
└── test_api.py

Dockerfile
.env.example
requirements.txt
```

> 说明：这是从“面试 Demo 结构”升级到“可上线服务结构”的关键补充，重点在 `core`（配置/日志）和 `api`（服务化）分层。

---

## 3. 架构能力映射（对应你的面试要求）

### 3.1 RAG
- `RAGEngine`：分块、索引、TF-IDF 风格召回、Top-K。
- 结果进入上下文工程，避免“无证据写作”。

### 3.2 Memory + 记忆管理
- `WorkingMemory`（短期）+ `LongTermMemory`（SQLite 持久化）+ `MemoryManager`（统一读写/摘要）。

### 3.3 Context Engineering
- `ContextBuilder` 聚合任务、提纲、检索证据、历史反馈、记忆摘要，并做长度预算。

### 3.4 MCP + Skills
- `MCPRegistry`：工具注册/发现/调用。
- `SkillManager`：能力包组合（citation/evidence/argument）。

### 3.5 双层 Multi-Agent + Sub-Agent
- Writer 下：Research / Outline / Drafting / Citation。
- Reviewer 下：Structure / Evidence / Language。

### 3.6 LangGraph 编排
- `writer -> reviewer -> gate -> conditional loop`。
- 若未安装 LangGraph，自动回退顺序执行。


### 3.7 新增：评审打分 + 质量门控（Architecture Governance）
- Reviewer 产出结构化评审报告，并给出 `Quality Score`。
- Pipeline 新增 `QualityGateSubAgent`：当分数达到阈值可提前终止，不再盲目跑满迭代轮次。
- 输出包含 `iterations_used / quality_score / stop_reason`，便于线上观测与A/B评估。

### 3.8 新增：运行记录持久化与可追踪性
- 新增 `PaperService` 作为 API 与 Pipeline 的服务层解耦。
- 新增 `RunStore` 持久化每次生成结果（含入参、评分、停止原因、草稿、评审）。
- API 通过 `run_id` 提供结果查询，支持上线后的审计和问题回放。

### 3.9 新增：请求级追踪（Request ID）
- API 中间件支持 `X-Request-ID` 透传（若未提供则自动生成）。
- 响应头返回同一个 `X-Request-ID`，便于日志关联与问题排查。

### 3.10 新增：API Key 鉴权与分页总数修复
- 当配置 `API_KEY` 后，核心业务接口需要 `X-API-Key` 访问。
- `GET /v1/papers/runs` 的 `total` 修复为全量记录数，而不是当前页条数。

### 3.11 新增：运行指标聚合（Metrics）
- 新增 `GET /v1/papers/metrics` 输出运行总数、平均质量分、停止原因分布。
- 为线上运维看板和质量趋势追踪提供基础数据接口。

### 3.12 新增：生成接口限流（Rate Limiting）
- `POST /v1/papers/generate` 增加每分钟请求数限制（`RATE_LIMIT_PER_MINUTE`）。
- 超限返回 `429 rate limit exceeded`，用于基础流量保护。

### 3.13 新增：生命周期管理与就绪探针
- FastAPI `lifespan` 中增加资源回收，服务停止时关闭持久化连接。
- 新增 `GET /ready` 作为部署探针接口，返回服务就绪状态。

### 3.14 新增：幂等生成（Idempotency Key）
- `POST /v1/papers/generate` 支持 `X-Idempotency-Key`。
- 相同 key 的重复请求将返回同一个 `run_id`，避免重试导致重复生成与重复计费。

### 3.15 新增：耗时观测（Duration Metrics）
- 每次生成记录 `duration_ms`，并在 run 明细与列表中返回。
- 聚合指标新增 `avg_duration_ms`，用于 SLA 监控与容量评估。

### 3.16 新增：运行数据保留与清理（Retention/Purge）
- 新增 `POST /v1/papers/maintenance/purge`，按 `RUN_RETENTION_DAYS` 清理历史 run。
- 便于长期运行时控制 SQLite 体积与清理历史数据。

### 3.17 新增：真实就绪检查（Dependency-aware Ready）
- `/ready` 不再仅返回静态值，而是检查底层存储可用性。
- 若依赖不可用返回 `503`，便于编排系统正确摘流。

### 3.18 新增：启动自动清理（Auto Purge on Startup）
- 通过 `AUTO_PURGE_ON_STARTUP=true` 可在服务启动时自动执行过期 run 清理。
- purge 接口支持 `retention_days` 临时覆盖，便于运维应急清理。

### 3.19 新增：可游标化分页字段（has_more / next_offset）
- `GET /v1/papers/runs` 返回 `has_more` 与 `next_offset`。
- 前端列表可直接按返回值继续翻页，避免手动推算偏移。

---
### 3.20 新增：运行列表过滤（stop_reason / q）
- `GET /v1/papers/runs` 支持 `stop_reason` 精确过滤与 `q`（task 关键词）模糊过滤。
- 分页字段 `total/has_more/next_offset` 基于过滤后的结果计算，便于前端做条件检索翻页。

---


### 3.21 新增：运行列表过滤的数据库级优化
- `RunStore` 在 `pipeline_runs` 表中冗余存储 `task` 和 `stop_reason` 字段，并增加索引。
- 列表与计数过滤从 Python 内存筛选改为 SQL 过滤，提升 `GET /v1/papers/runs` 在数据量增长时的性能与稳定性。

---

### 3.22 新增：时间范围过滤（created_after / created_before）
- `GET /v1/papers/runs` 支持按创建时间窗口过滤，便于排查某一时间段的运行质量与故障。
- 当 `created_after >= created_before` 时返回 `422`，避免无效查询进入数据库。

---

### 3.23 新增：质量分区间过滤（min_quality_score / max_quality_score）
- `GET /v1/papers/runs` 支持按质量分区间筛选，便于快速定位低质量样本或高质量样本做评估。
- 当 `min_quality_score > max_quality_score` 时返回 `422`，避免无效区间查询。

---

### 3.24 新增：列表排序（sort_by / sort_order）
- `GET /v1/papers/runs` 支持 `sort_by=created_at|quality_score` 与 `sort_order=asc|desc`。
- 便于运维场景按最新运行查看，也可按质量分排序快速定位高/低质量样本。

---

### 3.25 新增：指标接口支持同维度过滤
- `GET /v1/papers/metrics?stop_reason=max_iterations&q=agent&min_quality_score=7&min_duration_ms=0&max_duration_ms=5000` 支持 `stop_reason/q/created_after/created_before/min_quality_score/max_quality_score/min_duration_ms/max_duration_ms` 过滤参数。
- 便于按时间窗口、任务域、质量区间查看聚合指标，减少手动二次统计。

---

### 3.26 新增：耗时区间过滤（min_duration_ms / max_duration_ms）
- `GET /v1/papers/runs` 与 `GET /v1/papers/metrics` 支持按耗时区间过滤，便于 SLA 与性能回归分析。
- 当 `min_duration_ms > max_duration_ms` 时返回 `422`，避免无效查询。

---

### 3.27 新增：运行记录 CSV 导出接口
- 新增 `GET /v1/papers/runs/export.csv`，支持与列表接口一致的过滤、排序（`created_at|quality_score|duration_ms`）与 `offset` 分页参数。
- 支持字段选择（`fields=run_id,quality_score,duration_ms`），便于按需导出轻量报表。
- 支持 `include_bom=true`，用于 Excel 等工具更稳定识别 UTF-8 中文。
- 支持 `compress=true` 返回 gzip 压缩 CSV（二进制 gzip 文件，下载文件名为 `runs_export.csv.gz`），适合大批量导出。
- 可与 `include_bom=true` 组合使用，解压后仍保留 UTF-8 BOM，方便 Excel 等工具识别中文。
- 支持 `delimiter=comma|tab|semicolon|pipe` 控制导出分隔符，便于直接对接不同下游系统（非法值会返回 `422`）。
- 支持 `quote_all=true` 强制对所有 CSV 字段加引号，适用于部分严格 CSV 消费端。
- 支持 `quote_char=double|single` 指定 CSV 引号字符风格。
- 支持 `include_header=false` 跳过表头行，便于增量拼接导出文件。
- 支持 `line_ending=lf|crlf` 控制换行符风格，适配不同平台导入工具。
- 支持 `null_value=...` 指定空值（`null`）导出的替代文本，便于与下游数据仓库约定统一空值标识。
- 支持 `trim_strings=true` 对字符串字段做首尾空白裁剪，便于统一清洗导出数据。
- 支持 `empty_as_null=true` 将空字符串按 `null_value` 统一替换，便于下游空值一致化处理。
- 支持 `max_cell_length=...` 限制字符串单元格最大长度，便于控制导出体积。
- 支持 `escape_style=double|backslash` 控制引号转义策略，适配不同 CSV 解析器。
- 响应头返回 `X-Export-Generated-At/X-Export-Total/X-Export-Limit/X-Export-Offset/X-Export-Returned/X-Export-Has-Data/X-Export-Offset-End/X-Export-Remaining/X-Export-Limit-Reached/X-Export-Page-Index/X-Export-Total-Pages/X-Export-Next-Page-Index/X-Export-Is-Last-Page/X-Export-Has-More/X-Export-Next-Offset/X-Export-Has-Filters/X-Export-Filter-Count/X-Export-Filter-Keys/X-Export-Delimiter/X-Export-Quote-All/X-Export-Quote-Char/X-Export-Include-Header/X-Export-Line-Ending/X-Export-Null-Value/X-Export-Trim-Strings/X-Export-Empty-As-Null/X-Export-Sanitize-Cells/X-Export-Include-Bom/X-Export-Compressed/X-Export-Fields/X-Export-Field-Count/X-Export-Default-Fields/X-Export-Sort-By/X-Export-Sort-Order/X-Export-Stop-Reason/X-Export-Query/X-Export-Created-After/X-Export-Created-Before/X-Export-Min-Quality-Score/X-Export-Max-Quality-Score/X-Export-Min-Duration-Ms/X-Export-Max-Duration-Ms/X-Export-Escape-Style/X-Export-Max-Cell-Length`，方便批量抓取与断点续传。
- 导出默认会对以 `= + - @` 开头的文本单元格进行前缀转义（加单引号），降低表格工具公式注入风险。
- 如需原始值可使用 `sanitize_cells=false` 关闭该行为（例如机器消费场景）。
- 可直接导出报表用于离线分析、审计归档或 BI 管道对接。

### 3.28 新增：可选接入真实大模型（OpenAI 兼容）
- 当同时配置 `LLM_API_KEY` 与 `LLM_MODEL` 时，Writer 草稿阶段会调用 `POST {LLM_BASE_URL}/v1/chat/completions` 生成真实草稿内容。
- 未配置上述参数时自动回退到本地模板生成逻辑，保证离线开发与测试稳定。
- 若模型调用出现可恢复异常（网络错误、408/429/5xx），会按重试策略重试（429/503 时优先使用 `Retry-After`，支持秒数与 HTTP-date；无效值时回退到本地 backoff + jitter，并按 `LLM_RETRY_BACKOFF_MULTIPLIER` 指数退避，且受 `LLM_RETRY_MAX_DELAY_S` 上限保护）；若仍失败则自动降级到本地草稿生成，避免整条生成链路失败。
- 相关环境变量：`LLM_API_KEY`、`LLM_BASE_URL`（默认 `https://api.openai.com`）、`LLM_MODEL`、`LLM_TIMEOUT_S`、`LLM_MAX_RETRIES`、`LLM_RETRY_BACKOFF_S`、`LLM_RETRY_JITTER_S`、`LLM_RETRY_MAX_DELAY_S`、`LLM_RETRY_BACKOFF_MULTIPLIER`。

---


## 执行计划

项目执行计划与每日任务追踪见：`docs/EXECUTION_PLAN.md`。

Day 1 范围冻结与问题清单见：`docs/DAY1_SCOPE_FREEZE.md`。

Day 2 完成报告见：`docs/DAY2_COMPLETION_REPORT.md`。

Day 3 完成报告见：`docs/DAY3_COMPLETION_REPORT.md`。

---

## 4. 本地运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
python -m paper_writer_agent.main
```

也可以直接使用 `Makefile`（推荐，避免漏步骤）：

```bash
make help    # 查看可用命令
make show-config  # 查看当前解析后的运行/探活配置
make doctor  # 首次创建 .venv；仅在 requirements 变化时重装依赖并打印版本
make test    # 复用 .venv，仅在 requirements 变化时重装依赖并执行全量测试
make test-fast  # 快速回归：仅执行 llm/config/workflow 核心测试（跳过 API 集成测试）
make test-api  # 仅执行 API 相关测试
make test-llm  # 仅执行 LLM 客户端相关测试
make test-config  # 仅执行配置相关测试
make test-workflow  # 仅执行 pipeline workflow 相关测试
make test-core  # 执行 llm/config/workflow 核心测试集合
make run     # 复用 .venv，仅在 requirements 变化时重装依赖并启动 API
APP_RUN_PORT=18001 make run  # 自定义 API 启动端口
make ci      # 连续执行 doctor + test，做一次完整本地自检
make healthcheck  # 启动 API 并探活 /health，做运行时冒烟检查
HEALTHCHECK_PORT=18000 make healthcheck  # 自定义探活端口
HEALTHCHECK_PATH=/ready HEALTHCHECK_TIMEOUT_S=8 make healthcheck  # 自定义探活路径与超时
HEALTHCHECK_LOG_FILE=./healthcheck.log make healthcheck  # 自定义失败日志输出文件
make smoke  # 连续执行 healthcheck + ci，做完整发布前自检
```

---


## 4.1 常见环境问题排查

- 若运行 `pytest` 时出现 `ModuleNotFoundError: No module named fastapi` 或 `No module named requests`，通常是当前 shell 没有进入项目虚拟环境。
- 请确保在项目根目录执行以下命令（尤其是 `source .venv/bin/activate`）：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
```

- 建议统一用 `python -m pytest`（而不是裸 `pytest`），避免误用到系统解释器。
- 若你不确定当前环境是否正确，可先执行 `make doctor` 快速检查关键依赖版本。

---

## 5. API 运行（上线前入口）

```bash
uvicorn paper_writer_agent.api.app:app --host 0.0.0.0 --port 8000
```

接口：
- `GET /`（内置简易前端页面）
- `GET /health`
- `GET /ready`
- `POST /v1/papers/generate`
- `GET /v1/papers/runs/{run_id}`
- `GET /v1/papers/runs?limit=10&offset=0&stop_reason=max_iterations&q=agent&created_after=2026-01-01T00:00:00%2B00:00&min_quality_score=7&max_quality_score=10&min_duration_ms=0&max_duration_ms=5000&sort_by=duration_ms&sort_order=desc`
- `GET /v1/papers/runs/export.csv?limit=1000&offset=0&q=agent&sort_by=duration_ms&sort_order=desc&fields=run_id,quality_score,duration_ms&delimiter=tab&quote_all=true&quote_char=single&include_header=true&line_ending=crlf&null_value=NULL&trim_strings=true&empty_as_null=true&escape_style=backslash&max_cell_length=5000&include_bom=true&compress=true`
- `GET /v1/papers/metrics?stop_reason=max_iterations&q=agent&min_quality_score=7&min_duration_ms=0&max_duration_ms=5000`
- `POST /v1/papers/maintenance/purge`

请求示例：

```json
{
  "task": "Design an AI agent framework for academic writing",
  "outline": "1.Intro 2.Related Work 3.Method 4.Evaluation 5.Conclusion",
  "iterations": 2
}
```

> 如果配置了 `API_KEY`，请在请求头中传入 `X-API-Key: <your-key>`。
> 如果配置了 `LLM_API_KEY` + `LLM_MODEL`，草稿阶段将调用真实大模型；否则使用本地回退逻辑。
> 如果你希望直接在浏览器体验，可启动服务后访问 `http://localhost:8000/` 使用内置前端页面发起生成、查看最近运行记录、点击某条运行查看完整详情，并可按关键词/停止原因/时间范围/质量分/耗时区间过滤列表，使用下拉选择排序方式与每页条数、一键清空筛选、翻页浏览运行记录、导出 CSV，同时通过统计摘要卡片快速查看运行总数、平均质量分与平均耗时。

---

## 6. Docker 部署

```bash
docker build -t paper-writer-agent:latest .
docker run --rm -p 8000:8000 --env-file .env.example paper-writer-agent:latest
```

---

## 7. 下一步企业级增强建议

- 接入真实 LLM Provider（OpenAI/Azure/vLLM）与重试熔断策略
- 接入向量数据库（pgvector/Milvus）与检索评估基准
- 增加鉴权（JWT/API Key）、限流、审计日志
- 引入 CI/CD（lint+test+build+deploy）
- 增加 tracing（OpenTelemetry）与业务指标（生成耗时、检索命中率）

---

## Day 5 更新（路由/编排回归 + 演示）

### 架构分层图（简化）

```text
Frontend(static) -> FastAPI Routes -> PaperService -> PaperPipeline
                                         |                |
                                         v                v
                                      RunStore        Writer/Reviewer/Gate
                                         |                |
                                         v                v
                                      SQLite      subagents_research / subagents_writing / subagents_review
```

### 主链路 5 分钟演示

1. 启动服务：`make run`
2. 打开页面：`http://127.0.0.1:8000/`
3. 输入 task/outline 后执行 Generate
4. 在 Run Detail 查看 `quality_score`、`stop_reason`、`review_report`
5. 在 Metrics 查看运行聚合信息
6. 导出 CSV：`/v1/papers/runs/export.csv`

详细讲解脚本见：`docs/DAY5_DEMO_SCRIPT.md`。

---

## Day 8 更新（固定评测样本 + 指标示例）

### 固定评测样本

项目已新增基础任务集：`paper_writer_agent/eval_samples.py`（`BASELINE_EVAL_SAMPLES`），用于稳定回归评测与版本对比。

### 指标示例（含成功率）

`GET /v1/papers/metrics` 现在可返回：
- `total_runs`
- `avg_quality_score`
- `avg_duration_ms`
- `success_rate`
- `stop_reason_counts`

示例：

```json
{
  "total_runs": 12,
  "avg_quality_score": 8.17,
  "avg_duration_ms": 1324.5,
  "success_rate": 0.9167,
  "stop_reason_counts": {
    "quality_threshold_reached": 9,
    "max_iterations_reached": 2,
    "failed": 1
  }
}
```

---

## Day 10 更新（部署与答辩材料）

- Docker 一键启动演示说明：`docs/DAY10_DEPLOYMENT_GUIDE.md`
- 模型不可用故障演练：`docs/DAY10_FAILURE_DRILL.md`
- 面试问答提纲：`docs/DAY10_INTERVIEW_QA.md`

---

## Day 11 更新（离线评测 Runner）

- 新增 `paper_writer_agent/evaluation_runner.py`，可对 `BASELINE_EVAL_SAMPLES` 批量跑评测并输出 JSON 汇总。
- 新增 Makefile 命令：`make eval-baseline`。
- 汇总字段：`total_samples`、`success_rate`、`avg_quality_score`、`avg_iterations_used`。

---

## Day 12 更新（观测增强：Trace ID）

- 生成与运行记录新增 `trace_id` 字段，用于跨接口串联单次运行链路。
- `generate`、`run detail`、`runs list` 均可返回 `trace_id`，便于排障与日志关联。

---

## Day 13 更新（SLO 监控接口）

- 新增 `GET /v1/papers/slo`：返回当前 `status`（ok/degraded/no_data）、阈值配置、违规项列表。
- 新增可配置阈值：
  - `SLO_MIN_SUCCESS_RATE`
  - `SLO_MIN_AVG_QUALITY_SCORE`
  - `SLO_MAX_AVG_DURATION_MS`

---

## Day 14 更新（告警通知与SLO趋势）

- 新增 `GET /v1/papers/slo/history`：按 `day/week` 输出最近 N 天的 SLO 趋势点（成功率/质量分/耗时/状态/违规项）。
- 新增 `POST /v1/papers/slo/alerts/check`：按当前阈值评估告警并返回各通知通道投递结果。
- 新增告警通道配置：
  - `SLO_ALERT_CHANNELS`（支持 `log,webhook`）
  - `SLO_ALERT_WEBHOOK_URL`

---

## Day 15 更新（告警去重与冷却策略）

- `POST /v1/papers/slo/alerts/check` 新增 `force` 参数，可手动绕过抑制策略触发检查。
- 新增告警抑制能力：
  - 冷却窗口（cooldown）
  - 指纹去重窗口（dedupe window）
- 告警检查响应新增：`should_alert`、`suppressed`、`suppression_reason`、`alert_fingerprint`。
- Webhook 通道支持直接 POST（JSON）并返回投递状态。
- 新增配置：
  - `SLO_ALERT_COOLDOWN_SECONDS`
  - `SLO_ALERT_DEDUPE_WINDOW_SECONDS`
  - `SLO_ALERT_WEBHOOK_TIMEOUT_S`

---

## Day 16 更新（告警路由分组与模板治理）

- 告警检查新增“按违规类型分组路由”策略：
  - `success_rate_below_threshold` → reliability
  - `avg_quality_below_threshold` → quality
  - `avg_duration_above_threshold` → latency
- 新增路由覆盖配置 `SLO_ALERT_ROUTE_OVERRIDES`（示例：`quality=log;latency=webhook`）。
- 告警检查响应新增 `routed_channels` 与 `rendered_message`，便于审计通知决策。
- 新增通知模板配置 `SLO_ALERT_TEMPLATE`，支持 `{status}`、`{violations}`、`{fingerprint}` 等变量渲染。

---

## Day 17 更新（告警策略版本化与多租户隔离）

- `POST /v1/papers/slo/alerts/check` 支持 `X-Tenant-ID`，默认租户为 `default`。
- 告警冷却/去重状态按租户隔离，避免不同租户之间互相影响。
- 告警响应新增：
  - `tenant_id`
  - `policy_version`
- 新增策略版本配置 `SLO_ALERT_POLICY_VERSION`，用于审计当前告警策略版本。

---

## Day 18 更新（告警事件持久化与策略回放）

- 新增告警事件持久化（SQLite `alert_events`），每次 `/v1/papers/slo/alerts/check` 都会落库审计记录。
- 新增 `GET /v1/papers/slo/alerts/events`：支持分页与租户过滤，查看历史告警事件。
- 新增 `POST /v1/papers/slo/alerts/replay/{event_id}`：基于历史事件生成 replay 消息，便于策略回放与排障。

---

## Day 19 更新（告警聚合看板与压缩归档）

- 新增 `GET /v1/papers/slo/alerts/dashboard`：按时间窗口输出告警总量、状态分布、抑制率、Top 违规项。
- 新增 `POST /v1/papers/slo/alerts/archive`：将历史告警事件压缩归档（gzip）后从主表删除，降低在线表体积。
- 归档结果返回 `archive_id`、归档条数、压缩后字节数，便于运维审计。

---

## Day 20 更新（归档检索与回灌）

- 新增 `GET /v1/papers/slo/alerts/archives`：分页查看归档元数据（租户、时间窗、事件数、压缩大小）。
- 新增 `POST /v1/papers/slo/alerts/archives/{archive_id}/restore`：将归档事件回灌到在线事件表，用于回放和问题复盘。

---

## Day 21 更新（告警生命周期自动化）

- 新增 `POST /v1/papers/slo/alerts/lifecycle/run`：按策略一键执行归档生命周期任务。
- 新增启动期自动归档开关：
  - `SLO_ALERT_AUTO_ARCHIVE_ON_STARTUP`
  - `SLO_ALERT_AUTO_ARCHIVE_DAYS`

---

## Day 22 更新（告警SLA对账与修复工单）

- 新增 `GET /v1/papers/slo/alerts/sla-reconcile`：输出时间窗口内告警总量、degraded 数、未抑制 degraded 数与是否 breach。
- 新增 `POST /v1/papers/slo/alerts/remediation-tickets`：创建修复工单。
- 新增 `GET /v1/papers/slo/alerts/remediation-tickets`：查询修复工单列表（支持租户过滤）。

---

## Day 23 更新（工单闭环与根因分类）

- 新增 `POST /v1/papers/slo/alerts/remediation-tickets/{ticket_id}/close`：修复工单闭环。
- 新增 `GET /v1/papers/slo/alerts/root-causes`：按时间窗口输出自动根因分类统计（reliability/quality/latency/unknown）。

---

## Day 24 更新（告警质量评分与策略调参）

- 新增 `GET /v1/papers/slo/alerts/quality-score`：输出告警质量评分（0-100）和构成项。
- 新增 `POST /v1/papers/slo/alerts/strategy-tune`：根据质量评分给出阈值调参建议。
- 新增配置 `SLO_ALERT_AUTO_TUNE_ENABLED`：控制是否启用自动调参建议。

---

## Day 25 更新（策略实验对照与回归安全阈值）

- 新增 `GET /v1/papers/slo/alerts/strategy-experiments`：对比 baseline/candidate 的策略效果，并返回是否建议推广 candidate。
- 新增配置 `SLO_ALERT_REGRESSION_GUARDRAIL_MIN_DELTA`：控制允许的最大回归幅度（例如 `-3.0` 表示候选策略质量分可最多回退 3 分）。
- 实验结果包含 `guardrail_passed` 与 `recommend_promote_candidate`，用于上线前安全闸门判定。

### 前后端演示（5 分钟）

1. 启动后端：`make run`
2. 浏览器打开内置前端：`http://localhost:8000/`，执行一次 generate + runs 查询。
3. 另开终端执行策略实验接口：

```bash
curl "http://localhost:8000/v1/papers/slo/alerts/strategy-experiments?days=7&candidate_max_open_degraded_alerts=3"
```

4. 查看返回的 `guardrail_passed` 与 `recommend_promote_candidate`，并结合前端 runs/metrics 页面进行讲解。

---

## Day 26 更新（实验结果落库与看板）

- 新增 `POST /v1/papers/slo/alerts/strategy-experiments/run`：执行策略实验并将结果持久化。
- 新增 `GET /v1/papers/slo/alerts/strategy-experiments/dashboard`：输出实验总量、平均回归值、安全阈值通过率、推荐率和最近实验记录。
- 可用于面试演示“策略设计 -> 风险闸门 -> 结果留痕 -> 看板复盘”的完整闭环。

---

## Day 27 更新（自动回放与灰度联动）

- 新增 `POST /v1/papers/slo/alerts/strategy-experiments/auto-replay`：对已落库实验做自动回放统计，输出推荐 canary 比例。
- 新增 `GET /v1/papers/slo/alerts/strategy-canary/status`：结合通过率/推荐率与阈值，判断是否建议开启 canary。
- 新增配置：
  - `SLO_ALERT_CANARY_ENABLED`
  - `SLO_ALERT_CANARY_PROMOTION_THRESHOLD`

---

## Day 28 更新（前端看板可视化与灰度开关交互）

- 前端新增 **Strategy Canary Dashboard** 卡片：可查看策略实验总量、通过率、canary 推荐状态与比例。
- 前端新增操作按钮：`Refresh Dashboard`、`Auto Replay`、`Enable Canary`、`Disable Canary`。
- 后端新增 `POST /v1/papers/slo/alerts/strategy-canary/toggle`：支持按租户运行时切换 canary 开关，便于演示灰度开关交互。

---

## Day 29 更新（最终验收收口与演示彩排）

- 新增 `GET /v1/papers/demo/readiness`：输出最终验收维度（架构/质量/可观测/可演示/可讲述）的 readiness 状态。
- 新增 `POST /v1/papers/demo/rehearsal`：输出演示彩排检查项与耗时，便于面试前快速自检。
- 执行计划 DoD 已完成勾选，进入持续运营迭代阶段。

---

## Day 30 更新（交付报告自动化）

- 新增 `POST /v1/papers/demo/final-report`：聚合 readiness + rehearsal，输出 `release_recommended` 与 `release_notes`。
- 用于最终交付前快速生成结构化上线建议，减少手工核对成本。

---

## Day 31 更新（发布后监控与回滚建议）

- 新增 `GET /v1/papers/demo/post-release-monitor`：输出风险等级、监控检查项、指标快照与 canary 状态快照。
- 新增 `GET /v1/papers/demo/rollback-advice`：输出是否建议回滚与原因列表，支撑发布后处置决策。

---

## Day 32 更新（运营评分卡）

- 新增 `GET /v1/papers/demo/ops-scorecard`：输出运营评分、等级（A/B/C/D）、release/rollback 结论与关键摘要。
- 用于每日巡检时快速查看“当前版本是否健康可持续运营”。

---

## Day 33 更新（发布门禁与发布计划）

- 新增 `GET /v1/papers/demo/release-gate`：按 `staging/production` 环境输出门禁是否通过、评分阈值、阻塞原因。
- 新增 `POST /v1/papers/demo/release-plan`：输出结构化发布步骤和 blocker 原因，便于发布执行与复盘。
- 新增配置：
  - `RELEASE_GATE_MIN_SCORE`
  - `RELEASE_GATE_REQUIRE_NO_ROLLBACK`

---

## Day 34 更新（路线图状态盘点）

- 新增 `GET /v1/papers/demo/roadmap-status`：输出已完成天数、当前阶段、待完成阶段、能力现状与下一步行动项。
- 用于向面试官/评审方快速解释“当前系统已完成什么、还缺什么、接下来怎么做”。

---

## Day 35 更新（CI/CD 联动）

- 新增 `POST /v1/papers/demo/cicd/webhook`：按 `release-gate` 结果触发或阻断发布流程，并返回 pipeline_id。
- 新增配置 `RELEASE_WEBHOOK_SECRET`：用于发布 webhook 的 token 校验。

---

## Day 36 更新（验收门禁流水线）

- 新增 `POST /v1/papers/demo/cicd/acceptance-gate`：将发布门禁与关键健康检查聚合为流水线验收步骤。
- 新增配置 `ACCEPTANCE_GATE_MAX_FAILED_CHECKS`：用于控制验收门禁允许的最大失败检查数。

---

## Day 37 更新（生产 Rollout Runbook）

- 新增 `GET /v1/papers/demo/rollout-runbook`：输出可执行发布步骤、回滚方案、阻塞项与是否 ready to rollout。
- 新增配置 `ROLLOUT_AUTO_ROLLBACK_ENABLED`：用于控制是否启用自动回滚策略。

---

## Day 38 更新（运营审计）

- 新增 `GET /v1/papers/demo/operations-audit`：结合运营评分与 rollout readiness 输出审计是否通过。
- 新增配置 `OPERATIONS_AUDIT_MIN_GRADE`：用于配置最低可接受运营等级（A/B/C/D）。

---

## Day 39 更新（发布审批流）

- 新增 `POST /v1/papers/demo/release-approvals/request`：发起发布审批申请。
- 新增 `POST /v1/papers/demo/release-approvals/{approval_id}/decision`：审批通过/拒绝。
- 新增 `GET /v1/papers/demo/release-approvals`：查询审批历史。
- 新增配置 `RELEASE_APPROVAL_REQUIRED`：控制是否必须经过人工审批。

---

## Day 40 更新（跨系统审批与审计报表）

- 新增 `POST /v1/papers/demo/release-approvals/{approval_id}/sync`：将审批结果同步到外部审批系统（未配置 URL 时走 mock 同步模式）。
- 新增 `GET /v1/papers/demo/audit-report`：自动汇总审批状态、同步覆盖率与运营审计结论，输出日报级审计结果。
- 新增配置 `RELEASE_APPROVAL_SYNC_URL` 与 `RELEASE_APPROVAL_SYNC_TIMEOUT_S`：用于配置外部审批系统地址与超时。

---

## Day 41 更新（审计报表归档与历史追溯）

- 新增 `POST /v1/papers/demo/audit-report/generate`：生成并归档一条审计报表快照。
- 新增 `GET /v1/papers/demo/audit-report/history`：按环境/租户分页查询历史审计报表。
- 新增配置 `AUDIT_REPORT_HISTORY_LIMIT`：控制内存中保留的审计报表历史上限。

---

## Day 42 更新（审计报表历史导出）

- 新增 `GET /v1/papers/demo/audit-report/history/export.csv`：将审计报表历史按环境/租户过滤后导出为 CSV。
- 导出字段包含 `report_id/generated_at/period_days/target_env/tenant_id/report_status/approval_sync_rate/operations_audit_passed/highlights`，便于离线审计留档。

---

## Day 43 更新（审计报表趋势分析）

- 新增 `GET /v1/papers/demo/audit-report/trend`：按时间窗口统计每日审计报表总数、健康数和健康率。
- 支持按 `target_env` 与 `tenant_id` 过滤趋势范围，可用于后续可视化看板接入。

---

## Day 44 更新（审计趋势摘要与状态判定）

- 新增 `GET /v1/papers/demo/audit-report/trend/summary`：输出趋势窗口内总报表数、平均健康率、最新健康率与变化值。
- 提供 `improving/stable/degrading/no_data` 状态判定，便于自动化门禁或运营播报直接消费。

---

## Day 45 更新（审计趋势摘要通知）

- 新增 `POST /v1/papers/demo/audit-report/trend/summary/notify`：将趋势摘要结果推送到通知通道（支持 webhook，未配置时走 mock 通道）。
- 新增配置 `AUDIT_TREND_NOTIFY_WEBHOOK_URL` 与 `AUDIT_TREND_NOTIFY_TIMEOUT_S`：用于通知地址与超时控制。

---

## Day 46 更新（通知记录查询）

- 新增 `GET /v1/papers/demo/audit-report/trend/notifications`：分页查询趋势摘要通知记录。
- 支持按 `status` 与 `sent` 过滤，便于运营侧审计通知投递结果。

---

## Day 47 更新（通知回放）

- 新增 `POST /v1/papers/demo/audit-report/trend/notifications/{notification_id}/replay`：对历史通知进行回放重发。
- 对 webhook 通道执行真实重发；对 mock 通道执行模拟回放并保留回放记录。

---

## Day 48 更新（失败通知批量重放）

- 新增 `POST /v1/papers/demo/audit-report/trend/notifications/replay-failed`：批量重放失败通知（支持 `limit`）。
- 返回批量重放统计（重放成功数、跳过数、重放通知ID列表），便于自动修复任务对接。

---

## Day 49 更新（失败重放计划）

- 新增 `GET /v1/papers/demo/audit-report/trend/notifications/replay-plan`：输出失败通知规模、可重放规模与推荐批次大小。
- 返回 `reasons` 字段用于说明是否建议立即重放或分批重放。

---

## Day 50 更新（失败重放执行器）

- 新增 `POST /v1/papers/demo/audit-report/trend/notifications/replay-run`：先计算重放计划，再按推荐批次执行失败通知重放。
- 返回计划快照 + 执行结果，便于在流水线中做一次性“评估+执行”。

---

## Day 51 更新（通知投递指标）

- 新增 `GET /v1/papers/demo/audit-report/trend/notifications/metrics`：输出通知总量、成功/失败数、回放数、成功率与回放覆盖率。
- 可用于运营看板与告警修复效果评估。

---

## Day 52 更新（通知演练）

- 新增 `POST /v1/papers/demo/audit-report/trend/notifications/drill`：可注入模拟失败通知并可选自动重放。
- 用于快速验证通知补偿链路（失败注入 → 重放执行 → 指标变化）。

---

## Day 53 更新（演练历史查询）

- 新增 `GET /v1/papers/demo/audit-report/trend/notifications/drills`：分页查询通知演练历史。
- 便于复盘每次演练的注入规模、自动重放开关与结果统计。

---

## Day 54 更新（演练汇总指标）

- 新增 `GET /v1/papers/demo/audit-report/trend/notifications/drills/summary`：输出演练总量、注入失败总数、重放总数、自动重放率与平均重放成功率。
- 便于持续观察演练质量和补偿链路有效性。

---

## Day 55 更新（演练记录导出）

- 新增 `GET /v1/papers/demo/audit-report/trend/notifications/drills/export.csv`：导出演练历史记录为 CSV。
- 支持将演练结果用于离线复盘或合规留档。

---

## Day 56 更新（演练综合报告）

- 新增 `GET /v1/papers/demo/audit-report/trend/notifications/drills/report`：聚合演练汇总指标与通知投递指标，输出推荐动作。
- 便于在运营巡检中直接给出“当前状态 + 建议”的结论。

---

## Day 57 更新（演练报告快照归档）

- 新增 `POST /v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots`：将当前演练综合报告落为快照。
- 新增 `GET /v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots`：分页查询快照历史，便于长期追踪。

---

## Day 58 更新（演练报告快照对比）

- 新增 `GET /v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/{snapshot_id}`：按 ID 查询单个快照。
- 新增 `GET /v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/compare`：对比两次快照，输出关键指标差值与趋势（`improved/regressed/stable`）。

---

## Day 59 更新（演练报告快照导出）

- 新增 `GET /v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/export.csv`：导出快照历史为 CSV。
- 便于将快照用于离线巡检、周报复盘与跨系统留档。

---

## Day 60 更新（演练报告快照清理）

- 新增 `POST /v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/cleanup`：按 `keep` 保留最新快照并清理历史冗余。
- 便于控制演练快照体量，避免长期运行时内存中快照无限增长。

---

## Day 61 更新（演练报告快照保留预览）

- 新增 `GET /v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/retention-plan`：清理前预览保留计划。
- 输出将保留/将删除的快照 ID 列表与 `would_delete` 数量，便于在自动化任务中先审阅后执行。

---

## Day 62 更新（演练报告快照保留执行器）

- 新增 `POST /v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/retention-run`：统一保留策略“预演 + 执行”。
- 支持 `dry_run`：可先查看预期删除数量，再切换为真实执行，便于流水线安全落地。

---

## Day 63 更新（演练报告快照保留执行历史）

- 新增 `GET /v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/retention-runs`：分页查询保留策略执行历史。
- 每条记录包含执行模式（`dry_run`/`executed`）、保留策略参数与结果统计，便于审计追溯。
